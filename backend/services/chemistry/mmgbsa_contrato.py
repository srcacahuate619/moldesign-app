"""Limitaciones del motor MM-GBSA legacy.

La auditoría reproducible de backend/audits/mmgbsa_parameter_integrity.py
confirma términos angulares ausentes y cargas inconsistentes entre Nonbonded,
GB y excepciones 1-4. No se ha demostrado cancelación de esos errores entre
poses. La resta de tres energías no valida por sí misma el modelo físico.
El reemplazo científico está autorizado, pero aún debe superar sus controles.
"""

from __future__ import annotations

#: Elementos con tipo de átomo asignable en la biblioteca de proteína AMBER14.
ELEMENTOS_PARAMETRIZABLES: frozenset[str] = frozenset({"C", "H", "O", "N", "S", "P"})

#: La condición bajo la cual el número significa algo. Viaja con el número:
#: a la pantalla, a la respuesta del endpoint y al dossier.
MMGBSA_CONDICION: str = (
    "Resultado del motor MM-GBSA legacy no validado científicamente: el tipado "
    "del ligando sobre AMBER14 presenta parámetros incompletos y cargas "
    "inconsistentes entre electrostática y solvatación. No se ha demostrado "
    "que permita ordenar poses, ni que sus errores se cancelen. No es comparable "
    "entre ligandos distintos ni con un ΔG experimental; no debe sustentar "
    "decisiones científicas hasta validar el protocolo de reemplazo."
)


def elementos_no_parametrizables(smiles: str) -> set[str]:
    """Los elementos del ligando que este cálculo no puede tipar.

    Devuelve un conjunto vacío cuando la molécula es tratable. Si el SMILES no
    se puede leer devuelve un conjunto vacío también: decidir que «no se puede
    parametrizar» por un fallo de parseo sería nombrar la causa equivocada, y
    el camino de abajo ya falla con su propio mensaje.
    """
    try:
        from rdkit import Chem
    except ImportError:
        return set()

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return set()
    presentes = {atomo.GetSymbol() for atomo in mol.GetAtoms()}
    return presentes - ELEMENTOS_PARAMETRIZABLES


def motivo_de_no_parametrizable(elementos: set[str]) -> str:
    """El mensaje que lee quien pulsó el botón. Nombra la causa, no el síntoma."""
    lista = ", ".join(sorted(elementos))
    return (
        f"MM-GBSA no puede parametrizar esta molécula: contiene {lista}. "
        f"El cálculo asigna al ligando tipos de átomo de la biblioteca de proteína "
        f"de AMBER14, que no tiene ninguno para esos elementos. Hacen falta "
        f"parámetros de ligando (GAFF2 vía antechamber, u OpenFF), que no forman "
        f"parte de esta instalación. El resto de la evaluación —acoplamiento, "
        f"poses y controles físicos— no depende de MM-GBSA y sigue siendo válido."
    )
