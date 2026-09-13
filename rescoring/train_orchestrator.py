"""
rescoring/train_orchestrator.py

Orquestador de entrenamiento end-to-end para ML rescoring.

Ejecuta el pipeline completo en secuencia:
  1. Cargar PDBbind (refined + other sets)
  1.5. Curacion de datos (filtrar ruido, duplicados, outliers)
  2. VIP audit (5 checks de calidad individual)
  3. Clasificar por familia estructural
  4. Congelar test set
  5. Scaffold-split CV
  6. Feature extraction masiva
  7. Entrenar Model A + Model NULL
  8. Ablation testing
  9. SHAP values
  10. Delta distribution
  11. Applicability Domain
  12. Performance por familia
  13. Evaluar criterios de aceptación
  14. Guardar todos los artefactos

Uso:
    python train_orchestrator.py --data-dir /data/pdbbind --output-dir /app/artifacts

Todos los resultados van a artifacts/:
  - model_a.joblib
  - model_null.joblib
  - applicability_domain.json
  - delta_distribution.json
  - training_report.json
  - pdbbind_audit_report.json
  - split_config.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from logger import get_logger

log = get_logger(__name__)


def run_training_pipeline(
    data_dir: str | Path = "/data/pdbbind",
    output_dir: str | Path = "/app/artifacts",
    n_folds: int = 5,
    test_size: int = 500,
    seed: int = 42,
    skip_structure_checks: bool = False,
    include_other_set: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Ejecutar pipeline de entrenamiento completo.

    Args:
        data_dir: directorio con datos de PDBbind
        output_dir: directorio para artefactos
        n_folds: folds de cross-validation
        test_size: tamaño del frozen test set
        seed: semilla para reproducibilidad
        skip_structure_checks: True para omitir checks que requieren PDB files
        include_other_set: True para incluir el "other/general" set de PDBbind
                           ademas del refined set (~14,000 complejos adicionales)
        dry_run: True para solo auditar sin entrenar

    Returns:
        dict con resumen de resultados
    """
    start_time = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "status": "started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "data_dir": str(data_dir),
            "output_dir": str(output_dir),
            "n_folds": n_folds,
            "test_size": test_size,
            "seed": seed,
            "skip_structure_checks": skip_structure_checks,
            "include_other_set": include_other_set,
        },
    }

    # ─── Paso 1: Cargar PDBbind ───
    log.info("step_1_loading_pdbbind", include_other=include_other_set)
    from pdbbind_parser import PDBBindParser

    parser = PDBBindParser(data_dir)
    n_loaded = parser.load(include_other=include_other_set)

    if n_loaded == 0:
        report["status"] = "failed"
        report["error"] = "No se pudieron cargar datos de PDBbind"
        _save_report(report, output_dir / "training_report.json")
        return report

    report["pdbbind_loaded"] = n_loaded
    report["pdbbind_summary"] = parser.summary()
    log.info("step_1_complete", n_complexes=n_loaded)

    # ─── Paso 1.5: Curacion de datos ───
    # Filtrar ruido sistematico ANTES del VIP audit.
    # El VIP audit valida calidad individual, pero la curacion opera a nivel
    # de dataset: elimina datos de binding dudosos, outliers, duplicados, etc.
    log.info("step_1_5_data_curation")
    from data_curator import DataCurator

    curator = DataCurator()
    curated_complexes, curation_report = curator.curate(parser.complexes)
    curator.save_report(curation_report, output_dir / "data_curation_report.json")
    curator.print_summary(curation_report)

    report["data_curation"] = {
        "input_total": curation_report.n_input_total,
        "output_curated": curation_report.n_output,
        "removal_rate_pct": curation_report.overall_removal_rate_pct,
        "filters_applied": [
            {
                "name": f.name,
                "removed": f.n_removed,
            }
            for f in curation_report.filters
        ],
    }
    log.info("step_1_5_complete", n_curated=len(curated_complexes))

    if len(curated_complexes) < 100:
        report["status"] = "failed"
        report["error"] = (
            f"Solo {len(curated_complexes)} complejos tras curacion (minimo 100). "
            "Verifique que los datos de PDBbind se descargaron correctamente."
        )
        _save_report(report, output_dir / "training_report.json")
        return report

    # ─── Paso 2: VIP Audit ───
    # Ahora opera sobre los datos ya curados (no sobre el dataset crudo)
    log.info("step_2_vip_audit")
    from vip_audit import VIPAuditor, get_vip_complexes

    auditor = VIPAuditor(skip_structure_checks=skip_structure_checks)
    audit_report = auditor.audit_all(curated_complexes)
    auditor.save_report(audit_report, output_dir / "pdbbind_audit_report.json")

    vip_ids = get_vip_complexes(audit_report)
    vip_complexes = [c for c in curated_complexes if c.pdb_id in set(vip_ids)]

    report["vip_audit"] = {
        "total_evaluated": audit_report.total_evaluated,
        "total_accepted": audit_report.total_accepted,
        "acceptance_rate_pct": round(
            audit_report.total_accepted / max(audit_report.total_evaluated, 1) * 100, 1
        ),
        "rejection_reasons": audit_report.rejection_reasons,
    }
    log.info("step_2_complete", n_vip=len(vip_complexes))

    if len(vip_complexes) < 100:
        report["status"] = "failed"
        report["error"] = f"Solo {len(vip_complexes)} complejos VIP (mínimo 100)"
        _save_report(report, output_dir / "training_report.json")
        return report

    # ─── Paso 3: Clasificar por familia estructural ───
    log.info("step_3_family_classification")
    from structural_family import StructuralFamilyClassifier

    classifier = StructuralFamilyClassifier()
    family_classifications = classifier.classify_all(vip_complexes)
    family_summary = classifier.get_family_summary(family_classifications)
    report["family_classification"] = family_summary
    log.info("step_3_complete", families=family_summary.get("by_family", {}).keys())

    # ─── Paso 4: Congelar test set ───
    log.info("step_4_frozen_test_set")
    from data_splitter import create_frozen_test_set

    test_ids = create_frozen_test_set(
        vip_complexes, family_classifications, test_size=test_size, seed=seed,
    )
    report["test_set_size"] = len(test_ids)
    log.info("step_4_complete", test_size=len(test_ids))

    # ─── Paso 5: Scaffold-split CV ───
    log.info("step_5_scaffold_split")
    from data_splitter import build_ltr_groups, save_split_config, scaffold_split_cv

    splits = scaffold_split_cv(vip_complexes, test_ids, n_folds=n_folds, seed=seed)
    save_split_config(test_ids, splits, output_dir / "split_config.json", seed=seed)
    report["splits"] = {
        "n_folds": n_folds,
        "fold_sizes": [{"train": s.n_train, "val": s.n_val} for s in splits],
    }
    log.info("step_5_complete", n_folds=n_folds)

    if dry_run:
        report["status"] = "dry_run_complete"
        report["duration_seconds"] = round(time.time() - start_time, 2)
        _save_report(report, output_dir / "training_report.json")
        log.info("dry_run_complete", duration_s=report["duration_seconds"])
        return report

    # ─── Paso 6: Feature extraction masiva ───
    log.info("step_6_feature_extraction")
    feature_cache = Path(data_dir) / "feature_cache_v4"
    _extract_features_for_all(
        vip_complexes,
        skip_structure_checks,
        max_workers=6,
        cache_dir=feature_cache,
    )
    log.info("step_6_complete")

    # ─── Paso 7: Entrenar Model A + Model NULL ───
    log.info("step_7_training")
    from train_pipeline import ALL_FEATURES, MLTrainer

    trainer = MLTrainer(seed=seed)

    # Usar fold 0 para training principal, promedio de folds para métricas
    primary_split = splits[0]
    groups_train, _ = build_ltr_groups(vip_complexes, primary_split.train_ids)
    groups_val, _ = build_ltr_groups(vip_complexes, primary_split.val_ids)

    model_a = trainer.train_model_a(
        vip_complexes, primary_split, groups_train, groups_val,
    )
    model_null = trainer.train_model_null(
        vip_complexes, primary_split, groups_train, groups_val,
    )

    # Guardar modelos
    trainer.save_model(model_a, output_dir / "model_a.joblib")
    trainer.save_model(model_null, output_dir / "model_null.joblib")

    report["model_a_validation_metrics"] = model_a.metrics
    report["model_null_validation_metrics"] = model_null.metrics
    # Add PDBbind version for reproducibility
    report["pdbbind_version"] = getattr(parser, "version", "unknown") if "parser" in dir() else "unknown"
    report["training_script"] = "train_orchestrator.py"
    report["notes"] = (
        "ALL_FEATURES=167 (fix #3: ProLIF interaction counts removed). "
        "Metricas son de VALIDACION (fold 0). "
        "Test set (held-out) se evalua por separado en family_performance."
    )
    log.info("step_7_complete", model_a=model_a.metrics, model_null=model_null.metrics)

    # ─── Paso 7.5: Entrenar Model A Extended (consenso dual) ───
    log.info("step_7_5_extended")
    model_a_extended = trainer.train_model_a_extended(
        vip_complexes, primary_split, groups_train, groups_val,
    )
    trainer.save_model(model_a_extended, output_dir / "model_a_extended.joblib")
    report["model_a_extended_validation_metrics"] = model_a_extended.metrics
    log.info("step_7_5_complete", model_a_extended=model_a_extended.metrics)

    # ─── Paso 8: Ablation testing ───
    log.info("step_8_ablation")
    ablation_results = trainer.run_ablation(
        vip_complexes, primary_split, groups_train, groups_val,
    )
    report["ablation"] = [
        {
            "config": r.feature_set_name,
            "n_features": r.n_features,
            "metrics": r.metrics,
        }
        for r in ablation_results
    ]
    log.info("step_8_complete", n_configs=len(ablation_results))

    # ─── Paso 9: SHAP values ───
    log.info("step_9_shap")
    X_train_a = trainer.prepare_features(
        vip_complexes, primary_split.train_ids, model_a.feature_names,
    )
    shap_summary = trainer.compute_shap_values(model_a, X_train_a)
    report["shap_summary"] = shap_summary
    trainer.save_json_artifact(
        {"shap_mean_abs": shap_summary},
        output_dir / "shap_summary.json",
        "SHAP mean |SHAP| values for Model A",
    )
    log.info("step_9_complete")

    # ─── Paso 10: Delta distribution ───
    log.info("step_10_delta")
    all_vip_ids = [c.pdb_id for c in vip_complexes]
    deltas = trainer.compute_delta(model_a, model_null, vip_complexes, all_vip_ids)
    delta_dist = trainer.build_delta_distribution(deltas)
    trainer.save_json_artifact(
        delta_dist,
        output_dir / "delta_distribution.json",
        "Delta distribution for 3D specificity semaphore",
    )
    report["delta_distribution"] = delta_dist
    log.info("step_10_complete")

    # ─── Paso 11: Applicability Domain ───
    log.info("step_11_ad")
    ad_data = trainer.build_applicability_domain(
        vip_complexes, primary_split.train_ids, ALL_FEATURES,
    )
    trainer.save_json_artifact(
        ad_data,
        output_dir / "applicability_domain.json",
        "Applicability Domain (Mahalanobis) for Model A",
    )
    report["applicability_domain"] = {
        "n_features": ad_data["n_features"],
        "threshold_p99": ad_data["threshold_p99"],
    }
    log.info("step_11_complete")

    # Applicability Domain para modelo Extended (mismas features, mismo AD)
    trainer.save_json_artifact(
        ad_data,
        output_dir / "applicability_domain_extended.json",
        "Applicability Domain (Mahalanobis) for Model A Extended",
    )

    # ─── Paso 12: Performance por familia ───
    log.info("step_12_family_performance")
    # Evaluar en test set
    groups_test, _ = build_ltr_groups(vip_complexes, test_ids)
    family_perf = trainer.evaluate_by_family(
        model_a, vip_complexes, test_ids, family_classifications,
    )
    report["family_performance"] = family_perf
    log.info("step_12_complete", performance=family_perf)

    # ─── Paso 13: Evaluar criterios de aceptación ───
    log.info("step_13_acceptance")
    acceptance = trainer.evaluate_acceptance_criteria(
        ablation_results, shap_summary, delta_dist, model_a.metrics,
    )
    report["acceptance_criteria"] = acceptance
    log.info("step_13_complete", all_passed=acceptance.get("all_passed", False))

    # ─── Paso 14: Cross-validation (métricas promedio sobre todos los folds) ───
    log.info("step_14_cross_validation")
    cv_metrics = _run_cross_validation(trainer, vip_complexes, splits, seed)
    report["cross_validation"] = cv_metrics
    log.info("step_14_complete")

    # ─── Finalizar ───
    duration = round(time.time() - start_time, 2)
    report["status"] = "success" if acceptance.get("all_passed", False) else "completed_with_warnings"
    report["duration_seconds"] = duration

    _save_report(report, output_dir / "training_report.json")

    log.info(
        "training_pipeline_complete",
        status=report["status"],
        duration_s=duration,
        acceptance_all_passed=acceptance.get("all_passed", False),
    )

    return report


