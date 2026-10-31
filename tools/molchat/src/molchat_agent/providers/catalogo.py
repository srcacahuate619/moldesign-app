"""Catálogo de proveedores de IA: URL base, familia de protocolo y modelo por defecto.

Vive en la llave (`catalogo.json`): MolDesign lee el mismo fichero de la copia
verificada, así que la URL de cada proveedor la fija esta versión, no quien
configura la máquina. Un proveedor remoto sólo puede usar https y no loopback;
uno local sólo loopback. Una familia sin adaptador no entra al registro.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ESQUEMA = "moldesign.molchat-catalogo/1"
#: Familias de protocolo con adaptador en este sidecar.
FAMILIAS = frozenset({"openai_chat", "anthropic", "gemini", "meta", "llama_server", "ollama"})
RUTA = Path(__file__).with_name("catalogo.json")
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class Entrada:
    id: str
    nombre: str
    familia: str
    base_url: str
    requiere_clave: bool
    remoto: bool
    modelo_por_defecto: str
    modelos_ejemplo: tuple[str, ...]
    prefijo_clave: str
    documentacion: str
    que_sale: str

    @property
    def host(self) -> str:
        return (urlsplit(self.base_url).hostname or "").lower()


def cargar(ruta: Path = RUTA) -> tuple[Entrada, ...]:
    """Entradas del catálogo. Lanza ValueError si el fichero no cumple el contrato."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict) or datos.get("schema") != ESQUEMA:
        raise ValueError("catálogo de proveedores con esquema desconocido")
    crudas = datos.get("proveedores")
    if not isinstance(crudas, list) or not crudas:
        raise ValueError("el catálogo no trae proveedores")
    entradas: list[Entrada] = []
    ids: set[str] = set()
    for c in crudas:
        entrada = Entrada(
            id=str(c["id"]), nombre=str(c["nombre"]), familia=str(c["familia"]),
            base_url=str(c["base_url"]), requiere_clave=bool(c["requiere_clave"]),
            remoto=bool(c["remoto"]), modelo_por_defecto=str(c.get("modelo_por_defecto", "")),
            modelos_ejemplo=tuple(str(m) for m in c.get("modelos_ejemplo", [])),
            prefijo_clave=str(c.get("prefijo_clave", "")),
            documentacion=str(c.get("documentacion", "")), que_sale=str(c.get("que_sale", "")),
        )
        if entrada.id in ids:
            raise ValueError(f"id de proveedor repetido: {entrada.id}")
        ids.add(entrada.id)
        if entrada.familia not in FAMILIAS:
            raise ValueError(f"{entrada.id}: familia sin adaptador: {entrada.familia}")
        scheme = urlsplit(entrada.base_url).scheme
        if entrada.remoto and (scheme != "https" or entrada.host in _LOOPBACK):
            raise ValueError(f"{entrada.id}: un proveedor remoto va por https fuera de la máquina")
        if not entrada.remoto and entrada.host not in _LOOPBACK:
            raise ValueError(f"{entrada.id}: un proveedor local apunta a la máquina")
        entradas.append(entrada)
    return tuple(entradas)


ENTRADAS: tuple[Entrada, ...] = cargar()


def por_id(proveedor: str) -> Entrada | None:
    for entrada in ENTRADAS:
        if entrada.id == proveedor:
            return entrada
    return None
