"""Generate and verify the deterministic rescoring model manifest v4.

The registry below is intentionally declarative: every runtime model must be
named here before it can appear in a release.  ``--check`` never writes and
fails if an artifact hash, provenance field, manifest version or registered
model set is inconsistent with the files on disk.

Usage from ``rescoring``::

    python scripts/generate_model_manifest.py
    python scripts/generate_model_manifest.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
_RESCORING_DIR = _SCRIPTS_DIR.parent
_REPO_ROOT = _RESCORING_DIR.parent
if str(_RESCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_RESCORING_DIR))

from model_manifest import MANIFEST_VERSION, canonical_manifest_bytes, load_manifest, sha256_file


ARTIFACTS_DIR = _RESCORING_DIR / "artifacts"
MANIFEST_PATH = ARTIFACTS_DIR / "model-manifest.json"
TRAINING_REPORT_PATH = ARTIFACTS_DIR / "training_report.json"
SPLIT_CONFIG_PATH = ARTIFACTS_DIR / "split_config.json"
DATASET_INDEX_PATH = _REPO_ROOT / "data" / "pdbbind" / "INDEX_refined_data.2020"
POSE_DATASET_MANIFEST_PATH = _REPO_ROOT / "data" / "pose_selector_dataset" / "manifest.json"

# Huellas de entradas de entrenamiento que no se redistribuyen. Un clon limpio
# debe poder verificar el manifiesto sin necesitar el dataset PDBbind privado.
# Si esas entradas existen en la máquina de desarrollo, sus bytes se comprueban
# contra estas huellas antes de usarlas.
DATASET_INDEX_DECLARED_SHA256 = "ca7702c5e6fd4e814281a3e65ddbdcf17bd62df78e62daef6daaa2106f70c4b6"
POSE_DATASET_DECLARED = {
    "manifest_sha256": "d4b1a98051e94193c324017fd544f71808cba9be01b92c236c795eb2875f2813",
    "train_complexes": 116,
    "train_poses": 2739,
    "split_method": "scaffold_group_holdout_seed42",
    "test_complexes": 47,
    "test_pids_sha256": "4cbff399c87240af35429638ba62eb60f16862e05a27871b6bce6c6d6a8bccbd",
}


# This is the complete release registry.  Adding a deployable model requires
# a corresponding builder and an explicit scientific status; omission is a
# hard error rather than a silently incomplete manifest.
MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "model_a_universal": {
        "kind": "training_report",
        "file": "model_a_universal.json",
        "report_key": "model_a_universal",
    },
    # ── Clasificador de binder (XGBoost) ─────────────────────────────────
    #
    # Anadido el 2026-09-04. Es el modelo que produce `xgb_score`, y `xgb` es
    # el componente con MAS peso del stacking en el artefacto vigente: 0.60 en
    # los pesos por defecto —los que reciben todas las familias salvo GPCR— y
    # 0.40 en GPCR. Movia el ranking de cada evaluacion y no estaba en el
    # manifiesto, asi que sus bytes no se ligaban a ninguna procedencia y la
    # build no comprobaba que fueran los mismos.
    #
    # Las cifras se transcriben de `classifier_binder.metadata.json`. Se
    # declaran las DOS: la de validacion (n=108, balanceada 54/54) y la de
    # holdout (n=328, 151/177). Citar solo la segunda haria parecer el modelo
    # mejor de lo que la validacion sostiene; citar solo la primera esconderia
    # que existe un holdout scaffold-disjoint.
    "classifier_binder": {
        "kind": "classifier_binder",
        "file": "classifier_binder.json",
        "metadata_file": "classifier_binder.metadata.json",
        "scientific_status": "HOLDOUT_SCAFFOLD_DISJOINT__COHORTE_PEQUENA",
        "note": (
            "Produce `xgb_score`. Es el componente de mayor peso del stacking "
            "(0.60 por defecto, 0.40 en GPCR). El umbral de binder es pKi>=7.0: "
            "la etiqueta es una DICOTOMIZACION de una afinidad continua, no una "
            "medida experimental de union. Cohorte pequena -108 de validacion y "
            "328 de holdout- asi que los intervalos son anchos y el AUC no debe "
            "citarse sin ellos."
        ),
    },
    "pose_selector_v06": {
        "kind": "pose_selector",
        "file": "pose_selector_v06.xgb",
        "metadata_file": "pose_selector_v06_meta.json",
        "scientific_status": "HONEST_FROZEN_HOLDOUT_BELOW_PREREGISTERED_0.70_TARGET",
        "metrics": {
            "vina_top1_crystal_like": 0.532,
            "selector_top1_crystal_like": 0.660,
            "selector_median_rmsd_angstrom": 1.428,
            "abstention_rate": 0.43,
            "accepted_top1_crystal_like": 0.852,
        },
        "note": (
            "Top-1 0.660 supera Vina, pero no alcanza el objetivo preregistrado "
            "final >=0.70. El 0.852 es condicional a 43% de abstencion y no "
            "debe citarse como rendimiento global."
        ),
    },
    # ── CL-GNN ───────────────────────────────────────────────────────────
    #
    # Anadido el 2026-09-04. El checkpoint existia desde julio y su procedencia
    # estaba entera en `docs/CL_GNN_MULTITARGET_RESULTS.md`; lo que faltaba era
    # esta entrada, que es la que liga los BYTES a esa procedencia y la que la
    # build comprueba.
    #
    # Las cifras se transcriben de ese documento. Se declaran POR FAMILIA y no
    # como un AUC global a proposito: la transferencia depende de la familia y
    # un promedio ocultaria exactamente lo que hay que ver.
    "gnn_v2_cl": {
        "kind": "clgnn",
        "file": "gnn_v2_cl_best.pt",
        "metadata_file": "contrastive_v31_pretrained.pt",
        "feature_schema": (
            "Grafo heterogeneo: ligando (38-dim por atomo) + proteina (Ca de "
            "residuos de bolsillo) + cross-edges ligando-Ca a <8 A. "
            "ContrastiveGNN (GAT+GIN+Set2Set+Cross-Attention) -> "
            "GNNv2Classifier, 677657 parametros entrenables, hidden_dim=128."
        ),
        "dataset": {
            "complexes": 708,
            "source": "PDBbind refined, redockeados con AutoDock Vina (exhaustiveness=8)",
            "train": 566,
            "val": 142,
            "note": "Procedencia declarada del entrenamiento (PDBbind refined, redockeado). Los pesos se distribuyen gratuitamente bajo LICENSE-MODELS por decision del titular (2026-09-23); el dataset de entrenamiento no se redistribuye.",
        },
        "split": {"method": "train/val 566/142 sobre PDBbind refined redockeado", "evaluacion": "No existe evaluacion externa sellada para el SHA-256 actual."},
        "training_date": "2026-07-26",
        "scientific_status": "CHECKPOINT_INCLUDED__EXTERNAL_VALIDATION_FOR_EXACT_SHA256_PENDING",
        "metrics": {"checkpoint_self_reported_val_auc": 0.6109756097560977, "checkpoint_epoch": 22, "external_metrics_for_exact_sha256": None},
        "historical_metrics_not_attributable_to_current_sha256": {
            "val_auc_pdbbind_docked": 0.6433,
            "gpcr_5HT1A_7E2Y": 0.8496,
            "protease_HIV_1HSG": 0.9491,
            "source": "docs/CL_GNN_MULTITARGET_RESULTS.md y docs/STOCHASTICITY_REPORT.md",
        },
        "note": (
            "El checkpoint actual carga y puede producir una senal experimental, "
            "pero sus bytes no son los del modelo al que pertenecen los AUC externos "
            "historicos. Hasta repetir y sellar la evaluacion externa para este SHA-256, "
            "su peso de stacking de release es 0.0 y no decide ranking ni recomendacion."
        ),
    },
}


class ManifestCheckError(RuntimeError):
    """The committed manifest does not represent the declared release inputs."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} ausente: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} debe ser un objeto JSON: {path}")
    return payload


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"{label} ausente: {path}")
    return path


