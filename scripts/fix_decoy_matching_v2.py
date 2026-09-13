#!/usr/bin/env python3
"""
Fix decoy matching via stratified subsampling from combined pool.
Strategy: 
  1. Compute properties for all actives + all pool decoys
  2. For each active, find decoys in same MW/logP/HBA/HBD/rotB bin
  3. Pick closest matches
  4. Force balanced matching by active MW bins
"""
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, "scripts")
from rdkit import Chem
from rdkit.Chem import Descriptors

np.random.seed(42)

def props(smi):
    mol = Chem.MolFromSmiles(smi)
    if not mol: return None
    return {"mw": Descriptors.ExactMolWt(mol), "logp": Descriptors.MolLogP(mol),
            "hba": Descriptors.NumHAcceptors(mol), "hbd": Descriptors.NumHDonors(mol),
            "rotb": Descriptors.NumRotatableBonds(mol)}

# Build max pool: ALL decoys from all targets + ChEMBL
pool = set()
for tgt in ['5ht1a','cdk2','er_alpha','factor_xa','hiv_protease','thrombin','ca2','ache','mmp9','pde5a','cyp3a4']:
    p = Path(f"data/multitarget/{tgt}/decoys.smi")
    if p.exists() and tgt not in ["pde5a","cyp3a4"]:  # skip newly curated ones
        for l in p.read_text().splitlines():
            s = l.strip().split()[0] if l.strip() else ""
            if s and not s.startswith("#"): pool.add(s)

# Also add ChEMBL pool molecules
for p in Path("data/").glob("*.smi"):
    if p.exists():
        for l in p.read_text().splitlines():
            s = l.strip().split()[0] if l.strip() else ""
            if s and not s.startswith("#"): pool.add(s)

pool_mols = list(pool)
print(f"Total pool: {len(pool_mols)}")

# Compute pool properties
pool_props = []
for smi in pool_mols:
    p = props(smi)
    if p: pool_props.append((smi, p))

print(f"Pool with valid props: {len(pool_props)}")
pool_mws = np.array([p[1]["mw"] for p in pool_props])
print(f"  MW: mean={pool_mws.mean():.0f} std={pool_mws.std():.0f} min={pool_mws.min():.0f} max={pool_mws.max():.0f}")

# Fix each target
for name in ["ace", "pde5a", "cyp3a4"]:
    print(f"\n=== {name} ===")
    tdir = Path(f"data/multitarget/{name}")
    with open(tdir / "actives.txt") as f:
        actives = [l.split()[0] for l in f if l.strip()]
    act_props = [props(s) for s in actives]
    act_props = [p for p in act_props if p]
    act_mws = np.array([p["mw"] for p in act_props])

    # Create MW bins based on active distribution
    bins = np.percentile(act_mws, [0, 25, 50, 75, 100])
    bin_labels = list(range(len(bins)-1))

    # Bin actives
    act_bins = np.digitize(act_mws, bins[1:-1])  # 0..3

    # Pool properties
    selected = set()
    for bi in range(4):
        bin_lo = bins[bi]
        bin_hi = bins[bi + 1] + 1  # +1 to include upper bound
        mw_pad = max(50, (bin_hi - bin_lo) * 0.3)

        # Find pool molecules in this MW range
        pool_in_bin = [(s, p) for s, p in pool_props
                      if s not in selected and (bin_lo - mw_pad) <= p["mw"] <= (bin_hi + mw_pad)]
        print(f"  MW bin [{bin_lo:.0f}, {bin_hi:.0f}): {(act_bins == bi).sum()} actives, {len(pool_in_bin)} pool candidates")

        # Active indices in this bin
        act_idx = [i for i in range(len(act_props)) if act_bins[i] == bi]
        rng = np.random.RandomState(bi)

        for ai in act_idx:
            if len(selected) >= 2000:
                break
            ap = act_props[ai]
            # Score pool molecules by property distance
            scored = []
            for smi, pp in pool_in_bin:
                if smi in selected:
                    continue
                # Weighted distance: MW dominates
                d = (abs(ap["mw"] - pp["mw"]) / max(50, ap["mw"] * 0.1) * 3 +
                     abs(ap["logp"] - pp["logp"]) / 2 * 1 +
                     abs(ap["hba"] - pp["hba"]) / 2 * 1 +
                     abs(ap["hbd"] - pp["hbd"]) / 2 * 0.5 +
                     abs(ap["rotb"] - pp["rotb"]) / 3 * 0.5)
                scored.append((d, smi))
            scored.sort(key=lambda x: x[0])
            for _, smi in scored[:30]:
                selected.add(smi)

    selected_list = list(selected)
    rng.shuffle(selected_list)
    selected_list = selected_list[:2000]

    # Write
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "decoys.smi").write_text("\n".join(selected_list))
    print(f"  Wrote {len(selected_list)} decoys")

    # Verify
    dec_props = [props(s) for s in selected_list[:500]]
    dec_props = [p for p in dec_props if p]
    print(f"  Verification:")
    for pn in ["mw", "logp", "hba", "hbd", "rotb"]:
        a = np.array([p[pn] for p in act_props])
        d = np.array([p[pn] for p in dec_props])
        ratio = a.mean() / max(d.mean(), 0.01)
        ok = "OK" if 0.85 <= ratio <= 1.15 else "FAIL"
        if pn == "logp":
            ok = "OK" if abs(a.mean() - d.mean()) <= 1.5 else "FAIL"
        elif pn in ("hba", "hbd", "rotb"):
            ok = "OK" if abs(a.mean() - d.mean()) <= 2 else "FAIL"
        print(f"    {pn:6s}: active={a.mean():8.1f}  decoy={d.mean():8.1f}  ratio={ratio:.2f}  {ok}")

print("\n=== DONE ===")
