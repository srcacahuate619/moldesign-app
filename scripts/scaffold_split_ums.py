#!/usr/bin/env python3
"""
Scaffold split (Murcko) for CA2 and MMP9 to refute DUD-E tautology charge.

DUD-E tautology charge: "actives are all sulfonamides, decoys are non-sulfonamides, 
so UMS just detects sulfonamide = trivial separation".

Refutation: if we split by Murcko scaffold (core ring system), keeping the SAME warhead
but DIFFERENT scaffolds in test vs train, UMS should still work on test scaffolds
because it detects the WARHEAD (sulfonamide), not the scaffold.

If UMS AUC on test scaffolds > 0.7 (significantly above random), the tautology charge fails.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
import random
import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from universal_metal_score import compute_universal_metal_score

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "multitarget"

TARGETS = ["ca2", "mmp9", "ace"]  # ACE has carboxylate/thiol warhead too

def load_smiles(filepath):
    """Load SMILES from file, one per line (or space-separated)."""
    smis = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            smi = line.split()[0]
            if Chem.MolFromSmiles(smi):
                smis.append(smi)
    return smis

def get_murcko_scaffold(smiles):
    """Get Murcko scaffold SMILES for a molecule."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        return None
    return Chem.MolToSmiles(scaffold)

def scaffold_split(smiles_list, test_frac=0.2, seed=42):
    """Split smiles by Murcko scaffold. Returns (train_smiles, test_smiles)."""
    # Group by scaffold
    scaffold_to_smiles = defaultdict(list)
    for smi in smiles_list:
        scaffold = get_murcko_scaffold(smi)
        if scaffold:
            scaffold_to_smiles[scaffold].append(smi)
        else:
            scaffold_to_smiles["__NO_SCAFFOLD__"].append(smi)
    
    # Shuffle scaffolds and split
    scaffolds = list(scaffold_to_smiles.keys())
    random.seed(seed)
    random.shuffle(scaffolds)
    
    n_test_scaffolds = max(1, int(len(scaffolds) * test_frac))
    test_scaffolds = set(scaffolds[:n_test_scaffolds])
    
    train = []
    test = []
    for scaffold in scaffolds:
        if scaffold in test_scaffolds:
            test.extend(scaffold_to_smiles[scaffold])
        else:
            train.extend(scaffold_to_smiles[scaffold])
    
    return train, test, scaffold_to_smiles, test_scaffolds

