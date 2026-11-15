"""Qué cambia, estructuralmente, entre la molécula base y un análogo.

La tabla SAR mostraba en cada fila «Protocolo estructural y condiciones químicas coincidentes»: eso dice que la
comparación es legítima, no QUÉ cambió. Aquí se mide: el núcleo común máximo (RDKit `rdFMCS`, con plazo) y la
diferencia de fórmula. Es una descripción geométrica del grafo, no una explicación de por qué cambia la afinidad.

Puro: recibe dos SMILES, no toca base de datos ni HTTP. Si algo no se puede medir, devuelve `None`, no un valor.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

#: Plazo del MCS por análogo; pasado esto se declara «incompleto» y no se usa el resultado parcial como completo.
MCS_TIMEOUT_S = 2


def _elementos(mol: Any) -> Counter:
    from rdkit import Chem

    return Counter(atom.GetSymbol() for atom in Chem.AddHs(mol).GetAtoms())


def cambio_estructural(base_smiles: str | None, analogo_smiles: str | None) -> dict[str, Any] | None:
    """`{core_heavy_atoms, base_heavy_atoms, analog_heavy_atoms, formula_delta, core_complete}` o `None`."""
    if not base_smiles or not analogo_smiles:
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem import rdFMCS

        base, analogo = Chem.MolFromSmiles(base_smiles), Chem.MolFromSmiles(analogo_smiles)
        if base is None or analogo is None:
            return None
        mcs = rdFMCS.FindMCS(
            [base, analogo], timeout=MCS_TIMEOUT_S, ringMatchesRingOnly=True, completeRingsOnly=True,
        )
        a, b = _elementos(base), _elementos(analogo)
        delta = {el: b[el] - a[el] for el in set(a) | set(b) if b[el] != a[el]}
        orden = sorted(delta, key=lambda el: (el not in ("C", "H"), el != "C", el))
        return {
            "core_heavy_atoms": mcs.numAtoms,
            "base_heavy_atoms": base.GetNumHeavyAtoms(),
            "analog_heavy_atoms": analogo.GetNumHeavyAtoms(),
            "formula_delta": [{"element": el, "delta": delta[el]} for el in orden],
            "core_complete": not mcs.canceled,
        }
    except Exception:  # noqa: BLE001 - una fila sin descripción es válida; una tabla que falla no
        return None
