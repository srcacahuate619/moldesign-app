"""
scoring/engine.py

Motor de score compuesto del MVP.

Combina:
- Ligand Efficiency (LE) o Afinidad absoluta
- QED (Quantitative Estimate of Drug-likeness) para propiedades fisicoquímicas

El resultado es una métrica de priorización basada en estándares de la industria.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.exceptions import ScoringError
from core.models import DockingResult, PhysicochemicalProperties, ScoreBreakdown
from db.repository import Repository
from scoring.normalizer import (
    calculate_adme_score,
    calculate_druglikeness_score,
    clamp_score,
    normalize_affinity,
)
from scoring.ums import _is_metalloenzyme_family
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# M4 release stacking (Vina + XGBoost; CL-GNN is experimental with w=0)
# Canonical source: backend/artifacts/sci_config_registry.json
# ═══════════════════════════════════════════════════════════════════════

_RELEASE_SAFE_M4_WEIGHTS = {
    "vina": 0.25,
    "xgb": 0.75,
    "gnn": 0.0,
    "clgnn": 0.0,
    "quantum_sign": 1.0,
}

# Fallback de emergencia. El contrato canonico vive en
# backend/artifacts/sci_config_registry.json y este espejo solo existe para que
# una instalacion danada se degrade de manera conservadora. CL-GNN se incluye,
# ejecuta y serializa, pero el checkpoint distribuido todavia no tiene una
# validacion externa sellada atribuible a su SHA-256 exacto; por tanto no decide
# ranking en la alpha. La GNN legacy tampoco recibe peso.
STACKING_WEIGHTS = {
    family: dict(_RELEASE_SAFE_M4_WEIGHTS)
    for family in (
        "default",
        "gpcr",
        "protease",
        "kinase",
        "nuclear_receptor",
        "soluble_enzyme",
        "phosphodiesterase",
        "unknown",
    )
}

_STACKING_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "rescoring" / "artifacts" / "stacking_weights.json"

# Caché en memoria con TTL para evitar leer stacking_weights.json del disco
# en cada evaluate(). TTL = 300s: balance entre frescura y rendimiento.
_STACKING_CACHE: dict[str, Any] | None = None
_STACKING_CACHE_TIME: float = 0.0
_STACKING_CACHE_TTL: float = 300.0


# ═══════════════════════════════════════════════════════════════════════
# Un área terapéutica NO es una familia estructural
# ═══════════════════════════════════════════════════════════════════════
#
# Aquí vivía `CLINICAL_FAMILY_MAP`, que traducía el área clínica a una clase
# estructural antes de elegir los pesos del stacking:
#
#     "cardiovascular" -> "metaloenzyme"      vina 0.0 · xgb 0.1 · gnn 0.9
#     "oncologia"      -> "kinase"            vina 0.2 · xgb 0.8 · gnn 0.0
#     "antivirals"     -> "protease"
#
# La equivalencia no existe. La oncología incluye MDM2, Bcl-2, HDAC y
# proteasoma además de kinasas; lo cardiovascular incluye receptores
# adrenérgicos —GPCR— y canales iónicos, que en este catálogo son 30 y 30
# entradas. Un GPCR clasificado como «cardiovascular» habría recibido los pesos
# de metaloenzima: `vina: 0.0`, es decir, **tirar el score de acoplamiento
# entero** y decidir con la GNN.
#
# LO QUE SE MIDIÓ ANTES DE QUITARLO. El mapa no se dispara hoy: las 380 entradas
# del catálogo curado traen en `structural_family` valores estructurales de
# verdad (protease 62, gpcr 30, ion_channel 30, nuclear_receptor 29, kinase 29 …
# 26 familias, ninguna clínica), y los cuatro llamadores del pipeline pasan
# `pipeline_params.target_structural_family`. El área clínica vive en OTRA
# columna, `therapeutic_family`, y no llega hasta aquí.
#
# Así que esto no arregla un número: desarma una trampa. Las dos columnas son
# vecinas en `core/models.py` y casi homónimas, y el día que un llamador pase la
# equivocada el efecto habría sido silencioso. Y el propio mapa era incoherente:
# `_get_stacking_weights` traducía el nombre, pero la puerta de UMS de más abajo
# —`_is_metalloenzyme_family(target_family)`— mira el valor CRUDO. Un target
# «cardiovascular» habría cobrado pesos de metaloenzima y a la vez habría sido
# tratado como no-metaloenzima por el scorer de metales.
#
# En su lugar, la confusión se DETECTA y se dice. Un área clínica que llegue
# aquí no se traduce a nada: cae a `default` con un aviso, que es la lectura
# honesta —no sabemos la familia estructural de este receptor— en vez de una
# familia inventada.
AREAS_CLINICAS_CONOCIDAS = frozenset({
    "cardiovascular",
    "oncologia",
    "inmuno-oncologia",
    "neurociencia",
    "neurologia",
    "neurodegeneration",
    "metabolismo",
    "endocrinologia",
    "infecciosas",
    "inmunologia",
    "antibacterials",
    "antivirals",
    "antivirales",
    "fibrosis",
    "transporters",
    "aging_senescence",
    "inflamacion___dolor",
    "enfermedades_raras",
    "psiquiatria",
})


def _load_stacking_weights() -> dict:
    """
    Load per-family stacking weights from artifacts JSON, with fallback to defaults.

    Cachea en memoria con TTL de _STACKING_CACHE_TTL segundos para evitar
    lecturas repetitivas del disco en evaluaciones sucesivas.
    """
    global _STACKING_CACHE, _STACKING_CACHE_TIME

    now = time.time()
    if _STACKING_CACHE is not None and (now - _STACKING_CACHE_TIME) < _STACKING_CACHE_TTL:
        return _STACKING_CACHE

    if _STACKING_WEIGHTS_PATH.exists():
        try:
            with open(_STACKING_WEIGHTS_PATH) as f:
                _STACKING_CACHE = json.load(f)
                _STACKING_CACHE_TIME = now
                return _STACKING_CACHE
        except Exception as e:
            log.warning("stacking_weights_load_failed, using defaults", error=str(e)[:100], path=str(_STACKING_WEIGHTS_PATH))

    _STACKING_CACHE = STACKING_WEIGHTS
    _STACKING_CACHE_TIME = now
    return _STACKING_CACHE


# Canonical path is source-relative, so cwd cannot change the contract.
_SCI_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "artifacts" / "sci_config_registry.json"
)


def _get_stacking_weights(target_family: str | None) -> dict:
    # SciConfigRegistry is the active, sealed source for M4 release weights.
    family = (target_family or "").lower().strip()
    if family in AREAS_CLINICAS_CONOCIDAS:
        # Ver el bloque sobre AREAS_CLINICAS_CONOCIDAS: no se traduce a una
        # familia estructural, porque no hay traducción. Se avisa y se usan los
        # pesos por defecto.
        log.warning(
            "stacking_familia_clinica_recibida",
            recibido=family,
            usando="default",
            motivo=(
                "Es un área terapéutica, no una familia estructural. Los pesos "
                "del stacking se calibran por clase de receptor; pásale "
                "target.structural_family, no target.therapeutic_family."
            ),
        )
        family = ""

    try:
        from scoring.sci_config_registry import SciConfigRegistry, ParameterCategory

        registry = SciConfigRegistry.load(_SCI_REGISTRY_PATH)
        key = f"stacking_{family}" if family else "stacking_default"
        parameter = registry.get(key) or registry.get("stacking_default")
        if parameter is None:
            raise KeyError("stacking_default no existe en SciConfigRegistry")
        if parameter.category != ParameterCategory.SCORING_WEIGHTS:
            raise ValueError(
                f"{parameter.name} tiene categoria {parameter.category.value}, "
                "se esperaba scoring_weights"
            )
        configured = parameter.current_value
        if isinstance(configured, dict):
            return configured
        raise TypeError(f"{parameter.name} no contiene un diccionario de pesos")
    except Exception as e:
        log.debug("stacking_weights_registry_unavailable, using fallback", error=str(e)[:100])

    weights = _load_stacking_weights()
    # Normalización de claves: el JSON calibrado por auto_recalibrator puede
    # usar "prob" (probabilidad del clasificador) en lugar de "xgb". Mapeamos
    # para que la calibración nunca quede huérfana en el fallback.
    if isinstance(weights, dict):
        weights = _normalize_weight_keys(weights)

    return weights.get(family, weights.get("default", STACKING_WEIGHTS["default"]))


# ═══════════════════════════════════════════════════════════════════════
# `_auc` en stacking_weights.json NO mide el pipeline de metaloenzimas
# ═══════════════════════════════════════════════════════════════════════
#
# El 2026-09-04 se añadió aquí un filtro que descartaba cualquier calibración
# cuyo `_auc` declarado no llegase a 0.55, a raíz de ver esta entrada:
#
#     "metaloenzyme": {"vina": 0.0, "prob": 0.0, "gnn": 0.0, "clgnn": 1.0,
#                      "_auc": 0.5, "_delta": 0.0453}
#
# El filtro estaba MAL y se ha retirado. Dos motivos, y el segundo es el que
# importa:
#
# 1. Esos pesos NO son un accidente del optimizador: son el diseño deliberado.
#    `docs/PAPER_UMS.md` §2.1.3 los documenta y los justifica —ese manuscrito
#    no está enviado a revista y no se distribuye con el repositorio, así que
#    la justificación se cita aquí entera— «Metalloenzyme:
#    Vina = 0.00 (validated: Vina AUC < 0.56 on all three metal targets with
#    full pipeline). CL-GNN dominates (0.90–1.00). UMS is added with weight w5
#    tuned per target»— y declara este mismo archivo como el artefacto donde
#    viven. Descartarlos devolvía las metaloenzimas a M4, que es justo la
#    línea base que el paper mide como peor (CA2: M4 0.804 -> M5_gated 0.926).
#
# 2. `_auc` lo escribe `scripts/benchmark_ef_vina.py`, y ese optimizador
#    recorre SOLO tres componentes:
#
#        scores = vina_norm*w_v + xgb*w_x + clgnn*w_c
#
#    UMS no entra en esa búsqueda. Para una metaloenzima eso deja fuera al
#    único scorer que discrimina: medido en `docs/26_UNIVERSAL_METAL_SCORE_RESULTS.md`
#    §1.3 sobre CA2, vina 0.558, xgb 0.766, clgnn 0.592 y **UMS 0.978**.
#
#    Un `_auc` de 0.5 en esta familia no dice «la calibración es basura»: dice
#    «el subconjunto de tres scorers no discrimina aquí», que es exactamente
#    la premisa por la que existe M5. Filtrar por esa cifra es filtrar por una
#    medición que estructuralmente no puede ver el componente que decide.
#
# Lo que sí queda abierto, y no se arregla en silencio porque cambia
# rankings, está anotado sobre la puerta de UMS más abajo: el peso con el que
# se aplica aquí (0.06) no es el que valida el paper (w5 = 0.25-0.40).


def _normalize_weight_keys(weights: dict) -> dict:
    """Mapa 'prob' → 'xgb' en los pesos por familia del JSON calibrado.

    El auto_recalibrator escribe 'prob' (probabilidad XGBoost), pero el engine
    lee 'xgb'. Sin el mapeo, familias como metaloenzyme/unknown caían al
    fallback hardcodeado y la calibración post-benchmark se ignoraba.
    """
    normalized: dict[str, Any] = {}
    for fam, w in weights.items():
        if isinstance(w, dict):
            w2 = dict(w)
            if "prob" in w2 and "xgb" not in w2:
                w2["xgb"] = w2.pop("prob")
            # clgnn: sinónimo de gnn en el JSON calibrado (ambos se suman a
            # 'gnn' si falta, ver _resolve_stacking_component).
            normalized[fam] = w2
        else:
            normalized[fam] = w
    return normalized


def _resolve_stacking_weights(weights: dict) -> dict:
    """Resuelve vina/xgb/gnn/clgnn con saneamiento robusto.

    Reglas:
      - 'gnn' y 'clgnn' son componentes separados (el engine valora ambos).
      - Si el JSON solo trae 'gnn' (formato legacy), clgnn hereda 0.0
        (el CL-GNN no corrió en esos benchmarks) y gnn queda como está.
      - Si el JSON solo trae 'clgnn' (formato nuevo), gnn es 0 y clgnn su valor.
      - Devuelve SIEMPRE claves vina, xgb, gnn, clgnn con floats no negativos
        y quantum_sign por familia.

    [A3] NO se fabrican pesos: si la suma es <= 0 (config calibrada corrupta),
    se devuelven todos en 0.0 y el engine cae a regresión pura de afinidad
    (stacking_factor = 1.0), con log explícito — antes se hardcodeaban
    (0.3, 0.5, 0.0, 0.2) de forma silenciosa.
    """
    fam_weights = STACKING_WEIGHTS.get("default", {})
    vina = float(weights.get("vina", fam_weights.get("vina", 0.3)))
    xgb = float(weights.get("xgb", fam_weights.get("xgb", 0.5)))
    gnn = float(weights.get("gnn", 0.0))
    clgnn = float(weights.get("clgnn", 0.0))
    quantum_sign = float(weights.get("quantum_sign", fam_weights.get("quantum_sign", 1.0)))

    total = vina + xgb + gnn + clgnn
    if total <= 0:
        log.warning("stacking_weights_zero_total", weights=weights)
        return {
            "vina": 0.0,
            "xgb": 0.0,
            "gnn": 0.0,
            "clgnn": 0.0,
            "quantum_sign": quantum_sign,
        }
    return {
        "vina": vina / total,
        "xgb": xgb / total,
        "gnn": gnn / total,
        "clgnn": clgnn / total,
        "quantum_sign": quantum_sign,
    }


def _pick_dimensions(
    affinity_score: float,
    adme_score: float,
    druglikeness_score: float,
) -> tuple[str, str]:
    # Agrupamos las dimensiones de afinidad y propiedades fisicoquímicas para análisis
    dimensions = {
        "afinidad (LE)": affinity_score,
        "propiedades (QED)": (adme_score + druglikeness_score) / 2.0,
    }
    strongest = max(dimensions, key=dimensions.get)
    weakest = min(dimensions, key=dimensions.get)
    return strongest, weakest


def _calculate_sa_factor(sa_score: float | None) -> tuple[float, str]:
    """
    Calcula un factor multiplicativo [0.35, 1.00] basado en el SA Score.

    SA Score (Ertl & Schuffenhauer 2009):
      1.0 = trivialmente sintetizable
      10.0 = prácticamente imposible de sintetizar

    Este factor penaliza directamente el total_score para reflejar
    que una molécula no sintetizable no puede ser un fármaco real,
    independientemente de su afinidad o propiedades fisioquímicas.

    Curva calibrada para química medicinal estándar:
      SA ≤ 3.5  → factor=1.00 (sin penalización)
      SA = 4.0  → factor=0.95
      SA = 4.5  → factor=0.85
      SA = 5.0  → factor=0.72
      SA = 6.0  → factor=0.55
      SA = 7.0  → factor=0.42
      SA ≥ 8.0  → factor=0.35 (máximo castigo)

    Returns:
        (factor, severity_label): el multiplicador y una etiqueta descriptiva.
    """
    if sa_score is None:
        return 1.0, "sin_dato"

    if sa_score <= 3.5:
        return 1.0, "excelente"
    elif sa_score <= 4.0:
        # Gracia suave: SA 3.5–4.0
        factor = 1.0 - (sa_score - 3.5) * 0.10
        return round(factor, 3), "buena"
    elif sa_score <= 5.0:
        # Penalización progresiva: SA 4.0–5.0
        # En 4.0: 0.95, en 5.0: 0.72 (descenso de ~0.23)
        factor = 0.95 - (sa_score - 4.0) * 0.23
        return round(factor, 3), "moderada"
    elif sa_score <= 6.0:
        # Penalización significativa: SA 5.0–6.0
        # En 5.0: 0.72, en 6.0: 0.55 (descenso de ~0.17)
        factor = 0.72 - (sa_score - 5.0) * 0.17
        return round(factor, 3), "dificil"
    elif sa_score <= 7.0:
        # Penalización severa: SA 6.0–7.0
        # En 6.0: 0.55, en 7.0: 0.42 (descenso de ~0.13)
        factor = 0.55 - (sa_score - 6.0) * 0.13
        return round(factor, 3), "muy_dificil"
    else:
        # Penalización máxima: SA > 7.0
        # Decae linealmente hasta 0.35 en SA=8+
        factor = max(0.35, 0.42 - (sa_score - 7.0) * 0.07)
        return round(factor, 3), "inviable"


def _build_improvement_hint(
    properties: PhysicochemicalProperties,
    weakest_dimension: str,
) -> str:
    if weakest_dimension == "afinidad (LE)":
        return (
            "La Eficiencia de Ligando es baja. Considera optimizar los contactos "
            "existentes antes de añadir más peso molecular."
        )

    # Si QED es la más débil
    if properties.qed < 0.5:
        if properties.molecular_weight > 500:
            return "El QED es bajo. Intenta reducir el peso molecular para mejorar el perfil general."
        if properties.log_p > 5:
            return "El QED es bajo. Reduce la lipofilia (logP) para mejorar la viabilidad."
        if properties.tpsa > 140:
            return "El QED es bajo. La polaridad excesiva (TPSA) está reduciendo el score."
        return "El QED es bajo. Revisa la complejidad estructural de la molécula."

    return (
        "El perfil general es muy bueno. Cualquier mejora futura debería priorizar "
        "la optimización del ajuste estérico sin degradar el QED."
    )


def _finite_or_none(value, name: str):
    """[A3] NaN/Inf → None (componente AUSENTE), nunca un score fabricado.

    Los subsistemas upstream (model_manager, model_router, predict_clgnn)
    ahora propagan NaN/None explícito en fallos; aquí se convierte a
    "componente ausente" para re-normalizar pesos o degradar.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        fv = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(fv) or math.isinf(fv):
        return None
    return fv

