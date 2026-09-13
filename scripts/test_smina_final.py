#!/usr/bin/env python3
"""Complete Smina vs Vina speed/quality test."""
import json, subprocess, tempfile, os, time
from pathlib import Path
from meeko import MoleculePreparation, PDBQTWriterLegacy
from rdkit import Chem; from rdkit.Chem import AllChem
import numpy as np

SMINA_WIN = "D:/moldesign-build/tools/smina/smina.static"
VINA_EXE = "D:/moldesign-build/tools/vina/vina.exe"
REC_WIN = "D:/moldesign-build/data/multitarget/mmp9/1gkc.pdbqt"

def wsl_p(p):
    p = str(Path(p).resolve()).replace("\\", "/")
    return f"/mnt/{p[0].lower()}{p[2:]}"

def prep_lig(smi, out, seed=42):
    mol = Chem.MolFromSmiles(smi); mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=seed) != 0: return False
    AllChem.MMFFOptimizeMolecule(mol)
    prep = MoleculePreparation(); setups = prep.prepare(mol)
    if not setups: return False
    pdbqt, ok, _ = PDBQTWriterLegacy.write_string(setups[0])
    if not ok: return False
    open(out, "w").write(pdbqt)
    return True

def vina_dock(smi, out, exhaust=8, seed=42):
    with tempfile.TemporaryDirectory() as tmp:
        lig = os.path.join(tmp, "lig.pdbqt")
        if not prep_lig(smi, lig, seed): return None, 0
        t0 = time.time()
        r = subprocess.run([VINA_EXE, "--receptor", REC_WIN, "--ligand", lig,
            "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
            "--size_x", "25", "--size_y", "25", "--size_z", "25",
            "--exhaustiveness", str(exhaust), "--num_modes", "3",
            "--out", out, "--seed", str(seed)],
            capture_output=True, timeout=180)
        elapsed = time.time() - t0
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 50:
            for line in open(out).read().splitlines():
                if "REMARK VINA RESULT:" in line:
                    return float(line.split()[3]), elapsed
        return None, elapsed

def smina_dock(smi, out, exhaust=4, seed=42):
    with tempfile.TemporaryDirectory() as tmp:
        lig = os.path.join(tmp, "lig.pdbqt")
        if not prep_lig(smi, lig, seed): return None, 0
        t0 = time.time()
        r = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "--", wsl_p(SMINA_WIN),
            "--receptor", wsl_p(REC_WIN), "--ligand", wsl_p(lig),
            "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
            "--size_x", "25", "--size_y", "25", "--size_z", "25",
            "--exhaustiveness", str(exhaust), "--num_modes", "3",
            "--out", wsl_p(out), "--seed", str(seed)],
            capture_output=True, timeout=180)
        elapsed = time.time() - t0
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 50:
            for line in open(out).read().splitlines():
                if "minimizedAffinity" in line and "REMARK" in line:
                    score = float(line.split()[2])
                    if score != 0:  # Skip minimization failures
                        return score, elapsed
            return None, elapsed

# ── Test ──
ckpt = json.loads(open("data/benchmark_checkpoint_mmp9.json","rb").read().decode("utf-8"))
test_mols = [r for r in ckpt["results"] if r.get("is_active") and r.get("vina_score") and abs(r["vina_score"])>1][:5]

ref_scores = [r["vina_score"] for r in test_mols]
smiles = [r["smiles"] for r in test_mols]
print(f"Reference scores (Vina exh=8 in benchmark): {[f'{s:.1f}' for s in ref_scores]}")
print(f"Testing {len(test_mols)} molecules\n")

configs = [
    ("Vina exh=8", "vina", 8),
    ("Vina exh=4", "vina", 4),
    ("Vina exh=2", "vina", 2),
    ("Smina exh=4", "smina", 4),
    ("Smina exh=2", "smina", 2),
]

TMPDIR = "data/molchamb_loto/smina_test"
os.makedirs(TMPDIR, exist_ok=True)

results = {}
for name, engine, exhaust in configs:
    scores, times = [], []
    for i, smi in enumerate(smiles):
        out = os.path.join(TMPDIR, f"{name.replace(' ','_')}_{i}.pdbqt")
        if engine == "vina":
            score, t = vina_dock(smi, out, exhaust=exhaust)
        else:
            score, t = smina_dock(smi, out, exhaust=exhaust)
        scores.append(score or float("nan"))
        times.append(t)
    scores = np.array(scores)
    times = np.array(times)
    from scipy.stats import pearsonr
    corr, _ = pearsonr(scores, ref_scores)
    results[name] = {"exhaust": exhaust, "scores": scores, "times": times, "corr": corr,
                     "mean_score": np.nanmean(scores), "mean_time": np.nanmean(times)}
    print(f"{name:18s} | score={results[name]['mean_score']:+.2f} | time={results[name]['mean_time']:5.1f}s | corr_vina8={corr:+.3f} | scores={[f'{s:.1f}' for s in scores]}")

# Speedup table
v8_t = results["Vina exh=8"]["mean_time"]
print(f"\n{'='*70}")
print(f"{'Method':18s} | {'Speedup':8s} | {'Score corr':10s} | {'Mean score':10s}")
print("-"*55)
for name, r in results.items():
    sp = v8_t / r["mean_time"] if r["mean_time"] > 0 else 0
    print(f"{name:18s} | {sp:8.2f}x | {r['corr']:+10.3f} | {r['mean_score']:+10.2f}")
v4_t = results["Vina exh=4"]["mean_time"]; v4_sp = v8_t / v4_t
print(f"\nVina exh=4 speedup: {v4_sp:.2f}x (direct CPU improvement)")
print(f"Best Smina exh=2 vs Vina exh=8: {v8_t/results['Smina exh=2']['mean_time']:.2f}x")
