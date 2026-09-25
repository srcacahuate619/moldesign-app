"""Local RDKit structural alerts for exploratory molecules.

PAINS A/B/C and BRENK are screening flags, not toxicity predictions.
Candidate generators abstain on a match; callers can show the matched
catalog descriptions without implying confirmed biological effects.
"""

from __future__ import annotations

from functools import lru_cache

from rdkit import Chem
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams


@lru_cache(maxsize=1)
def _catalog() -> FilterCatalog:
    params = FilterCatalogParams()
    for category in (
        FilterCatalogParams.FilterCatalogs.PAINS_A,
        FilterCatalogParams.FilterCatalogs.PAINS_B,
        FilterCatalogParams.FilterCatalogs.PAINS_C,
        FilterCatalogParams.FilterCatalogs.BRENK,
    ):
        params.AddCatalog(category)
    return FilterCatalog(params)


def alertas_estructurales(mol: Chem.Mol) -> list[str]:
    return sorted({entry.GetDescription() for entry in _catalog().GetMatches(mol)})
