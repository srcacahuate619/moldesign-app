#!/usr/bin/env python3
"""Quick test: Smina exhaust=2+minimize vs Vina exhaust=8 on one molecule."""
import json, subprocess, tempfile, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, "scripts")

SMINA_WIN = "D:/moldesign-build/tools/smina/smina.static"
VINA_EXE = "D:/moldesign-build/tools/vina/vina.exe"
REC_WIN = "D:/moldesign-build/data/multitarget/mmp9/1gkc.pdbqt"

def wsl_p(p):
    p = str(Path(p).resolve())
    p = p.replace("\\", "/")
    drive = p[0].lower()
    return f"/mnt/{drive}{p[2:]}"

def prepare_ligand_pdbqt(smi, out_path, seed=42):
    """Prepare ligand PDBQT using RDKit + OpenBabel."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(smi)
    if not mol: return False
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=seed) != 0:
        return False
    AllChem.MMFFOptimizeMolecule(mol)

    # Try PDBQTWriterLegacy first
    try:
        from meeko import PDBQTWriterLegacy, MoleculePreparation
        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        pdbqt_string, is_ok, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
        if is_ok and pdbqt_string:
            with open(out_path, "w") as f:
                f.write(pdbqt_string)
            return True
    except ImportError:
        pass

    # Fallback: OpenBabel
    try:
        sdf = out_path + ".sdf"
        Chem.SDWriter(sdf).write(mol)
        subprocess.run(["obabel", sdf, "-O", out_path, "--gen3d"],
                      capture_output=True, timeout=30)
        os.unlink(sdf)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 50
    except:
        pass

    return False

def vina_dock(smi, exhaust=8, seed=42):
    with tempfile.TemporaryDirectory() as tmp:
        lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
        out_pdbqt = os.path.join(tmp, "out.pdbqt")

        if not prepare_ligand_pdbqt(smi, lig_pdbqt, seed):
            return None, 0

        t0 = time.time()
        try:
            result = subprocess.run([
                VINA_EXE,
                "--receptor", REC_WIN,
                "--ligand", lig_pdbqt,
                "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
                "--size_x", "25", "--size_y", "25", "--size_z", "25",
                "--exhaustiveness", str(exhaust),
                "--num_modes", "3",
                "--out", out_pdbqt,
                "--seed", str(seed),
            ], capture_output=True, text=True, timeout=180)
            elapsed = time.time() - t0
            if os.path.exists(out_pdbqt) and os.path.getsize(out_pdbqt) > 50:
                text = open(out_pdbqt).read()
                for line in text.splitlines():
                    if "REMARK VINA RESULT:" in line:
                        return float(line.split()[3]), elapsed
            return None, elapsed
        except subprocess.TimeoutExpired:
            return None, 180

def smina_dock(smi, exhaust=4, minimize=True, seed=42):
    with tempfile.TemporaryDirectory() as tmp:
        lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
        out_pdbqt = os.path.join(tmp, "out.pdbqt")

        if not prepare_ligand_pdbqt(smi, lig_pdbqt, seed):
            return None, 0

        cmd = [
            "wsl", "-d", "Ubuntu-22.04", "--",
            wsl_p(SMINA_WIN),
            "--receptor", wsl_p(REC_WIN),
            "--ligand", wsl_p(lig_pdbqt),
            "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
            "--size_x", "25", "--size_y", "25", "--size_z", "25",
            "--exhaustiveness", str(exhaust),
            "--num_modes", "3",
            "--out", wsl_p(out_pdbqt),
            "--seed", str(seed),
        ]
        if minimize:
            cmd.append("--minimize")

        # Show command for debugging
        # print(" ".join(cmd))

        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            elapsed = time.time() - t0
            if result.returncode != 0:
                # print(f"STDERR: {result.stderr[:300]}")
                pass
            if os.path.exists(out_pdbqt) and os.path.getsize(out_pdbqt) > 50:
                text = open(out_pdbqt).read()
                # print(f"OUTPUT preview: {text[:500]}")
                for line in text.splitlines():
                    if "REMARK VINA RESULT:" in line:
                        score = float(line.split()[3])
                        return score, elapsed
            return None, elapsed
        except subprocess.TimeoutExpired:
            return None, 180

# ── Test ──
print("Loading checkpoint...")
ckpt = json.loads(open("data/benchmark_checkpoint_mmp9.json","rb").read().decode("utf-8"))

test_mols = []
for r in ckpt["results"]:
    if r.get("is_active") and r.get("vina_score") and abs(r["vina_score"]) > 1:
        test_mols.append(r)
    if len(test_mols) >= 3:
        break

print(f"Testing {len(test_mols)} MMP9 actives\n")

configs = [
    ("Vina exh=8", False, False, 8),
    ("Smina exh=2", False, False, 2),
    ("Smina exh=2+min", True, True, 2),
    ("Smina exh=4+min", True, True, 4),
]

for name, is_smina, minimize, exhaust in configs:
    times = []
    scores = []
    for i, r in enumerate(test_mols):
        smi = r["smiles"]
        if is_smina:
            score, t = smina_dock(smi, exhaust=exhaust, minimize=minimize)
        else:
            score, t = vina_dock(smi, exhaust=exhaust)

        status = f"score={score:.1f}" if score else "FAIL"
        times.append(t)
        if score: scores.append(score)
        ref = r["vina_score"]
        print(f"  {name:20s} [{i+1}] {status:12s} time={t:.1f}s  ref={ref:.1f}")

    if scores and times:
        refs = [r["vina_score"] for r in test_mols[:len(scores)]]
        from scipy.stats import pearsonr
        corr, _ = pearsonr(scores, refs)
        print(f"  {'':20s} => mean_score={np.mean(scores):.2f} mean_time={np.mean(times):.1f}s corr_vina={corr:.3f}")
    print()
