"""Qué dianas del catálogo no se pueden preparar hoy, y por qué.

Lee `backend/data/disponibilidad_catalogo.json`, que genera
`scripts/generate_catalog_availability.py` con la misma función que usa
`prepare_target` (DOCK-003) y con un barrido real de Meeko (DOCK-002). Una diana
no disponible sigue en el catálogo: se lista con su motivo y la interfaz no la
ofrece para evaluar. Si el archivo falta, nada se marca y la preparación sigue
deteniéndose sola: se pierde el aviso previo, no la garantía.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

RUTA_DISPONIBILIDAD = Path(__file__).resolve().parents[2] / "data" / "disponibilidad_catalogo.json"


@lru_cache(maxsize=1)
def _no_disponibles() -> dict[str, str]:
    try:
        datos = json.loads(RUTA_DISPONIBILIDAD.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("disponibilidad_catalogo_ilegible", ruta=str(RUTA_DISPONIBILIDAD), error=str(exc))
        return {}
    return {
        str(pdb_id).upper(): str(fila.get("motivo") or "Preparación no disponible")
        for pdb_id, fila in (datos.get("no_disponibles") or {}).items()
    }


def motivo_no_disponible(pdb_id: str | None) -> str | None:
    """El motivo si la diana no se puede preparar hoy; `None` si está disponible."""
    return _no_disponibles().get(str(pdb_id or "").upper())
