"""
chem/pains.py

PAINS (Pan-Assay Interference Compounds) filter.
Uses RDKit's built-in FilterCatalog with the 480 PAINS substructure patterns
from Baell & Holloway (2010).

PAINS are compounds that show activity in many assays regardless of the
biological target — they are false positives that plague drug discovery.
Any serious drug discovery platform MUST filter them out.

Reference:
  Baell, J. B. & Holloway, G. A. (2010). New Substructure Filters for
  Removal of Pan Assay Interference Compounds (PAINS) from Screening
  Libraries and for Their Exclusion in Bioassays. J. Med. Chem.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rdkit import Chem
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams


@lru_cache(maxsize=1)
def _get_pains_catalog() -> FilterCatalog:
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_B)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_C)
    return FilterCatalog(params)


def check_pains(smiles: str) -> dict[str, Any]:
    """
    Check if a molecule matches any PAINS substructure.

    Returns:
        {
            "is_pains": bool,
            "matches": [
                {
                    "name": str,           # PAINS family name (e.g. "anil_di_alk")
                    "description": str,    # Human-readable description
                    "atom_indices": list[int],  # matching atom indices
                },
                ...
            ],
            "total_matches": int,
        }
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"is_pains": False, "matches": [], "total_matches": 0, "error": "Invalid SMILES"}

    catalog = _get_pains_catalog()
    entries = catalog.GetMatches(mol)

    matches = []
    for entry in entries:
        matcher = entry.GetDescription()
        # Get atom indices from each filter match
        atom_indices = []
        for fm in entry.GetFilterMatches(mol):
            for pair in fm.atomPairs:
                atom_indices.append(pair.target)
        matches.append({
            "name": matcher,
            "description": _pains_descriptions.get(matcher, "PAINS substructure match"),
            "atom_indices": list(set(atom_indices)),
        })

    return {
        "is_pains": len(matches) > 0,
        "matches": matches,
        "total_matches": len(matches),
    }


def is_pains(smiles: str) -> bool:
    """Quick check: is this molecule a PAINS compound?"""
    return check_pains(smiles)["is_pains"]


# ── Human-readable descriptions for the most common PAINS families ──────────

_pains_descriptions: dict[str, str] = {
    "anil_di_alk": "Anilines with two alkyl/aryl substituents — common false positive in biochemical assays",
    "anil_di_alk_A": "Anilines with electron-withdrawing groups — redox cyclers",
    "anil_di_alk_B": "Anilines with bulky ortho substituents",
    "anil_di_alk_C": "Dialkylanilines — phototoxic and metabolically unstable",
    "ene_one_ester": "Ene-ones with ester — Michael acceptors, covalent modifiers",
    "ene_rhodanine": "Rhodanines — historically over-represented in screening hits",
    "hzone_phenol": "Phenolhydrazones — metal chelators, redox active",
    "imine_one": "Imine/iminium species — Schiff base formers, reactive electrophiles",
    "pyrrole_c": "Pyrroles with specific substitution patterns — aggregation-prone",
    "quinone_A": "Quinones — redox cyclers, generate ROS in assays",
    "rhodanine": "Rhodanines and analogs — frequent hitters across many targets",
    "sulfonate_A": "Alkyl/aryl sulfonates — detergent-like, denature proteins",
    "thio_amide": "Thioamides — reactive, metabolically unstable",
    "thio_carbamate": "Thiocarbamates — reactive electrophiles",
    "thio_urea": "Thioureas — metal chelators, aggregators",
    "ene_sulfone": "Vinyl sulfones — irreversible covalent modifiers",
    "cyanopyridone": "Cyanopyridones — fluorescent artifacts in many assays",
    "hzone_imine": "Arylhydrazones with imine — chelators, redox cyclers",
    "imine_one_A": "Imine/enamine Michael systems — protein-reactive",
    "imine_one_B": "Extended imine/enamine systems",
    "indole_3yl_alk": "3-Alkylindoles — oxidation-prone, form reactive species",
    "keto_thiazole": "Ketothiazoles — potential aggregators",
    "mannich": "Mannich bases — reactive, form iminium species under assay conditions",
    "pyrid_imine": "Pyridyl imines — metal chelators in biological media",
    "styrene_A": "Styrenes with activating groups — covalent modifiers",
    "sulfonamide_A": "Primary sulfonamides — carbonic anhydrase inhibitors (may be genuine but flagged)",
    "thio_ester": "Thioesters — reactive acylating agents",
    "thio_ketone": "Thioketones — oxidation-prone, form reactive species",
    "thiophene_amino": "Aminothiophenes — oxidation-prone, form colored byproducts",
    "thiophene_ene": "Thiophene enes — electrophilic, potentially covalent",
    "triazole_A": "Triazoles with specific substitution — frequent hitters",
}