def _relative_to_repo(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _parse_feature_schema(definition: str) -> str:
    rhs = definition.split("=", 1)[-1].strip()
    n_features, _, breakdown = rhs.partition(" ")
    return f"{n_features} features {breakdown}"


def _build_training_report_entry(spec: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    filename = str(spec["file"])
    model_path = _require_file(ARTIFACTS_DIR / filename, "Artefacto de modelo")
    model_key = str(spec["report_key"])
    model_info = report.get("models", {}).get(model_key)
    if not isinstance(model_info, dict):
        raise KeyError(f"Modelo '{model_key}' ausente en training_report.json['models']")

    data_context = report.get("data_context", {})
    split_context = report.get("split_context", {})
    holdout = report.get("holdout", {})
    training_context = report.get("training_context", {})
    if not all(isinstance(value, dict) for value in (data_context, split_context, holdout)):
        raise ValueError("training_report.json no contiene data/split/holdout válidos")
    if not isinstance(training_context, dict):
        raise ValueError("training_report.json no contiene training_context válido")

    split_path = _require_file(SPLIT_CONFIG_PATH, "Configuración de split")
    index_path = DATASET_INDEX_PATH
    if index_path.is_file():
        actual_index_hash = sha256_file(index_path)
        if actual_index_hash != DATASET_INDEX_DECLARED_SHA256:
            raise ManifestCheckError(
                "El índice PDBbind local no coincide con la huella declarada: "
                f"{actual_index_hash}"
            )
    comparison = report.get("comparison_with_v2", {})
    old_inflated = comparison.get("v2_inflated_holdout_spearman", 0.8732)

    return {
        "file": filename,
        "sha256": sha256_file(model_path),
        "feature_schema": _parse_feature_schema(
            str(report["training_context"]["feature_set_definition"])
        ),
        "prolif_included": bool(model_info.get("has_prolif", False)),
        "dataset": {
            "source": f"PDBbind {training_context['pdbbind_version']}",
            "complexes": int(data_context["total_cached_complexes"]),
            "index_file": _relative_to_repo(index_path),
            "sha256": DATASET_INDEX_DECLARED_SHA256,
            "note": (
                "Huella del índice top-level PDBbind v2020 refined. El índice no se "
                "redistribuye; si existe localmente, el generador verifica sus bytes. "
                "El feature cache no tiene un hash único."
            ),
        },
        "split": {
            "file": split_path.name,
            "sha256": sha256_file(split_path),
            "method": (
                f"{split_context['method']} — frozen holdout "
                f"{int(split_context['frozen_holdout_ids'])} complexes"
            ),
        },
        "training_date": str(report["generated_at"])[:10],
        "scientific_status": "HONEST_HOLDOUT",
        "metrics": {
            "spearman_cv": float(model_info["spearman"]),
            "spearman_holdout": float(holdout["spearman"]),
            "spearman_holdout_ci95": [float(value) for value in holdout["spearman_ci95"]],
            "pearson_holdout": float(holdout["pearson"]),
        },
        "note": f"Historical {old_inflated} INVALIDATED (leakage). Do not cite.",
    }


def _build_pose_selector_entry(spec: dict[str, Any]) -> dict[str, Any]:
    filename = str(spec["file"])
    metadata_filename = str(spec["metadata_file"])
    model_path = _require_file(ARTIFACTS_DIR / filename, "Artefacto pose-selector")
    metadata_path = _require_file(ARTIFACTS_DIR / metadata_filename, "Metadata pose-selector")
    metadata = _load_json(metadata_path, "Metadata pose-selector")

    model_hash = sha256_file(model_path)
    metadata_hash = sha256_file(metadata_path)
    if str(metadata.get("sha256_modelo", "")).lower() != model_hash:
        raise ManifestCheckError(
            "pose_selector_v06_meta.json no coincide con el SHA-256 del artefacto"
        )

    if POSE_DATASET_MANIFEST_PATH.is_file():
        actual_manifest_hash = sha256_file(POSE_DATASET_MANIFEST_PATH)
        if actual_manifest_hash != POSE_DATASET_DECLARED["manifest_sha256"]:
            raise ManifestCheckError(
                "El manifest local del pose-selector no coincide con la huella declarada: "
                f"{actual_manifest_hash}"
            )
        dataset = _load_json(POSE_DATASET_MANIFEST_PATH, "Manifest dataset pose-selector")
        train_counts = dataset.get("conteos", {}).get("train", {})
        test_counts = dataset.get("conteos", {}).get("test", {})
        if not isinstance(train_counts, dict) or not isinstance(test_counts, dict):
            raise ValueError("Manifest dataset pose-selector no contiene conteos train/test")
        observed = {
            "train_complexes": int(train_counts["complejos"]),
            "train_poses": int(train_counts["registros"]),
            "split_method": str(dataset["split_method"]),
            "test_complexes": int(test_counts["complejos"]),
            "test_pids_sha256": str(dataset["test_pids_sha256"]),
        }
        expected = {key: POSE_DATASET_DECLARED[key] for key in observed}
        if observed != expected:
            raise ManifestCheckError(
                f"El manifest local del pose-selector contradice la procedencia declarada: {observed}"
            )

    return {
        "file": filename,
        "sha256": model_hash,
        "metadata_file": metadata_filename,
        "metadata_sha256": metadata_hash,
        "feature_schema": (
            f"{int(metadata['n_features_modelo'])} features "
            "(224 raw relativizadas por complejo + 9 percentiles)"
        ),
        "dataset": {
            "manifest_file": _relative_to_repo(POSE_DATASET_MANIFEST_PATH),
            "manifest_sha256": POSE_DATASET_DECLARED["manifest_sha256"],
            "train_complexes": POSE_DATASET_DECLARED["train_complexes"],
            "train_poses": POSE_DATASET_DECLARED["train_poses"],
        },
        "split": {
            "method": POSE_DATASET_DECLARED["split_method"],
            "test_complexes": POSE_DATASET_DECLARED["test_complexes"],
            "test_pids_sha256": POSE_DATASET_DECLARED["test_pids_sha256"],
        },
        "training_date": str(metadata["generated_at"])[:10],
        "scientific_status": str(spec["scientific_status"]),
        "metrics": dict(spec["metrics"]),
        "note": str(spec["note"]),
    }


def _build_clgnn_entry(spec: dict[str, Any]) -> dict[str, Any]:
    """Entrada del CL-GNN: bytes reales + procedencia declarada en el registro.

    El checkpoint contiene la métrica interna que se declara. Los AUC externos
    históricos se conservan explícitamente como no atribuibles a estos bytes.
    El generador calcula los SHA-256 del clasificador y del encoder.
    """
    ruta = ARTIFACTS_DIR / str(spec["file"])
    if not ruta.is_file():
        raise FileNotFoundError(f"Checkpoint del CL-GNN ausente: {ruta}")

    entrada: dict[str, Any] = {
        "file": str(spec["file"]),
        "sha256": sha256_file(ruta),
        "feature_schema": str(spec["feature_schema"]),
        "dataset": dict(spec["dataset"]),
        "split": dict(spec["split"]),
        "training_date": str(spec["training_date"]),
        "scientific_status": str(spec["scientific_status"]),
        "metrics": dict(spec["metrics"]),
        "note": str(spec["note"]),
    }

    historical = spec.get("historical_metrics_not_attributable_to_current_sha256")
    if isinstance(historical, dict):
        entrada["historical_metrics_not_attributable_to_current_sha256"] = dict(historical)

    encoder = spec.get("metadata_file")
    if encoder:
        ruta_encoder = ARTIFACTS_DIR / str(encoder)
        if not ruta_encoder.is_file():
            raise FileNotFoundError(f"Encoder contrastivo ausente: {ruta_encoder}")
        entrada["metadata_file"] = str(encoder)
        entrada["metadata_sha256"] = sha256_file(ruta_encoder)

    return entrada


def _build_classifier_binder_entry(spec: dict[str, Any]) -> dict[str, Any]:
    """El clasificador de binder, con sus DOS cohortes y su umbral.

    Las metricas no se recalculan aqui: se leen de la metadata que dejo el
    entrenamiento y se hashean las dos rutas. Recalcularlas en el generador
    convertiria el manifiesto en una segunda fuente de verdad.
    """
    ruta_modelo = ARTIFACTS_DIR / str(spec["file"])
    ruta_meta = ARTIFACTS_DIR / str(spec["metadata_file"])
    if not ruta_modelo.is_file():
        raise FileNotFoundError(f"Clasificador de binder ausente: {ruta_modelo}")
    if not ruta_meta.is_file():
        raise FileNotFoundError(f"Metadata del clasificador ausente: {ruta_meta}")

    metadata = _load_json(ruta_meta, "Metadata del clasificador de binder")

    return {
        "file": str(spec["file"]),
        "sha256": sha256_file(ruta_modelo),
        "metadata_file": str(spec["metadata_file"]),
        "metadata_sha256": sha256_file(ruta_meta),
        "feature_schema": str(metadata.get("feature_set")),
        "n_features": metadata.get("n_features"),
        "split": {
            "method": str(metadata.get("split")),
            "train_samples": metadata.get("train_samples"),
            "val_samples": metadata.get("val_samples"),
        },
        "training_date": str(metadata.get("train_timestamp")),
        "binder_threshold_pki": metadata.get("binder_threshold"),
        "best_iteration": metadata.get("best_iteration"),
        "scientific_status": str(spec["scientific_status"]),
        "metrics": {
            "validacion": metadata.get("metrics"),
            "holdout": metadata.get("holdout_metrics"),
        },
        "note": str(spec["note"]),
    }


def build_manifest() -> dict[str, Any]:
    """Build the complete deterministic v4 document from declared sources."""
    report = _load_json(TRAINING_REPORT_PATH, "Informe de entrenamiento")
    models: dict[str, Any] = {}
    for model_key, spec in MODEL_REGISTRY.items():
        kind = spec["kind"]
        if kind == "training_report":
            models[model_key] = _build_training_report_entry(spec, report)
        elif kind == "pose_selector":
            models[model_key] = _build_pose_selector_entry(spec)
        elif kind == "clgnn":
            models[model_key] = _build_clgnn_entry(spec)
        elif kind == "classifier_binder":
            models[model_key] = _build_classifier_binder_entry(spec)
        else:
            raise ValueError(f"Tipo de modelo no soportado en registro: {kind!r}")
    return {"manifest_version": MANIFEST_VERSION, "models": models}


def _assert_safe_transition(existing: dict[str, Any], desired: dict[str, Any]) -> None:
    existing_version = existing.get("manifest_version")
    if not isinstance(existing_version, int):
        raise ManifestCheckError("El manifiesto existente no tiene manifest_version entero")
    if existing_version > MANIFEST_VERSION:
        raise ManifestCheckError(
            f"Downgrade prohibido: existente v{existing_version}, generador v{MANIFEST_VERSION}"
        )

    existing_models = existing.get("models")
    if not isinstance(existing_models, dict):
        raise ManifestCheckError("El manifiesto existente no contiene models válido")
    missing = sorted(set(existing_models) - set(desired["models"]))
    if missing:
        raise ManifestCheckError(
            "Regeneración perdería modelos existentes no registrados: " + ", ".join(missing)
        )


def check_manifest(manifest_path: Path = MANIFEST_PATH) -> None:
    """Fail without writing when the committed manifest differs from sources."""
    desired = build_manifest()
    if not manifest_path.is_file():
        raise ManifestCheckError(f"Manifiesto ausente: {manifest_path}")
    existing = load_manifest(manifest_path)
    _assert_safe_transition(existing, desired)
    if manifest_path.read_bytes() != canonical_manifest_bytes(desired):
        raise ManifestCheckError(
            "model-manifest.json no coincide con el registro y sus artefactos; "
            "ejecute generate_model_manifest.py para regenerarlo."
        )


def write_manifest(manifest_path: Path = MANIFEST_PATH) -> bool:
    """Write only the deterministic document, refusing unsafe release changes."""
    desired = build_manifest()
    if manifest_path.is_file():
        _assert_safe_transition(load_manifest(manifest_path), desired)
    content = canonical_manifest_bytes(desired)
    if manifest_path.is_file() and manifest_path.read_bytes() == content:
        return False
    manifest_path.write_bytes(content)
    return True


def _pesos_que_no_se_distribuyen() -> list[str]:
    """Pesos declarados por el registro que el repositorio Git no publica."""
    sys.path.insert(0, str(_RESCORING_DIR))
    from pesos_ausentes import pesos_ausentes

    nombres: list[str] = []
    for entrada in MODEL_REGISTRY.values():
        for clave in ("file", "metadata_file"):
            valor = entrada.get(clave)
            if isinstance(valor, str):
                nombres.append(valor)
    return pesos_ausentes(ARTIFACTS_DIR, nombres)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validar sin escribir")
    parser.add_argument("--output", type=Path, default=MANIFEST_PATH, help="ruta del manifiesto")
    parser.add_argument(
        "--permitir-pesos-ausentes",
        action="store_true",
        help=(
            "no fallar si faltan los pesos entrenados que el repositorio no "
            "distribuye. Se pasa explicitamente en CI sobre un clon limpio; "
            "el gate informa entonces que NO ha verificado los hashes."
        ),
    )
    args = parser.parse_args()

    try:
        if args.check:
            faltan = _pesos_que_no_se_distribuyen()
            if faltan and args.permitir_pesos_ausentes:
                # No decimos "verificado". Decimos que no se pudo, y por que.
                print(
                    f"Manifiesto v{MANIFEST_VERSION} NO verificado: faltan "
                    f"{len(faltan)} peso(s) que el repositorio Git no distribuye "
                    f"({', '.join(faltan)}). Los hashes de esos artefactos "
                    "quedan sin comprobar."
                )
                return 0
            check_manifest(args.output)
            print(f"Manifiesto v{MANIFEST_VERSION} verificado: {args.output}")
        else:
            changed = write_manifest(args.output)
            action = "escrito" if changed else "sin cambios"
            print(f"Manifiesto v{MANIFEST_VERSION} {action}: {args.output}")
    except (OSError, ValueError, KeyError, ManifestCheckError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
