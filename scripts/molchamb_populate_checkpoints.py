#!/usr/bin/env python3
"""
scripts/molchamb_populate_checkpoints.py
========================================
New experiment (branch molchamb-loto-experiment).

Adds `molchamb_score` to every result entry of the 8 existing benchmark
checkpoints using the cached MolChamb quantum score (compute_quantum_score).

SAFETY CONTRACT:
  - READS checkpoints from data/gnn_v31/checkpoints/
  - WRITES to a NEW directory: data/molchamb_loto/checkpoints/
  - NEVER modifies the original checkpoint files in-place
  - Preserves all existing fields (vina_score, prob, clgnn_prob, gnn_d_prob)
  - Only ADDS the new field `molchamb_score`
  - If a SMILES already has a cached xTB result -> use it (instant).
  - If not -> run xTB realtime (worst case ~5-30s/mol) with sensible fallback
    on failure (molchamb_score = 0.5).

Usage:
  python scripts/molchamb_populate_checkpoints.py
  python scripts/molchamb_populate_checkpoints.py --workers 4
"""
import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from compute_quantum_features import compute_quantum_score_cached

SRC_DIR = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints"
DST_DIR = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints"


def populate_one(smiles: str) -> float:
    """Compute (or fetch from cache) the MolChamb score. Fallback 0.5 on error."""
    if not smiles or not isinstance(smiles, str) or len(smiles) < 3:
        return 0.5
    try:
        return float(compute_quantum_score_cached(smiles))
    except Exception:
        # xTB failure (e.g. exotic chemistry, impossible geometry, weird valence)
        return 0.5


def process_checkpoint(src_path: Path, dst_path: Path, workers: int) -> dict:
    print(f"[{src_path.stem}] loading...")
    data = json.loads(src_path.read_text())
    results = data.get("results", [])
    print(f"[{src_path.stem}] {len(results)} molecules")

    # Report cache coverage
    already = sum(
        1 for r in results
        if r.get("molchamb_score") is not None
        and r["molchamb_score"] != 0.5
    )
    if already > len(results) * 0.5:
        print(
            f"[{src_path.stem}] WARNING: {already} already have molchamb_score -- "
            f"checkpoint may already be populated. Re-scoring anyway."
        )

    smiles_list = [r.get("smiles", "") for r in results]

    t0 = time.time()
    scores = [None] * len(smiles_list)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(populate_one, s): i for i, s in enumerate(smiles_list)}
        done = 0
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                scores[idx] = fut.result()
            except Exception:
                scores[idx] = 0.5
            done += 1
            if done % 200 == 0 or done == len(smiles_list):
                elapsed = time.time() - t0
                rate = elapsed / max(done, 1)
                eta = rate * (len(smiles_list) - done)
                print(
                    f"  [{src_path.stem}] {done}/{len(smiles_list)} "
                    f"({elapsed:.0f}s, eta {eta:.0f}s, {rate:.3f}s/mol)"
                )

    # Attach new field. NEVER touch existing fields.
    n_added = 0
    n_fallback = 0
    for r, sc in zip(results, scores):
        if sc is None:
            sc = 0.5
        if sc == 0.5:
            n_fallback += 1
        r["molchamb_score"] = round(float(sc), 4)
        n_added += 1

    # Write to DST only
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(data, indent=2))
    elapsed = time.time() - t0
    print(
        f"[{src_path.stem}] wrote {dst_path} | "
        f"added={n_added} | fallback={n_fallback} | "
        f"elapsed={elapsed:.1f}s"
    )
    return {
        "target": src_path.stem,
        "n_molecules": len(results),
        "n_added": n_added,
        "n_fallback": n_fallback,
        "elapsed_sec": round(elapsed, 2),
        "dst_path": str(dst_path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4,
                    help="Threads for xTB realtime evaluation of cache misses.")
    ap.add_argument("--targets", type=str, default="",
                    help="Comma-separated target stems. Empty = all 8.")
    args = ap.parse_args()

    if not SRC_DIR.exists():
        print(f"FATAL: source dir {SRC_DIR} does not exist")
        return 1

    files = sorted(SRC_DIR.glob("benchmark_checkpoint_*.json"))
    if args.targets:
        wanted = {t.strip() for t in args.targets.split(",")
                  if t.strip()}
        files = [
            f for f in files
            if f.stem.replace("benchmark_checkpoint_", "") in wanted
        ]
    if not files:
        print("No matching checkpoint files found.")
        return 1

    print(f"MolChamb populate | src={SRC_DIR}")
    print(f"MolChamb populate | dst={DST_DIR}")
    print(f"MolChamb populate | targets={[f.stem for f in files]}")
    print(f"MolChamb populate | workers={args.workers}")
    print()

    summary = []
    t_start = time.time()
    for src in files:
        dst = DST_DIR / src.name
        try:
            r = process_checkpoint(src, dst, args.workers)
            summary.append(r)
        except Exception as e:
            print(f"[{src.stem}] FAILED: {e}")
            traceback.print_exc()
            summary.append({"target": src.stem, "error": str(e)})

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in summary:
        if "error" in r:
            print(f"  {r['target']:35s} ERROR: {r['error']}")
        else:
            pct_fallback = 100.0 * r["n_fallback"] / max(1, r["n_molecules"])
            print(
                f"  {r['target']:35s} "
                f"mols={r['n_molecules']:5d} "
                f"fallback={r['n_fallback']:4d} ({pct_fallback:.1f}%) "
                f"elapsed={r['elapsed_sec']}s"
            )
    print()
    print(f"Total time: {time.time() - t_start:.1f}s")
    print(f"Output dir: {DST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
