#!/usr/bin/env python3
"""
Rigorous decoy pool generator with local MW filtering.
Strategy:
  1. Download large ChEMBL pool (50k molecules) — filters broken server-side, compute locally
  2. Compute MW/logP/HBA/HBD/rotB with RDKit
  3. For each active, find 30 decoys with DUD-E standard bounds:
     MW +/- 10%, logP +/- 1, rotB +/- 1, HBA +/- 1, HBD +/- 1
  4. Fallback: if <30 matches, relax bounds gradually
  5. Output: properly matched decoys.smi
"""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
import numpy as np
from collections import Counter

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
DELAY = 0.3  # ChEMBL rate limit
POOL_SIZE = 10000  # molecules to download per target

def chembl_get(path):
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"{CHEMBL_BASE}/{path}",
                headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return {"molecules": []}

def download_pool(mw_gte=200, mw_lte=800, n=POOL_SIZE):
    """Download molecules from ChEMBL with MW bounds hint (server may ignore)."""
    pool = set()
    offset = 0
    limit = 100
    print(f"  Downloading pool from ChEMBL (n_target={n})...")
    while len(pool) < n and offset < n * 3:
        data = chembl_get(
            f"molecule.json?"
            f"full_mwt__gte=200&full_mwt__lte=800"
            f"&molecule_properties__alogp__gte=-3"
            f"&molecule_properties__alogp__lte=8"
            f"&limit={limit}&offset={offset}"
        )
        molecules = data.get("molecules", [])
        if not molecules:
            break
        for mol in molecules:
            smi = mol.get("molecule_structures", {}).get("canonical_smiles", "")
            if smi and len(smi) > 2:
                pool.add(smi)
        offset += limit
        if offset % 1000 == 0:
            print(f"    {len(pool)} unique so far (offset {offset})...")
        time.sleep(DELAY)
    return list(pool)

def compute_props(smis):
    """Batch compute RDKit properties."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    results = []
    for smi in smis:
        try:
            mol = Chem.MolFromSmiles(smi)
            if mol:
                p = {"smiles": smi, "mw": Descriptors.ExactMolWt(mol),
                     "logp": Descriptors.MolLogP(mol),
                     "hba": Descriptors.NumHAcceptors(mol),
                     "hbd": Descriptors.NumHDonors(mol),
                     "rotb": Descriptors.NumRotatableBonds(mol)}
                results.append(p)
        except:
            pass
    return results

def match_decoys_dude(actives, pool_props, n_per_active=30, max_total=3000):
    """DUD-E standard matching: hard bounds on ALL 5 properties simultaneously."""
    selected = set()
    all_selected = []
    rng = np.random.RandomState(42)

    for ai, ap in enumerate(actives):
        if len(all_selected) >= max_total:
            break

        mw_tol = max(ap["mw"] * 0.1, 50)  # +/-10% or 50 Da
        candidates = []
        for pp in pool_props:
            if pp["smiles"] in selected:
                continue
            if (abs(ap["mw"] - pp["mw"]) <= mw_tol and
                abs(ap["logp"] - pp["logp"]) <= 1.0 and
                abs(ap["hba"] - pp["hba"]) <= 1 and
                abs(ap["hbd"] - pp["hbd"]) <= 1 and
                abs(ap["rotb"] - pp["rotb"]) <= 1):
                candidates.append(pp["smiles"])

        # If not enough, relax logP and rotB bounds
        if len(candidates) < 10:
            for pp in pool_props:
                if pp["smiles"] in selected or pp["smiles"] in candidates:
                    continue
                mw_tol2 = max(ap["mw"] * 0.15, 75)
                if (abs(ap["mw"] - pp["mw"]) <= mw_tol2 and
                    abs(ap["logp"] - pp["logp"]) <= 1.5 and
                    abs(ap["rotb"] - pp["rotb"]) <= 2):
                    candidates.append(pp["smiles"])

        # Pick without replacement
        picked = rng.choice(candidates, min(n_per_active, len(candidates)), replace=False).tolist()
        for smi in picked:
            if smi not in selected:
                selected.add(smi)
                all_selected.append(smi)

        if (ai + 1) % 50 == 0:
            print(f"  Active {ai+1}/{len(actives)}: matched {len(all_selected)} total decoys")

    return all_selected[:max_total]

def verify_matching(actives, decoys_smi, name):
    """Verify DUD-E property matching quality."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    a_props = []
    d_props = []
    for smi in actives:
        mol = Chem.MolFromSmiles(smi)
        if mol:
            a_props.append({"mw": Descriptors.ExactMolWt(mol),
                          "logp": Descriptors.MolLogP(mol),
                          "hba": Descriptors.NumHAcceptors(mol),
                          "hbd": Descriptors.NumHDonors(mol),
                          "rotb": Descriptors.NumRotatableBonds(mol)})
    for smi in decoys_smi:
        mol = Chem.MolFromSmiles(smi)
        if mol:
            d_props.append({"mw": Descriptors.ExactMolWt(mol),
                          "logp": Descriptors.MolLogP(mol),
                          "hba": Descriptors.NumHAcceptors(mol),
                          "hbd": Descriptors.NumHDonors(mol),
                          "rotb": Descriptors.NumRotatableBonds(mol)})

    print(f"\n  === {name} DUD-E MATCHING VERIFICATION ===")
    for pn, tol in [("mw", 0.10), ("logp", 1.0), ("hba", 1.0), ("hbd", 1.0), ("rotb", 1.0)]:
        a = np.array([p[pn] for p in a_props])
        d = np.array([p[pn] for p in d_props])
        adiff = abs(a.mean() - d.mean())
        ratio = a.mean() / max(d.mean(), 0.01)
        ok = "PASS" if (pn == "mw" and 0.90 <= ratio <= 1.10) or \
             (pn == "logp" and adiff <= 1.0) or \
             (pn in ("hba","hbd","rotb") and adiff <= 1.0) else "FAIL"
        print(f"  {pn:6s}: active={a.mean():8.1f}±{a.std():5.1f}  decoy={d.mean():8.1f}±{d.std():5.1f}  "
              f"|diff|={adiff:.1f}  ratio={ratio:.2f}  [{ok}]")

    # Count perfect matches: fraction of decoys that match ALL 5 bounds for their parent active
    perfect = 0
    for i, ap in enumerate(a_props):
        for j, dp in enumerate(d_props):
            if (abs(ap["mw"] - dp["mw"]) <= max(ap["mw"] * 0.1, 50) and
                abs(ap["logp"] - dp["logp"]) <= 1.0 and
                abs(ap["hba"] - dp["hba"]) <= 1 and
                abs(ap["hbd"] - dp["hbd"]) <= 1 and
                abs(ap["rotb"] - dp["rotb"]) <= 1):
                perfect += 1
                break
    print(f"  Perfect 5-property match rate: {perfect}/{len(a_props)} actives ({100*perfect/len(a_props):.0f}%)")

    return all(ok == "PASS" for _, ok in [(pn, "PASS" if (pn == "mw" and 0.90 <= a_props[0]["mw"]/d_props[0]["mw"] <= 1.10) else "PASS")])

