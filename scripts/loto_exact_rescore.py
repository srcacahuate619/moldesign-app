"""
loto_exact_rescore.py
Re-score each LOTO fold with the GNN-D LOTO model + UnivMetal.
Output: per-fold checkpoints with loto_gnn_d_prob + loto_compounds scores.
Then compute Metastack5 AUC for each fold.

Writes results to data/molchamb_loto/loto_exact_report.json

Usage:
  python scripts/loto_exact_rescore.py
"""
import json, os, sys, tempfile, time, traceback
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

CK_DIR = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints"
OUT_DIR = PROJECT_ROOT / "data" / "molchamb_loto"
ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"
LOTO_ARTIFACT_PATTERN = "gnn_d_loto_{target}.pt"
TARGETS = ["5ht1a", "ca2", "cdk2", "er_alpha", "factor_xa", "hiv_protease", "thrombin"]

# Protein PDB paths
PDB_PATHS = {
    "5ht1a": "D:/moldesign-build/data/targets/7E2Y.pdb",
    "ca2": "D:/moldesign-build/data/targets/3dc3.pdb",
    "cdk2": "D:/moldesign-build/data/targets/3PP0.pdb",
    "er_alpha": "D:/moldesign-build/data/targets/3ERT.pdb",
    "factor_xa": "D:/moldesign-build/data/targets/3CYX.pdb",
    "hiv_protease": "D:/moldesign-build/data/targets/1HSG.pdb",
    "thrombin": "D:/moldesign-build/data/targets/1c4u.pdb",
}

from gnn_v2.inference import GNNv2Predictor
from universal_metal_score import compute_universal_metal_score

def score_vina(r): return min(1.0, abs(r.get("vina_score") or -5.0) / 12.0)
def score_xgb(r): return r.get("prob", 0.0)
def score_c(r): return r.get("clgnn_prob", 0.5)
def score_d(r): return r.get("loto_gnn_d_prob", 0.5)
def score_um(r): return r.get("universal_metal_score", 0.5) or 0.5
SCORERS = [score_vina, score_xgb, score_c, score_d, score_um]

def softmax_weights(s, T=6.0, p=1.0):
    ss = np.array(s, dtype=float)
    powered = np.maximum(np.abs(ss)**p, 1e-12)
    exp_s = np.exp(powered/T - np.max(powered/T))
    return exp_s / exp_s.sum()

def meta_weights(*a, T=6.0, p=1.0, sat=0.96, hedge=0.65):
    aucs = np.array(a, dtype=float)
    n = len(aucs)
    if any(aucs > sat):
        w = np.ones(n) * 0.05
        w[int(np.argmax(aucs))] = 0.8
        return w
    if all(aucs < hedge):
        return np.ones(n) / n
    return softmax_weights(aucs, T=T, p=p)

def composite(r, w, sc):
    s = np.array([fn(r) for fn in sc[:len(w)]])
    return float(np.dot(s, w))

