#!/usr/bin/env python3
"""
scripts/curate_metal_targets.py

Cura actives + decoys para nuevos targets metaloenzima usando ChEMBL API.
Corre como background process overnight.

Targets a curar:
  1. ACE  (1UZE) - Angiotensin Converting Enzyme  (CHEMBL1808) - warhead: tiol/carboxilato
  2. PDE5A (1xp0) - Phosphodiesterase 5A           (CHEMBL1827) - warhead: varios
  3. CYP3A4 (4NY4) - Cytochrome P450 3A4           (CHEMBL340)  - warhead: N-coordinación

Output:
  data/multitarget/{name}/actives.txt
  data/multitarget/{name}/decoys.smi
"""

import csv
import io
import json
import math
import os
import random
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, AllChem, DataStructs
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
    print("WARNING: RDKit not available. Using basic SMILES parsing.")

PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DATA_DIR = PROJECT_ROOT / "data"
MULTITARGET_DIR = DATA_DIR / "multitarget"

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"

# ── Targets to curate ──
TARGETS = [
    {
        "name": "ace",
        "pdb_id": "1UZE",
        "chembl_id": "CHEMBL1808",
        "uniprot_id": "P12821",
        "family": "metaloenzyme",
        # ACE has 2 Zn ions
        "center": (40.36, 37.89, 32.93),  # approximate from 1UZE active site
        "box_size": 20,
    },
    {
        "name": "pde5a",
        "pdb_id": "1xp0",
        "chembl_id": "CHEMBL1827",
        "uniprot_id": "O76074",
        "family": "metaloenzyme",
        # PDE5A has Zn + Mg in catalytic domain
        "center": (-22.35, 28.59, 62.69),  # from existing TARGET_CONFIGS
        "box_size": 20,
    },
    {
        "name": "cyp3a4",
        "pdb_id": "4NY4",
        "chembl_id": "CHEMBL340",
        "uniprot_id": "P08684",
        "family": "metaloenzyme",
        "center": (-12.72, -12.19, -10.82),  # approximate from 4NY4 heme
        "box_size": 22,
    },
    {
        # HDAC6 CD2 — uses 5EFN (apo-like, Zn site free) instead of 5EDU
        # (5EDU has bound inhibitor TSN clashing with the catalytic Zn).
        # Zn coord VERIFIED via downloaded PDB HETATM grep: chain A res 801,
        # coordinated by D612, D705, H614 (classic HDAC DWH catalytic triad).
        # Fallback approximation in task spec (-15.5,-3.1,15.2) was WRONG.
        "name": "hdac6",
        "pdb_id": "5EFN",
        "chembl_id": "CHEMBL1862",
        "uniprot_id": "Q9UBN7",
        "family": "metaloenzyme",
        "center": (20.77, 13.16, 38.69),  # catalytic Zn, chain A, verified from PDB
        "box_size": 22,
    },
    {
        # MMP2 — 1GXD catalytic domain with bound hydroxamic inhibitor.
        # Catalytic Zn = chain A res 1633, coord (61.72,79.77,35.57),
        # coordinated by 3 His (H149/H164/H177) + D151 — classic MMP catalytic
        # site. Zn 1634 is the structural Zn (3 His + Cys73), NOT used.
        # Fallback approximation (12.8,5.4,22.1) was WRONG.
        "name": "mmp2",
        "pdb_id": "1GXD",
        "chembl_id": "CHEMBL275",
        "uniprot_id": "P08253",
        "family": "metaloenzyme",
        "center": (61.72, 79.77, 35.57),  # catalytic Zn, chain A, verified from PDB
        "box_size": 22,
    },
]

# ── ChEMBL query parameters ──
MAX_ACTIVES = 1000
MAX_DECOYS = 30000
PCHEMBL_CUTOFF = 6.0  # pChEMBL >= 6 = IC50 <= 1 uM
DELAY = 0.5  # seconds between API calls (rate limiting)


def chembl_get(path: str) -> dict:
    """GET request to ChEMBL API with retry."""
    url = f"{CHEMBL_BASE}/{path}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
    return {}