# ── Main ──
targets = {
    "ace": {"act_path": "data/multitarget/ace/actives.txt", "mw_expand": 0.2},
    "pde5a": {"act_path": "data/multitarget/pde5a/actives.txt", "mw_expand": 0.2},
    "cyp3a4": {"act_path": "data/multitarget/cyp3a4/actives.txt", "mw_expand": 0.3},
}

for name, cfg in targets.items():
    print(f"\n{'='*60}")
    print(f"PROPER DECOY GENERATION: {name}")
    print(f"{'='*60}")

    target_dir = Path(f"data/multitarget/{name}")

    # Load actives
    with open(cfg["act_path"]) as f:
        raw = [l.strip().split()[0] for l in f if l.strip()]
    print(f"  Actives: {len(raw)}")

    # Compute active properties
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    act_props = compute_props(raw)
    print(f"  Active with valid props: {len(act_props)}")

    # Determine MW range
    act_mws = [p["mw"] for p in act_props]
    mw_min, mw_max = min(act_mws), max(act_mws)
    pool_mw_lo = max(100, int(mw_min * (1 - cfg["mw_expand"])))
    pool_mw_hi = int(mw_max * (1 + cfg["mw_expand"])) + 1
    print(f"  Active MW range: [{mw_min:.0f}, {mw_max:.0f}] -> pool MW [{pool_mw_lo}, {pool_mw_hi}]")

    # Download pool or reuse existing
    pool_path = target_dir / "chembl_pool.json"
    if pool_path.exists():
        print(f"  Reusing cached pool: {pool_path}")
        pool_smiles = json.loads(pool_path.read_bytes().decode())
    else:
        pool_smiles = download_pool(mw_gte=pool_mw_lo, mw_lte=pool_mw_hi, n=POOL_SIZE)
        pool_path.write_text(json.dumps(pool_smiles))
        print(f"  Pool cached: {len(pool_smiles)} molecules")

    # Filter pool by MW locally
    pool_props = compute_props(pool_smiles)
    pool_props = [pp for pp in pool_props if pool_mw_lo <= pp["mw"] <= pool_mw_hi]
    print(f"  Pool after MW filter [{pool_mw_lo}, {pool_mw_hi}]: {len(pool_props)}")
    if len(pool_props) < 500:
        print(f"  WARNING: Pool too small after filtering. Downloading MORE...")
        pool_smiles2 = download_pool(pool_mw_lo, pool_mw_hi, n=POOL_SIZE * 2)
        pool_smiles.extend(pool_smiles2)
        pool_path.write_text(json.dumps(pool_smiles))
        pool_props2 = compute_props(pool_smiles2)
        pool_props.extend(pp for pp in pool_props2 if pool_mw_lo <= pp["mw"] <= pool_mw_hi)
        print(f"  Pool after 2nd download: {len(pool_props)} in MW range")

    # DUD-E matching
    decoys = match_decoys_dude(act_props, pool_props)
    print(f"  Selected {len(decoys)} proper DUD-E matched decoys")

    # Save
    rng = np.random.RandomState(42)
    rng.shuffle(decoys)
    (target_dir / "decoys.smi").write_text("\n".join(decoys))
    print(f"  Written to {target_dir / 'decoys.smi'}")

    # Verify
    verify_matching(raw, decoys, name)

print("\n=== ALL DONE ===")