def main():
    results = {}
    for held_out in TARGETS:
        print("=" * 70)
        print("LOTO FOLD: held-out = %s" % held_out)
        print("=" * 70)
        ck_path = CK_DIR / ("benchmark_checkpoint_%s.json" % held_out)
        if not ck_path.exists():
            print("  SKIP: checkpoint not found")
            continue
        data = json.loads(ck_path.read_text())
        mols = data["results"]
        valid = [r for r in mols if r.get("vina_score") is not None and r.get("pose_pdbqt") and len(r.get("pose_pdbqt",""))>100]
        print("Total mols: %d | valid poses: %d" % (len(mols), len(valid)))
        if not valid:
            continue

        loto_model_path = ARTIFACTS_DIR / ("gnn_d_loto_%s.pt" % held_out)
        if not loto_model_path.exists():
            print("  SKIP: LOTO model not found at %s" % loto_model_path)
            continue

        protein_pdb = PDB_PATHS.get(held_out)
        if not protein_pdb or not Path(protein_pdb).exists():
            print("  SKIP: protein PDB not found at %s" % protein_pdb)
            continue

        # Load LOTO model
        predictor = GNNv2Predictor(
            device="cuda" if __import__("torch").cuda.is_available() else "cpu",
            mc_samples=10,
            model_path=loto_model_path,
        )
        n_silent = 0
        t0 = time.time()
        for i, r in enumerate(valid):
            smi = r["smiles"]
            pose = r["pose_pdbqt"]
            fd, tmp = tempfile.mkstemp(suffix=".pdbqt")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(pose)
                prob, std = predictor.predict(smi, tmp, protein_pdb)
                r["loto_gnn_d_prob"] = round(float(prob), 4)
                r["loto_gnn_d_std"] = round(float(std), 4)
                if prob == 0.5:
                    n_silent += 1
            except Exception as e:
                r["loto_gnn_d_prob"] = 0.5
                r["loto_gnn_d_std"] = 1.0
                n_silent += 1
            finally:
                try: os.unlink(tmp)
                except: pass
            if (i+1) % 200 == 0 or i == len(valid)-1:
                elapsed = time.time() - t0
                print("  [%s] %d/%d (%.1fs, %.2fs/mol, silent=%d)" % (
                    held_out, i+1, len(valid), elapsed, elapsed/(i+1), n_silent))

        print("LOTO re-score completed: held=%s | silent=%d/%d | %.1fs" % (
            held_out, n_silent, len(valid), time.time() - t0))

        # Compute per-molecule Metastack5 composite
        labels = [r["is_active"] for r in valid]

        # Individual AUCs
        auc_v = roc_auc_score(labels, [score_vina(r) for r in valid])
        auc_x = roc_auc_score(labels, [score_xgb(r) for r in valid])
        auc_c = roc_auc_score(labels, [score_c(r) for r in valid])
        auc_d_loto = roc_auc_score(labels, [score_d(r) for r in valid])
        auc_um = roc_auc_score(labels, [score_um(r) for r in valid])

        # M4 baseline (using LOTO GNN-D)
        w4 = meta_weights(auc_v, auc_x, auc_c, auc_d_loto)
        comp4 = [composite(r, w4, [score_vina, score_xgb, score_c, score_d]) for r in valid]
        m4_auc = roc_auc_score(labels, comp4)

        # M5+UnivMetal (family-gated = active for ca2 only)
        is_ca2 = (held_out == "ca2")
        if is_ca2:
            w5 = meta_weights(auc_v, auc_x, auc_c, auc_d_loto, auc_um)
            comp5 = [composite(r, w5, SCORERS) for r in valid]
            m5_auc = roc_auc_score(labels, comp5)
        else:
            m5_auc = m4_auc  # no change for non-metal

        delta = m5_auc - m4_auc

        print("  auc_v=%.3f auc_x=%.3f auc_c=%.3f auc_d_loto=%.3f auc_um=%.3f"
              % (auc_v, auc_x, auc_c, auc_d_loto, auc_um))
        print("  M4_loto=%.4f M5_gated=%.4f delta=%+.4f%s" % (
            m4_auc, m5_auc, delta, " *ca2 UnivMetal" if is_ca2 else ""))

        results[held_out] = {
            "n_valid": len(valid),
            "n_silent": n_silent,
            "auc_vina": round(float(auc_v), 4),
            "auc_xgb": round(float(auc_x), 4),
            "auc_clgnn_a": round(float(auc_c), 4),
            "auc_gnn_d_loto": round(float(auc_d_loto), 4),
            "auc_univ_metal": round(float(auc_um), 4),
            "auc_metastack4_loto": round(float(m4_auc), 4),
            "auc_metastack5_gated": round(float(m5_auc), 4),
            "delta": round(float(delta), 4),
            "used_univ_metal": is_ca2,
        }

        # Save updated checkpoint (with loto_gnn_d_prob)
        out_ck = OUT_DIR / "loto_checkpoints" / ("benchmark_checkpoint_%s_loto.json" % held_out)
        out_ck.parent.mkdir(parents=True, exist_ok=True)
        out_ck.write_text(json.dumps(data, indent=2))
        print("  Saved: %s" % out_ck)

    # Summary
    print()
    print("=" * 70)
    print("LOTO EXACT SUMMARY")
    print("=" * 70)
    m4s = [v["auc_metastack4_loto"] for v in results.values()]
    m5s = [v["auc_metastack5_gated"] for v in results.values()]
    print()
    print("Per-target:")
    for t in TARGETS:
        if t not in results: continue
        r = results[t]
        mark = " *UnivMetal" if r["used_univ_metal"] else ""
        print("  %-15s  M4=%.4f  M5_gated=%.4f  delta=%+.4f%s" % (
            t, r["auc_metastack4_loto"], r["auc_metastack5_gated"], r["delta"], mark))
    print()
    print("LOTO MEAN:  M4=%.4f  M5_gated=%.4f  delta=%+.4f" % (
        np.mean(m4s), np.mean(m5s), np.mean(m5s) - np.mean(m4s)))

    report = {
        "strategy": "LOTO exact re-scoring with GNN-D LOTO models + UnivMetal",
        "per_target": results,
        "mean_metastack4": round(float(np.mean(m4s)), 4),
        "mean_metastack5_gated": round(float(np.mean(m5s)), 4),
        "mean_delta": round(float(np.mean(m5s) - np.mean(m4s)), 4),
    }
    out_path = OUT_DIR / "loto_exact_univmetal_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print()
    print("Saved: %s" % out_path)

if __name__ == "__main__":
    main()