def evaluate_ums_on_scaffold_split(target, actives_file, decoys_file, test_frac=0.2, n_bootstrap=1000):
    """Evaluate UMS AUC on scaffold-split actives vs full decoys."""
    
    print(f"\n{'='*60}")
    print(f"TARGET: {target.upper()}")
    print(f"{'='*60}")
    
    # Load actives and decoys
    actives = load_smiles(actives_file)
    decoys = load_smiles(decoys_file)
    
    print(f"Total actives: {len(actives)}")
    print(f"Total decoys: {len(decoys)}")
    
    # Scaffold split actives
    train_actives, test_actives, scaffold_map, test_scaffolds = scaffold_split(actives, test_frac)
    
    print(f"Train actives: {len(train_actives)} ({len([s for s in scaffold_map if s not in test_scaffolds])} scaffolds)")
    print(f"Test actives: {len(test_actives)} ({len(test_scaffolds)} scaffolds)")
    
    # Show scaffold diversity
    print(f"\nTest scaffolds ({len(test_scaffolds)}):")
    for scaf in sorted(test_scaffolds)[:10]:
        n = len(scaffold_map[scaf])
        print(f"  {scaf} (n={n})")
    if len(test_scaffolds) > 10:
        print(f"  ... and {len(test_scaffolds) - 10} more")
    
    # Compute UMS scores
    # Use metalloenzyme family for UMS
    family = "metaloenzyme"
    
    print("\nComputing UMS scores...")
    train_scores = [compute_universal_metal_score(s, 0.5, family)[0] for s in train_actives]
    test_scores = [compute_universal_metal_score(s, 0.5, family)[0] for s in test_actives]
    decoy_scores = [compute_universal_metal_score(s, 0.5, family)[0] for s in decoys]
    
    # AUC on TRAIN scaffolds
    y_train = [1]*len(train_scores) + [0]*len(decoy_scores)
    s_train = train_scores + decoy_scores
    auc_train = roc_auc_score(y_train, s_train)
    
    # AUC on TEST scaffolds (the key metric)
    y_test = [1]*len(test_scores) + [0]*len(decoy_scores)
    s_test = test_scores + decoy_scores
    auc_test = roc_auc_score(y_test, s_test)
    
    # Bootstrap CI on test AUC
    print(f"\nBootstrapping CI ({n_bootstrap} iterations)...")
    boot_aucs = []
    n_test = len(test_scores)
    n_dec = len(decoy_scores)
    
    for i in range(n_bootstrap):
        # Sample with replacement from test actives and decoys
        idx_test = np.random.choice(n_test, n_test, replace=True)
        idx_dec = np.random.choice(n_dec, n_dec, replace=True)
        
        y_boot = [1]*n_test + [0]*n_dec
        s_boot = [test_scores[i] for i in idx_test] + [decoy_scores[i] for i in idx_dec]
        
        try:
            boot_aucs.append(roc_auc_score(y_boot, s_boot))
        except:
            pass
    
    if boot_aucs:
        ci_lower = np.percentile(boot_aucs, 2.5)
        ci_upper = np.percentile(boot_aucs, 97.5)
    else:
        ci_lower = ci_upper = auc_test
    
    print(f"\nRESULTS:")
    print(f"  UMS AUC on TRAIN scaffolds: {auc_train:.4f}")
    print(f"  UMS AUC on TEST scaffolds:  {auc_test:.4f}")
    print(f"  Bootstrap 95% CI:           [{ci_lower:.4f}, {ci_upper:.4f}]")
    
    # Warhead coverage on test set
    warhead_counts = defaultdict(int)
    for smi in test_actives:
        score, details = compute_universal_metal_score(smi, 0.5, family)
        for wh in details.get("warheads", []):
            warhead_counts[wh] += 1
    
    print(f"\nWarhead coverage on TEST actives:")
    for wh, count in warhead_counts.items():
        print(f"  {wh}: {count}/{len(test_actives)} ({100*count/len(test_actives):.1f}%)")
    
    # Also check: are test actives truly different scaffolds from train?
    print(f"\nScaffold overlap check:")
    train_scaffolds = set(get_murcko_scaffold(s) for s in train_actives if get_murcko_scaffold(s))
    test_scaffolds_set = set(get_murcko_scaffold(s) for s in test_actives if get_murcko_scaffold(s))
    overlap = train_scaffolds & test_scaffolds_set
    print(f"  Train scaffolds: {len(train_scaffolds)}")
    print(f"  Test scaffolds: {len(test_scaffolds_set)}")
    print(f"  Overlap (should be 0): {len(overlap)}")
    
    return {
        "target": target,
        "n_actives": len(actives),
        "n_decoys": len(decoys),
        "n_train_actives": len(train_actives),
        "n_test_actives": len(test_actives),
        "n_train_scaffolds": len(train_scaffolds),
        "n_test_scaffolds": len(test_scaffolds),
        "auc_train": auc_train,
        "auc_test": auc_test,
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "warhead_coverage": dict(warhead_counts),
        "scaffold_overlap": len(overlap)
    }

def main():
    results = {}
    
    for target in TARGETS:
        actives_file = DATA_DIR / target / "actives.txt"
        decoys_file = DATA_DIR / target / "decoys.smi"
        
        if not actives_file.exists():
            print(f"SKIP {target}: {actives_file} not found")
            continue
        if not decoys_file.exists():
            print(f"SKIP {target}: {decoys_file} not found")
            continue
        
        res = evaluate_ums_on_scaffold_split(target, actives_file, decoys_file)
        results[target] = res
    
    # Save results
    out_file = DATA_DIR.parent / "scaffold_split_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for target, res in results.items():
        print(f"{target.upper():8s} | Test AUC: {res['auc_test']:.4f} "
              f"[{res['ci_lower']:.4f}, {res['ci_upper']:.4f}] "
              f"| Train AUC: {res['auc_train']:.4f} "
              f"| Test scaffolds: {res['n_test_scaffolds']}")
    
    print(f"\nResults saved to: {out_file}")

if __name__ == "__main__":
    main()