"""Llamadas en modo alojado: la clave llega de MolDesign para ESTA llamada y no se guarda.

MolDesign dice qué proveedor es el activo de la cuenta. El destino lo dice el
catálogo de esta llave. MolDesign comprueba que el host que pedimos es el suyo y
que la cuenta autorizó ese destino antes de entregar la clave; si no, la llamada
no sale y el usuario ve el motivo en Ajustes > Proveedores.
"""

from __future__ import annotations

from typing import Any

from ..bridge import BridgeError
from . import catalogo
from .registry import ProviderRegistry, construir

#: Lo que ve el usuario cuando MolDesign no entrega la clave, por motivo del host.
MENSAJES = {
    "sin_clave": "Falta la clave de {nombre}: añádela en Ajustes > Proveedores.",
    "sin_autorizacion": "Autoriza el envío a {host} en Ajustes > Proveedores.",
    "destino_distinto": "El destino de {nombre} no es el que MolDesign autorizó.",
    "sin_proveedor_activo": "No hay proveedor de IA activo: elígelo en Ajustes > Proveedores.",
}
_GENERICO = "No se pudo obtener la credencial de {nombre}. Revísala en Ajustes > Proveedores."


def _rechazo(base: ProviderRegistry, entrada: catalogo.Entrada, motivo: str) -> ProviderRegistry:
    texto = MENSAJES.get(motivo, _GENERICO).format(nombre=entrada.nombre, host=entrada.host)
    return base.de_llamada(activo=entrada.id, bloqueo={entrada.id: texto})


async def registro_del_turno(base: ProviderRegistry, bridge: Any) -> ProviderRegistry:
    """El registro de esta llamada: el activo de la cuenta, con su clave si la hay."""
    estado = await bridge.proveedores_de_cuenta()
    activo = estado.get("activo")
    if not activo:
        return base.de_llamada(activo=None)
    entrada = catalogo.por_id(str(activo))
    if entrada is None:
        return base.de_llamada(activo=str(activo), bloqueo={
            str(activo): f"El proveedor {activo} no existe en esta versión de MolChat."})
    if not entrada.requiere_clave:
        # Local: el adaptador ya está en el registro base, con su URL y su modelo.
        return base.de_llamada(activo=entrada.id)
    try:
        credencial = await bridge.credencial(entrada.id, entrada.host)
    except BridgeError as exc:
        return _rechazo(base, entrada, exc.detail or "")
    clave = str(credencial.get("api_key") or "")
    if not clave:
        return _rechazo(base, entrada, "sin_clave")
    modelo = credencial.get("modelo") or None
    proveedor = construir(entrada, api_key=clave, modelo=str(modelo) if modelo else None)
    return base.de_llamada(activo=entrada.id, proveedor=proveedor)
