#!/usr/bin/env python3
"""
scripts/compute_ums_standalone.py — Generate PAPER_UMS Table 3.1 (UMS standalone AUC).

Fixes the reproducibility gap found in Fase 0 (2026-08-05):
- `compute_ums_fixed.py` truncated decoys to 1000 -> produced wrong values
  (ACE 0.8234 vs paper 0.751). This script uses ALL decoys per target,
  faithful to the paper claim "UMS standalone AUCs are computed over the
  full raw active/decoy sets" (PAPER_UMS.md line 221).
- HDAC6/MMP2 use the warhead-filtered sets (actives_hydroxamic/decoys_hydroxamic),
  consistent with the paper (15/279 and 26/597).

Output: data/ums_standalone_full.json (same schema as ums_standalone_postfix.json,
plus n_dec total and the previous postfix value for comparison).

Usage:
  python scripts/compute_ums_standalone.py            # full run
  python scripts/compute_ums_standalone.py --boot-iters 1000
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from universal_metal_score import compute_universal_metal_score, detect_warheads

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data" / "multitarget"

# target -> (actives file, decoys file)
TARGETS = {
    "ca2":     ("actives.txt",            "decoys.smi"),
    "mmp9":    ("actives.txt",            "decoys.smi"),
    "ace":     ("actives.txt",            "decoys.smi"),
    "hdac6":   ("actives_hydroxamic.txt", "decoys_hydroxamic.smi"),
    "mmp2":    ("actives_hydroxamic.txt", "decoys_hydroxamic.smi"),
    "pde5a":   ("actives.txt",            "decoys.smi"),
    "cyp3a4":  ("actives.txt",            "decoys.smi"),
}


def load_smiles(path: Path) -> list[str]:
    if not path.exists():
        print(f"[ERROR] missing file: {path}")
        return []
    return [line.split()[0] for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def boot_ci(y_true, y_score, iters: int, seed: int = 42, alpha: float = 0.05):
    """Percentile bootstrap CI on AUC (stratified resampling)."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return None, None
    aucs = []
    for _ in range(iters):
        p = rng.choice(pos_idx, size=len(pos_idx), replace=True)
        n = rng.choice(neg_idx, size=len(neg_idx), replace=True)
        idx = np.concatenate([p, n])
        try:
            aucs.append(roc_auc_score(y_true[idx], y_score[idx]))
        except ValueError:
            continue
    if not aucs:
        return None, None
    lo = np.percentile(aucs, 100 * alpha / 2)
    hi = np.percentile(aucs, 100 * (1 - alpha / 2))
    return float(lo), float(hi)


def main():
    ap = argparse.ArgumentParser(description="Generate PAPER_UMS Table 3.1")
    ap.add_argument("--boot-iters", type=int, default=1000,
                    help="bootstrap iterations for CI (paper used 10,000; default 1000 for speed)")
    ap.add_argument("--out", type=str, default=str(PROJECT / "data" / "ums_standalone_full.json"))
    ap.add_argument("--compare-postfix", action="store_true",
                    help="compare against ums_standalone_postfix.json")
    args = ap.parse_args()

    results = {}
    for name, (act_f, dec_f) in TARGETS.items():
        actives = load_smiles(DATA / name / act_f)
        decoys = load_smiles(DATA / name / dec_f)
        if not actives or not decoys:
            print(f"[SKIP] {name}: missing data (act={len(actives)} dec={len(decoys)})")
            continue

        y_true = [1] * len(actives) + [0] * len(decoys)
        y_score = []
        for smi in actives + decoys:
            s, _ = compute_universal_metal_score(smi, 0.5, "metaloenzyme")
            y_score.append(s)

        auc = float(roc_auc_score(y_true, y_score))
        lo, hi = boot_ci(y_true, y_score, args.boot_iters)

        # Warhead stats for transparency
        wh_act = sum(1 for smi in actives if any(detect_warheads(smi).values()))
        wh_dec = sum(1 for smi in decoys if any(detect_warheads(smi).values()))

        results[name] = {
            "auc": round(auc, 4),
            "ci_lo": round(lo, 4) if lo is not None else None,
            "ci_hi": round(hi, 4) if hi is not None else None,
            "n_act": len(actives),
            "n_dec": len(decoys),
            "boot_iters": args.boot_iters,
            "warhead_pct_act": round(100 * wh_act / len(actives), 1) if actives else None,
            "warhead_pct_dec": round(100 * wh_dec / len(decoys), 1) if decoys else None,
        }
        print(f"{name:7s} | AUC={auc:.4f} [{lo:.4f}, {hi:.4f}] | act={len(actives)} dec={len(decoys)}")

    out = Path(args.out)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")

    if args.compare_postfix:
        postfix = PROJECT / "data" / "ums_standalone_postfix.json"
        if postfix.exists():
            prev = json.loads(postfix.read_text(encoding="utf-8"))
            print("\n--- Comparison vs ums_standalone_postfix.json ---")
            for name, rec in results.items():
                if name in prev:
                    p = prev[name]
                    delta = rec["auc"] - p["auc"]
                    flag = "OK" if abs(delta) < 0.005 else "DIFF"
                    print(f"{name:7s} | full={rec['auc']:.4f} (n_dec={rec['n_dec']}) "
                          f"| postfix={p['auc']:.4f} (n_dec={p['n_dec']}) | d={delta:+.4f} [{flag}]")
                else:
                    print(f"{name:7s} | not in postfix")


if __name__ == "__main__":
    main()
