"""Perfil de un receptor propio: con qué modo se preparó y de dónde viene.

# Por qué existe

El catálogo se prepara siempre con la receta 7 (``preparer.prepare_target``): se
retiran las aguas, se filtra la cadena y se vuelve a protonar con Meeko. Un
receptor que sube la persona no tiene por qué pasar por ahí: puede traer su
propia preparación (PDB protonado, PQR, PDBQT para Vina) y entonces MolDesign no
debe rehacerla en silencio.

El modo no cabe en las columnas del receptor ni se puede deducir de los bytes,
así que se guarda junto a él, en ``targets/USR_xxxx/perfil.json``. Sólo existe
para identificadores ``USR_*``: **el catálogo nunca tiene perfil**, por lo que
su preparación no puede cambiar por culpa de este archivo. Eso es lo que
comprueba ``scripts/invariancia_catalogo_receptores.py``.

# Modos

``automatico``   la estructura cruda, experimental o predicha: la prepara MolDesign
                 (la receta de siempre).
``respetar``     la estructura ya preparada por el equipo: se conservan su
                 protonación, sus cofactores, sus metales y sus aguas.
``pdbqt``        un PDBQT listo para Vina, con o sin la estructura de origen.
"""

from __future__ import annotations

import json
from typing import Any

from utils.file_handlers import StoragePath
from utils.local_storage import path_for, write_text

SCHEMA = "receptor-propio/v1"

MODO_AUTOMATICO = "automatico"
MODO_RESPETAR = "respetar"
MODO_PDBQT = "pdbqt"
MODOS = (MODO_AUTOMATICO, MODO_RESPETAR, MODO_PDBQT)

PREFIJO = "USR_"


def es_propio(pdb_id: str) -> bool:
    return str(pdb_id or "").strip().upper().startswith(PREFIJO)


def cargar(pdb_id: str) -> dict[str, Any] | None:
    """El perfil del receptor, o ``None`` si es del catálogo o no tiene perfil."""
    if not es_propio(pdb_id):
        return None
    try:
        datos = json.loads(path_for(StoragePath.target_profile(pdb_id)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict) or datos.get("schema") != SCHEMA:
        return None
    return datos


def modo_de(pdb_id: str) -> str | None:
    """El modo del receptor propio, o ``None`` para el catálogo."""
    perfil = cargar(pdb_id)
    return perfil.get("modo") if perfil else None


def distinto_del_automatico(pdb_id: str) -> dict[str, Any] | None:
    """El perfil sólo si el receptor NO se prepara con la receta de siempre."""
    perfil = cargar(pdb_id)
    if perfil and perfil.get("modo") in (MODO_RESPETAR, MODO_PDBQT):
        return perfil
    return None


async def guardar(pdb_id: str, perfil: dict[str, Any]) -> None:
    perfil = {"schema": SCHEMA, **perfil}
    await write_text(
        StoragePath.target_profile(pdb_id),
        json.dumps(perfil, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )


def extras_del_informe(
    pdb_id: str,
    *,
    texto: str | None = None,
    center: tuple[float, float, float] | None = None,
    size: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """Lo que el informe de preparación añade para un receptor propio.

    Vacío para el catálogo: su informe no cambia ni un byte. Con ``texto`` (el receptor, en PDB o PDBQT) y la caja,
    una estructura predicha añade además la confianza (pLDDT) de los residuos junto al sitio.
    """
    perfil = cargar(pdb_id)
    if not perfil:
        return {}
    extras: dict[str, Any] = {"modo_de_preparacion": perfil.get("modo_detallado") or perfil.get("modo")}
    for clave in ("entrada", "origen", "prediccion", "protonacion_declarada"):
        if perfil.get(clave) is not None:
            extras[clave] = perfil[clave]
    mapa = perfil.get("plddt_residuos")
    if extras.get("prediccion") and mapa and texto is not None and center is not None and size is not None:
        from services.targets.prediccion import confianza_del_sitio

        extras["prediccion"] = {**extras["prediccion"], "sitio": confianza_del_sitio(mapa, texto, center, size)}
    return extras
