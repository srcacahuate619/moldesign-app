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
from core.models import UserORM, RevokedTokenORM
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
    from api.auth import decode_token, valid_guest_token
    from core.identity import GUEST_EMAIL

    token = _extract_token(authorization)

    if token.startswith("mh1."):
        return await _usuario_por_sesion_molchat(request, db, token)

    try:
        payload = decode_token(token)
    except (InvalidCredentials, TokenExpired) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message if hasattr(exc, "message") else str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Tipo de token inválido")
    if await db.get(RevokedTokenORM, payload["jti"]) is not None:
        raise HTTPException(status_code=401, detail="Token revocado")
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

    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if user.email == GUEST_EMAIL and not valid_guest_token(payload):
        raise HTTPException(status_code=401, detail="Sesión invitada caducada")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario desactivado",
        )

    from services.red import fijar_identidad_peticion
    fijar_identidad_peticion(str(user.id))
    request.state.user = user
    return user


async def _usuario_por_sesion_molchat(
    request: Request, db: AsyncSession, token: str
) -> UserORM:
    """Identidad vía sesión mh1 del sidecar (Fase 6): la plataforma acepta el
    token que acuñó para MolChat como prueba de identidad en sus propios
    endpoints, así el sidecar reenvía el Bearer que recibe sin credenciales
    de larga vida. Espejo estricto del camino JWT: usuario existente y activo
    o 401. Sin chequeo de invitado separado: el secreto HMAC rota por proceso,
    luego todo mh1 válido nació en ESTE arranque (atadura más fuerte que la
    del JWT de invitado).
    """
    from services.molchat_host import sesion

    visto = sesion.verificar_para_plataforma(token)
    if visto is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión MolChat no válida",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = uuid.UUID(visto["sub"])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión MolChat no válida",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    stmt = select(UserORM).where(UserORM.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario desactivado",
        )

    from services.red import fijar_identidad_peticion
    fijar_identidad_peticion(str(user.id))
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
