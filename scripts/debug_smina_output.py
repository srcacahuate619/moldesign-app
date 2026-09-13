#!/usr/bin/env python3
"""Debug: what does Smina --minimize output look like?"""
import json, subprocess, tempfile, os, time
from pathlib import Path
from meeko import MoleculePreparation, PDBQTWriterLegacy
from rdkit import Chem
from rdkit.Chem import AllChem

SMINA_WIN = "D:/moldesign-build/tools/smina/smina.static"
REC_WIN = "D:/moldesign-build/data/multitarget/mmp9/1gkc.pdbqt"

def wsl_p(p):
    p = str(Path(p).resolve()).replace("\\", "/")
    return f"/mnt/{p[0].lower()}{p[2:]}"

# Load one molecule
ckpt = json.loads(open("data/benchmark_checkpoint_mmp9.json","rb").read().decode("utf-8"))
for r in ckpt["results"]:
    if r.get("is_active"):
        smi = r["smiles"]
        break

# Prepare ligand PDBQT
tmp = tempfile.mkdtemp()
lig_pdbqt = os.path.join(tmp, "lig.pdbqt")
out_pdbqt = os.path.join(tmp, "out.pdbqt")

mol = Chem.MolFromSmiles(smi)
mol = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol, randomSeed=42)
AllChem.MMFFOptimizeMolecule(mol)
prep = MoleculePreparation()
setups = prep.prepare(mol)
pdbqt_str, ok, _ = PDBQTWriterLegacy.write_string(setups[0])
open(lig_pdbqt, "w").write(pdbqt_str)
print(f"Ligand PDBQT: {len(pdbqt_str)} bytes, ok={ok}")
print(f"SMILES: {smi[:80]}")

# Test 1: Smina exh=2 without minimize (should work)
cmd1 = ["wsl", "-d", "Ubuntu-22.04", "--", wsl_p(SMINA_WIN),
        "--receptor", wsl_p(REC_WIN), "--ligand", wsl_p(lig_pdbqt),
        "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
        "--size_x", "25", "--size_y", "25", "--size_z", "25",
        "--exhaustiveness", "2", "--num_modes", "1",
        "--out", wsl_p(out_pdbqt), "--seed", "42"]
print(f"\nTest 1: Smina exh=2 (no minimize)")
r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=120)
if os.path.exists(out_pdbqt):
    txt1 = open(out_pdbqt).read()
    for line in txt1.splitlines()[:10]:
        if "REMARK" in line or "MODEL" in line or "ENDMDL" in line:
            print(f"  {line.strip()}")

# Test 2: Smina exh=2 WITH minimize
out_pdbqt2 = os.path.join(tmp, "out2.pdbqt")
cmd2 = ["wsl", "-d", "Ubuntu-22.04", "--", wsl_p(SMINA_WIN),
        "--receptor", wsl_p(REC_WIN), "--ligand", wsl_p(lig_pdbqt),
        "--center_x", "53.25", "--center_y", "22.51", "--center_z", "129.72",
        "--size_x", "25", "--size_y", "25", "--size_z", "25",
        "--exhaustiveness", "2", "--num_modes", "1",
        "--out", wsl_p(out_pdbqt2), "--minimize", "--seed", "42"]
print(f"\nTest 2: Smina exh=2 WITH --minimize")
r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
print(f"  Return code: {r2.returncode}")
print(f"  STDERR: {r2.stderr[:200] if r2.stderr else '(empty)'}")
if os.path.exists(out_pdbqt2):
    txt2 = open(out_pdbqt2).read()
    print(f"  Output size: {len(txt2)} bytes")
    for line in txt2.splitlines()[:15]:
        print(f"  {line.strip()}")
    # Search for score in all REMARK lines
    for line in txt2.splitlines():
        if "REMARK" in line and ("RESULT" in line or "score" in line.lower()):
            print(f"  SCORE LINE: {line.strip()}")
else:
    print(f"  Output file NOT created")
    # Check stderr
    if r2.stderr:
        print(f"  STDERR full: {r2.stderr[:500]}")
