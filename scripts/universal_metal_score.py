#!/usr/bin/env python3
"""
scripts/universal_metal_score.py
================================
Universal metal-coordination scoring module.

Cheminformatics approach: detect common Zn-binding warheads in SMILES,
combine with MolChamb quantum score and heavy-atom donor count.

Features (all ligand-only, NO docking required):
  - metal_warhead_sulfonamide     : S(=O)(=O)N  (CA2 warhead)
  - metal_warhead_hydroxamic      : C(=O)NOH     (MMP warhead)
  - metal_warhead_thiol           : SH           (ACE, MMP, various)
  - metal_warhead_carboxylate     : C(=O)O-      (general)
  - metal_warhead_phosphonate     : P(=O)(O)O    (general)
  - metal_warhead_n_hydroxy       : N-OH         (general)
  - metal_warhead_any             : any warhead present
  - metal_donor_count             : N + O + S heavy atom count
  - molchamb_score                : quantum electronic score (pre-computed)
  - universal_metal_score         : combined heuristic [0..1]

Usage (standalone):
  python scripts/universal_metal_score.py --smiles "c1ccc(S(=O)(=O)N)cc1"

Usage (pipeline):
  from universal_metal_score import compute_universal_metal_score
  score, features = compute_universal_metal_score(smiles, target_family=None)
"""
import argparse
import json
import math
import re
import sys

# ── Warhead detection patterns ──
# Use RDKit SMARTS substructure matching, NOT regex on SMILES strings.
# Regex matching is fragile because the same chemical substructure can have
# multiple canonical SMILES representations (e.g., C(=O)NO vs O=C(NO)).
# SMARTS provides chemically aware substructure matching via RDKit.

_WARHEAD_SMARTS = {
    "sulfonamide": [
        "S(=O)(=O)[N;!$(N-C=O)]",          # sulfonamide S(=O)(=O)N, exclude sulfonamides
        "O=S(=O)[N;!$(N-C=O)]",            # reverse orientation
    ],
    "primary_sulfonamide": [
        "S(=O)(=O)[NH2]",                   # primary sulfonamide
        "O=S(=O)[NH2]",
    ],
    "hydroxamic": [
        "[C;$(C(=O))]N[O;$(O-*)]",          # C(=O)NOH — vorinostat, marimastat, batimastat
        "C(=O)NO",                           # explicit
    ],
    "thiol": [
        "[SH]",                              # explicit [SH] bracket notation
    ],
    "carboxylate": [
        "C(=O)[O-]",                         # deprotonated carboxylate
        "C(=O)[OH1]",                        # protonated carboxylic acid (OH with 1 H)
    ],
    "phosphonate": [
        "P(=O)(O)(O)",                       # phosphonic acid
        "P(=O)(O)([O-])",                    # deprotonated
    ],
    "n_hydroxy": [
        "[N]-[OH1]",                         # N-OH single bond, hydroxylamine-type
        "N(O)",                              # explicit N-oxide notation
    ],
}

# Ordered list of warhead keys for feature vector stability
WARHEAD_KEYS = [
    "sulfonamide",
    "primary_sulfonamide",
    "hydroxamic",
    "thiol",
    "carboxylate",
    "phosphonate",
    "n_hydroxy",
]


def detect_warheads(smiles: str) -> dict:
    """Return dict of warhead_key -> bool for all patterns using RDKit SMARTS."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {k: False for k in WARHEAD_KEYS}
    except Exception:
        return {k: False for k in WARHEAD_KEYS}

    result = {}
    for key, smarts_list in _WARHEAD_SMARTS.items():
        found = False
        for smarts in smarts_list:
            pat = Chem.MolFromSmarts(smarts)
            if pat and mol.HasSubstructMatch(pat):
                found = True
                break
        result[key] = found

    # Special case: thiol detection via RDKit (infer implicit H on S)
    # SMARTS-only misses thiols written as plain 'S' without [SH] brackets
    if not result.get("thiol"):
        try:
            for a in mol.GetAtoms():
                if a.GetSymbol() == "S" and a.GetTotalNumHs() == 1:
                    result["thiol"] = True
                    break
        except Exception:
            pass

    return result


def count_donor_atoms(smiles: str) -> int:
    """Count N, O, S heavy atoms from SMILES using RDKit if available,
    otherwise a simple regex count."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return sum(1 for a in mol.GetAtoms()
                       if a.GetAtomicNum() in (7, 8, 16))  # N, O, S
    except Exception:
        pass
    # Fallback: count N, O, S patterns in SMILES string
    count = 0
    # Count N, O, S that are not part of explicit H
    for ch in smiles:
        if ch in ('N', 'O', 'S') and ch != 'H':
            count += 1
    return count


