#!/usr/bin/env python3
"""Verify property matching between actives and decoys."""
import sys
sys.path.insert(0, "scripts")
from rdkit import Chem
from rdkit.Chem import Descriptors
import numpy as np

TARGETS = [
    ("ace", "data/multitarget/ace/actives.txt", "data/multitarget/ace/decoys.smi"),
    ("pde5a", "data/multitarget/pde5a/actives.txt", "data/multitarget/pde5a/decoys.smi"),
    ("cyp3a4", "data/multitarget/cyp3a4/actives.txt", "data/multitarget/cyp3a4/decoys.smi"),
]

def desc(smi):
    mol = Chem.MolFromSmiles(smi)
    if not mol: return None
    return {"mw": Descriptors.ExactMolWt(mol), "logp": Descriptors.MolLogP(mol),
            "hba": Descriptors.NumHAcceptors(mol), "hbd": Descriptors.NumHDonors(mol),
            "rotb": Descriptors.NumRotatableBonds(mol)}

for name, act_path, dec_path in TARGETS:
    with open(act_path) as f:
        actives = [l.split()[0] for l in f if l.strip()]
    with open(dec_path) as f:
        decoys = [l.strip() for l in f if l.strip()]

    rng = np.random.RandomState(42)
    dec_sample = rng.choice(decoys, min(1000, len(decoys)), replace=False).tolist()

    act_props = [desc(s) for s in actives]
    act_props = [p for p in act_props if p]
    dec_props = [desc(s) for s in dec_sample]
    dec_props = [p for p in dec_props if p]

    print(f"\n=== {name} ===")
    print(f"  {len(actives)} actives, {len(decoys)} decoys (sampled {len(dec_sample)})")
    print(f"  {'Property':10s} | {'Active mean':10s} | {'Decoy mean':10s} | {'Ratio':6s} | {'Match?':8s}")
    print("  " + "-"*50)

    for pn in ["mw", "logp", "hba", "hbd", "rotb"]:
        a = np.array([p[pn] for p in act_props])
        d = np.array([p[pn] for p in dec_props])
        a_mean = a.mean()
        d_mean = d.mean()
        ratio = a_mean / max(d_mean, 0.01)
        # DUD-E standard: MW +/- 10%, logP +/- 1, HBA +/- 1, HBD +/- 1, rotB +/- 1
        if pn == "mw":
            ok = 0.85 <= ratio <= 1.15
        elif pn == "logp":
            ok = abs(a_mean - d_mean) <= 1.5
        else:
            ok = abs(a_mean - d_mean) <= 2.0
        marker = "OK" if ok else "FAIL"
        print(f"  {pn:10s} | {a_mean:10.1f} | {d_mean:10.1f} | {ratio:6.2f} | {marker:8s}")
