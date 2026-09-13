#!/usr/bin/env python3
"""
Smina speed/quality test vs Vina.
Hypothesis: Smina exhaust=2 + --minimize ≥ Vina exhaust=8 quality, 2-4x faster.
"""
import json, subprocess, time, sys, os, tempfile
from pathlib import Path
import numpy as np

SMINA = "D:/moldesign-build/tools/smina/smina.static"
VINA_EXE = "D:/moldesign-build/tools/vina/vina.exe"
WSL = ["wsl", "-d", "Ubuntu-22.04", "--"]

# MMP9 receptor
RECEPTOR_PDBQT = "D:/moldesign-build/data/multitarget/mmp9/1gkc.pdbqt"
BOX_CX, BOX_CY, BOX_CZ = 53.25, 22.51, 129.72
BOX_SIZE = 25

def wsl_path(win_path):
    """Convert Windows path to WSL path."""
    path = str(Path(win_path).resolve())
    # Convert D:\x\y to /mnt/d/x/y
    path = path.replace("\\", "/")
    drive = path[0].lower()
    return f"/mnt/{drive}{path[2:]}"

def run_smina(smiles, exhaust=4, num_modes=3, minimize=False, seed=42):
    """Run Smina docking via WSL."""
    # Prepare ligand
    with tempfile.TemporaryDirectory() as tmp:
        lig_sdf = os.path.join(tmp, "lig.sdf")
        out_pdbqt = os.path.join(tmp, "out.pdbqt")
        lig_pdbqt = os.path.join(tmp, "lig.pdbqt")

        # Convert SMILES to 3D SDF via RDKit
        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None, None
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=seed)
        AllChem.MMFFOptimizeMolecule(mol)
        writer = Chem.SDWriter(lig_sdf)
        writer.write(mol)
        writer.close()

        # Build Smina command
        lig_wsl = wsl_path(lig_sdf)
        out_wsl = wsl_path(out_pdbqt)
        rec_wsl = wsl_path(RECEPTOR_PDBQT)

        cmd = WSL + [
            SMINA.replace("D:", "/mnt/d").replace("moldesign-build", "moldesign-build").replace("\\", "/"),
            "--receptor", rec_wsl,
            "--ligand", lig_wsl,
            "--center_x", str(BOX_CX), "--center_y", str(BOX_CY), "--center_z", str(BOX_CZ),
            "--size_x", str(BOX_SIZE), "--size_y", str(BOX_SIZE), "--size_z", str(BOX_SIZE),
            "--exhaustiveness", str(exhaust),
            "--num_modes", str(num_modes),
            "--out", out_wsl,
            "--seed", str(seed),
        ]
        if minimize:
            cmd.append("--minimize")

        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elapsed = time.time() - t0

            if result.returncode != 0:
                return None, elapsed

            # Parse output PDBQT for scores
            if os.path.exists(out_pdbqt):
                with open(out_pdbqt) as f:
                    content = f.read()
                # Extract score from REMARK lines
                scores = []
                for line in content.splitlines():
                    if "REMARK VINA RESULT:" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            scores.append(float(parts[3]))
                if scores:
                    return scores[0], elapsed  # Best score
            return None, elapsed
        except subprocess.TimeoutExpired:
            return None, 120.0


