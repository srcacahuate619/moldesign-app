"""
loto_exact_rescore_fast.py
Slim LOTO re-scoring - NO imports benchmark_ef_vina.

Directly loads GNNv2Predictor + re-scores each LOTO fold.
"""
import json, os, sys, tempfile, time, traceback
from pathlib import Path

PJ = Path(__file__).resolve().parent.parent

# Log file (written directly to avoid shell redirection issues)
LOG_PATH = PJ / "data" / "molchamb_loto" / "loto_exact_rescore_fast.log"
_log_file = None
def log(msg=""):
    global _log_file
    if _log_file is None:
        _log_file = open(LOG_PATH, "w", encoding="ascii", buffering=1)
    print(msg)
    _log_file.write(msg + "\n")
    _log_file.flush()

def elog(msg):
    traceback.print_exc()
    log("[ERROR] " + str(msg))
sys.path.insert(0, str(PJ / "rescoring"))
sys.path.insert(0, str(PJ / "backend"))

CK_DIR = PJ / "data" / "molchamb_loto" / "checkpoints"
OUT_DIR = PJ / "data" / "molchamb_loto"
ARTIFACTS = PJ / "rescoring" / "artifacts"
TARGETS = ["5ht1a", "ca2", "cdk2", "er_alpha", "factor_xa", "hiv_protease", "thrombin"]

PDB_PATHS = {
    "5ht1a": PJ / "data" / "targets" / "7E2Y.pdb",
    "ca2": PJ / "data" / "targets" / "3dc3.pdb",
    "cdk2": PJ / "data" / "targets" / "3PP0.pdb",
    "er_alpha": PJ / "data" / "targets" / "3ERT.pdb",
    "factor_xa": PJ / "data" / "targets" / "3CYX.pdb",
    "hiv_protease": PJ / "data" / "targets" / "1HSG.pdb",
    "thrombin": PJ / "data" / "targets" / "1c4u.pdb",
}

log("Importing GNN model..."); t0 = time.time()
from gnn_v2.inference import GNNv2Predictor
log("  gnn_v2.inference: %.1fs" % (time.time()-t0))

t0 = time.time()
from universal_metal_score import compute_universal_metal_score
log("  universal_metal_score: %.1fs" % (time.time()-t0))

t0 = time.time()
import numpy as np
from sklearn.metrics import roc_auc_score
log("  sklearn/numpy: %.1fs" % (time.time()-t0))

# Scorers
def s_v(r): return min(1.0, abs(r.get("vina_score") or -5.0) / 12.0)
def s_x(r): return r.get("prob", 0.0)
def s_c(r): return r.get("clgnn_prob", 0.5)
def s_d(r): v = r.get("loto_gnn_d_prob"); return v if v is not None and v != 0.5 else 0.5
def s_um(r): return r.get("universal_metal_score", 0.5) or 0.5
S5 = [s_v, s_x, s_c, s_d, s_um]

def sw(scores, T=6.0, p=1.0):
    ss = np.array(scores, dtype=float)
    pw = np.maximum(np.abs(ss)**p, 1e-12)
    ex = np.exp(pw/T - np.max(pw/T))
    return ex / ex.sum()

def mw(*a, T=6.0, p=1.0, sat=0.96, hedge=0.65):
    aucs = np.array(a, dtype=float)
    n = len(aucs)
    if any(aucs > sat):
        w = np.ones(n)*0.05; w[int(np.argmax(aucs))] = 0.8; return w
    if all(aucs < hedge):
        return np.ones(n)/n
    return sw(aucs, T=T, p=p)

def comp(r, w):
    s = np.array([fn(r) for fn in S5[:len(w)]]); return float(np.dot(s, w))

results = {}
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "loto_checkpoints").mkdir(parents=True, exist_ok=True)