def _extract_features_for_all(
    complexes: list,
    skip_structure: bool,
    max_workers: int = 6,
    cache_dir: str | Path | None = None,
) -> None:
    """
    Extraer features para todos los complejos VIP.

    Guarda features en cpx.features dict.

    Features extraídas por grupo:
      A. 1D/2D (RDKit desde SMILES): mw, logp, tpsa, hbd, hba, rotatable_bonds, qed
      B. Vina (del docking — 0 si no hay datos): vina_best_score, pose_score_variance,
         pose_score_range, poses_passing_ratio
      C. Interacción 3D (ProLIF desde PDB+SDF): hbond_donor_count, hbond_acceptor_count,
         hydrophobic_contacts, salt_bridges, pi_stacking, pi_cation, metal_coordination,
         close_contacts_4A, close_contacts_6A

    Notas sobre degradación:
      - Si skip_structure=True: Group C = zeros (documentado)
      - Si ProLIF no está disponible: Group C = zeros + warning
      - Si un archivo PDB/SDF falla: ese complejo Group C = zeros + counter n_failed_3d
      - Group B siempre = 0 en training PDBbind (no re-dockeamos los cristales)

    Paralelización:
      ProLIF fingerprint tarda ~20s por complejo (inherente al algoritmo per-residue).
      Con max_workers procesos en paralelo, 3,019 complejos tardan ~2h (vs ~17h serial).
      Usa concurrent.futures.ProcessPoolExecutor con la función top-level
      extract_single_complex() de feature_extractor.py (pickleable).

    Cache:
      Si cache_dir se proporciona, los features 3D se guardan/cargan de un archivo
      JSON por complejo ({pdb_id}.json).  Esto evita re-extracción en re-runs.
    """
    import concurrent.futures

    from feature_extractor import (
        CACHE_VERSION,
        INTERACTION_FEATURES,
        InteractionFeatureExtractor,
        extract_single_complex,
        zero_all_3d_features,
    )

    extractor = InteractionFeatureExtractor()
    n_extracted = 0
    n_failed_3d = 0
    n_success_3d = 0
    n_cached_3d = 0

    # ── Preparar cache dir ──
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Paso 1: Extraer Group A + B para todos (rápido, secuencial) ──
    print(f"[step6] Extracting Group A+B for {len(complexes)} complexes...", flush=True)
    for cpx in complexes:
        features: dict[str, float] = {}

        # Grupo A: descriptores 1D/2D desde SMILES (RDKit)
        features["mw"] = cpx.molecular_weight or 0.0
        features["logp"] = getattr(cpx, "logp", 0.0)
        features["tpsa"] = getattr(cpx, "tpsa", 0.0)
        features["hbd"] = getattr(cpx, "hbd", 0.0)
        features["hba"] = getattr(cpx, "hba", 0.0)
        features["rotatable_bonds"] = getattr(cpx, "rotatable_bonds", 0.0)
        features["qed"] = getattr(cpx, "qed", 0.0)

        if cpx.ligand_smiles and features["logp"] == 0.0:
            try:
                _fill_1d2d_features(cpx, features)
            except Exception:
                pass

        # Grupo A_EXT: log_mw (v4 — breaks MW dominance)
        import math
        features["log_mw"] = math.log(max(features["mw"], 1.0))

        # Grupo B: Vina
        features["vina_best_score"] = getattr(cpx, "vina_score", 0.0)
        features["pose_score_variance"] = 0.0
        features["pose_score_range"] = 0.0
        features["poses_passing_ratio"] = 1.0

        cpx.features = features

    print(f"[step6] Group A+B done. skip_structure={skip_structure}, prolif_available={extractor.is_available}", flush=True)

    # ── Paso 2: Extraer Group C+D+E (3D) con multiprocessing ──
    if skip_structure or not extractor.is_available:
        # Sin extracción 3D — rellenar zeros
        for cpx in complexes:
            cpx.features.update(zero_all_3d_features())
        n_extracted = len(complexes)
        log.info(
            "features_extracted_no_3d",
            total=n_extracted,
            skip_structure=skip_structure,
            prolif_available=extractor.is_available,
        )
        return

    # Identificar qué complejos necesitan extracción 3D
    jobs: list[tuple[int, str, str, str]] = []  # (idx, pdb_id, prot_path, lig_path)
    for i, cpx in enumerate(complexes):
        pdb_id = getattr(cpx, "pdb_id", f"cpx_{i}")
        if cpx.protein_pdb_path and cpx.ligand_sdf_path:
            # ¿Hay cache v4?
            if cache_dir is not None:
                cache_file = cache_dir / f"{pdb_id}.json"
                if cache_file.exists():
                    try:
                        raw = json.loads(cache_file.read_text())
                        # v4 cache format: {"version": 4, "features": {...}}
                        if isinstance(raw, dict) and raw.get("version") == CACHE_VERSION:
                            cached = raw["features"]
                        else:
                            raise ValueError("cache version mismatch")
                        cpx.features.update(cached)
                        has_nonzero = any(
                            cached.get(f, 0.0) > 0.0 for f in INTERACTION_FEATURES
                        )
                        if has_nonzero:
                            n_success_3d += 1
                        n_cached_3d += 1
                        n_extracted += 1
                        continue
                    except Exception:
                        pass  # Cache corrupto or version mismatch, re-extraer
            jobs.append((i, pdb_id, str(cpx.protein_pdb_path), str(cpx.ligand_sdf_path)))
        else:
            cpx.features.update(zero_all_3d_features())
            n_extracted += 1

    print(f"[step6] Jobs to extract: {len(jobs)}, cached: {n_cached_3d}, no_paths: {len(complexes) - len(jobs) - n_cached_3d}", flush=True)
    log.info(
        "3d_extraction_starting",
        n_jobs=len(jobs),
        n_cached=n_cached_3d,
        max_workers=max_workers,
        est_minutes=round(len(jobs) * 2 / max_workers / 60, 1),
    )

    # Ejecutar en paralelo con ProcessPoolExecutor
    t_start = time.time()
    results_3d: dict[int, dict[str, float]] = {}

    effective_workers = min(max_workers, len(jobs)) if jobs else 1
    print(f"[step6] Starting ProcessPoolExecutor with {effective_workers} workers...", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=effective_workers) as executor:
        future_to_meta = {
            executor.submit(
                extract_single_complex, prot_path, lig_path
            ): (idx, pdb_id)
            for idx, pdb_id, prot_path, lig_path in jobs
        }
        print(f"[step6] All {len(future_to_meta)} futures submitted. Waiting for results...", flush=True)

        done_count = 0
        for future in concurrent.futures.as_completed(future_to_meta):
            idx, pdb_id = future_to_meta[future]
            done_count += 1
            try:
                feats_3d = future.result(timeout=120)  # 2 min max por complejo
            except Exception as e:
                log.warning("3d_extraction_worker_error", pdb_id=pdb_id, error=str(e))
                feats_3d = zero_all_3d_features()

            results_3d[idx] = feats_3d

            has_nonzero = any(
                feats_3d.get(f, 0.0) > 0.0 for f in INTERACTION_FEATURES
            )
            if has_nonzero:
                n_success_3d += 1
            else:
                n_failed_3d += 1

            # Guardar en cache (v4 format with version tag)
            if cache_dir is not None:
                try:
                    cache_file = cache_dir / f"{pdb_id}.json"
                    cache_data = {"version": CACHE_VERSION, "features": feats_3d}
                    cache_file.write_text(json.dumps(cache_data))
                except Exception:
                    pass

            # Progreso cada 50 complejos (o cada 10 al inicio)
            report_interval = 10 if done_count <= 50 else 50
            if done_count % report_interval == 0 or done_count == len(jobs) or done_count <= 3:
                elapsed = time.time() - t_start
                rate = done_count / elapsed if elapsed > 0 else 0
                eta_min = (len(jobs) - done_count) / rate / 60 if rate > 0 else 0
                log.info(
                    "3d_extraction_progress",
                    done=done_count,
                    total=len(jobs),
                    success=n_success_3d,
                    failed=n_failed_3d,
                    elapsed_min=round(elapsed / 60, 1),
                    eta_min=round(eta_min, 1),
                )
                sys.stdout.flush()

    # Asignar features 3D a los complejos
    for idx, pdb_id, prot_path, lig_path in jobs:
        feats_3d = results_3d.get(idx, zero_all_3d_features())
        complexes[idx].features.update(feats_3d)
        n_extracted += 1

    total_time = time.time() - t_start
    log.info(
        "features_extracted",
        total=n_extracted,
        success_3d=n_success_3d,
        failed_3d=n_failed_3d,
        cached_3d=n_cached_3d,
        extraction_time_min=round(total_time / 60, 1),
        avg_seconds_per_complex=round(total_time / max(len(jobs), 1), 1),
        max_workers=effective_workers,
    )


