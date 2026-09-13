"""
api/dependencies.py

Dependencias compartidas de FastAPI para autenticación y autorización.

Provee:
- get_current_user: extrae y valida el JWT del header Authorization
- get_current_user_optional: permite requests anónimos (devuelve None)

Estas dependencias se inyectan en los endpoints que requieren autenticación.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import InvalidCredentials, TokenExpired
from core.models import UserORM
from utils.logger import get_logger

log = get_logger(__name__)


def _extract_token(authorization: str | None) -> str:
    """Extrae el token Bearer del header Authorization."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido. Usa: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    """
    Dependencia que autentica al usuario y lo devuelve.
    Si el token proviene de Supabase/Auth0 y el usuario no existe localmente,
    lo crea automáticamente (JIT Provisioning).
    Lanza 401 si el token es inválido o expirado.
    """
    from api.auth import decode_token

    token = _extract_token(authorization)

    try:
        payload = decode_token(token)
    except (InvalidCredentials, TokenExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message if hasattr(exc, "message") else str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta claim 'sub'",
        )

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: subject no es un UUID válido",
        ) from exc

    stmt = select(UserORM).where(UserORM.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # JIT Provisioning para usuarios de Supabase
    if user is None:
        email = payload.get("email", f"user_{user_id}@oauth.local")
        user = UserORM(
            id=user_id,
            email=email,
            username=email.split("@")[0],
            auth_provider="oauth",
            subscription_tier="free"
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception:
            await db.rollback()
            # Race condition recovery: Check if user was created concurrently
            stmt = select(UserORM).where(UserORM.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error creando usuario OAuth local",
                )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario desactivado",
        )

    request.state.user = user
    return user


async def get_current_user_optional(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> UserORM | None:
    """
    Como get_current_user pero permite requests anónimos.
    Si no hay token, devuelve None en vez de lanzar error.
    Útil para endpoints que funcionan con o sin autenticación.
    """
    if not authorization:
        return None

    # Si hay token, delegamos a get_current_user.
    # Si está expirado o es inválido, dejará pasar el 401 HTTPException
    # para que el frontend intente el refresh.
    return await get_current_user(request=request, authorization=authorization, db=db)
