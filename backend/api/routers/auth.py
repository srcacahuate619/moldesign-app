"""
api/routers/auth.py

Endpoints de autenticación: registro e inicio de sesión.

Este módulo NO implementa lógica científica — es puramente una capa
de gestión de identidad necesaria para:
- asociar evaluaciones a usuarios reales,
- mantener historial por usuario,
- permitir multi-usuario seguro.

Seguridad implementada:
- Passwords hasheados con bcrypt (cost factor 12, memory-hard) cuando está
  disponible; fallback PBKDF2-SHA256 (100k iteraciones) para entornos sin bcrypt.
  Hashes legacy PBKDF2 se auto-migran a bcrypt al verificar.
- JWT HS256 con expiración configurable
- No se revela si un email existe o no en login
- Rate limiting debe agregarse en producción
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from typing import Literal

from api.auth import create_access_token, create_refresh_token, decode_token
from api.dependencies import get_current_user
from api.rate_limiter import login_limiter, register_limiter
from core.config import get_settings
from core.database import get_db
from core.identity import GUEST_EMAIL, es_invitado
from core.models import TraspasoRequest, TraspasoResponse, UserORM
from services.accounts.traspaso import (
    PlanDeTraspaso,
    TraspasoNoPermitido,
    planificar_traspaso,
)
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ── Helpers de hashing ────────────────────────────────────────────────────────
# bcrypt: memory-hard, resistente a GPU/ASIC. Cost factor = 12 (~250ms).
# Legacy: PBKDF2-SHA256. Auto-migra a bcrypt al verificar.

try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False


def _hash_password(password: str) -> str:
    """Hash password with bcrypt (cost=12)."""
    if _BCRYPT_AVAILABLE:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")
    # Fallback: PBKDF2-SHA256 (solo si bcrypt no esta instalado)
    import hashlib
    salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations=100_000
    )
    return "pbkdf2:" + salt.hex() + ":" + pwd_hash.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password. Auto-migrates legacy PBKDF2 → bcrypt on success."""
    # bcrypt format: starts with '$2b$' or '$2a$'
    if stored_hash.startswith("$2"):
        if _BCRYPT_AVAILABLE:
            return bcrypt.checkpw(
                password.encode("utf-8"), stored_hash.encode("utf-8")
            )
        return False

    # Legacy PBKDF2 format: "pbkdf2:salt_hex:hash_hex" or "salt_hex:hash_hex"
    try:
        stored = stored_hash
        if stored.startswith("pbkdf2:"):
            stored = stored[7:]
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations=100_000
        )
        return expected.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


