"""Redacción de secretos antes de que un texto salga a la pantalla o al log.

MOLCHAT-AUD-01, higiene transversal del §8. Los errores de proveedor se
devolvían al investigador y se escribían en `backend.latest.log` tal cual:
`f"Error conectando con {self._config.base_url}: {str(e)[:100]}"`. Basta con
que el `base_url` lleve credenciales embebidas —`http://user:clave@host`, o un
proxy con `?api_key=`— para que la clave quede en un archivo de texto que luego
viaja en el bundle de soporte.

La regla que sigue este módulo: **el destino sí se ve, la credencial no**. El
host es justo el dato que MOLCHAT-NET-005 obliga a declarar —a dónde van los
datos—, así que borrarlo empeoraría el producto; lo que se borra es lo que
autentica.
"""

from __future__ import annotations

import re

MARCA = "[redactado]"

#: `esquema://usuario:clave@host` → se conserva el host.
_CREDENCIAL_EN_URL = re.compile(r"(://)[^/\s:@]+:[^/\s@]+@")

#: `api_key=…`, `apikey=…`, `key=…`, `token=…`, `access_token=…` en una query.
_CLAVE_EN_QUERY = re.compile(
    r"((?:api[-_]?key|apikey|access[-_]?token|token|key|secret)\s*=\s*)"
    r"[^\s&#\"']+",
    re.IGNORECASE,
)

#: `Authorization: Bearer …` y variantes de cabecera.
_CABECERA = re.compile(
    r"((?:authorization|x-api-key|x-goog-api-key)\s*[:=]\s*)(?:bearer\s+)?[^\s,;\"']+",
    re.IGNORECASE,
)

#: Claves sueltas con prefijo conocido, que aparecen sin cabecera ni query.
_CLAVE_SUELTA = re.compile(
    r"\b(sk-ant-[A-Za-z0-9]{2,}-|sk-proj-|sk-|gsk_|AIza|ghp_|xoxb-)[A-Za-z0-9\-_]{8,}",
)


def redactar_secretos(texto: object) -> str:
    """Devuelve el texto sin credenciales, conservando host y motivo.

    Acepta cualquier cosa porque se usa en rutas de error, donde el llamador
    suele tener una excepción y no una cadena.
    """
    if texto is None:
        return ""
    if not isinstance(texto, str):
        texto = str(texto)

    limpio = _CREDENCIAL_EN_URL.sub(rf"\1{MARCA}@", texto)
    limpio = _CABECERA.sub(rf"\1{MARCA}", limpio)
    limpio = _CLAVE_EN_QUERY.sub(rf"\1{MARCA}", limpio)
    limpio = _CLAVE_SUELTA.sub(MARCA, limpio)
    return limpio
