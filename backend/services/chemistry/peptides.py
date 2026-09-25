"""Conservative advisory detection of linear peptides supported by ESMFold.

Routing always follows the engine selected by the user. This predicate only
offers a hint when a linear chain of at least three standard residues can be
read unambiguously. A negative result does not prove a molecule is not a
peptide: cyclic, branched and modified peptides are outside this rule.
"""

from __future__ import annotations

from sidecars.esmfold.secuencia import SecuenciaNoDeterminable, extraer_secuencia


def es_peptido_lineal(smiles: str) -> bool:
    try:
        sequence = extraer_secuencia(smiles)
    except (SecuenciaNoDeterminable, ValueError):
        return False
    return len(sequence.residuos) >= 3 and not sequence.tiene_no_estandar