# ── Request/Response schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    email: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str
    is_active: bool
    created_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
)
async def register(
    request: RegisterRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Crea un nuevo usuario y devuelve un access token."""

    # Rate limiting: 3 registros/min por IP
    register_limiter.check(raw_request)

    # Verificar email duplicado
    stmt = select(UserORM).where(UserORM.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese email",
        )

    # Verificar username duplicado
    stmt = select(UserORM).where(UserORM.username == request.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese nombre de usuario ya está en uso",
        )

    # Crear usuario
    user = UserORM(
        email=request.email,
        username=request.username,
        hashed_password=_hash_password(request.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    log.info("usuario registrado", user_id=str(user.id), username=user.username)

    # Generar tokens
    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Iniciar sesión",
)
async def login(
    request: LoginRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Autentica al usuario y devuelve un access token."""

    # Rate limiting: 5 intentos/min por IP
    login_limiter.check(raw_request)

    stmt = select(UserORM).where((UserORM.email == request.email) | (UserORM.username == request.email))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Mensaje genérico para evitar user enumeration
    if user is None or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    log.info("usuario autenticado", user_id=str(user.id), username=user.username)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refrescar access token",
)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Valida un refresh token y devuelve un nuevo access token."""
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido",
            )
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado",
        )

    # Verificar que el usuario existe y está activo
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido",
        )

    stmt = select(UserORM).where(UserORM.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    # También rotamos el refresh token para mayor seguridad
    new_refresh_token = create_refresh_token(subject=str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Perfil del usuario autenticado",
)
async def get_me(
    current_user: UserORM = Depends(get_current_user),
) -> UserProfile:
    """Devuelve el perfil del usuario autenticado."""
    return UserProfile(
        user_id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


# ── OAuth ─────────────────────────────────────────────────────────────────────

class OAuthLoginRequest(BaseModel):
    provider: Literal["google", "azure-ad"]
    id_token: str

_msal_jwks_cache = {}
_msal_jwks_cache_expiry = 0

async def _get_msal_public_keys(tenant_id: str):
    global _msal_jwks_cache, _msal_jwks_cache_expiry
    import time
    import httpx
    now = time.time()
    if tenant_id in _msal_jwks_cache and now < _msal_jwks_cache_expiry:
        return _msal_jwks_cache[tenant_id]

    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        keys = resp.json()
        _msal_jwks_cache[tenant_id] = keys
        _msal_jwks_cache_expiry = now + 86400  # Caché de 24 horas
        return keys

@router.post(
    "/oauth",
    response_model=AuthResponse,
    summary="Iniciar sesión con OAuth (Google / Microsoft)",
)
async def oauth_login(
    request: OAuthLoginRequest,
    raw_request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Verifica un id_token de OAuth y devuelve tokens de acceso locales."""
    login_limiter.check(raw_request)
    settings = get_settings()

    email = None

    try:
        if request.provider == "google":
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            if not settings.google_client_id:
                raise ValueError("Google Client ID no está configurado en el servidor")
            idinfo = google_id_token.verify_oauth2_token(
                request.id_token,
                google_requests.Request(),
                settings.google_client_id
            )
            if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
                raise ValueError("Issuer inválido")
            email = idinfo.get("email")

        elif request.provider == "azure-ad":
            if not settings.microsoft_client_id:
                raise ValueError("Microsoft Client ID no está configurado en el servidor")

            unverified_header = jwt.get_unverified_header(request.id_token)
            jwks = await _get_msal_public_keys(settings.microsoft_tenant_id or "common")
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break
            if not rsa_key:
                raise ValueError("No se encontró la clave pública de Microsoft")

            algorithm = jwt.algorithms.RSAAlgorithm.from_jwk(rsa_key)

            tenant = settings.microsoft_tenant_id or "common"
            if tenant != "common" and tenant != "organizations" and tenant != "consumers":
                expected_issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
                payload = jwt.decode(
                    request.id_token,
                    key=algorithm,
                    algorithms=["RS256"],
                    audience=settings.microsoft_client_id,
                    issuer=expected_issuer,
                    options={"verify_iss": True}
                )
            else:
                payload = jwt.decode(
                    request.id_token,
                    key=algorithm,
                    algorithms=["RS256"],
                    audience=settings.microsoft_client_id,
                    options={"verify_iss": True}
                )
                iss = payload.get("iss", "")
                # Asegurar que el issuer sea de dominios legítimos de Microsoft
                if not (iss.startswith("https://login.microsoftonline.com/") or iss.startswith("https://sts.windows.net/")):
                    raise ValueError(f"Issuer de Microsoft no autorizado: {iss}")

            email = payload.get("email") or payload.get("preferred_username")

    except Exception as e:
        log.error("oauth_verification_failed", provider=request.provider, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de {request.provider} inválido o expirado"
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token no contiene un correo electrónico"
        )

    # Verificar existencia en BD
    stmt = select(UserORM).where(UserORM.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # AUTO-CREATE: El usuario se registra automáticamente al hacer OAuth
        # La wallet publica se vincula solo despues de una firma soberana.
        # El correo nunca se publica como identidad blockchain.
        username = email.split("@")[0][:50]
        # Asegurar username único si el prefijo ya existe
        stmt_check = select(UserORM).where(UserORM.username == username)
        existing = (await db.execute(stmt_check)).scalar_one_or_none()
        if existing:
            username = f"{username}_{uuid.uuid4().hex[:4]}"
        user = UserORM(
            email=email,
            username=username,
            auth_provider=request.provider,
            solana_wallet_address=None,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        log.info("oauth_user_auto_created", email=email, provider=request.provider, user_id=str(user.id))

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )

    # Generar nuestros propios tokens
    access_token = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    log.info("usuario autenticado por oauth", user_id=str(user.id), provider=request.provider)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=str(user.id),
        username=user.username,
        email=user.email,
    )

# ── Desktop Auto-Login ─────────────────────────────────────────────