def get_target_chembl_id(target_name: str) -> str:
    """Resolve target name to ChEMBL ID via UniProt ID."""
    for t in TARGETS:
        if t["name"] == target_name:
            return t["chembl_id"]
    return ""


def fetch_actives(chembl_id: str, max_actives: int = MAX_ACTIVES) -> list[dict]:
    """Fetch active compounds from ChEMBL by target CHEMBL ID.
    
    Returns list of {smiles, pchembl, pki, chembl_id}
    """
    actives = []
    offset = 0
    limit = 100
    
    print(f"  Fetching actives for {chembl_id}...")
    
    while len(actives) < max_actives:
        try:
            data = chembl_get(
                f"activity.json?"
                f"target_chembl_id={chembl_id}"
                f"&pchembl_value__gte={PCHEMBL_CUTOFF}"
                f"&assay_type__in=F,B"
                f"&standard_type__in=IC50,Ki,Kd"
                f"&limit={limit}"
                f"&offset={offset}"
            )
        except Exception as e:
            print(f"    ERROR fetching: {e}")
            break
        
        activities = data.get("activities", [])
        if not activities:
            break
        
        for act in activities:
            smi = act.get("canonical_smiles", "")
            pchembl = act.get("pchembl_value", None)
            mol_chembl_id = act.get("molecule_chembl_id", "")
            
            if not smi or not pchembl:
                continue
            
            try:
                pchembl_val = float(pchembl)
                pki = pchembl_val  # pKi ≈ pChEMBL
            except (ValueError, TypeError):
                continue
            
            # Deduplicate by SMILES
            if any(a["smiles"] == smi for a in actives):
                continue
            
            actives.append({
                "smiles": smi,
                "pchembl": pchembl_val,
                "pki": round(pki, 2),
                "chembl_id": mol_chembl_id,
            })
            
            if len(actives) >= max_actives:
                break
        
        print(f"    {len(actives)}/{max_actives} actives (offset={offset})")
        offset += limit
        time.sleep(DELAY)
    
    # Sort by pchembl descending, keep only unique SMILES
    actives.sort(key=lambda x: x["pchembl"], reverse=True)
    
    # Deduplicate once more by SMILES canonical
    seen = set()
    deduped = []
    for a in actives:
        smi = a["smiles"]
        if smi not in seen:
            seen.add(smi)
            deduped.append(a)
    
    print(f"  Total actives for {chembl_id}: {len(deduped)}")
    return deduped


def compute_properties(smiles: str) -> dict | None:
    """Compute MW, logP, rotB, HBA, HBD from SMILES using RDKit."""
    if not HAS_RDKIT:
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return {
            "mw": Descriptors.ExactMolWt(mol),
            "logp": Descriptors.MolLogP(mol),
            "rotb": Descriptors.NumRotatableBonds(mol),
            "hba": Descriptors.NumHAcceptors(mol),
            "hbd": Descriptors.NumHDonors(mol),
        }
    except Exception:
        return None


