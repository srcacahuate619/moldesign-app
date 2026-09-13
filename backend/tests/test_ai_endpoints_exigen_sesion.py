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

Cuatro rutas se dejan accesibles a propósito: son sondas de capacidad que el
arranque de la interfaz consulta **antes** de que exista sesión, no devuelven
datos de ninguna cuenta y no exponen secretos —`ProviderInfoResponse` publica
`requires_api_key` y `configured`, nunca el valor de la clave—.
"""

from __future__ import annotations

import inspect

from fastapi import Depends

from api import dependencies
from api.routers import ai

#: Sondas de arranque. La interfaz las llama al montar, antes del auto-login.
ABIERTAS: dict[str, str] = {
    "GET /ai/startup": "modo de arranque del motor local; sin datos de cuenta",
    "GET /ai/providers": "catálogo de proveedores disponibles; nunca la clave",
    "GET /ai/status": "salud del subsistema AI; sin datos de cuenta",
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


def test_configurar_el_proveedor_exige_sesion():
    """MOLCHAT-BE-003: es la ruta que puede cambiar el destino de los datos."""
    for nombre, ruta in _rutas():
        if nombre == "POST /ai/providers/configure":
            assert _exige_sesion(ruta)
            return
    raise AssertionError("no se encontró POST /ai/providers/configure")


def test_las_conversaciones_exigen_sesion():
    protegidas = {
        "POST /ai/conversations",
        "GET /ai/conversations",
        "GET /ai/conversations/{conv_id}",
        "DELETE /ai/conversations/{conv_id}",
    }
    encontradas = {nombre for nombre, _ in _rutas()} & protegidas

    assert encontradas == protegidas, f"faltan rutas: {protegidas - encontradas}"
    for nombre, ruta in _rutas():
        if nombre in protegidas:
            assert _exige_sesion(ruta), nombre


def test_el_chat_exige_sesion_y_no_cae_al_usuario_demo():
    """El chat aceptaba anónimos y resolvía las herramientas contra demo."""
    for nombre, ruta in _rutas():
        if nombre == "POST /ai/chat":
            assert _exige_sesion(ruta)
            return
    raise AssertionError("no se encontró POST /ai/chat")
