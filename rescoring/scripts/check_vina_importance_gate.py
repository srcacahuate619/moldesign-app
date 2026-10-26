"""Quality gate: Vina feature importance vs training/inference regime.

F-20 (auditoría 2026-08-09): las 4 features Vina (grupo B) son CERO durante el
entrenamiento y reales en inferencia. Mientras el modelo les asigne importancia
~0 esto es un distribution shift aceptado y documentado; pero si una versión
futura del artefacto aprende pesos no nulos, ese shift se vuelve no controlado.

Este gate FALLA (exit 1) si la importancia relativa del grupo Vina en el
artefacto distribuido supera el umbral, bloqueando así un release que dependa
de una feature cuyo régimen de entrenamiento e inferencia difiere.

Uso:
    python rescoring/scripts/check_vina_importance_gate.py
    python rescoring/scripts/check_vina_importance_gate.py --threshold 0.15

Salida: reporte JSON con grupo Vina, share y veredicto. Exit 0 = PASS,
1 = FAIL, 2 = datos insuficientes, 3 = NO_VERIFICABLE.

SCI-A-056 (auditoría científica, 2026-10-20): la cuota sólo describe el modelo
distribuido si el SHAP dice de qué modelo es. `shap_analysis.json` no lleva el
SHA-256 de `model_a_universal.json` y se calculó sobre 692/173 muestras, cuando el
modelo distribuido se entrenó con 429/108: daba PASS sobre otro modelo. Sin ese
vínculo el veredicto es NO_VERIFICABLE, no PASS. `--permitir-no-verificable` sale
con 0 diciéndolo, para la CI mientras no se recalcule el SHAP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = REPO_ROOT / "rescoring" / "artifacts"
SHAP_PATH = ARTIFACTS / "shap_analysis.json"
TRAINING_REPORT_PATH = ARTIFACTS / "training_report.json"
MODEL_PATH = ARTIFACTS / "model_a_universal.json"

VINA_GROUP_KEY = "Vina (B)"
DEFAULT_THRESHOLD = 0.10  # 10% de la importancia global total


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"artefacto requerido no encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_vina_share(shap: dict) -> dict:
    group = shap.get("group_importance") or {}
    vina_importance = float(group.get(VINA_GROUP_KEY, 0.0))
    total = sum(float(v) for v in group.values())
    share = vina_importance / total if total > 0 else 0.0
    return {
        "group_importance": group,
        "vina_importance": vina_importance,
        "total_importance": total,
        "vina_share": share,
    }


def check_regime(training_report: dict) -> dict:
    """Confirma que el artefacto declara Vina=0 en entrenamiento."""
    context = training_report.get("training_context") or {}
    feature_set = str(context.get("feature_set_definition") or "")
    vina_in_features = "B=4" in feature_set
    # El training report actual no guarda un flag explícito de "Vina cero en
    # training"; la definición del feature set (B=4) más la nota del README de
    # artefactos lo documentan. Este check es de estructura, no de causalidad.
    return {
        "vina_declared_in_features": vina_in_features,
        "feature_set_definition": feature_set,
    }


def check_binding(shap: dict, model_sha256: str, training_report: dict) -> dict:
    """Si el SHAP declara el modelo que explica, y si es el distribuido (SCI-A-056)."""
    universal = (training_report.get("models") or {}).get("model_a_universal") or {}
    declarado = shap.get("model_sha256")
    return {
        "model_sha256": model_sha256,
        "shap_model_sha256": declarado,
        "bound": declarado == model_sha256,
        "samples": {
            "shap_train_val": [shap.get("n_samples_train"), shap.get("n_samples_val")],
            "model_train_val": [universal.get("n_train"), universal.get("n_val")],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"share máximo permitido para el grupo Vina (default {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--permitir-no-verificable",
        action="store_true",
        help="sale con 0 si el SHAP no está ligado al modelo, pero lo dice (NO_VERIFICABLE)",
    )
    args = parser.parse_args()

    report = {
        "gate": "vina_importance",
        "artifact": str(SHAP_PATH),
        "threshold": args.threshold,
    }

    try:
        shap = load_json(SHAP_PATH)
        training_report = load_json(TRAINING_REPORT_PATH)
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"artefacto requerido no encontrado: {MODEL_PATH}")
        model_sha256 = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    except FileNotFoundError as e:
        report["verdict"] = "INSUFFICIENT_DATA"
        report["error"] = str(e)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    report.update(compute_vina_share(shap))
    report["regime"] = check_regime(training_report)
    report["binding"] = check_binding(shap, model_sha256, training_report)

    share = report["vina_share"]
    if not report["binding"]["bound"]:
        muestras = report["binding"]["samples"]
        report["verdict"] = "NO_VERIFICABLE"
        report["reason"] = (
            f"{SHAP_PATH.name} no declara el SHA-256 del modelo distribuido "
            f"({model_sha256[:12]}…); se calculó sobre {muestras['shap_train_val']} muestras "
            f"(entrenamiento/validación) y el modelo, con {muestras['model_train_val']}. "
            f"Su cuota Vina ({share:.1%}) no describe el modelo que se distribuye."
        )
        exit_code = 0 if args.permitir_no_verificable else 3
    elif share >= args.threshold:
        report["verdict"] = "FAIL"
        report["reason"] = (
            f"el grupo Vina concentra {share:.1%} de la importancia global "
            f"(umbral {args.threshold:.0%}); el modelo dependería de una feature "
            f"con régimen train/inference distinto. Bloquear release."
        )
        exit_code = 1
    else:
        report["verdict"] = "PASS"
        report["reason"] = (
            f"grupo Vina en {share:.1%} (< {args.threshold:.0%}): distribution "
            f"shift aceptado y documentado; el modelo no depende de features Vina."
        )
        exit_code = 0

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
