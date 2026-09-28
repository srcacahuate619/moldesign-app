"""¿Se puede comparar esta corrida con las que se hacen hoy?

Los resultados de 1.0.1 no son comparables con los de 1.0.2: cambian la receta
del receptor (truncado de cadenas laterales, cofactores, histidinas declaradas)
y el ranking (M4 v2: Vina 1,0 y XGBoost 0). Historial, Moldex y SAR ponían las
dos series lado a lado sin decirlo.

Dos datos lo deciden, y los dos se leen de lo que la corrida persistió. Nada se
deduce del valor de un peso ni de la fecha:

- `execution_provenance.receta_receptor`: versión de la receta con la que se
  preparó el receptor. Se sella desde 1.0.2; las corridas anteriores no la
  tienen.
- `weights_calibration_id`: calibración del stacking que produjo
  `total_score` (p. ej. `M4_STACKING_ALPHA_V1` frente a
  `M4_VINA_ONLY_PENDING_DOCKED_VALIDATION_V2`).

`vigente` tiene tres valores:

- ``False``: al menos uno de los dos datos está registrado y difiere del de hoy.
  No es comparable.
- ``True``: los dos están registrados y coinciden.
- ``None``: no hay diferencia registrada, pero falta alguno de los dos. No se
  afirma que sea comparable.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

_REGISTRO = Path(__file__).resolve().parents[2] / "artifacts" / "sci_config_registry.json"


def receta_vigente() -> int:
    from services.docking.preparer import RECEPTOR_RECIPE_VERSION

    return RECEPTOR_RECIPE_VERSION


@lru_cache(maxsize=1)
def _calibraciones_vigentes() -> dict[str, str]:
    """Última `calibration_id` de cada parámetro de pesos del registro."""
    try:
        datos = json.loads(_REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("registro_cientifico_ilegible", ruta=str(_REGISTRO), error=str(exc))
        return {}
    salida: dict[str, str] = {}
    for nombre, parametro in (datos.get("parameters") or {}).items():
        versiones = parametro.get("versions") or []
        if versiones and versiones[-1].get("calibration_id"):
            salida[nombre] = str(versiones[-1]["calibration_id"])
    return salida


def calibracion_vigente(target_family: str | None) -> str | None:
    """La calibración que usaría hoy `scoring/engine.py` para esta familia."""
    # Las áreas clínicas no son familias estructurales: el motor las resuelve a
    # los pesos por defecto, y aquí se hace lo mismo.
    from scoring.engine import AREAS_CLINICAS_CONOCIDAS

    familia = (target_family or "").lower().strip()
    if familia in AREAS_CLINICAS_CONOCIDAS:
        familia = ""
    vigentes = _calibraciones_vigentes()
    clave = f"stacking_{familia}" if familia else "stacking_default"
    return vigentes.get(clave) or vigentes.get("stacking_default")


def describir_protocolo(
    docking_protocol: dict[str, Any] | None,
    weights_calibration_id: str | None,
    target_family: str | None,
) -> dict[str, Any]:
    """Qué protocolo produjo la corrida, cuál es el de hoy y si coinciden."""
    procedencia = (docking_protocol or {}).get("execution_provenance") or {}
    receta = procedencia.get("receta_receptor") if isinstance(procedencia, dict) else None
    receta = int(receta) if isinstance(receta, int) and not isinstance(receta, bool) else None
    calibracion = str(weights_calibration_id) if weights_calibration_id else None

    receta_hoy = receta_vigente()
    calibracion_hoy = calibracion_vigente(target_family)

    diferencias: list[str] = []
    if receta is not None and receta != receta_hoy:
        diferencias.append("receta_receptor")
    if calibracion is not None and calibracion_hoy is not None and calibracion != calibracion_hoy:
        diferencias.append("calibracion_ranking")

    if diferencias:
        vigente: bool | None = False
    elif receta is None or calibracion is None:
        vigente = None
    else:
        vigente = True

    return {
        "vigente": vigente,
        "diferencias": diferencias,
        "receta_receptor": receta,
        "receta_vigente": receta_hoy,
        "calibracion_ranking": calibracion,
        "calibracion_vigente": calibracion_hoy,
    }