def _fill_1d2d_features(cpx, features: dict) -> None:
    """Calcular features 1D/2D desde SMILES con RDKit."""
    from rdkit import Chem
    from rdkit.Chem import QED, Descriptors

    mol = Chem.MolFromSmiles(cpx.ligand_smiles)
    if mol is None:
        return

    features["mw"] = Descriptors.MolWt(mol)
    features["logp"] = Descriptors.MolLogP(mol)
    features["tpsa"] = Descriptors.TPSA(mol)
    features["hbd"] = float(Descriptors.NumHDonors(mol))
    features["hba"] = float(Descriptors.NumHAcceptors(mol))
    features["rotatable_bonds"] = float(Descriptors.NumRotatableBonds(mol))
    features["qed"] = QED.qed(mol)

    cpx.molecular_weight = features["mw"]


def _run_cross_validation(
    trainer,
    complexes: list,
    splits: list,
    seed: int,
) -> dict:
    """
    Ejecutar cross-validation sobre todos los folds.

    Reporta: media ± std de Spearman y NDCG@10 sobre todos los folds.
    """
    from data_splitter import build_ltr_groups
    from train_pipeline import ALL_FEATURES, NULL_FEATURES

    fold_metrics_a = []
    fold_metrics_null = []
    fold_metrics_extended = []

    for split in splits:
        try:
            groups_train, _ = build_ltr_groups(complexes, split.train_ids)
            groups_val, _ = build_ltr_groups(complexes, split.val_ids)

            # Model A (Core)
            model_a = trainer.train_model(
                trainer.prepare_features(complexes, split.train_ids, ALL_FEATURES),
                trainer.prepare_labels(complexes, split.train_ids),
                groups_train,
                trainer.prepare_features(complexes, split.val_ids, ALL_FEATURES),
                trainer.prepare_labels(complexes, split.val_ids),
                groups_val,
                ALL_FEATURES,
                f"cv_model_a_fold{split.fold}",
            )
            fold_metrics_a.append(model_a.metrics)

            # Model NULL
            model_null = trainer.train_model(
                trainer.prepare_features(complexes, split.train_ids, NULL_FEATURES),
                trainer.prepare_labels(complexes, split.train_ids),
                groups_train,
                trainer.prepare_features(complexes, split.val_ids, NULL_FEATURES),
                trainer.prepare_labels(complexes, split.val_ids),
                groups_val,
                NULL_FEATURES,
                f"cv_model_null_fold{split.fold}",
            )
            fold_metrics_null.append(model_null.metrics)

            # Model A Extended (diferentes hiperparámetros)
            import copy
            orig_params = copy.deepcopy(trainer._xgb_params)
            trainer._xgb_params.update({
                "max_depth": 8,
                "learning_rate": 0.03,
                "subsample": 0.7,
                "colsample_bytree": 0.7,
                "reg_alpha": 0.5,
                "reg_lambda": 2.0,
                "gamma": 0.2,
                "min_child_weight": 8,
            })
            try:
                model_extended = trainer.train_model(
                    trainer.prepare_features(complexes, split.train_ids, ALL_FEATURES),
                    trainer.prepare_labels(complexes, split.train_ids),
                    groups_train,
                    trainer.prepare_features(complexes, split.val_ids, ALL_FEATURES),
                    trainer.prepare_labels(complexes, split.val_ids),
                    groups_val,
                    ALL_FEATURES,
                    f"cv_model_a_extended_fold{split.fold}",
                )
                fold_metrics_extended.append(model_extended.metrics)
            finally:
                trainer._xgb_params = orig_params

        except Exception as e:
            log.warning("cv_fold_failed", fold=split.fold, error=str(e))

    return {
        "model_a": _aggregate_cv_metrics(fold_metrics_a),
        "model_null": _aggregate_cv_metrics(fold_metrics_null),
        "model_a_extended": _aggregate_cv_metrics(fold_metrics_extended),
        "n_folds_completed": len(fold_metrics_a),
    }


