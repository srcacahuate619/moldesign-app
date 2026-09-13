"""
Test Smina vs Vina CPU on 20 molecules each for MMP9 and AChE
"""
import json, time, subprocess, sys, os
from pathlib import Path
from meeko import MoleculePreparation, PDBQTWriterLegacy
from rdkit import Chem
from rdkit.Chem import AllChem

PJ = Path("D:/moldesign-build")
OUT = PJ / "tools" / "smina"
OUT.mkdir(parents=True, exist_ok=True)

RECEPTORS = {
    "mmp9": str(PJ / "data/multitarget/mmp9/1gkc.pdbqt"),
    "ache": str(PJ / "data/multitarget/ache/1gpk_vina.pdbqt"),
}
CENTERS = {
    "mmp9": (53.25, 22.51, 129.72),
    "ache": (8.90, 38.06, 62.49),
}
SIZE = 25

def load_mols(target):
    actives = (PJ / f"data/multitarget/{target}/actives.txt").read_text().splitlines()
    decoys = (PJ / f"data/multitarget/{target}/decoys.smi").read_text().splitlines()
    mols = []
    for line in actives[:10]:
        parts = line.strip().split()
        if parts: mols.append(parts[0])
    for line in decoys[:10]:
        parts = line.strip().split()
        if parts: mols.append(parts[0])
    return mols

def prep_ligand(smiles, path):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return False
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    preparator = MoleculePreparation()
    mol_setup = preparator.prepare(mol)[0]
    pdbqt_str, is_ok, _ = PDBQTWriterLegacy.write_string(mol_setup)
    path.write_text(pdbqt_str)
    return is_ok

def wsl_path(win_path):
    p = Path(win_path)
    rel = p.relative_to("D:\\" if str(p).startswith("D:\\") else p.drive + "\\")
    return f"/mnt/d/{rel.as_posix()}"

def dock_smina(lig_pdbqt, target):
    rc = wsl_path(RECEPTORS[target])
    lg = wsl_path(str(lig_pdbqt))
    cx, cy, cz = CENTERS[target]
    out = lig_pdbqt.with_suffix(".smina_out.pdbqt")
    out_wsl = wsl_path(str(out))
    smina = "/mnt/d/moldesign-build/tools/smina/smina.static"
    cmd = f"wsl -d Ubuntu-22.04 -- {smina} --receptor {rc} --ligand {lg} --center_x {cx} --center_y {cy} --center_z {cz} --size_x {SIZE} --size_y {SIZE} --size_z {SIZE} --exhaustiveness 4 --num_modes 3 --out {out_wsl}"
    t0 = time.time()
    subprocess.run(cmd, shell=True, capture_output=True, timeout=120)
    t = time.time() - t0
    score = None
    if out.exists():
        txt = out.read_text()
        for line in txt.splitlines():
            if "minimizedAffinity" in line:
                try: score = float(line.split()[-1])
                except: pass
                break
    return score, t

def dock_vina(lig_pdbqt, target):
    rc = RECEPTORS[target]
    cx, cy, cz = CENTERS[target]
    out = lig_pdbqt.with_suffix(".vina_out.pdbqt")
    vina = str(PJ / "tools/vina/vina.exe")
    cmd = f'"{vina}" --receptor "{rc}" --ligand "{lig_pdbqt}" --center_x {cx} --center_y {cy} --center_z {cz} --size_x {SIZE} --size_y {SIZE} --size_z {SIZE} --exhaustiveness 4 --num_modes 3 --out "{out}"'
    t0 = time.time()
    subprocess.run(cmd, shell=True, capture_output=True, timeout=300)
    t = time.time() - t0
    score = None
    if out.exists():
        txt = out.read_text()
        for line in txt.splitlines():
            if "VINA RESULT" in line:
                try: score = float(line.split()[3])
                except: pass
                break
    return score, t

for target in ["mmp9", "ache"]:
    print(f"\n===== {target} =====")
    mols = load_mols(target)
    print(f"Mols: {len(mols)}")
    results = []
    for i, smi in enumerate(mols):
        lig = OUT / f"test_{target}_{i}.pdbqt"
        if not prep_ligand(smi, lig):
            print(f"  [{i:2d}] SKIP (prep fail): {smi}")
            continue

        s_smi, t_smi = dock_smina(lig, target)
        s_vina, t_vina = dock_vina(lig, target)

        if s_smi is not None and s_vina is not None:
            d = s_smi - s_vina
            results.append((s_smi, s_vina, d, t_smi, t_vina))
            print(f"  [{i:2d}] smina={s_smi:7.3f} ({t_smi:5.1f}s)  vina={s_vina:7.3f} ({t_vina:5.1f}s)  delta={d:+.3f}")
        else:
            print(f"  [{i:2d}] FAIL  smina={s_smi}  vina={s_vina}")

        # Cleanup
        for f in [lig, lig.with_suffix(".smina_out.pdbqt"), lig.with_suffix(".vina_out.pdbqt")]:
            if f.exists(): f.unlink()

    if results:
        s_smis, s_vs, ds, ts, tvs = zip(*results)
        print(f"\n  SUMMARY {target}: {len(results)} mols")
        print(f"  Smina: mean={sum(s_smis)/len(s_smis):.3f}  mean_time={sum(ts)/len(ts):.1f}s")
        print(f"  Vina:  mean={sum(s_vs)/len(s_vs):.3f}  mean_time={sum(tvs)/len(tvs):.1f}s")
        print(f"  Delta mean={sum(ds)/len(ds):+.3f}  |delta| mean={sum(abs(d) for d in ds)/len(ds):.3f}")
        # Spearman-like ranking comparison
        from scipy.stats import spearmanr
        rho, p = spearmanr(s_smis, s_vs)
        print(f"  Spearman rho={rho:.4f} (p={p:.4f})")
        print(f"  Speedup: {sum(tvs)/sum(ts):.1f}x")
print("\nDone!")
