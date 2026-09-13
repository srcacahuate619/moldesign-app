#!/usr/bin/env python3
"""
Fix decoy property matching for curated targets.
Queries ChEMBL with correct MW range per target and re-runs matching.
"""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
import numpy as np

sys.path.insert(0, "scripts")
from rdkit import Chem
from rdkit.Chem import Descriptors

HAS_RDKIT = True

TARGETS = {
    "ace": {"chembl_id": "CHEMBL1808", "mw_range": (266, 685)},
    "pde5a": {"chembl_id": "CHEMBL1827", "mw_range": (272, 665)},
    "cyp3a4": {"chembl_id": "CHEMBL340", "mw_range": (197, 873)},
}

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
DELAY = 0.5
N_DECOYS_TARGET = 2000
MAX_PAGES = 200

def chembl_get(path):
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"{CHEMBL_BASE}/{path}", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"    ERROR: {e}")
                return {"molecules": []}

def compute_props(smi):
    try:
        mol = Chem.MolFromSmiles(smi)
        if mol:
            return {"mw": Descriptors.ExactMolWt(mol), "logp": Descriptors.MolLogP(mol),
                    "hba": Descriptors.NumHAcceptors(mol), "hbd": Descriptors.NumHDonors(mol),
                    "rotb": Descriptors.NumRotatableBonds(mol)}
    except:
        pass
    return None

for name, cfg in TARGETS.items():
    print(f"\n=== Fixing {name} ===")
    target_dir = Path(f"data/multitarget/{name}")

    # Load actives
    actives = []
    with open(target_dir / "actives.txt") as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                actives.append(parts[0])

    # Compute active MW range
    act_props = [compute_props(s) for s in actives]
    act_props = [p for p in act_props if p]
    act_mws = np.array([p["mw"] for p in act_props])
    mw_lo, mw_hi = np.percentile(act_mws, [5, 95])
    mw_gte = max(100, int(mw_lo * 0.8))
    mw_lte = int(mw_hi * 1.2)
    print(f"  Actives: {len(actives)} | MW range [{mw_lo:.0f}, {mw_hi:.0f}] -> query range [{mw_gte}, {mw_lte}]")

    # Download decoys from ChEMBL with correct MW range
    decoy_pool = set()
    offset = 0
    limit = 100
    active_smiles = set(actives)

    print(f"  Fetching molecules from ChEMBL (MW {mw_gte}-{mw_lte})...")
    while len(decoy_pool) < N_DECOYS_TARGET * 2 and offset < MAX_PAGES * limit:
        data = chembl_get(
            f"molecule.json?full_mwt__gte={mw_gte}"
            f"&full_mwt__lte={mw_lte}"
            f"&molecule_properties__alogp__gte=-2"
            f"&molecule_properties__alogp__lte=7"
            f"&limit={limit}&offset={offset}"
        )
        molecules = data.get("molecules", [])
        if not molecules:
            break
        for mol in molecules:
            smi = mol.get("molecule_structures", {}).get("canonical_smiles", "")
            if smi and smi not in active_smiles and smi not in decoy_pool:
                decoy_pool.add(smi)
        offset += limit
        time.sleep(DELAY)
        if offset % 500 == 0:
            print(f"    {len(decoy_pool)} so far (offset {offset})...")

    print(f"  Total candidates: {len(decoy_pool)}")

    # Now property-match with hard MW bounds
    print(f"  Computing properties and matching...")
    pool_items = [(s, compute_props(s)) for s in list(decoy_pool)[:N_DECOYS_TARGET * 3]]
    pool_items = [(s, p) for s, p in pool_items if p]

    selected = set()
    for ai, ap in enumerate(act_props):
        if len(selected) >= N_DECOYS_TARGET:
            break
        # Hard MW filter
        mw_min = max(0, ap["mw"] - max(ap["mw"] * 0.1, 50))
        mw_max = ap["mw"] + max(ap["mw"] * 0.1, 50)

        candidates = []
        for smi, pp in pool_items:
            if smi in selected or not (mw_min <= pp["mw"] <= mw_max):
                continue
            logp_ok = abs(ap["logp"] - pp["logp"]) <= 1.5
            hba_ok = abs(ap["hba"] - pp["hba"]) <= 2
            hbd_ok = abs(ap["hbd"] - pp["hbd"]) <= 2
            rotb_ok = abs(ap["rotb"] - pp["rotb"]) <= 2
            if logp_ok and hba_ok and hbd_ok and rotb_ok:
                candidates.append(smi)

        if len(candidates) < 5:
            # Fallback: just match MW
            candidates = []
            for smi, pp in pool_items:
                if smi in selected or not (mw_min <= pp["mw"] <= mw_max):
                    continue
                candidates.append(smi)

        # Pick top 30 random from candidates
        rng = np.random.RandomState(42 + ai)
        picked = rng.choice(candidates, min(30, len(candidates)), replace=False).tolist()
        for smi in picked:
            selected.add(smi)

        if (ai + 1) % 50 == 0:
            print(f"    Active {ai+1}/{len(act_props)}: {len(selected)} decoys")

    selected_list = list(selected)
    # Add remaining from pool to hit target if still short
    if len(selected_list) < N_DECOYS_TARGET:
        remaining = [s for s, _ in pool_items if s not in selected]
        rng = np.random.RandomState(0)
        extra = rng.choice(remaining, min(N_DECOYS_TARGET - len(selected_list), len(remaining)), replace=False).tolist()
        selected_list.extend(extra)

    rng.shuffle(selected_list)
    selected_list = selected_list[:N_DECOYS_TARGET]

    # Write decoys
    (target_dir / "decoys.smi").write_text("\n".join(selected_list))
    print(f"\n  Wrote {len(selected_list)} decoys to {target_dir / 'decoys.smi'}")

    # Verify matching
    dec_props = [compute_props(s) for s in selected_list[:500]]
    dec_props = [p for p in dec_props if p]
    print(f"  Verification:")
    for pn in ["mw", "logp", "hba", "hbd", "rotb"]:
        a_mean = np.mean([p[pn] for p in act_props])
        d_mean = np.mean([p[pn] for p in dec_props])
        ratio = a_mean / max(d_mean, 0.01)
        ok = "OK" if 0.85 <= ratio <= 1.15 or pn != "mw" else "FAIL"
        if pn == "logp":
            ok = "OK" if abs(a_mean - d_mean) <= 1.5 else "FAIL"
        elif pn in ("hba", "hbd", "rotb"):
            ok = "OK" if abs(a_mean - d_mean) <= 2 else "FAIL"
        print(f"    {pn:6s}: active={a_mean:8.1f}  decoy={d_mean:8.1f}  ratio={ratio:.2f}  {ok}")

print("\n=== DONE ===")
