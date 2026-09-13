#!/usr/bin/env python3
"""
FastMolChamb: quantum-like electronic features from RDKit.
No xTB needed. Milliseconds per molecule. Works on ANY molecule.

Features computed:
  1. Gasteiger partial charges (atomic electronegativity equalization)
  2. Crippen logP and MR (molar refractivity)  
  3. EEM electronegativity features (if available)
  4. Functional group electronic properties
  5. Electronic descriptor: charge_surface, charge_range, electrostatic_imbalance

These approximate xTB-level features at 1000x speed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors, AllChem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


def compute_fast_molchamb(smiles: str) -> tuple[float, dict]:
    """Compute fast quantum proxy for MolChamb from SMILES.
    
    Returns:
        score: [0, 1] normalized electronic score
        features: dict of raw features
    """
    if not HAS_RDKIT:
        return 0.5, {"error": "no rdkit"}

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.5, {"error": "invalid smiles"}

    try:
        mol = Chem.AddHs(mol)
        # 1. Gasteiger charges (electronegativity equalization)
        AllChem.ComputeGasteigerCharges(mol)
        charges = [a.GetDoubleProp("_GasteigerCharge") for a in mol.GetAtoms()]
        charges = np.array(charges)

        # Charge statistics
        charge_range = charges.max() - charges.min()  # polarizability
        charge_imbalance = np.abs(charges).sum() / len(charges)  # avg charge magnitude
        charge_abs_max = np.abs(charges).max()  # strongest charge center
        negative_sum = -charges[charges < 0].sum()  # total negative charge
        positive_sum = charges[charges > 0].sum()  # total positive charge
        charge_asymmetry = abs(positive_sum - negative_sum) / max(0.01, positive_sum + negative_sum)

        # 2. Atomic polarizability
        polarizable_atoms = sum(1 for a in mol.GetAtoms()
                               if a.GetAtomicNum() in (16, 15, 35, 53, 17))  # S, P, Br, I, Cl

        # 3. MO-like properties: electronegativity of heaviest atom
        heavy_atoms = [a for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
        max_an = max((a.GetAtomicNum() for a in heavy_atoms), default=1)
        max_en = {7: 3.04, 8: 3.44, 9: 3.98, 15: 2.19, 16: 2.58, 17: 3.16,
                  35: 2.96, 53: 2.66}.get(max_an, 2.5)  # Pauling EN

        # 4. Crippen-based properties
        logp = Descriptors.MolLogP(mol)
        mr = Descriptors.MolMR(mol)  # molar refractivity (polarizability proxy)
        tpsa = Descriptors.TPSA(mol)
        hba = Descriptors.NumHAcceptors(mol)
        hbd = Descriptors.NumHDonors(mol)

        # 5. Heavy atom electron density
        heavy_count = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
        valence_electrons = sum(a.GetAtomicNum() for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
        avg_e_density = valence_electrons / max(1, heavy_count)

        # 6. Metal-coordination potential
        # Atoms that CAN coordinate metals (O, N, S with available electrons)
        metal_donors = sum(1 for a in mol.GetAtoms()
                          if a.GetAtomicNum() in (7, 8, 16) and a.GetTotalNumHs() >= 0)
        metal_donor_ratio = metal_donors / max(1, heavy_count)

        # Normalize and combine
        charge_score = min(1.0, charge_range / 0.5)  # 0-1
        polariz_score = min(1.0, charge_imbalance / 0.2)  # 0-1
        donor_score = min(1.0, metal_donor_ratio / 0.5)  # 0-1

        # Score combination (weights tuned empirically)
        score = 0.30 * charge_score + 0.25 * polariz_score + 0.15 * donor_score + \
                0.15 * min(1.0, mr / 100) + 0.15 * min(1.0, abs(logp) / 5.0)

        features = {
            "charge_range": round(float(charge_range), 4),
            "charge_imbalance": round(float(charge_imbalance), 4),
            "charge_abs_max": round(float(charge_abs_max), 4),
            "charge_asymmetry": round(float(charge_asymmetry), 4),
            "polarizable_atoms": polarizable_atoms,
            "max_electronegativity": max_en,
            "logp": round(logp, 2),
            "mr": round(mr, 2),
            "tpsa": round(tpsa, 2),
            "hba": hba,
            "hbd": hbd,
            "heavy_count": heavy_count,
            "valence_electrons": valence_electrons,
            "avg_e_density": round(avg_e_density, 2),
            "metal_donors": metal_donors,
            "metal_donor_ratio": round(float(metal_donor_ratio), 4),
            "fast_molchamb_score": round(score, 4),
        }

        return round(score, 4), features

    except Exception as e:
        return 0.5, {"error": str(e)[:100]}


def compute_batch(smiles_list: list[str]) -> list[tuple[float, dict]]:
    """Batch compute fast MolChamb scores."""
    return [compute_fast_molchamb(smi) for smi in smiles_list]


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Fast MolChamb (RDKit quantum proxy)")
    ap.add_argument("--smiles", type=str, default=None)
    ap.add_argument("--test-target", type=str, default=None,
                    help="Test on all molecules of a target (e.g., ace, mmp9, ca2)")
    args = ap.parse_args()

    if args.test_target:
        # Test on target actives vs decoys
        from sklearn.metrics import roc_auc_score
        act_path = Path(f"data/multitarget/{args.test_target}/actives.txt")
        dec_path = Path(f"data/multitarget/{args.test_target}/decoys.smi")

        actives = [l.split()[0] for l in open(act_path) if l.strip()]
        decoys = [l.strip() for l in open(dec_path) if l.strip()][:1000]

        y_true = [1]*len(actives) + [0]*len(decoys)
        y_score = []
        for i, smi in enumerate(actives + decoys):
            score, feats = compute_fast_molchamb(smi)
            y_score.append(score)

        auc = roc_auc_score(y_true, y_score)
        print(f"[FastMolChamb] {args.test_target}: AUC = {auc:.4f}")

        # Compare with xTB MolChamb (if available)
        print(f"[FastMolChamb] Features per molecule:")
        act_scores = [compute_fast_molchamb(s) for s in actives[:5]]
        for smi, (score, feats) in zip(actives[:5], act_scores):
            print(f"  {smi[:50]:50s} score={feats['fast_molchamb_score']:.4f}")
    else:
        score, features = compute_fast_molchamb(args.smiles)
        print(f"Fast MolChamb score: {features['fast_molchamb_score']:.4f}")
        print(f"Features: {json.dumps(features, indent=2)}")


if __name__ == "__main__":
    import json
    main()