def compute_universal_metal_score(
    smiles: str,
    molchamb_score: float = 0.5,
    target_family: str | None = None,
) -> tuple[float, dict]:
    """Compute universal metal score [0..1] and all sub-features.

    Args:
        smiles: SMILES string of the ligand
        molchamb_score: pre-computed MolChamb score (0-1), or 0.5 if unknown
        target_family: optional family name for warhead biasing.
                       e.g., "metaloenzyme" for neutral, "gpcr" to disable
                       (only sulfonamide/hydroxamic get weighted normally)

    Returns:
        (universal_metal_score, features_dict)
        universal_metal_score: combined score [0..1]
        features_dict: all components for transparency
    """
    warheads = detect_warheads(smiles)
    donor_count = count_donor_atoms(smiles)
    any_warhead = int(any(warheads.values()))

    # Warhead vector: for each warhead type, 1 if present
    wh_vec = {k: int(warheads.get(k, False)) for k in WARHEAD_KEYS}
    n_warheads = sum(wh_vec.values())

    # If this is not a metalloenzyme, return conservative estimate
    # (only use MolChamb, which is generally neutral on non-metal targets)
    if target_family and target_family != "metaloenzyme":
        score = 0.3 * molchamb_score + 0.7 * 0.5  # pull toward 0.5
        score = max(0.0, min(1.0, score))
        return round(score, 4), {
            "any_warhead": any_warhead,
            "n_warheads": n_warheads,
            "donor_count": donor_count,
            "molchamb_score": molchamb_score,
            "is_metalloenzyme": False,
            "universal_metal_score": round(score, 4),
            "warheads": wh_vec,
        }

    # Metalloenzyme: combine signals
    # Warhead component: if ANY warhead present, high score; else 0
    if any_warhead:
        warhead_component = 0.85 + 0.10 * min(n_warheads / 3.0, 1.0)  # 0.85-0.95
    else:
        warhead_component = 0.0

    # Donor component: normalize by expected max (~50 N+O+S atoms)
    donor_component = min(1.0, donor_count / 30.0)

    # MolChamb component: raw score
    mc_component = molchamb_score

    # Combine: warhead dominates (primary signal), donor + molchamb tune
    score = 0.60 * warhead_component + 0.20 * donor_component + 0.20 * mc_component
    score = max(0.0, min(1.0, score))

    features = {
        "any_warhead": any_warhead,
        "n_warheads": n_warheads,
        "donor_count": donor_count,
        "molchamb_score": round(molchamb_score, 4),
        "is_metalloenzyme": True,
        "universal_metal_score": round(score, 4),
        "warheads": wh_vec,
    }

    return round(score, 4), features


def compute_all(smiles_list: list[str],
                molchamb_scores: list[float] | None = None,
                target_family: str | None = None
                ) -> list[tuple[float, dict]]:
    """Batch compute universal metal scores."""
    if molchamb_scores is None:
        molchamb_scores = [0.5] * len(smiles_list)
    return [
        compute_universal_metal_score(smi, mc, target_family)
        for smi, mc in zip(smiles_list, molchamb_scores)
    ]


# ── CLI ──

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smiles", type=str, required=True)
    ap.add_argument("--molchamb", type=float, default=0.5)
    ap.add_argument("--family", type=str, default=None)
    args = ap.parse_args()

    score, features = compute_universal_metal_score(
        args.smiles, args.molchamb, args.family
    )
    print(json.dumps(features, indent=2))
    print(f"\nscore = {score}")


if __name__ == "__main__":
    main()
