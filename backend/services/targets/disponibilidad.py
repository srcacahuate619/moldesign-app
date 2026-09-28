"""Qué dianas del catálogo no se pueden preparar hoy, y por qué.

Lee `backend/data/disponibilidad_catalogo.json`, que genera
`scripts/generate_catalog_availability.py` con la misma función que usa
`prepare_target` (DOCK-003) y con un barrido real de Meeko (DOCK-002). Una diana
no disponible sigue en el catálogo: se lista con su motivo y la interfaz no la
ofrece para evaluar. Si el archivo falta, nada se marca y la preparación sigue
deteniéndose sola: se pierde el aviso previo, no la garantía.

El mismo barrido registra, por diana disponible, las cadenas laterales
truncadas dentro del sitio (receta v7). Esas dianas se pueden acoplar, pero la
cavidad pierde esos grupos: la interfaz lo avisa antes de elegirlas, no sólo en
el aviso CRÍTICO de la corrida.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

RUTA_DISPONIBILIDAD = Path(__file__).resolve().parents[2] / "data" / "disponibilidad_catalogo.json"


@lru_cache(maxsize=1)
def _datos() -> dict[str, Any]:
    try:
        return json.loads(RUTA_DISPONIBILIDAD.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("disponibilidad_catalogo_ilegible", ruta=str(RUTA_DISPONIBILIDAD), error=str(exc))
        return {}


@lru_cache(maxsize=1)
def _no_disponibles() -> dict[str, str]:
    return {
        str(pdb_id).upper(): str(fila.get("motivo") or "Preparación no disponible")
        for pdb_id, fila in (_datos().get("no_disponibles") or {}).items()
    }


def motivo_no_disponible(pdb_id: str | None) -> str | None:
    """El motivo si la diana no se puede preparar hoy; `None` si está disponible."""
    return _no_disponibles().get(str(pdb_id or "").upper())


def cadenas_truncadas_en_sitio(pdb_id: str | None) -> list[str] | None:
    """Cadenas laterales truncadas a 6 Å o menos de la caja, según el barrido.

    `[]` si el barrido preparó la diana y no truncó nada en el sitio. `None` si
    no hay medida: el archivo no trae el barrido, o la diana no está disponible
    (entonces no se preparó). Ausencia de medida no es «ninguna».
    """
    datos = _datos()
    if "truncadas_en_sitio" not in datos:
        return None
    clave = str(pdb_id or "").upper()
    if not clave or clave in _no_disponibles():
        return None
    return list((datos.get("truncadas_en_sitio") or {}).get(clave, []))
