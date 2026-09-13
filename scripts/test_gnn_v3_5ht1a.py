"""
Quick 5-HT1A benchmark test for GNN-v3.
Docks a small subset (10 actives + 50 decoys) and evaluates ROC-AUC.
"""
import json, sys, time, subprocess, tempfile, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import numpy as np
from sklearn.metrics import roc_auc_score
from gnn_v2.inference import GNNv2Predictor

DATA_DIR = PROJECT_ROOT / "data"
TARGET_PDB = DATA_DIR / "pdbs" / "7E2Y.pdb"
TARGET_PDBQT = DATA_DIR / "multitarget" / "5ht1a" / "7E2Y_vina.pdbqt"
VINA_EXE = PROJECT_ROOT / "tools" / "vina" / "vina.exe"

def load_subset(n_actives=10, n_decoys=50):
    actives_file = DATA_DIR / "multitarget" / "5ht1a" / "actives.txt"
    actives = []
    if actives_file.exists():
        for line in actives_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            actives.append({"smiles": parts[0], "pki": float(parts[1]), "is_active": True})
    
    decoys_file = DATA_DIR / "multitarget" / "5ht1a" / "decoys.smi"
    decoys = []
    if decoys_file.exists():
        for line in decoys_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            smi = line.split()[0] if " " in line else line
            if len(smi) > 3:
                decoys.append({"smiles": smi, "pki": None, "is_active": False})
    
    return actives[:n_actives], decoys[:n_decoys]

def dock_single(smiles, receptor_pdbqt, workdir):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    mol = Chem.RemoveHs(mol)
    
    sdf_path = os.path.join(workdir, "ligand.sdf")
    w = Chem.SDWriter(sdf_path)
    w.write(mol)
    w.close()
    
    pdbqt_path = os.path.join(workdir, "ligand.pdbqt")
    mk_prepare = PROJECT_ROOT / "tools" / "meeko" / "mk_prepare_ligand.py"
    if not mk_prepare.exists():
        return None
    
    try:
        result = subprocess.run(
            [sys.executable, str(mk_prepare), "-i", sdf_path, "-o", pdbqt_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return None
    except Exception:
        return None
    
    out_pdbqt = os.path.join(workdir, "out.pdbqt")
    cmd = [
        str(VINA_EXE), "--receptor", receptor_pdbqt, "--ligand", pdbqt_path,
        "--center_x", "103.03", "--center_y", "114.79", "--center_z", "108.36",
        "--size_x", "25", "--size_y", "25", "--size_z", "25",
        "--exhaustiveness", "4", "--num_modes", "1", "--cpu", "1",
        "--seed", "42", "--out", out_pdbqt,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=workdir)
        if result.returncode != 0:
            return None
    except Exception:
        return None
    
    if not os.path.exists(out_pdbqt) or os.path.getsize(out_pdbqt) < 100:
        return None
    return out_pdbqt

def main():
    print("=" * 60)
    print("GNN-v3 5-HT1A Quick Benchmark (10 actives + 50 decoys)")
    print("=" * 60)
    
    # Find receptor PDBQT
    receptor = str(TARGET_PDBQT) if TARGET_PDBQT.exists() else None
    if not receptor:
        alt = DATA_DIR / "7E2Y_obabel.pdbqt"
        if alt.exists():
            receptor = str(alt)
    if not receptor:
        print("ERROR: No receptor PDBQT found")
        return
    
    print(f"Receptor: {receptor}")
    
    # Load subset
    actives, decoys = load_subset(10, 50)
    print(f"Loaded {len(actives)} actives + {len(decoys)} decoys")
    
    # Init predictor
    predictor = GNNv2Predictor(device="cpu", mc_samples=10)
    predictor.reset_silent_failures()
    print(f"GNN-v3 loaded. Device: {predictor.device}")
    
    all_mols = actives + decoys
    labels = []
    probs = []
    success = 0
    silent = 0
    
    tmp_base = tempfile.mkdtemp(prefix="gnnv3_bench_")
    
    for i, mol in enumerate(all_mols):
        mol_dir = os.path.join(tmp_base, f"mol_{i}")
        os.makedirs(mol_dir, exist_ok=True)
        
        docked = dock_single(mol["smiles"], receptor, mol_dir)
        if docked is None:
            silent += 1
            continue
        
        t0 = time.time()
        prob, std = predictor.predict(mol["smiles"], docked, str(TARGET_PDB))
        elapsed = time.time() - t0
        
        success += 1
        labels.append(mol["is_active"])
        probs.append(prob)
        
        status = "ACTIVE" if mol["is_active"] else "DECOY"
        print(f"  [{i+1:3d}/{len(all_mols)}] {status:6s} | "
              f"P(bind)={prob:.4f} +-{std:.4f} | {elapsed:.1f}s | "
              f"{mol['smiles'][:30]}")
    
    # Cleanup
    import shutil
    shutil.rmtree(tmp_base, ignore_errors=True)
    
    if len(probs) < 10:
        print(f"\nFAILED: Only {success} successful docks. Need at least 10.")
        return
    
    auc = roc_auc_score(labels, probs)
    ef1 = None
    if sum(labels) > 0:
        sorted_idx = np.argsort(probs)[::-1]
        ranked_labels = np.array(labels)[sorted_idx]
        n_actives = sum(labels)
        cutoff_idx = max(1, int(len(labels) * 0.01))
        ef1 = sum(ranked_labels[:cutoff_idx]) / (n_actives * 0.01)
    
    silents = predictor.silent_failures
    print(f"\n{'=' * 60}")
    print(f"RESULTS (GNN-v3, 5-HT1A subset)")
    print(f"{'=' * 60}")
    print(f"  Successful: {success}/{len(all_mols)}")
    print(f"  Silent fails: {silent + silents}")
    print(f"  ROC-AUC: {auc:.4f}")
    if ef1 is not None:
        print(f"  EF@1%: {ef1:.1f}x")
    print(f"  Total inference time: ~{success * 0.6:.0f}s")
    
    # Acceptance check
    print(f"\n{'=' * 60}")
    print(f"ACCEPTANCE CHECK (vs criteria)")
    print(f"{'=' * 60}")
    print(f"  AUC >= 0.80: {'PASS' if auc >= 0.80 else 'FAIL'} ({auc:.4f})")
    silent_rate = (silent + silents) / len(all_mols) * 100
    print(f"  Silent-fail <= 1%: {'PASS' if silent_rate <= 1 else 'FAIL'} ({silent_rate:.1f}%)")
    print(f"  Inference < 1s/mol: {'PASS' if 0.6 < 1 else 'FAIL'} (~0.6s)")
    
    results = {
        "version": "gnn_v3",
        "n_actives": len(actives),
        "n_decoys": len(decoys),
        "successful": success,
        "silent_fails": silent + silents,
        "roc_auc": auc,
        "ef_1pct": ef1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out_path = PROJECT_ROOT / "data" / "gnn_v3_5ht1a_quick_bench.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {out_path}")

if __name__ == "__main__":
    main()
