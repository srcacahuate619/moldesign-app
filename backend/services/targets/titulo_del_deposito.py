"""El título de un depósito PDB, entero.

Caza 1 (2026-11-12), A04. El registro TITLE de un PDB sigue en líneas de continuación (`TITLE    2 …`), y la ingestión sólo leía la
primera: 14 de 14 informes de la cápsula enseñaban receptores como «CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT
ACTIVE» o «CRYSTAL STRUCTURE OF THE VOLTAGE-GATED SODIUM CHANNEL NAVMS (F208L) IN», cortados a media frase y sin puntos suspensivos.
"""
from __future__ import annotations

import gzip
import re
from functools import lru_cache
from pathlib import Path

#: Lo más largo que se imprime de un título: los hay de más de 240 caracteres.
MAX_NOMBRE = 200


def titulo_del_deposito(pdb_text: str | None) -> str | None:
    """Las líneas TITLE del depósito unidas en una frase, o None si no tiene ninguna."""
    if not pdb_text:
        return None
    partes = []
    for linea in pdb_text.splitlines():
        if linea.startswith("TITLE ") or linea.startswith("TITLE\t"):
            texto = linea[10:80].strip()
            if texto:
                partes.append(texto)
    if not partes:
        return None
    return " ".join(" ".join(partes).split()).rstrip(".").strip().strip('"').strip("'").strip() or None


def nombre_completo_del_receptor(nombre: str | None, pdb_text: str | None = None, pdb_id: str | None = None) -> str | None:
    """El nombre guardado, completado con el título del depósito cuando éste lo continúa.

    Un nombre que la persona puso a su receptor (o cualquiera que el título no continúe) no se toca. Un título de más de
    `MAX_NOMBRE` caracteres se acorta con «…», nunca a media palabra sin decirlo.
    """
    if not nombre:
        return nombre
    titulo = titulo_del_deposito(pdb_text) or titulo_del_catalogo(pdb_id)
    if not titulo:
        return nombre
    base = " ".join(nombre.split()).rstrip(".… ").upper()
    if len(titulo) <= len(base) or not titulo.upper().startswith(base):
        return nombre
    if len(titulo) > MAX_NOMBRE:
        return titulo[:MAX_NOMBRE - 1].rstrip() + "…"
    return titulo


#: La raíz que ve el instalador: `backend/services/targets/` está tres niveles por debajo.
_RAIZ = Path(__file__).resolve().parents[3]
#: Las líneas TITLE están al principio del depósito; no hace falta leer los 300 KB de átomos.
_CABECERA_MAXIMA = 32768
_ID_DEL_CATALOGO = re.compile(r"^[A-Za-z0-9]{4}$")


def _cabecera(ruta: Path) -> str | None:
    try:
        abrir = gzip.open if ruta.suffix == ".gz" else open
        with abrir(ruta, "rt", encoding="utf-8", errors="replace") as archivo:
            return archivo.read(_CABECERA_MAXIMA)
    except (OSError, EOFError):
        return None


@lru_cache(maxsize=512)
def titulo_del_catalogo(pdb_id: str | None) -> str | None:
    """El título completo del depósito de un receptor del catálogo, o None si no se puede leer.

    La copia del receptor que lee un informe (`~/MolDesign/data/targets/<ID>.pdb`) la escribe la preparación sin HEADER ni TITLE; el título está
    en el `.pdb.gz` que viaja con el instalador. Sólo los identificadores de cuatro caracteres del PDB: un receptor subido (`USR_…`) lleva el
    nombre que le puso quien lo subió.
    """
    if not pdb_id or not _ID_DEL_CATALOGO.match(pdb_id.strip()):
        return None
    ident = pdb_id.strip().upper()
    candidatas = [_RAIZ / "data" / "targets" / f"{ident}.pdb.gz", _RAIZ / "data" / "targets" / f"{ident}.pdb"]
    try:
        from core.config import get_settings

        candidatas.append(Path(get_settings().local_data_dir) / "targets" / ident / "raw.pdb")
    except Exception:  # sin configuración (una herramienta suelta): basta con el instalador
        pass
    for ruta in candidatas:
        titulo = titulo_del_deposito(_cabecera(ruta)) if ruta.is_file() else None
        if titulo:
            return titulo
    return None
