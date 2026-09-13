"""
services/rescoring_bridge.py

Encapsulación ÚNICA del sidecar rescoring/ (audit F-14).

Este módulo es el ÚNICO punto del backend autorizado a:
  1. resolver la ubicación del sidecar rescoring/ (una sola vez),
  2. mutar sys.path (inserción idempotente de repo root + rescoring/),
  3. inicializar los defaults RESCORING_*_PATH con rutas absolutas,
  4. importar símbolos del sidecar (ningún otro módulo toca rescoring.*).

Contexto: el sidecar rescoring/ vive en el repo root y usa DOS
convenciones de import que coexisten en el codebase:
  (1) "flat"   — `from model_manager import`, `from config import`,
                `from schemas import` (dentro del propio sidecar).
                Requiere <repo>/rescoring/ en sys.path.
  (2) "prefix" — `from rescoring.model_manager import` (desde el
                backend). Requiere <repo>/ en sys.path.
Ambos paths se insertan AQUÍ, una sola vez y con guard idempotente,
por lo que el backend puede arrancar desde cualquier cwd del installer
sin que main.py, rescoring_service.py o las AI tools muten sys.path
por su cuenta.

IMPORTANTE (orden de inicialización): rescoring/model_manager.py llama
a get_rescoring_settings() a nivel de módulo con lru_cache, y sus
paths de artefactos son relativos al cwd. Los defaults RESCORING_*_PATH
con rutas absolutas DEBEN existir en os.environ ANTES del primer import
de cualquier módulo del sidecar (si se cacheara después, lru_cache ya
quedó con defaults erróneos). Este bridge garantiza ese orden: los
callers importan el bridge y piden símbolos vía sus getters; NUNCA
importan rescoring.* directamente.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)

# ── Resolución del sidecar: independiente del cwd del proceso ──────────
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/services/ → repo root
_SIDECAR_DIR = _REPO_ROOT / "rescoring"
_ARTIFACTS_DIR = _SIDECAR_DIR / "artifacts"

# ── (1) sys.path: inserción única e idempotente ────────────────────────
for _p in (str(_REPO_ROOT), str(_SIDECAR_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── (2) Registro central de artefactos: LA ÚNICA fuente de verdad de los
#    paths del sidecar. setdefault respeta env vars pre-existentes del
#    usuario; se ejecuta ANTES de importar cualquier módulo del sidecar.
_ARTIFACT_DEFAULTS: dict[str, str] = {
    "RESCORING_MODEL_A_PATH": "model_a_universal.json",
    "RESCORING_MODEL_NULL_PATH": "model_null.json",
    "RESCORING_DELTA_DISTRIBUTION_PATH": "delta_distribution.json",
    "RESCORING_APPLICABILITY_DOMAIN_PATH": "applicability_domain.json",
    "RESCORING_TRAINING_REPORT_PATH": "training_report.json",
    "RESCORING_MODEL_MANIFEST_PATH": "model-manifest.json",
    "RESCORING_POSE_SELECTOR_MODEL_PATH": "pose_selector_v06.xgb",
    "RESCORING_POSE_SELECTOR_META_PATH": "pose_selector_v06_meta.json",
}
for _var, _filename in _ARTIFACT_DEFAULTS.items():
    os.environ.setdefault(_var, str(_ARTIFACTS_DIR / _filename))


def get_sidecar_dir() -> Path:
    """Directorio del sidecar rescoring/ (resuelto una sola vez)."""
    return _SIDECAR_DIR


def get_artifact_defaults() -> dict[str, str]:
    """Mapa VAR → nombre de artefacto. Fuente de verdad central de paths."""
    return dict(_ARTIFACT_DEFAULTS)


@lru_cache(maxsize=1)
def get_model_manager() -> tuple[Any, Any, Any, Any]:
    """Instancia única de ModelManager (lru_cache), ya cargada.

    Se usa lru_cache para que el import ocurra UNA sola vez (al primer
    llamado) y quede disponible en memoria compartida — el startup y el
    primer request comparten la misma instancia.

    Returns:
        (ModelManager, RescoreRequest, RescoreResponse, PoseData)
        o (None, None, None, None) si el import o la carga falla.
    """
    try:
        from model_manager import ModelManager
        from schemas import (
            RescoreRequest as _RescoreRequest,
            RescoreResponse as _RescoreResponse,
            PoseData as _PoseData,
        )

        mm = ModelManager()
        mm.load_models()

        loaded_ok = bool(mm.is_loaded)
        info = mm.get_info() if loaded_ok else {}
        log.info(
            "rescoring_service_ready",
            loaded=loaded_ok,
            families=info.get("families_trained"),
            version=info.get("model_version"),
        )

        return mm, _RescoreRequest, _RescoreResponse, _PoseData

    except ImportError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        log.warning("rescoring_import_missing_module", module=missing_module)
        return None, None, None, None
    except Exception as e:
        log.error("rescoring_import_failed", error=str(e))
        return None, None, None, None


@lru_cache(maxsize=1)
def get_model_manager_class():
    """Clase ModelManager del sidecar, SIN instanciar ni cargar.

    El caller es responsable de instanciar y llamar load_models()
    (p. ej. AI tools que quieren su propia instancia).

    Raises:
        ImportError: si el módulo del sidecar no está disponible, para
        que los callers mantengan su manejo `except ImportError`.
    """
    from model_manager import ModelManager

    return ModelManager


@lru_cache(maxsize=1)
def get_interaction_feature_extractor():
    """Clase InteractionFeatureExtractor del sidecar.

    Usada por el endpoint inline /rescore y por servicios de AI que
    necesitan extraer features 3D directamente.
    """
    from feature_extractor import InteractionFeatureExtractor

    return InteractionFeatureExtractor


# ── Manifiesto de modelos (audit F-19) ────────────────────────────────────────
#
# model-manifest.json se genera con rescoring/scripts/generate_model_manifest.py
# (hashes SHA-256 reales + métricas del training_report.json). El backend lo
# expone para que /health y el launcher puedan auditar la identidad exacta de
# los artefactos de rescoring desplegados.
@lru_cache(maxsize=1)
def _load_model_manifest() -> dict:
    """Carga artifacts/model-manifest.json una sola vez (lru_cache).

    Raises:
        FileNotFoundError: si el manifiesto no existe.
        json.JSONDecodeError / ValueError: si el contenido no es JSON válido.
    """
    path = Path(
        os.environ.get(
            "RESCORING_MODEL_MANIFEST_PATH",
            str(_ARTIFACTS_DIR / "model-manifest.json"),
        )
    )
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"model-manifest.json no es un objeto JSON: {path}")
    return data


def get_model_manifest() -> dict | None:
    """Manifiesto de modelos del sidecar si su integridad está verificada.

    El fallo NO propaga la excepción: un manifiesto ausente, corrupto o cuyo
    hash ya no representa los artefactos no tumba el backend; /health lo
    expone como componente degradado.
    """
    status = get_model_manifest_verification()
    if not status["valid"]:
        return None
    try:
        return _load_model_manifest()
    except FileNotFoundError:
        log.warning("model_manifest_missing", path=str(_ARTIFACTS_DIR / "model-manifest.json"))
        return None
    except (json.JSONDecodeError, ValueError) as e:
        log.error("model_manifest_invalid", error=str(e))
        return None
    except Exception as e:
        log.error("model_manifest_load_failed", error=str(e))
        return None


@lru_cache(maxsize=1)
def get_model_manifest_verification() -> dict[str, Any]:
    """Verificar hashes del manifiesto v4 una vez por proceso.

    Se mantiene como un dict serializable para que el endpoint de health no
    dependa de las clases internas del sidecar.
    """
    path = Path(
        os.environ.get(
            "RESCORING_MODEL_MANIFEST_PATH",
            str(_ARTIFACTS_DIR / "model-manifest.json"),
        )
    )
    try:
        from model_manifest import verify_model_manifest

        result = verify_model_manifest(path, path.parent)
        if not result.valid:
            log.error(
                "model_manifest_integrity_failed",
                version=result.version,
                errors=list(result.errors),
            )
        return {
            "valid": result.valid,
            "manifest_version": result.version,
            "models": list(result.model_keys),
            "errors": list(result.errors),
        }
    except Exception as exc:
        log.error("model_manifest_verify_failed", error=str(exc))
        return {
            "valid": False,
            "manifest_version": None,
            "models": [],
            "errors": [f"verification_failed:{exc}"],
        }
