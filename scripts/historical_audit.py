#!/usr/bin/env python3
"""Historical audit: what did we start but never finish?"""
from pathlib import Path

print("="*65)
print("HISTORICAL AUDIT — Abandoned tasks tracker")
print("="*65)

# 1. MSYS2 Smina build
smina_src = Path("D:/ad-gpu-project/source/smina")
if smina_src.exists():
    build = smina_src / "build"
    print(f"[MSYS2 Smina] Source exists at {smina_src}")
    print(f"  Build dir: {'EXISTS' if build.exists() else 'NOT CREATED'} (compilation never completed)")
else:
    print(f"[MSYS2 Smina] Source NOT found at D:/ad-gpu-project/source/smina")

# 2. 4NY4.pdb re-download
pdb_4ny4 = Path("data/4NY4.pdb")
if pdb_4ny4.exists():
    lines = len(pdb_4ny4.read_text().splitlines())
    kb = pdb_4ny4.stat().st_size / 1024
    print(f"[4NY4.pdb] Exists: {kb:.0f}KB, {lines} lines (expected >20000)")
    if lines < 1000:
        print(f"  ** TRUNCATED — never properly re-downloaded")
else:
    print(f"[4NY4.pdb] NOT FOUND")

# 3. AChE benchmark
ache_dir = Path("data/multitarget/ache")
ache_ckpt = Path("data/benchmark_checkpoint_ache.json")
if ache_dir.exists():
    actives = len(list(ache_dir.glob("*")))
    print(f"[AChE] Data dir: {actives} files. Checkpoint: {'EXISTS' if ache_ckpt.exists() else 'NOT RUN'}")
else:
    print(f"[AChE] NOT SETUP")

# 4. MolChamb for MMP9
mmp9_ckpt = Path("data/benchmark_checkpoint_mmp9.json")
if mmp9_ckpt.exists():
    with open(mmp9_ckpt, "rb") as f:
        chunk = f.read(200*1024).decode("utf-8", errors="replace")
    has_mc = "molchamb_score" in chunk
    print(f"[MMP9 MolChamb] Checkpoint: {'POPULATED' if has_mc else 'NOT POPULATED'} (needs run)")
else:
    print(f"[MMP9 MolChamb] Checkpoint NOT FOUND")

# 5. CLGNN model - retrain needed?
clgnn_path = Path("rescoring/artifacts/clgnn_finetuned.pt")
if clgnn_path.exists():
    import torch
    ck = torch.load(clgnn_path, map_location="cpu", weights_only=False)
    sd = ck.get("model_state_dict", ck)
    if "lig_encoder.in_proj.weight" in sd:
        dim = sd["lig_encoder.in_proj.weight"].shape[1]
        print(f"[CLGNN] Model: {clgnn_path.name} ({clgnn_path.stat().st_size/1024:.0f}KB)")
        print(f"  Input dim: {dim} (code expects 38 — mismatch: {dim != 38})")
else:
    print(f"[CLGNN] Model NOT FOUND at rescoring/artifacts/clgnn_finetuned.pt")

# 6. PDE5A dir name mismatch
pde5_dir = Path("data/multitarget/pde5")
pde5a_dir = Path("data/multitarget/pde5a")
print(f"[PDE5A] TARGET_CONFIGS uses 'multitarget/pde5/'  -> exists: {pde5_dir.exists()}")
print(f"[PDE5A] Curation saved to  'multitarget/pde5a/' -> exists: {pde5a_dir.exists()}")
print(f"  ** DIR NAME MISMATCH!" if pde5_dir.exists() != pde5a_dir.exists() else "  Names match (ok)")

# 7. MolChamb ACE checkpoint (will exist after benchmark)
ace_ckpt = Path("data/benchmark_checkpoint_ace.json")
print(f"[ACE post-benchmark] Checkpoint: {'EXISTS' if ace_ckpt.exists() else 'NOT YET (benchmark running)'}")

# 8. GPU training (suggested but never started)
print(f"[GPU metal-aware GNN-D] Suggested but never started")

# Summary
print("\n" + "="*65)
print("SUMMARY")
print("="*65)
print("UNRESOLVED:")
print("  1. 4NY4.pdb download truncated — never re-downloaded")
print("  2. PDE5A dir name mismatch — TARGET_CONFIGS uses 'pde5', curation uses 'pde5a'")
print("  3. MolChamb NOT populated for MMP9 checkpoint")
print("  4. CLGNN model mismatch (18→38 dim) — needs retraining")
print("  5. Smina Windows compilation incomplete (MSYS2 deps)")
print("  6. AChE benchmark never run")
print("  7. GPU metal-aware GNN-D training never started")
print("  8. MSYS2 job status unknown")
print()
print("RESOLVED IN THIS SESSION:")
print("  ✓ Bootstrap CI (10k iterations, both significant)")
print("  ✓ Thiol pattern fix (captopril detection)")
print("  ✓ Carboxylate pattern fix (protonated form)")
print("  ✓ Proper DUD-E decoys (ACE MW=1.04, PDE5A MW=0.99)")
print("  ✓ ACE PDB fixed (1UZE→1O86 clean)")
print("  ✓ ACE benchmark launched")
print("  ✓ Ablation study (SMARTS-only=85-90%)")
print("  ✓ MW confounder test (r=0.027, p=0.38)")
