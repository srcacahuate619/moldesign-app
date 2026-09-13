"""
api/auth.py

Utilidades mínimas de autenticación para el MVP.

En esta fase inicial necesitamos dos cosas:
1. Poder crear un access token para tests y futuros endpoints.
2. Poder validarlo sin depender de librerías externas adicionales.

Implementamos un JWT HS256 mínimo usando solo stdlib para mantener
el backend autocontenido. No pretende reemplazar una capa completa
de autenticación, pero sí proporciona una base correcta y verificable
para el MVP.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import jwt
from datetime import UTC, datetime, timedelta
from typing import Any

from core.config import get_settings
from core.exceptions import InvalidCredentials, TokenExpired

settings = get_settings()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _sign(message: bytes) -> str:
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Crea un JWT HS256 mínimo para el MVP.

    Args:
        subject: identificador principal del usuario (normalmente user_id)
        expires_delta: override opcional del tiempo de expiración
        additional_claims: claims adicionales si se requieren más adelante
    """
    now = datetime.now(UTC)
    expires = now + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )

    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "access",
    }

    if additional_claims:
        payload.update(additional_claims)

    encoded_header = _b64url_encode(_json_dumps(header).encode("utf-8"))
    encoded_payload = _b64url_encode(_json_dumps(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un JWT de refresco de larga duración.
    """
    now = datetime.now(UTC)
    expires = now + (
        expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    )

    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "type": "refresh",
    }

    encoded_header = _b64url_encode(_json_dumps(header).encode("utf-8"))
    encoded_payload = _b64url_encode(_json_dumps(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = _sign(signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    """
    Valida firma y expiración del token usando PyJWT.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.InvalidTokenError as exc:
        if hasattr(settings, "supabase_jwt_secret") and settings.supabase_jwt_secret:
            try:
                return jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False}
                )
            except jwt.ExpiredSignatureError as e_exc:
                raise TokenExpired() from e_exc
            except jwt.InvalidTokenError as i_exc:
                raise InvalidCredentials() from i_exc
        raise InvalidCredentials() from exc


def get_subject_from_token(token: str) -> str:
    payload = decode_token(token)

    # En Supabase Auth y tokens locales, el ID de usuario viene en el claim 'sub'
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidCredentials()

    return subject