def calculate_score_breakdown(
    docking: DockingResult,
    properties: PhysicochemicalProperties,
    is_control: bool = False,
    target_hotspots: list[dict] | None = None,
    affinity_threshold: float = -7.5,
    specificity_floor: float = 0.5,
    gnn_score: float | None = None,
    xgb_prob: float | None = None,
    clgnn_prob: float | None = None,
    mmgbsa_score: float | None = None,
    quantum_score: float | None = None,
    ums_score: float | None = None,
    target_family: str | None = None,
) -> ScoreBreakdown:
    """Calcula el breakdown completo del score para una evaluación.

    ═══════════════════════════════════════════════════════════════════════
    REGLA DE ORO v2.0 — DESACOPLAMIENTO DE MÉTRICAS (fix #2 Spearman)
    ═══════════════════════════════════════════════════════════════════════
    El ranking de afinidad (total_score) usa SOLO docking + ML + MM-GBSA.
    ADME, Drug-likeness, SA Score y Blood Viability son "flags" de perfil
    farmacocinético para el químico medicinal — NUNCA alteran el score
    de afinidad.

    Razonamiento (benchmark 5-HT1A):
      Vina solo:              ρ=+0.19
      Composite original:     ρ=-0.11 (ADME + drug-likeness metieron ruido)
    ═══════════════════════════════════════════════════════════════════════

    Args:
        gnn_score: Score de RTMScore GNN (deprecated). Se mantiene para compatibilidad.
        xgb_prob: Probabilidad del clasificador XGBoost (binder classifier).
        clgnn_prob: Probabilidad del CL-GNN contrastivo.
        mmgbsa_score: MM-GBSA delta G (OpenMM OBC2). Se aplica solo al top 10%.
        target_family: Familia estructural (gpcr, kinase, protease, etc).
                      Determina los pesos del stacking.
    """

    # ═════════════════════════════════════════════════════════════════════
    # GRUPO A — Métricas de AFINIDAD PURA (determinan el ranking)
    # ═════════════════════════════════════════════════════════════════════

    affinity_score = normalize_affinity(
        docking.best_affinity,
        properties.heavy_atom_count,
        properties.log_p,
        threshold=affinity_threshold,
        is_control=is_control,
    )

    # ML Stacking: Vina + XGBoost + CL-GNN con pesos por familia
    weights = _get_stacking_weights(target_family)
    if not isinstance(weights, dict):
        weights = STACKING_WEIGHTS["default"]
    resolved = _resolve_stacking_weights(weights)
    w_vina = resolved["vina"]
    w_xgb = resolved["xgb"]
    w_gnn = resolved["gnn"]
    w_clgnn = resolved["clgnn"]
    quantum_sign = resolved["quantum_sign"]

    # ── [A3] Disponibilidad real de componentes (sin fabricar 0.5) ──
    # Cada componente es None si su fuente falta o devuelve NaN/Inf.
    # `is not None` y no la verdad-ez del float: una afinidad de 0.0 es un
    # RESULTADO —el peor posible, y el validador de `DockingResult` lo admite—,
    # no una señal ausente. Con `if docking.best_affinity` caía a `None`, el
    # stack se marcaba degradado y renormalizaba el peso de Vina a XGBoost, que
    # es un clasificador ligand-only y no ha visto el receptor.
    vina_norm = (
        _finite_or_none(min(1.0, abs(docking.best_affinity) / 12.0), "vina")
        if docking.best_affinity is not None
        else None
    )
    xgb_val = _finite_or_none(xgb_prob, "xgb")
    clgnn_val = _finite_or_none(clgnn_prob, "clgnn")
    quantum_val = _finite_or_none(quantum_score, "quantum")
    gnn_score_legacy = _finite_or_none(gnn_score, "gnn")  # RTMScore deprecated
    ums_finite = _finite_or_none(ums_score, "ums")

    components = {
        "vina": vina_norm,
        "xgb": xgb_val,
        "clgnn": clgnn_val,
        "gnn": gnn_score_legacy,
    }
    degraded_missing = [k for k, v in components.items() if v is None and resolved.get(k, 0.0) > 0.0]
    effective_weights = {"vina": 0.0, "xgb": 0.0, "gnn": 0.0, "clgnn": 0.0}
    available = {k: v for k, v in components.items() if v is not None}

    if not available or sum(resolved.get(k, 0.0) for k in available) <= 0:
        # REGRESIÓN PURA: sin componentes validos → sin stacking fabricado.
        # El ranking queda 100% afinidad normalizada (stacking_factor = 1.0).
        stacking_raw = 0.5
        stacking_degraded = True
        log.warning(
            "stacking_regression_pure_affinity",
            target_family=target_family,
            missing=degraded_missing,
        )
    else:
        avail_weights = {k: resolved.get(k, 0.0) for k in available}
        sum_avail_w = sum(avail_weights.values())
        w_vina_used = avail_weights.get("vina", 0.0) / sum_avail_w
        w_xgb_used = avail_weights.get("xgb", 0.0) / sum_avail_w
        w_gnn_used = avail_weights.get("gnn", 0.0) / sum_avail_w
        w_clgnn_used = avail_weights.get("clgnn", 0.0) / sum_avail_w

        if degraded_missing:
            stacking_degraded = True
            log.warning(
                "stacking_degraded_renormalized",
                target_family=target_family,
                missing=degraded_missing,
                weights_used={
                    "vina": round(w_vina_used, 3),
                    "xgb": round(w_xgb_used, 3),
                    "gnn": round(w_gnn_used, 3),
                    "clgnn": round(w_clgnn_used, 3),
                },
            )
        else:
            stacking_degraded = False
            w_vina_used, w_xgb_used, w_gnn_used, w_clgnn_used = (
                w_vina, w_xgb, w_gnn, w_clgnn,
            )
        effective_weights = {"vina": w_vina_used, "xgb": w_xgb_used, "gnn": w_gnn_used, "clgnn": w_clgnn_used}

        stacking_raw = (
            available["vina"] * w_vina_used
            if "vina" in available else 0.0
        ) + (
            available["xgb"] * w_xgb_used
            if "xgb" in available else 0.0
        ) + (
            available["clgnn"] * w_clgnn_used
            if "clgnn" in available else 0.0
        ) + (
            available["gnn"] * w_gnn_used
            if "gnn" in available else 0.0
        )

        # ═══════════════════════════════════════════════════════════════
        # El índice cuántico ya NO mueve el ranking
        # ═══════════════════════════════════════════════════════════════
        #
        # Auditoría del 2026-09-04. Aquí decía:
        #
        #     if quantum_val is not None:
        #         stacking_confidence = abs(stacking_raw - 0.5) * 2
        #         quantum_weight = 0.05 * (1.0 - stacking_confidence)
        #         stacking_raw += quantum_sign * quantum_val * quantum_weight
        #
        # `quantum_val` viene de `compute_quantum_score`, que NO es un
        # observable cuántico: es una combinación lineal de cuatro descriptores
        # normalizados con pesos 0.25/0.35/0.15/0.25 y cuatro divisores, todos
        # elegidos a mano y sin un ajuste documentado en este repositorio. El
        # signo por familia (`quantum_sign`, +1 o −1) tampoco sale de una
        # medición: está escrito en la tabla de pesos.
        #
        # Es decir: un índice heurístico sin validación externa, con un signo
        # sin justificar, desplazando el score que después se sella, se
        # certifica y se imprime. El desplazamiento es pequeño —hasta 0.05
        # cuando el stacking está indeciso— y es precisamente cuando el
        # stacking está indeciso cuando más pesa relativamente.
        #
        # Los descriptores de debajo (gap HOMO-LUMO, cargas de xTB, constantes
        # de MMFF94) son magnitudes reales y ortogonales al resto, y se siguen
        # calculando, guardando y mostrando: `quantum_score` sigue viajando en
        # el resultado. Lo que ya no hace es decidir. Vuelve al ranking cuando
        # exista una validación que diga cuánto vale y en qué dirección.
        if quantum_val is not None:
            log.debug(
                "quantum_score_informativo",
                valor=quantum_val,
                nota="índice heurístico: se guarda y se muestra, no entra al stacking",
            )

        # ═══════════════════════════════════════════════════════════════
        # EL SCORE DE METAL YA NO SE CALCULA AQUÍ
        # ═══════════════════════════════════════════════════════════════
        #
        # Aquí se sumaba UMS al stacking con un peso de hasta 0.06 que además
        # ENCOGÍA según la confianza del propio stack:
        #
        #     ums_weight = 0.06 * (1.0 - stacking_confidence)
        #     stacking_raw += ums_finite * ums_weight
        #
        # `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §1 lo retira por no
        # reproducir ningún experimento. Los pesos validados son 0.40 (CA2),
        # 0.25 (MMP9) y 0.40 (ACE), CONSTANTES, dentro de una fórmula por
        # perfil — no un empujón aditivo sobre un stack genérico.
        #
        # Y no bastaba con cambiar 0.06 por 0.40: CA2 usa GNN-D y no CL-GNN,
        # MMP9 no usa ni Vina ni GNN, y ACE no usa GNN. Son tres fórmulas
        # distintas, no un peso distinto.
        #
        # El score compuesto de metal lo calcula ahora
        # `services/pipeline/protocols/m5/zinc.py`, por perfil exacto, y se
        # ABSTIENE fuera de las tres dianas validadas en vez de heredar pesos.
        # Este motor es el de M4: `ums_score` viaja como señal para el dossier
        # y no toca el ranking.
        if ums_finite is not None:
            log.debug(
                "ums_informativo",
                valor=ums_finite,
                familia=target_family,
                nota=("el score de metal lo calcula el perfil M5-Zn; "
                      "aquí sólo se registra la señal"),
            )

    stacking_factor = 0.5 + stacking_raw  # escala [0.5, 1.5]; regresión pura → 1.0

    adjusted_affinity_score = clamp_score(affinity_score * stacking_factor)

    # MM-GBSA factor (ortogonal, se aplica sobre el score ajustado).
    # [A3] NaN/Inf de MM-GBSA → factor neutro 1.0, no se fabrica un delta G.
    mmgbsa_finite = _finite_or_none(mmgbsa_score, "mmgbsa")
    if mmgbsa_finite is not None:
        mmgbsa_norm = min(1.0, max(-1.0, mmgbsa_finite / 20.0))  # [-1, 1]
        mmgbsa_factor = 1.0 + (mmgbsa_norm * 0.10)  # [0.9, 1.1]
    else:
        mmgbsa_factor = 1.0

    adjusted_affinity_score = clamp_score(adjusted_affinity_score * mmgbsa_factor)

    # El ranking se basa PURAMENTE en la afinidad ajustada
    # specificity_multiplier solo aplica si hay hotspots validados
    specificity_score = 100.0
    specificity_multiplier = 1.0

    if target_hotspots:
        total_importance = sum(h.get("importance", 1.0) for h in target_hotspots)
        hits_importance = 0.0
        hit_names = set(docking.hotspots_hit or [])
        for h in target_hotspots:
            if h["name"].upper() in hit_names:
                hits_importance += h.get("importance", 1.0)
        if total_importance > 0:
            specificity_score = (hits_importance / total_importance) * 100
        specificity_floor = max(0.1, min(0.9, specificity_floor))
        specificity_multiplier = specificity_floor + ((1.0 - specificity_floor) * specificity_score / 100.0)

    total_score = clamp_score(adjusted_affinity_score * specificity_multiplier)

    # ═════════════════════════════════════════════════════════════════════
    # GRUPO B — Métricas de PERFIL FARMACOCINÉTICO (flags informativos)
    #          Ahora tambien generan un viability_adjusted_score para el usuario
    # ═════════════════════════════════════════════════════════════════════

    adme_score = calculate_adme_score(properties)
    druglikeness_score = calculate_druglikeness_score(properties)

    # SA Score como flag informativo (severidad textual)
    sa_factor, sa_severity = _calculate_sa_factor(properties.sa_score)

    # Blood Viability como flag informativo
    blood_factor = 1.0
    if properties.blood_viability_score is not None:
        blood_factor = properties.blood_viability_score / 100.0

    # ── Viability-adjusted score (para el usuario, NO para ranking cientifico) ──
    # Combina afinidad + drug-likeness + ADME + viabilidad sanguinea
    # El ranking cientifico (total_score) sigue siendo afinidad pura
    viability_components = []
    if druglikeness_score > 0:
        viability_components.append(druglikeness_score)
    if adme_score > 0:
        viability_components.append(adme_score)

    if viability_components:
        avg_viability = sum(viability_components) / len(viability_components)
        viability_multiplier = 0.5 + (blood_factor * 0.3) + (avg_viability / 200.0 * 0.2)
        viability_adjusted_score = clamp_score(total_score * viability_multiplier * sa_factor)
    else:
        viability_adjusted_score = clamp_score(total_score * blood_factor * sa_factor)

    # ═════════════════════════════════════════════════════════════════════
    # FEEDBACK — strongest/weakest CONSOLIDADO (no penaliza total_score)
    # ═════════════════════════════════════════════════════════════════════

    strongest, weakest = _pick_dimensions(
        affinity_score,
        adme_score,
        druglikeness_score,
    )

    # LE y LLE bruta para el frontend
    le_raw = round(docking.best_affinity / properties.heavy_atom_count, 3) if properties.heavy_atom_count else None

    best_affinity_val = docking.best_affinity
    if best_affinity_val > 0.0:
        log.warning(f"best_affinity is positive ({best_affinity_val}), which violates the Vina negative convention. Clipping to 0.0.")
        best_affinity_val = 0.0
    lle_raw = round((-best_affinity_val / 1.36) - properties.log_p, 3) if properties.log_p is not None else None

    return ScoreBreakdown(
        # Ranking (Afinidad pura)
        total_score=total_score,
        viability_adjusted_score=viability_adjusted_score,
        affinity_score=affinity_score,
        gnn_score=round(gnn_score_legacy, 4) if gnn_score_legacy is not None else None,
        clgnn_score=round(clgnn_val, 4) if clgnn_val is not None else None,
        xgb_score=round(xgb_val, 4) if xgb_val is not None else None,
        mmgbsa_score=round(mmgbsa_finite, 4) if mmgbsa_finite is not None else None,
        quantum_score=round(quantum_val, 4) if quantum_val is not None else None,
        ums_score=round(ums_finite, 4) if ums_finite is not None else None,
        gnn_factor=round(stacking_factor, 4),  # legacy: ahora es stacking_factor
        stacking_vina_weight=w_vina,
        stacking_xgb_weight=w_xgb,
        stacking_gnn_weight=w_gnn,
        stacking_clgnn_weight=w_clgnn,
        stacking_effective_weights={k: round(v, 8) for k, v in effective_weights.items()},
        stacking_degraded=stacking_degraded,
        degraded_missing=degraded_missing,
        target_family=target_family,
        specificity_score=specificity_score,
        specificity_multiplier=specificity_multiplier,
        affinity_threshold=affinity_threshold,
        affinity_multiplier=1.0,
        ligand_efficiency=le_raw,
        lipophilic_efficiency=lle_raw,
        # Flags farmacocinéticos (no afectan ranking)
        adme_score=adme_score,
        druglikeness_score=druglikeness_score,
        sa_factor=sa_factor,
        blood_factor=blood_factor,
        # Pesos
        weight_affinity=100.0,
        weight_adme=0.0,
        weight_druglikeness=0.0,
        # Feedback textual
        strongest_dimension=strongest,
        weakest_dimension=weakest,
        improvement_hint=_build_improvement_hint(properties, weakest),
    )


