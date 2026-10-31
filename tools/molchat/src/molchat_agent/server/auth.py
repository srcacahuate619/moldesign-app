"""Host session tokens: HMAC-signed, scoped, short-lived (MP-06).

Token format: ``mh1.<payload-b64url>.<sig-b64url>`` where ``sig`` is
HMAC-SHA256(secret, ``"mh1.<payload-b64url>"``) and payload is JSON::

    {"sub": "account-id", "scopes": ["read", "chat"],
     "exp": 1798765432, "jti": "random-id", "aud": "molchat"}

The host (§15.2, MolDesign side) mints these; the sidecar only verifies.
In standalone mode (``molchat-agent serve`` without ``MOLCHAT_HOST_SECRET``)
the sidecar mints its own single-session token at startup and prints it
once for the operator. Either way, every API call but health/version
presents a Bearer token and the sidecar verifies signature, audience,
expiry, and scopes on each call. No identity is ever taken from UI input.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

AUDIENCE = "molchat"
PREFIX = "mh1"

KNOWN_SCOPES = frozenset({
    "read",        # health-adjacent reads: catalog, executions, conversations
    "chat",        # conversational turns + conversation management
    "plan",        # propose read-only plans
    "approve",     # execute plans with non-read steps (core approval still applies)
    "cancel",      # cancel running jobs explicitly
    "transcribe",  # speech-to-text (returns text; never auto-executes)
})


class AuthError(ValueError):
    """A session token was rejected. The message is safe to show."""


@dataclass(frozen=True)
class Session:
    sub: str
    scopes: frozenset[str]
    exp: int
    jti: str

    def allows(self, *required: str) -> bool:
        return all(scope in self.scopes for scope in required)


def standalone_secret() -> bytes:
    """Fresh random secret for standalone mode (never persisted)."""
    return secrets.token_bytes(32)


def mint(secret: bytes, sub: str, scopes: set[str] | frozenset[str] | list[str],
         ttl_s: int, *, now: float | None = None) -> str:
    """Mint a session token. Raises AuthError on bad inputs (never mints)."""
    if not secret:
        raise AuthError("sin secreto de firma")
    if not sub or not sub.strip():
        raise AuthError("sin identidad de cuenta")
    wanted = set(scopes)
    if not wanted:
        raise AuthError("sin permisos")
    unknown = wanted - KNOWN_SCOPES
    if unknown:
        raise AuthError(f"permisos desconocidos: {sorted(unknown)}")
    if ttl_s <= 0:
        raise AuthError("caducidad no válida")
    moment = int(now if now is not None else time.time())
    payload = {"sub": sub, "scopes": sorted(wanted), "exp": moment + ttl_s,
               "jti": secrets.token_hex(8), "aud": AUDIENCE}
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("ascii")).decode("ascii")
    body = f"{PREFIX}.{raw}"
    sig = base64.urlsafe_b64encode(
        hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()).decode("ascii")
    return f"{body}.{sig}"


def verify(secret: bytes, token: str, *, now: float | None = None) -> Session:
    """Verify a token. Returns the session or raises AuthError."""
    if not secret:
        raise AuthError("sin secreto de firma")
    parts = (token or "").split(".")
    if len(parts) != 3 or parts[0] != PREFIX or not parts[1] or not parts[2]:
        raise AuthError("formato de sesión no válido")
    body = f"{parts[0]}.{parts[1]}"
    try:
        presented = base64.urlsafe_b64decode(parts[2].encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise AuthError("firma no válida") from exc
    expected = hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(presented, expected):
        raise AuthError("firma no válida")
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1].encode("ascii")))
    except (ValueError, UnicodeEncodeError) as exc:
        raise AuthError("sesión ilegible") from exc
    if not isinstance(payload, dict) or payload.get("aud") != AUDIENCE:
        raise AuthError("audiencia no válida")
    scopes = payload.get("scopes")
    if (not isinstance(scopes, list) or not scopes
            or not set(scopes) <= KNOWN_SCOPES):
        raise AuthError("permisos no válidos")
    exp = payload.get("exp")
    sub = payload.get("sub")
    jti = payload.get("jti")
    if not isinstance(exp, int) or not isinstance(sub, str) or not sub.strip() \
            or not isinstance(jti, str) or not jti:
        raise AuthError("sesión incompleta")
    moment = int(now if now is not None else time.time())
    if exp <= moment:
        raise AuthError("sesión caducada")
    return Session(sub=sub, scopes=frozenset(scopes), exp=exp, jti=jti)


def parse_bearer(authorization: str | None) -> str | None:
    """Extract the token from an Authorization header (None when absent)."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
