"""Sesiones del sidecar MolChat: acuñar aquí, verificar en el sidecar.

Formato `mh1.<carga-b64url>.<firma-b64url>` con HMAC-SHA256, byte a byte el
mismo que `molchat_agent.server.auth` (el sidecar) verifica: la carga es
`{"sub", "scopes" (ordenados), "exp", "jti", "aud": "molchat"}`. Este módulo
NO importa aquel paquete (frontera GPL, `test_frontera_molchat.py`): es una
reimplementación limpia del formato documentado, clavada por un vector
dorado en las pruebas.

El secreto del host nace por proceso de escritorio (32 bytes aleatorios) y
nunca se registra ni persiste: viaja al sidecar por entorno al arrancarlo.
Con el mismo secreto, la plataforma acepta un mh1 vigente como identidad
del usuario en sus propios endpoints (`verificar_para_plataforma`, que usa
`api/dependencies.py`): así el sidecar reenvía el Bearer que recibe y la
plataforma impone la identidad sin credenciales de larga vida.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

AUDIENCIA = "molchat"
PREFIJO = "mh1"
PERMISOS_CONOCIDOS = frozenset({
    "read", "chat", "plan", "approve", "cancel", "transcribe",
})


class SesionMolChatError(ValueError):
    """La sesión no se pudo acuñar. El mensaje se puede mostrar."""


def nuevo_secreto() -> bytes:
    """Secreto fresco de 32 bytes para el proceso de escritorio."""
    return secrets.token_bytes(32)


_SECRETO_HOST: bytes | None = None


def fijar_secreto_host(secreto: bytes) -> None:
    """Instala el secreto del proceso (el lanzador, al arrancar el sidecar)."""
    global _SECRETO_HOST
    if not secreto:
        raise SesionMolChatError("sin secreto de firma")
    _SECRETO_HOST = bytes(secreto)


def secreto_host() -> bytes | None:
    """El secreto instalado, o None si el sidecar aún no arrancó."""
    return _SECRETO_HOST


def acunar(sub: str, permisos: set[str] | frozenset[str] | list[str],
           ttl_s: int, *, ahora: float | None = None,
           jti: str | None = None) -> str:
    """Acuña un token de sesión con el secreto instalado. Nunca acuña mal."""
    secreto = _SECRETO_HOST
    if not secreto:
        raise SesionMolChatError("sin secreto de firma")
    if not sub or not sub.strip():
        raise SesionMolChatError("sin identidad de cuenta")
    pedidos = set(permisos)
    if not pedidos:
        raise SesionMolChatError("sin permisos")
    desconocidos = pedidos - PERMISOS_CONOCIDOS
    if desconocidos:
        raise SesionMolChatError(f"permisos desconocidos: {sorted(desconocidos)}")
    if ttl_s <= 0:
        raise SesionMolChatError("caducidad no válida")
    momento = int(ahora if ahora is not None else time.time())
    carga = {"sub": sub, "scopes": sorted(pedidos), "exp": momento + ttl_s,
             "jti": jti or secrets.token_hex(8), "aud": AUDIENCIA}
    crudo = base64.urlsafe_b64encode(
        json.dumps(carga, separators=(",", ":")).encode("ascii")).decode("ascii")
    cuerpo = f"{PREFIJO}.{crudo}"
    firma = base64.urlsafe_b64encode(
        hmac.new(secreto, cuerpo.encode("ascii"), hashlib.sha256).digest()).decode("ascii")
    return f"{cuerpo}.{firma}"


def verificar_para_plataforma(token: str, *, ahora: float | None = None) -> dict | None:
    """La sesión como identidad de plataforma, o None si no vale.

    Misma semántica que la verificación del sidecar (firma, audiencia,
    caducidad, permisos conocidos, forma completa). Los permisos gobiernan
    endpoints del sidecar; en la plataforma este token sólo autentica: la
    autorización por usuario de cada endpoint sigue intacta.
    """
    secreto = _SECRETO_HOST
    if not secreto:
        return None
    partes = (token or "").split(".")
    if len(partes) != 3 or partes[0] != PREFIJO or not partes[1] or not partes[2]:
        return None
    cuerpo = f"{partes[0]}.{partes[1]}"
    try:
        presentada = base64.urlsafe_b64decode(partes[2].encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None
    esperada = hmac.new(secreto, cuerpo.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(presentada, esperada):
        return None
    try:
        carga = json.loads(base64.urlsafe_b64decode(partes[1].encode("ascii")))
    except (ValueError, UnicodeEncodeError):
        return None
    if not isinstance(carga, dict) or carga.get("aud") != AUDIENCIA:
        return None
    permisos = carga.get("scopes")
    if (not isinstance(permisos, list) or not permisos
            or not set(permisos) <= PERMISOS_CONOCIDOS):
        return None
    exp = carga.get("exp")
    sub = carga.get("sub")
    jti = carga.get("jti")
    if not isinstance(exp, int) or not isinstance(sub, str) or not sub.strip() \
            or not isinstance(jti, str) or not jti:
        return None
    momento = int(ahora if ahora is not None else time.time())
    if exp <= momento:
        return None
    return {"sub": sub, "scopes": sorted(permisos), "exp": exp, "jti": jti}