def run_vina(smiles, exhaust=8, num_modes=3):
    """Run Vina CPU docking."""
    with tempfile.TemporaryDirectory() as tmp:
        lig_sdf = os.path.join(tmp, "lig.sdf")
        lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
        out_pdbqt = os.path.join(tmp, "out.pdbqt")

        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None, None
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)

        # Convert to PDBQT via OpenBabel if possible, else use obabel
        sdf_path = lig_sdf
        writer = Chem.SDWriter(sdf_path)
        writer.write(mol)
        writer.close()

        # Convert SDF to PDBQT using obabel
        subprocess.run([
            "obabel", sdf_path,
            "-O", lig_pdbqt,
            "--gen3d", "--minimize",
        ], capture_output=True, timeout=30)

        lig_pdbqt_path = lig_pdbqt if os.path.exists(lig_pdbqt) and os.path.getsize(lig_pdbqt) > 10 else None
        if not lig_pdbqt_path:
            # Fallback: use RDKit PDBQT
            from rdkit.Chem import MolToPDBQTBlock
            lig_pdbqt_path = lig_pdbqt
            with open(lig_pdbqt_path, "w") as f:
                f.write(MolToPDBQTBlock(mol))

        t0 = time.time()
        try:
            cmd = [
                VINA_EXE,
                "--receptor", RECEPTOR_PDBQT,
                "--ligand", lig_pdbqt_path,
                "--center_x", str(BOX_CX), "--center_y", str(BOX_CY), "--center_z", str(BOX_CZ),
                "--size_x", str(BOX_SIZE), "--size_y", str(BOX_SIZE), "--size_z", str(BOX_SIZE),
                "--exhaustiveness", str(exhaust),
                "--num_modes", str(num_modes),
                "--out", out_pdbqt,
                "--seed", "42",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elapsed = time.time() - t0

            if os.path.exists(out_pdbqt):
                with open(out_pdbqt) as f:
                    content = f.read()
                scores = []
                for line in content.splitlines():
                    if "REMARK VINA RESULT:" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            scores.append(float(parts[3]))
                if scores:
                    return scores[0], elapsed
            return None, elapsed
        except subprocess.TimeoutExpired:
            return None, 120.0


# ── Main test ──
print("="*65)
print("SMINA vs VINA: Speed/Quality Tradeoff Test")
print("="*65)
print(f"Receptor: MMP9 (1gkc)")
print(f"Grid: [{BOX_CX}, {BOX_CY}, {BOX_CZ}], size={BOX_SIZE}")
print()

# Load 10 random MMP9 molecules from checkpoint
ckpt = json.loads(Path("data/benchmark_checkpoint_mmp9.json").read_bytes().decode("utf-8"))
results = ckpt["results"]

# Get actives and decoys with Vina reference scores
ref_mols = []
for r in results:
    if r.get("vina_score") is not None and r.get("pose_pdbqt"):
        ref_mols.append(r)
        if len(ref_mols) >= 10:
            break

print(f"Testing {len(ref_mols)} molecules (5 active + 5 decoy target, got {sum(1 for r in ref_mols if r['is_active'])} actives)")

configs = [
    ("Vina exh=8", False, 8),
    ("Smina exh=8", False, 8),
    ("Smina exh=4 +min", True, 4),
    ("Smina exh=2 +min", True, 2),
]

results_table = []

for name, minimize, exhaust in configs:
    scores = []
    times = []
    for i, mol in enumerate(ref_mols):
        smi = mol["smiles"]
        if "vina" in name.lower() and "smina" not in name.lower():
            score, elapsed = run_vina(smi, exhaust=exhaust)
        else:
            score, elapsed = run_smina(smi, exhaust=exhaust, minimize=minimize)

        status = "OK" if score is not None else "FAIL"
        print(f"  {name:20s} [{i+1}/{len(ref_mols)}] {status:4s} score={score or 'N/A':>7s} time={elapsed:.1f}s")
        if score is not None:
            scores.append(score)
            times.append(elapsed)

    if scores:
        ref_vina_scores = [r["vina_score"] for r in ref_mols[:len(scores)]]
        from scipy.stats import pearsonr
        corr, p_corr = pearsonr(scores, ref_vina_scores)
        results_table.append({
            "name": name,
            "exhaust": exhaust,
            "minimize": minimize,
            "n_ok": len(scores),
            "n_total": len(ref_mols),
            "mean_score": np.mean(scores),
            "mean_time": np.mean(times),
            "time_per_mol": np.mean(times),
            "corr_vina": corr,
            "speedup_vs_vina8": None,  # computed below
        })

# Compute speedups
vina8_time = next(r["mean_time"] for r in results_table if "Vina exh=8" in r["name"])
for r in results_table:
    r["speedup_vs_vina8"] = vina8_time / r["mean_time"] if r["mean_time"] > 0 else 0

print(f"\n{'='*65}")
print(f"{'METHOD':22s} | {'OK':3s} | {'Score mean':10s} | {'Time(s)':8s} | {'Corr w/ Vina8':13s} | {'Speedup':8s}")
print("-"*80)
for r in results_table:
    print(f"{r['name']:22s} | {r['n_ok']:2d} | {r['mean_score']:10.2f} | {r['mean_time']:8.1f} | {r['corr_vina']:+13.4f} | {r['speedup_vs_vina8']:8.2f}x")

print()
print(f"Vina-exh=8 baseline: {vina8_time:.1f}s/mol")
print(f"Target: >=2x speedup with >=0.90 score correlation")