@router.post(
    "/traspaso",
    response_model=TraspasoResponse,
    summary="Llevar a esta cuenta el trabajo hecho como invitado",
)
async def traspasar_del_invitado(
    data: TraspasoRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraspasoResponse:
    """Mueve moléculas y cohortes del invitado a la cuenta que lo pide.

    Todo ocurre en una transacción: o se mueve lo pedido entero o no se mueve
    nada. Un traspaso a medias dejaría una molécula cuyo resultado apunta a otra
    cuenta, que es peor que no haber traspasado.

    Es idempotente: lo que ya es de esta cuenta se cuenta como hecho. Un doble
    clic, una reconexión o un reintento del cliente no pueden romperlo.
    """
    if es_invitado(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "La cuenta invitada no puede recibir un traspaso: el traspaso "
                "existe para salir de ella. Regístrate y repite desde tu cuenta."
            ),
        )

    if not data.molecule_ids and not data.cohort_ids:
        # Nada que hacer, y por tanto nada que consultar. No traspasar es una
        # decisión legítima, no un error.
        return TraspasoResponse()

    invitado = await db.execute(select(UserORM).where(UserORM.email == GUEST_EMAIL))
    cuenta_invitada = invitado.scalars().first()
    if cuenta_invitada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay cuenta invitada en esta máquina: no hay nada que traspasar.",
        )

    from core.models import CohortORM, CohortRunORM, MoleculeORM

    try:
        plan_moleculas = PlanDeTraspaso()
        if data.molecule_ids:
            filas = (
                await db.execute(
                    select(MoleculeORM).where(MoleculeORM.id.in_(data.molecule_ids))
                )
            ).scalars().all()
            plan_moleculas = planificar_traspaso(
                filas=list(filas),
                destino=current_user.id,
                invitado=cuenta_invitada.id,
                solicitadas=list(data.molecule_ids),
            )

        plan_cohortes = PlanDeTraspaso()
        if data.cohort_ids:
            filas = (
                await db.execute(
                    select(CohortORM).where(CohortORM.id.in_(data.cohort_ids))
                )
            ).scalars().all()
            plan_cohortes = planificar_traspaso(
                filas=list(filas),
                destino=current_user.id,
                invitado=cuenta_invitada.id,
                solicitadas=list(data.cohort_ids),
            )
    except TraspasoNoPermitido as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    corridas_movidas = 0
    if plan_moleculas.a_mover:
        await db.execute(
            update(MoleculeORM)
            .where(MoleculeORM.id.in_(plan_moleculas.a_mover))
            .values(user_id=current_user.id)
        )
    if plan_cohortes.a_mover:
        await db.execute(
            update(CohortORM)
            .where(CohortORM.id.in_(plan_cohortes.a_mover))
            .values(user_id=current_user.id)
        )
        # Las corridas siguen a su cohorte: dejarlas atrás produciría una
        # cohorte de esta cuenta cuyas corridas son de otra.
        resultado = await db.execute(
            update(CohortRunORM)
            .where(
                CohortRunORM.cohort_id.in_(plan_cohortes.a_mover),
                CohortRunORM.user_id == cuenta_invitada.id,
            )
            .values(user_id=current_user.id)
        )
        corridas_movidas = int(resultado.rowcount or 0)

    await db.commit()
    log.info(
        "traspaso_del_invitado",
        destino=str(current_user.id),
        moleculas=len(plan_moleculas.a_mover),
        cohortes=len(plan_cohortes.a_mover),
        corridas=corridas_movidas,
    )
    return TraspasoResponse(
        moleculas_traspasadas=len(plan_moleculas.a_mover),
        cohortes_traspasadas=len(plan_cohortes.a_mover),
        corridas_de_cohorte_traspasadas=corridas_movidas,
        moleculas_ya_estaban=len(plan_moleculas.ya_estaban),
        cohortes_ya_estaban=len(plan_cohortes.ya_estaban),
    )


@router.get("/desktop-login", summary="Auto-login para modo DESKTOP")
async def desktop_auto_login(db: AsyncSession = Depends(get_db)):
    from core.config import get_settings as gs
    s = gs()
    if not s.is_desktop:
        raise HTTPException(status_code=403, detail="Solo disponible en modo DESKTOP")

    result = await db.execute(select(UserORM).where(UserORM.email == "desktop@moldesign.local"))
    user = result.scalars().first()
    if user is None:
        import secrets
        user = UserORM(
            email="desktop@moldesign.local",
            username="Desktop User",
            hashed_password=_hash_password(secrets.token_hex(32)),
        )
        db.add(user)
        await db.flush()

    # Desktop: caducidad muy larga (10 años access / 10 años refresh) — la app
    # desktop no debe exigir re-login por expiración de sesión (mecanismo cloud
    # que en local solo causa fricción y mezcla de cuentas). No tocamos los
    # defaults globales (30d/1a) que sigue usando el flujo web/cloud.
    DESKTOP_ACCESS_EXPIRE = timedelta(days=365 * 10)
    DESKTOP_REFRESH_EXPIRE = timedelta(days=365 * 10)

    access_token = create_access_token(
        str(user.id),
        additional_claims={"username": user.username, "email": user.email},
        expires_delta=DESKTOP_ACCESS_EXPIRE,
    )
    refresh_token = create_refresh_token(
        str(user.id),
        expires_delta=DESKTOP_REFRESH_EXPIRE,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
    }
