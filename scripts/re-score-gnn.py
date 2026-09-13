"""
scripts/re-score-gnn.py v3
Re-aplica GNN-v2 + CL-GNN + calibrated stacking a checkpoints ya dockeados.
Lee checkpoint JSON, corre inference sobre cada mol via score_with_gnn() y
score_with_clgnn() importadas de benchmark_ef_vina.py (que ya tienen la pipe
completa: parse PDBQT ? graph ? predict). Guarda campos nuevos y reporta
m?tricas finales.

Input (originales intactos en backups/):
  data/benchmark_checkpoint_<ds>.json

Output (en data/gnn_fixed/):
  benchmark_checkpoint_<ds>.json  (actualizado con gn_prob/clgnn_prob/calib_stacking)
  ef_report_<ds>_gs.json          (m?tricas con GNN)
  logs/re_score_<ds>.log          (log)
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Import helpers del script principal (GNN + CL-GNN + stacking)
import benchmark_ef_vina as bm

CHECKPOINTS_OUT = PROJECT_ROOT / "data" / "gnn_fixed"
LOG_DIR = CHECKPOINTS_OUT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "5ht1a":        {"pdb": "7e2y.pdb",        "family": "gpcr"},
    "cdk2":         {"pdb": "3PP0.pdb",        "family": "kinase"},
    "hiv_protease": {"pdb": "1HSG.pdb",        "family": "protease"},
    "er_alpha":     {"pdb": "3ERT.pdb",        "family": "nuclear_receptor"},
    "factor_xa":    {"pdb": "1f0r_protein.pdb","family": "soluble_enzyme"},
}


def composite_score(r):
    vina = abs(r.get("vina_score") or -5.0)
    vina_norm = min(1.0, vina / 12.0)
    prob = r.get("prob", 0.0)
    if prob > 0.01:
        return round(prob * 0.70 + vina_norm * 0.30, 4)
    return round(vina_norm, 4)


# ?? Main per target ??????????????????????????????????????????????????
def re_score_target(dataset, cfg):
    ck_src = PROJECT_ROOT / "data" / f"benchmark_checkpoint_{dataset}.json"
    ck_dst = CHECKPOINTS_OUT / f"benchmark_checkpoint_{dataset}.json"
    pdb_path = str(PROJECT_ROOT / "data" / cfg["pdb"])
    family = cfg["family"]

    if not ck_src.exists():
        print(f"  [SKIP] No source checkpoint at {ck_src}")
        return

    # Copiar source fresh (no queremos tocar orig)
    import shutil
    shutil.copy2(ck_src, ck_dst)

    log_path = LOG_DIR / f"re_score_{dataset}.log"

    def log(msg):
        print(msg)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log("=" * 60)
    log(f"  RE-SCORE GNN: {dataset} ({family})")
    log(f"  PDB: {cfg['pdb']}")
    log("=" * 60)

    with open(ck_dst) as f:
        data = json.load(f)
    results = data.get("results", [])
    n_total = len(results)
    n_active = sum(1 for r in results if r["is_active"])
    valid = [r for r in results if r.get("pose_pdbqt") and len(r.get("pose_pdbqt","")) > 100]
    log(f"  Loaded {n_total} mols ({n_active} active) -- valid poses: {len(valid)}")

    receptor_config = {"protein_pdb": pdb_path, "target_id": dataset, "center": (0,0,0), "box_size": 25}

    # ?? GNN-v2 ??
    log(f"\n  GNN-v2 inference on {len(valid)} mols...")
    gnn_start = time.time()
    # Reset silent-failure counter on the predictor for this run (Bucket A.5)
    gnn_predictor_instance = bm._get_gnn("cpu")
    gnn_predictor_instance.reset_silent_failures()
    gnn_silent_initial = gnn_predictor_instance.silent_failures
    for i, r in enumerate(valid):
        if i % 500 == 0 or i == len(valid) - 1:
            elapsed = time.time() - gnn_start
            rate = elapsed / (i + 1) if i > 0 else 0
            log(f"  [GNN {i+1}/{len(valid)}] {elapsed:.0f}s | {rate:.2f}s/mol")
        try:
            r = bm.score_with_gnn(r, pdb_path, engine="cpu")
        except Exception:
            # [A3] SIN 0.5 fabricado: ausente ↔ no disponible
            r["gnn_prob"] = None
            r["gnn_std"] = None
            log(f"  [WARN gnn_missing] smiles={r.get('smiles', '')[:40]}")
    gnn_elapsed = time.time() - gnn_start
    gnn_silent_total = gnn_predictor_instance.silent_failures - gnn_silent_initial
    log(f"  GNN-v2 done: {gnn_elapsed:.0f}s ({gnn_elapsed/len(valid):.2f}s/mol) | silent={gnn_silent_total}/{len(valid)}")
    if gnn_silent_total > 0:
        log(f"  [WARNING] {gnn_silent_total} mols fell through GNN-v2 (silent returns). See logs gnn_v2.inference.")

    # ?? CL-GNN ??
    log(f"\n  CL-GNN inference on {len(valid)} mols...")
    cl_start = time.time()
    for i, r in enumerate(valid):
        if i % 500 == 0 or i == len(valid) - 1:
            elapsed = time.time() - cl_start
            rate = elapsed / (i + 1) if i > 0 else 0
            log(f"  [CL-GNN {i+1}/{len(valid)}] {elapsed:.0f}s | {rate:.2f}s/mol")
        try:
            r = bm.score_with_clgnn(r, pdb_path, receptor_config)
        except Exception:
            # [A3] SIN 0.5 fabricado: ausente ↔ no disponible
            r["clgnn_prob"] = None
            log(f"  [WARN clgnn_missing] smiles={r.get('smiles', '')[:40]}")
    cl_elapsed = time.time() - cl_start
    log(f"  CL-GNN done: {cl_elapsed:.0f}s ({cl_elapsed/len(valid):.2f}s/mol)")

    # ?? Composite v0 ??
    for r in results:
        r["composite"] = composite_score(r)

    # ?? Calibrated stacking (import from bm too) ??
    cal = bm.calibrated_stacking(valid, family)
    for r, cs in zip(valid, cal):
        r["composite_calibrated"] = cs

    # ?? Guardar checkpoint actualizado ??
    with open(ck_dst, "w") as f:
        json.dump(data, f)
    log(f"\n  Checkpoint updated: {ck_dst}")

    # ?? M?tricas ??
    from sklearn.metrics import roc_auc_score, average_precision_score
    labels = [r["is_active"] for r in valid]

    def report(name, scores):
        auc = roc_auc_score(labels, scores)
        pr = average_precision_score(labels, scores)
        ef1 = bm.enrichment_factor(scores, labels, 1)
        ef5 = bm.enrichment_factor(scores, labels, 5)
        ef10 = bm.enrichment_factor(scores, labels, 10)
        log(f"\n  {name} (N={len(valid)})")
        log(f"    EF@1%={ef1:.2f}x  EF@5%={ef5:.2f}x  EF@10%={ef10:.2f}x")
        log(f"    ROC-AUC={auc:.4f}  PR-AUC={pr:.4f}")
        return {"ef1": ef1, "ef5": ef5, "ef10": ef10, "auc": round(auc,4), "pr": round(pr,4)}

    vina_m = report("Vina Only", [abs(r.get("vina_score") or -5.0) for r in valid])
    comp_m = report("Composite (Vina+XGB)", [r.get("composite") or composite_score(r) for r in valid])

    # ?? [fix-a] Cortes intermedios requeridos por paper JCIM ??
    # "+GNN solo": re-score Vina con GNN-v2 (sin CL-GNN, sin XGB, sin stacking).
    # Ponderacion consistente con composite_score: vina 30% + gnn 70%.
    def _vina_plus_score(r, second_key, w_second=0.70):
        vina = abs(r.get("vina_score") or -5.0)
        vina_norm = min(1.0, vina / 12.0)
        second = r.get(second_key)
        if second is None or second < 0.01:
            return round(vina_norm, 4)
        return round(vina_norm * (1.0 - w_second) + float(second) * w_second, 4)

    gnn_only_m = report("Vina+GNN (no CL-GNN)", [_vina_plus_score(r, "gnn_prob") for r in valid])
    clgnn_only_m = report("Vina+CL-GNN (no GNN)", [_vina_plus_score(r, "clgnn_prob") for r in valid])

    cal_m = report("Calibrated Stacking (GNN+CL-GNN)", [r.get("composite_calibrated",0) for r in valid])

    rep = {
        "target": dataset, "family": family, "gnn_fixed": True,
        "n_total": n_total, "n_active": n_active, "n_valid": len(valid),
        "gnn_silent_failures": gnn_silent_total,
        "gnn_silent_failure_rate": round(gnn_silent_total / max(len(valid), 1), 4),
        "vina_only": vina_m,
        "vina_plus_xgb": comp_m,        # Baseline: composite original
        "vina_plus_gnn": gnn_only_m,    # [fix-a] Corte 3
        "vina_plus_clgnn": clgnn_only_m,# [fix-a] Corte 4
        "calibrated_stacking": cal_m,    # Corte 5: stacking final
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    rep_path = CHECKPOINTS_OUT / f"ef_report_{dataset}_gs.json"
    with open(rep_path, "w") as f:
        json.dump(rep, f, indent=2)
    log(f"\n  Report: {rep_path}")


def main():
    print("=" * 60)
    print("  RE-SCORE GNN v3 -- benchmark_ef_vina.score_with_gnn/clgnn")
    print("=" * 60)

    for ds, cfg in TARGETS.items():
        try:
            t0 = time.time()
            re_score_target(ds, cfg)
            print(f"\n  {ds}: {(time.time()-t0)/60:.1f} min")
        except Exception as e:
            print(f"\n  [FATAL] {ds}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("  ALL DONE -- reports in data/gnn_fixed/ef_report_*_gs.json")


if __name__ == "__main__":
    main()