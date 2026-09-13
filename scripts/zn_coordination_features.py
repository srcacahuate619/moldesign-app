#!/usr/bin/env python3
"""
scripts/zn_coordination_features.py
===================================
Compute Zn-coordination features for ligand poses in ca2 checkpoint.

For each molecule with a pose_pdbqt field:
  - zn_nearest_dist   : min distance (A) from any ligand atom to the Zn ion
  - zn_donors_count    : N,O,S atoms within 3.5 A of Zn (potential coordinators)
  - zn_closest_atom    : element of the closest atom (C/N/O/S/F/Br/etc)
  - zn_has_sulfonamide : 1 if SMILES contains S(=O)(=O)N (Zn-binding warhead), 0 else
  - zn_inside_box      : 1 if any ligand atom within 8A of Zn (in active site)
  - zn_coord_score     : heuristic score [0..1] combining the above

For ca2 (carbonic anhydrase), Zn is at coords from 3dc3.pdb HETATM ZN.

INPUT:  data/molchamb_loto/checkpoints/benchmark_checkpoint_ca2.json
OUTPUT: data/molchamb_loto/zn_features_ca2.json
        (also writes a summary print of separation power)
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CK_PATH = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints" / "benchmark_checkpoint_ca2.json"
OUT_PATH = PROJECT_ROOT / "data" / "molchamb_loto" / "zn_features_ca2.json"
PDB_PATH = PROJECT_ROOT / "data" / "targets" / "3dc3.pdb"

# Zn in 3dc3 is at (-6.838, -1.687, 15.420) -- verified directly from PDB.
# If we can't read the PDB, hardcode it.
FALLBACK_ZN = (-6.838, -1.687, 15.420)

ZN_COORD_THRESHOLD = 3.5  # Angstrom -- a "coordinating" atom is within 3.5 A
ZN_BOX_THRESHOLD = 8.0    # Angstrom -- "in the active site"


def get_zn_coords(pdb_path):
    """Read the catalytic Zn position from a PDB file."""
    if not pdb_path.exists():
        return FALLBACK_ZN
    for line in pdb_path.read_text(errors="ignore").splitlines():
        if line.startswith("HETATM") and " ZN " in line[12:16] and " ZN" in line[76:80]:
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                return (x, y, z)
            except (ValueError, IndexError):
                continue
    print(f"[WARN] Could not find ZN in {pdb_path}, using fallback {FALLBACK_ZN}")
    return FALLBACK_ZN


def parse_pdbqt_atoms(pdbqt_str):
    """Parse a pose_pdbqt string, returning a list of (element, x, y, z).
    pdbqt atom lines look like:
      ATOM      1  C   UNL     1      -7.029   3.021  16.523  1.00  0.00     0.017 A
    """
    atoms = []
    for line in pdbqt_str.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
        except (ValueError, IndexError):
            continue
        # PDBQT element is in columns 77-79 (or 78-80 in 1-based)
        el = line[76:79].strip()
        if not el:
            # fallback: derive from atom name in columns 13-16
            at_name = line[12:16].strip()
            el = at_name[0] if at_name else "C"
        atoms.append((el, x, y, z))
    return atoms


def has_sulfonamide(smiles):
    """Heuristic: check if SMILES contains a sulfonamide group S(=O)(=O)N
    (with possible protonation variants and aromatic attachment)."""
    # Common Zn-binding warhead patterns
    patterns = [
        r"S\(=O\)\(=O\)N",            # standard sulfonamide
        r"\[NH2\]S\(=O\)=O",           # alternative
        r"NS\(=O\)\(=O\)",             # reversed notation
        r"S\(=O\)\(=O\)\[NH",          # bracketed N
    ]
    for p in patterns:
        if re.search(p, smiles):
            return 1
    # Also phosphonate, hydroxamic acid, thiol (other Zn binders)
    extra_patterns = [
        r"C\(=O\)NO",      # hydroxamic acid
        r"C\(=O\)N\[OH",   # hydroxamate bracketed
        r"\[SH\]",          # thiol bracketed
        r"Sc[\d c]",        # thiol/aromatic S
    ]
    for p in extra_patterns:
        if re.search(p, smiles):
            return 1
    return 0


def dist_xyz(a, b):
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def compute_zn_features(pose_pdbqt, smiles, zn_xyz):
    if not pose_pdbqt or len(pose_pdbqt) < 20:
        return None
    atoms = parse_pdbqt_atoms(pose_pdbqt)
    if not atoms:
        return None
    # distances from each ligand atom to Zn
    dists = [dist_xyz((x, y, z), zn_xyz) for (_, x, y, z) in atoms]
    nearest = min(dists)
    # coordinating atoms: N, O, S within ZN_COORD_THRESHOLD
    zn_donors = [
        (el, d) for (el, d) in zip([a[0] for a in atoms], dists)
        if el.strip().upper() in ("N", "O", "S")
        and d <= ZN_COORD_THRESHOLD
    ]
    # Closest atom element
    closest_idx = int(np.argmin(dists))
    closest_el = atoms[closest_idx][0].strip()
    # Box check
    in_box = 1 if nearest <= ZN_BOX_THRESHOLD else 0
    # Sulfonamide
    has_sulf = has_sulfonamide(smiles)
    # Heuristic score: combines distance, donor count, sulfonamide
    # Closer to Zn + more donors + has sulfonamide = higher score
    # Distance component: 0 if nearest > 8A, ~1 if within 2.5A (coordination distance)
    if nearest > 8.0:
        dist_score = 0.0
    elif nearest <= 2.5:
        dist_score = 1.0
    else:
        # linear interp from 2.5 to 8
        dist_score = (8.0 - nearest) / (8.0 - 2.5)
    # Donor component: 0 if no donors, 1 if >=3 donors
    donor_score = min(1.0, len(zn_donors) / 3.0)
    # Sulfonamide bonus
    coord_score = 0.5 * dist_score + 0.3 * donor_score + 0.2 * has_sulf
    coord_score = max(0.0, min(1.0, coord_score))
    return {
        "zn_nearest_dist": round(nearest, 3),
        "zn_donors_count": len(zn_donors),
        "zn_closest_atom": closest_el,
        "zn_has_sulfonamide": has_sulf,
        "zn_in_box": in_box,
        "zn_coord_score": round(coord_score, 4),
        "zn_donor_elements": sorted({e.strip() for e, _ in zn_donors}),
    }


def main():
    if not CK_PATH.exists():
        print(f"Missing checkpoint: {CK_PATH}")
        return 1
    zn_xyz = get_zn_coords(PDB_PATH)
    print(f"Zn coords: {zn_xyz}")
    data = json.loads(CK_PATH.read_text())
    results = data["results"]
    print(f"Loaded {len(results)} molecules from ca2 checkpoint")

    out_records = []
    skipped_no_pose = 0
    skipped_parse = 0
    for i, r in enumerate(results):
        smi = r.get("smiles", "")
        pose = r.get("pose_pdbqt")
        if not pose:
            skipped_no_pose += 1
            continue
        features = compute_zn_features(pose, smi, zn_xyz)
        if features is None:
            skipped_parse += 1
            continue
        out_records.append({
            "smiles": smi,
            "is_active": r.get("is_active", False),
            "vina_score": r.get("vina_score"),
            "molchamb_score": r.get("molchamb_score"),
            "gnn_d_prob": r.get("gnn_d_prob"),
            **features,
        })

    print(f"Processed: {len(out_records)} | no_pose={skipped_no_pose} | parse_fail={skipped_parse}")

    # Analyze separation power
    actives = [r for r in out_records if r["is_active"]]
    decoys = [r for r in out_records if not r["is_active"]]
    print(f"Actives: {len(actives)} | Decoys: {len(decoys)}")
    print()

    # Statistics per metric
    print("=" * 80)
    print("Feature distributions -- actives vs decoys")
    print("=" * 80)
    for key in ["zn_nearest_dist", "zn_donors_count", "zn_has_sulfonamide",
                "zn_in_box", "zn_coord_score"]:
        a_vals = [r[key] for r in actives]
        d_vals = [r[key] for r in decoys]
        a_mean = np.mean(a_vals) if a_vals else 0
        d_mean = np.mean(d_vals) if d_vals else 0
        a_med = np.median(a_vals) if a_vals else 0
        d_med = np.median(d_vals) if d_vals else 0
        print(f"  {key:25s}  act: mean={a_mean:7.3f} med={a_med:7.3f}  |  "
              f"dec: mean={d_mean:7.3f} med={d_med:7.3f}")

    # AUC of each Zn feature (actives > decoys for zn_coord_score, in_box, sulfonamide)
    # (for zn_nearest_dist, smaller is better -- use 1/(1+x) or invert)
    print()
    print("=" * 80)
    print("Individual AUC of each Zn feature")
    print("=" * 80)
    labels = [r["is_active"] for r in out_records]
    for key in ["zn_coord_score", "zn_has_sulfonamide", "zn_in_box", "zn_donors_count",
                "zn_nearest_dist"]:
        scores = [r[key] for r in out_records]
        # For nearest_dist, smaller is better -- negate
        if key == "zn_nearest_dist":
            scores = [-s for s in scores]
        if len(set(labels)) > 1:
            auc = round(roc_auc_score(labels, scores), 4)
        else:
            auc = 0.5
        print(f"  {key:25s}  AUC = {auc:.4f}")

    # Combined: MolChamb + Zn coord_score
    print()
    print("=" * 80)
    print("Combined: MolChamb + Zn coord_score (heuristic blend)")
    print("=" * 80)
    # Weighted average
    blend_scores = []
    for r in out_records:
        mc = r["molchamb_score"] or 0.5
        zc = r["zn_coord_score"]
        blend = 0.5 * mc + 0.5 * zc
        blend_scores.append(blend)
    if len(set(labels)) > 1:
        auc_blend = round(roc_auc_score(labels, blend_scores), 4)
    else:
        auc_blend = 0.5
    print(f"  0.5*MolChamb + 0.5*ZnCoord: AUC = {auc_blend:.4f}")
    # Try different ratios
    for w_mc in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        w_zc = 1.0 - w_mc
        s = [w_mc * (r["molchamb_score"] or 0.5) + w_zc * r["zn_coord_score"]
             for r in out_records]
        auc = round(roc_auc_score(labels, s), 4) if len(set(labels)) > 1 else 0.5
        print(f"  {w_mc:.1f}*MolChamb + {w_zc:.1f}*ZnCoord: AUC = {auc:.4f}")

    # Save
    out = {
        "zn_xyz": list(zn_xyz),
        "n_total": len(out_records),
        "n_active": len(actives),
        "n_decoy": len(decoys),
        "skipped_no_pose": skipped_no_pose,
        "skipped_parse": skipped_parse,
        "records": out_records,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print()
    print(f"Saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
