#!/usr/bin/env python3
"""Replicate the exact benchmark main loop to find the hang."""
import sys, os, time, concurrent.futures, random
sys.path.insert(0, r"D:\moldesign-build\scripts")
sys.path.insert(0, r"D:\moldesign-build\backend")
sys.path.insert(0, r"D:\moldesign-build\rescoring")
os.chdir(r"D:\moldesign-build")

from pathlib import Path
import benchmark_ef_vina as bm
bm.PROJECT_ROOT = Path(r"D:\moldesign-build")
bm.DATA_DIR = bm.PROJECT_ROOT / "data"

# Exact same setup as main()
receptor_config = bm._get_target_path("1o86")
actives, decoys = bm.load_dataset("1o86")
random.seed(42)

n_decoys = min(len(decoys), 50)
n_actives_to_use = min(50, len(actives))
mols = actives[:n_actives_to_use] + decoys[:n_decoys]
random.shuffle(mols)
print(f"Mols: {len(mols)} (actives: {sum(1 for m in mols if m['is_active'])}")

completed = set()
results = []
t0 = time.time()

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    futures = {executor.submit(bm.dock_and_extract, m, receptor_config): m for m in mols}
    print(f"Submitted {len(futures)} futures")
    
    for i, future in enumerate(concurrent.futures.as_completed(futures)):
        mol = futures[future]
        try:
            r = future.result(timeout=300)
            if r:
                prob, xgb_score, delta = bm.score_with_classifier(r, engine="cpu")
                vina = abs(r.get("vina_score", 0)) if r.get("vina_score") else 0
                vina_norm = min(1.0, vina / 12.0)
                if prob is not None and prob > 0.01:
                    r["composite"] = round(prob * 0.70 + vina_norm * 0.30, 4)
                else:
                    r["composite"] = round(vina_norm, 4)
                results.append(r)
            else:
                print(f"  [{i}] DOCK FAILED: no result")
        except Exception as e:
            print(f"  [{i}] EXCEPTION: {type(e).__name__}: {e}")
        completed.add(mol["smiles"])
        
        elapsed = time.time() - t0
        rate = elapsed / max(len(completed), 1)
        remaining = rate * (len(mols) - len(completed))
        print(f"  [{len(completed)}/{len(mols)}] elapsed={elapsed:.0f}s rate={rate:.2f}s/mol remaining={remaining:.0f}s vina={r.get('vina_score') if r else 'N/A'} prob={prob if 'prob' in dir() else 'N/A'}")

print(f"\nDONE: {len(results)} results, {len(completed)} completed in {time.time()-t0:.1f}s")
print(f"Avg rate: {(time.time()-t0)/max(len(completed),1):.2f}s/mol")