async def score_and_persist(
    repository: Repository,
    molecule_id: uuid.UUID,
    docking: DockingResult,
    properties: PhysicochemicalProperties,
) -> ScoreBreakdown:
    """
    Calcula el score y persiste los resultados normalizados.
    """
    try:
        # Obtenemos el resultado previo y la molécula para saber el target
        result = await repository.get_evaluation_result(molecule_id)
        is_control = bool(result.is_control) if result else False

        mol = await repository.get_molecule(molecule_id)
        target = mol.target if mol else None

        breakdown = calculate_score_breakdown(
            docking,
            properties,
            is_control=is_control,
            target_hotspots=target.hotspots if target else None,
            affinity_threshold=target.affinity_threshold if target and target.affinity_threshold is not None else -7.5
        )
        await repository.upsert_evaluation_result(
            molecule_id=molecule_id,
            properties=properties,
            docking=docking,
            scores=breakdown.model_dump(),
            is_control=is_control,
        )
        return breakdown
    except Exception as e:
        raise ScoringError(
            molecule_id=str(molecule_id),
            detail=str(e),
        ) from e


def breakdown_to_result_dict(breakdown: ScoreBreakdown) -> dict[str, Any]:
    # Ensure all numerics are native Python types
    return {
        "affinity_score": float(breakdown.affinity_score),
        "adme_score": float(breakdown.adme_score),
        "druglikeness_score": float(breakdown.druglikeness_score),
        "total_score": float(breakdown.total_score),
        "ligand_efficiency": float(breakdown.ligand_efficiency) if breakdown.ligand_efficiency else None,
        "lipophilic_efficiency": float(breakdown.lipophilic_efficiency) if breakdown.lipophilic_efficiency is not None else None,
        "strongest_dimension": str(breakdown.strongest_dimension),
        "weakest_dimension": str(breakdown.weakest_dimension),
        "improvement_hint": str(breakdown.improvement_hint),
    }