def _aggregate_cv_metrics(fold_metrics: list[dict]) -> dict:
    """Agregar métricas de CV: media ± std."""
    if not fold_metrics:
        return {}

    result = {}
    for key in fold_metrics[0]:
        values = [m.get(key, 0.0) for m in fold_metrics if isinstance(m.get(key), (int, float))]
        if values:
            result[key] = {
                "mean": round(float(np.mean(values)), 4),
                "std": round(float(np.std(values)), 4),
                "min": round(float(np.min(values)), 4),
                "max": round(float(np.max(values)), 4),
            }

    return result


def _save_report(report: dict, path: Path) -> None:
    """Guardar reporte de entrenamiento."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info("training_report_saved", path=str(path))


def main():
    """Entry point para ejecución CLI."""
    parser = argparse.ArgumentParser(
        description="ML Rescoring Training Pipeline — MolDesign",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Entrenamiento completo
  python train_orchestrator.py --data-dir /data/pdbbind --output-dir /app/artifacts

  # Solo auditoría (dry run)
  python train_orchestrator.py --data-dir /data/pdbbind --dry-run

  # Sin checks de estructura (para testing)
  python train_orchestrator.py --data-dir /data/pdbbind --skip-structure-checks
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="/data/pdbbind",
        help="Directorio con datos PDBbind (default: /data/pdbbind)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/app/artifacts",
        help="Directorio de salida para artefactos (default: /app/artifacts)",
    )
    parser.add_argument(
        "--n-folds",
        type=int,
        default=5,
        help="Número de folds CV (default: 5)",
    )
    parser.add_argument(
        "--test-size",
        type=int,
        default=500,
        help="Tamaño del frozen test set (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla para reproducibilidad (default: 42)",
    )
    parser.add_argument(
        "--skip-structure-checks",
        action="store_true",
        help="Omitir checks que requieren archivos PDB/SDF",
    )
    parser.add_argument(
        "--include-other",
        action="store_true",
        default=True,
        help="Incluir el 'other/general' set de PDBbind (default: True)",
    )
    parser.add_argument(
        "--refined-only",
        action="store_true",
        help="Usar solo el refined set (ignora --include-other)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo auditar y curar sin entrenar",
    )

    args = parser.parse_args()

    # --refined-only desactiva --include-other
    include_other = not args.refined_only

    report = run_training_pipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        n_folds=args.n_folds,
        test_size=args.test_size,
        seed=args.seed,
        skip_structure_checks=args.skip_structure_checks,
        include_other_set=include_other,
        dry_run=args.dry_run,
    )

    if report.get("status") == "failed":
        print(f"\n[ERROR] Pipeline fallo: {report.get('error', 'Unknown')}")
        sys.exit(1)
    elif report.get("status") == "completed_with_warnings":
        print("\n[WARN] Pipeline completo con warnings - criterios de aceptacion NO cumplidos")
        print("   Revise artifacts/training_report.json para detalles")
        sys.exit(0)
    elif report.get("status") == "dry_run_complete":
        print(f"\n[OK] Dry run completado. {report.get('vip_audit', {}).get('total_accepted', 0)} complejos VIP")
        sys.exit(0)
    else:
        print(f"\n[OK] Pipeline completado exitosamente en {report.get('duration_seconds', 0)}s")
        criteria = report.get("acceptance_criteria", {})
        if criteria.get("all_passed"):
            print("   [OK] TODOS los criterios de aceptacion cumplidos")
        else:
            print("   [WARN] ALGUNOS criterios NO cumplidos - revisar antes de deploy")
        sys.exit(0)


if __name__ == "__main__":
    main()
