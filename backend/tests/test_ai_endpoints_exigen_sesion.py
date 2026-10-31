"""MOLCHAT-BE-002 y MOLCHAT-BE-003 — los endpoints AI exigen sesión.

De las 21 rutas de `api/routers/ai.py`, sólo `POST /ai/chat` recibía identidad,
y aun así la recibía vacía: `AIContext` no envía cabecera de autenticación en
ninguna llamada, así que `current_user` era siempre `None` y las herramientas
caían al usuario demo. MolChat nunca ha tenido identidad en la práctica.

Sin credenciales se podía:

* listar, leer y **borrar** conversaciones ajenas —con su `molecule_context`
  dentro, es decir, el caso y la molécula sobre los que se conversó—;
* reescribir la configuración del proveedor, incluido `base_url`, y con ello
  **redirigir todo el tráfico del chat a otro servidor** (MOLCHAT-BE-003);
* cambiar el proveedor activo, subir audio, iniciar descargas de modelo,
  cambiar la configuración global y abrir una carpeta en el escritorio.

(Fase 6.6) El router interno murió con el asistente; estas pruebas cubren la
superficie preservada (`api/routers/agent_platform.py`): propuestas,
idempotencia y STT. Queda una sola sonda abierta (estado del dictado, sin
datos de cuenta); todo lo demás exige sesión estricta.
"""

from __future__ import annotations

import inspect

from fastapi import Depends

from api import dependencies
from api.routers import agent_platform as ai

#: Sondas de arranque. La única que queda: disponibilidad del dictado, sin
#: datos de ninguna cuenta.
ABIERTAS: dict[str, str] = {
    "GET /ai/speech-to-text/status": "disponibilidad del dictado",
}


def _rutas():
    for ruta in ai.router.routes:
        metodos = getattr(ruta, "methods", set()) - {"HEAD", "OPTIONS"}
        for metodo in sorted(metodos):
            yield f"{metodo} {ruta.path}", ruta


def _exige_sesion(ruta) -> bool:
    """True si el endpoint depende de `get_current_user` (el estricto)."""
    firma = inspect.signature(ruta.endpoint)
    for parametro in firma.parameters.values():
        default = parametro.default
        if isinstance(default, type(Depends())) and (
            getattr(default, "dependency", None) is dependencies.get_current_user
        ):
            return True
    return False


def test_toda_ruta_que_no_sea_sonda_de_arranque_exige_sesion():
    desprotegidas = [
        nombre
        for nombre, ruta in _rutas()
        if nombre not in ABIERTAS and not _exige_sesion(ruta)
    ]

    assert desprotegidas == [], (
        "estas rutas AI no piden identidad y no están declaradas como sondas "
        f"de arranque: {desprotegidas}"
    )


def test_las_sondas_abiertas_estan_declaradas_una_a_una():
    """La lista de excepciones tiene que ser incómoda de ampliar."""
    nombres = {nombre for nombre, _ in _rutas()}

    for sonda in ABIERTAS:
        assert sonda in nombres, f"{sonda} ya no existe; retírala de la lista"