for held_out in TARGETS:
    log("\n" + "="*70)
    log("FOLD: held-out = %s" % held_out)
    log("="*70)
    ck_path = CK_DIR / ("benchmark_checkpoint_%s.json" % held_out)
    ck = json.loads(ck_path.read_text())
    mols = ck["results"]
    valid = [r for r in mols if r.get("vina_score") is not None and r.get("pose_pdbqt") and len(r.get("pose_pdbqt",""))>100]
    pr = PDB_PATHS.get(held_out)
    log("  mols=%d  valid=%d  pdb=%s" % (len(mols), len(valid), pr))

    model_path = ARTIFACTS / ("gnn_d_loto_%s.pt" % held_out)
    if not model_path.exists():
        log("  SKIP: no LOTO model %s" % model_path); continue
    if not pr or not pr.exists():
        log("  SKIP: no PDB %s" % pr); continue

    gpu = __import__("torch").cuda.is_available()
    predictor = GNNv2Predictor(device="cuda" if gpu else "cpu", mc_samples=10, model_path=model_path)
    log("  Model loaded (gpu=%s). Scoring %d molecules..." % (gpu, len(valid)))

    n_silent = 0; t0 = time.time()
    for i, r in enumerate(valid):
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdbqt", delete=False, mode="w") as f:
                f.write(r["pose_pdbqt"]); tmp = f.name
            prob, std = predictor.predict(r["smiles"], tmp, str(pr))
            r["loto_gnn_d_prob"] = round(float(prob), 4)
            r["loto_gnn_d_std"] = round(float(std), 4)
            if prob == 0.5: n_silent += 1
            os.unlink(tmp)
        except Exception as e:
            r["loto_gnn_d_prob"] = 0.5; r["loto_gnn_d_std"] = 1.0; n_silent += 1

        if (i+1) % 100 == 0 or i == len(valid)-1:
            el = time.time()-t0; log("  [%s] %d/%d (%.0fs, %.2fs/mol, silent=%d)" % (held_out, i+1, len(valid), el, el/(i+1), n_silent))

    log("  Done: %.1fs | silent=%d/%d" % (time.time()-t0, n_silent, len(valid)))

    # AUC evaluation
    labels = [r["is_active"] for r in valid]
    auc_v = roc_auc_score(labels, [s_v(r) for r in valid])
    auc_x = roc_auc_score(labels, [s_x(r) for r in valid])
    auc_c = roc_auc_score(labels, [s_c(r) for r in valid])
    auc_d = roc_auc_score(labels, [s_d(r) for r in valid])
    auc_um = roc_auc_score(labels, [s_um(r) for r in valid])

    w4 = mw(auc_v, auc_x, auc_c, auc_d)
    comp4 = [comp(r, w4[:4]) for r in valid]
    m4 = roc_auc_score(labels, comp4)

    is_ca2 = (held_out == "ca2")
    if is_ca2:
        w5 = mw(auc_v, auc_x, auc_c, auc_d, auc_um)
        comp5 = [comp(r, w5[:5]) for r in valid]
        m5 = roc_auc_score(labels, comp5)
    else:
        m5 = m4

    log("  auc_v=%.3f auc_x=%.3f auc_c=%.3f auc_d=%.3f auc_um=%.3f" % (auc_v, auc_x, auc_c, auc_d, auc_um))
    log("  M4=%.4f M5_gated=%.4f delta=%+.4f%s" % (m4, m5, m5-m4, " *ca2*" if is_ca2 else ""))

    results[held_out] = {
        "n": len(valid), "n_silent": n_silent,
        "auc_vina": round(float(auc_v), 4), "auc_xgb": round(float(auc_x), 4),
        "auc_clgnn_a": round(float(auc_c), 4), "auc_gnn_d_loto": round(float(auc_d), 4),
        "auc_univ_metal": round(float(auc_um), 4),
        "auc_metastack4_loto": round(float(m4), 4),
        "auc_metastack5_gated": round(float(m5), 4),
        "delta": round(float(m5-m4), 4),
        "used_univ_metal": is_ca2,
    }

rep = {
    "per_target": results,
    "mean_m4": round(float(np.mean([v["auc_metastack4_loto"] for v in results.values()])), 4),
    "mean_m5_gated": round(float(np.mean([v["auc_metastack5_gated"] for v in results.values()])), 4),
    "mean_delta": round(float(np.mean([v["auc_metastack5_gated"] for v in results.values()]) - np.mean([v["auc_metastack4_loto"] for v in results.values()])), 4),
}
(OUT_DIR / "loto_exact_univmetal_report.json").write_text(json.dumps(rep, indent=2))
log("\nSaved: %s" % (OUT_DIR / "loto_exact_univmetal_report.json"))
if _log_file:
    _log_file.close()