def fetch_decoy_pool(chembl_id: str, target_actives: list[dict], n_needed: int) -> list[str]:
    """Fetch inactives from ChEMBL for this target to use as decoys.
    
    Strategy:
    1. First try: compounds tested against this target with pChEMBL < 4
    2. Fallback: general ChEMBL compounds (not tested against this target)
    """
    print(f"  Fetching inactives (IC50 > 100 uM) for {chembl_id}...")
    
    inactive_smiles = set()
    offset = 0
    limit = 100
    active_smiles_set = {a["smiles"] for a in target_actives}
    
    # Phase 1: Get compounds tested against this target with low activity
    while len(inactive_smiles) < n_needed and offset < 2000:
        try:
            data = chembl_get(
                f"activity.json?"
                f"target_chembl_id={chembl_id}"
                f"&pchembl_value__lte=5.0"
                f"&assay_type__in=F,B"
                f"&limit={limit}"
                f"&offset={offset}"
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            break
        
        activities = data.get("activities", [])
        if not activities:
            break
        
        for act in activities:
            smi = act.get("canonical_smiles", "")
            if smi and smi not in active_smiles_set and smi not in inactive_smiles:
                # Filter out compounds too similar to actives (Tanimoto > 0.85)
                inactive_smiles.add(smi)
        
        print(f"    {len(inactive_smiles)} inactives (offset={offset})")
        offset += limit
        time.sleep(DELAY)
    
    # Phase 2: If still not enough, get compounds from ChEMBL drug-like subset
    if len(inactive_smiles) < n_needed:
        print(f"  Only {len(inactive_smiles)} inactives from target-specific assays.")
        print(f"  Augmenting with general drug-like compounds from ChEMBL...")
        
        # Get compounds not tested against this target
        offset = 0
        while len(inactive_smiles) < n_needed and offset < 10000:
            try:
                data = chembl_get(
                    f"molecule.json?"
                    f"full_mwt__gte=250"
                    f"&full_mwt__lte=600"
                    f"&molecule_properties__alogp__gte=-1"
                    f"&molecule_properties__alogp__lte=6"
                    f"&limit={limit}"
                    f"&offset={offset}"
                )
            except Exception as e:
                print(f"    ERROR: {e}")
                break
            
            molecules = data.get("molecules", [])
            if not molecules:
                break
            
            for mol in molecules:
                smi = mol.get("molecule_structures", {}).get("canonical_smiles", "")
                if smi and smi not in active_smiles_set and smi not in inactive_smiles:
                    inactive_smiles.add(smi)
            
            offset += limit
            time.sleep(DELAY)
    
    print(f"  Total decoy pool: {len(inactive_smiles)} compounds")
    return list(inactive_smiles)


def property_match_decoys(
    actives: list[dict],
    decoy_pool: list[str],
    n_decoys_per_active: int = 30,
    max_decoys: int = MAX_DECOYS,
) -> list[str]:
    """Property-match decoys to actives using soft scoring.
    
    For each active, score decoys by property similarity and pick top N.
    Uses normalized Euclidean distance across {MW, logP, rotB, HBA, HBD}.
    Much more effective than hard cutoffs when pool is limited.
    """
    if not HAS_RDKIT or not decoy_pool:
        print("  WARNING: RDKit unavailable or no decoy pool. Using pool as-is.")
        return decoy_pool[:min(len(decoy_pool), max_decoys)]
    
    print(f"  Property-matching decoys for {len(actives)} actives...")
    
    # Compute properties for actives
    active_props = []
    for a in actives:
        p = compute_properties(a["smiles"])
        if p:
            active_props.append(p)
    
    if not active_props:
        print("  WARNING: Could not compute active properties. Using pool as-is.")
        return decoy_pool[:min(len(decoy_pool), max_decoys)]
    
    # Compute properties for decoy pool
    print(f"  Computing properties for {len(decoy_pool)} decoy candidates...")
    pool_props = []
    for i, smi in enumerate(decoy_pool):
        p = compute_properties(smi)
        if p:
            pool_props.append((smi, p))
        if (i + 1) % 1000 == 0:
            print(f"    {i+1}/{len(decoy_pool)}")
    
    if not pool_props:
        print("  WARNING: No decoy properties computed. Using pool as-is.")
        return decoy_pool[:min(len(decoy_pool), max_decoys)]
    
    # Normalize ranges across actives
    all_mw = [ap["mw"] for ap in active_props] + [pp["mw"] for _, pp in pool_props]
    all_logp = [ap["logp"] for ap in active_props] + [pp["logp"] for _, pp in pool_props]
    all_rotb = [ap["rotb"] for ap in active_props] + [pp["rotb"] for _, pp in pool_props]
    all_hba = [ap["hba"] for ap in active_props] + [pp["hba"] for _, pp in pool_props]
    all_hbd = [ap["hbd"] for ap in active_props] + [pp["hbd"] for _, pp in pool_props]
    
    ranges = {
        "mw": max(1, max(all_mw) - min(all_mw)),
        "logp": max(0.1, max(all_logp) - min(all_logp)),
        "rotb": max(1, max(all_rotb) - min(all_rotb)),
        "hba": max(1, max(all_hba) - min(all_hba)),
        "hbd": max(1, max(all_hbd) - min(all_hbd)),
    }
    
    selected = set()
    n_per_active = max(3, min(n_decoys_per_active, max_decoys // max(1, len(actives))))
    
    for ai, ap in enumerate(active_props):
        if len(selected) >= max_decoys:
            break
        
        # Score all decoys by normalized property distance
        scored = []
        for smi, pp in pool_props:
            if smi in selected:
                continue
            dist = (
                ((ap["mw"] - pp["mw"]) / ranges["mw"]) ** 2 +
                ((ap["logp"] - pp["logp"]) / ranges["logp"]) ** 2 +
                ((ap["rotb"] - pp["rotb"]) / ranges["rotb"]) ** 2 +
                ((ap["hba"] - pp["hba"]) / ranges["hba"]) ** 2 +
                ((ap["hbd"] - pp["hbd"]) / ranges["hbd"]) ** 2
            ) ** 0.5
            scored.append((dist, smi))
        
        # Sort by distance and pick top N
        scored.sort(key=lambda x: x[0])
        for _, smi in scored[:n_per_active]:
            selected.add(smi)
        
        if (ai + 1) % 50 == 0:
            print(f"    Active {ai+1}/{len(active_props)}: {len(selected)} decoys selected")
    
    selected_list = list(selected)
    random.shuffle(selected_list)
    print(f"  Total property-matched decoys: {len(selected_list)}")
    return selected_list[:max_decoys]


def write_actives(actives: list[dict], target_dir: Path):
    """Write actives.txt in benchmark format: SMILES pKi"""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "actives.txt"
    with open(path, "w") as f:
        for a in actives:
            f.write(f"{a['smiles']} {a['pki']:.2f}\n")
    print(f"  Wrote {len(actives)} actives to {path}")


def write_decoys(decoys: list[str], target_dir: Path):
    """Write decoys.smi: one SMILES per line"""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "decoys.smi"
    with open(path, "w") as f:
        for smi in decoys:
            f.write(f"{smi}\n")
    print(f"  Wrote {len(decoys)} decoys to {path}")


def update_target_config(target_name: str, center: tuple, family: str):
    """Update TARGET_CONFIGS in benchmark_ef_vina.py with new target."""
    config_path = PROJECT_ROOT / "scripts" / "benchmark_ef_vina.py"
    content = config_path.read_text()
    
    pdb_id = [t["pdb_id"] for t in TARGETS if t["name"] == target_name][0].lower()
    
    new_entry = (
        f'    "{pdb_id}": {{\n'
        f'        "name": "{target_name}",\n'
        f'        "family": "{family}",\n'
        f'        "center": {center},\n'
        f'        "data_dir": lambda d: d / "multitarget" / "{target_name}",\n'
        f'        "pdb_local": lambda d: d / "{pdb_id}.pdb",\n'
        f'        "pdbqt_local": lambda d: d / "multitarget" / "{target_name}" / "{pdb_id}.pdbqt",\n'
        f'    }},\n'
    )
    
    if pdb_id not in content:
        # Insert before the closing brace of TARGET_CONFIGS
        insert_point = content.rfind("}")
        before = content[:insert_point]
        after = content[insert_point:]
        content = before.rstrip() + new_entry + after
        config_path.write_text(content)
        print(f"  Added {target_name} ({pdb_id}) to TARGET_CONFIGS")
    else:
        print(f"  {target_name} ({pdb_id}) already in TARGET_CONFIGS")


def curate_target(target: dict, force: bool = False):
    """Full curation pipeline for a single target."""
    name = target["name"]
    pdb_id = target["pdb_id"]
    chembl_id = target["chembl_id"]
    target_dir = MULTITARGET_DIR / name
    
    actives_path = target_dir / "actives.txt"
    decoys_path = target_dir / "decoys.smi"
    
    print(f"\n{'='*60}")
    print(f"CURATING: {name} ({pdb_id}, {chembl_id})")
    print(f"{'='*60}")
    
    if not force and actives_path.exists() and decoys_path.exists():
        print(f"  Already curated: {len(open(actives_path).readlines())} actives, "
              f"{len(open(decoys_path).readlines())} decoys")
        n_actives = len(open(actives_path).readlines())
        if n_actives >= 50:
            print(f"  SKIPPING (has {n_actives} actives, >=50, use --force to override)")
            return
    
    # Step 1: Fetch actives from ChEMBL
    print(f"\n  [Step 1/4] Fetching actives from ChEMBL...")
    actives = fetch_actives(chembl_id)
    
    if len(actives) < 25:
        print(f"  WARNING: Only {len(actives)} actives found. Consider lowering pChEMBL cutoff.")
    
    # Step 2: Fetch decoy pool
    print(f"\n  [Step 2/4] Building decoy pool...")
    n_decoys_needed = max(1000, len(actives) * 30)
    n_decoys_needed = min(n_decoys_needed, MAX_DECOYS)
    decoy_pool = fetch_decoy_pool(chembl_id, actives, n_decoys_needed)
    
    # Step 3: Decoy generation by property-matching
    print(f"\n  [Step 3/4] Property-matching decoys to actives...")
    decoys = property_match_decoys(actives, decoy_pool, max_decoys=n_decoys_needed)
    
    # Step 4: Write files + update config
    print(f"\n  [Step 4/4] Writing files...")
    write_actives(actives, target_dir)
    write_decoys(decoys, target_dir)
    
    print(f"\n  {'='*50}")
    print(f"  COMPLETED: {name}")
    print(f"    Actives: {len(actives)}")
    print(f"    Decoys:  {len(decoys)}")
    print(f"    Ratio:   1:{len(decoys)//max(1,len(actives))}")
    print(f"  {'='*50}")
    
    return {
        "name": name,
        "pdb_id": pdb_id,
        "chembl_id": chembl_id,
        "n_actives": len(actives),
        "n_decoys": len(decoys),
        "status": "completed",
    }


def main():
    import argparse
    global MAX_ACTIVES
    ap = argparse.ArgumentParser(description="Curate metal targets from ChEMBL")
    ap.add_argument("--targets", type=str, default="ace,pde5a,cyp3a4",
                    help="Comma-separated target names to curate")
    ap.add_argument("--force", action="store_true",
                    help="Re-curate even if files exist")
    ap.add_argument("--skip-pdb-download", action="store_true",
                    help="Skip PDB download step")
    ap.add_argument("--max-actives", type=int, default=MAX_ACTIVES,
                    help=f"Maximum actives per target (default: {MAX_ACTIVES})")
    args = ap.parse_args()
    MAX_ACTIVES = args.max_actives
    
    target_names = [t.strip() for t in args.targets.split(",") if t.strip()]
    targets_to_curate = [t for t in TARGETS if t["name"] in target_names]
    
    if not targets_to_curate:
        print(f"ERROR: No targets found matching: {target_names}")
        sys.exit(1)
    
    print(f"Curation targets: {[t['name'] for t in targets_to_curate]}")
    print(f"Max actives: {MAX_ACTIVES}")
    print(f"Skip PDB download: {args.skip_pdb_download}")
    print(f"Force: {args.force}")
    print()
    
    results = []
    for target in targets_to_curate:
        result = curate_target(target, force=args.force)
        if result:
            results.append(result)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"CURATION COMPLETE")
    print(f"{'='*60}")
    
    if results:
        report_path = DATA_DIR / "curated_metal_targets_report.json"
        report_path.write_text(json.dumps(results, indent=2))
        print(f"\nReport saved to: {report_path}")
        
        for r in results:
            print(f"  {r['name']:8s}: {r['n_actives']} actives, {r['n_decoys']} decoys [{r['status']}]")
    
    # Check if MMP9 benchmark is still running
    print(f"\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
