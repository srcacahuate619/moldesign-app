"""
Qué se puede afirmar de un ΔG de MM-GBSA producido por este programa.

# Por qué existe este archivo

La interfaz prometía, literalmente:

    «Usa la pose real de docking y reporta ΔG = G(complejo) − G(receptor) − G(ligando).»

La primera mitad es cierta. La segunda describe la aritmética, no el modelo, y
al leerse sola invita a tratar el número como una energía libre de unión
calculada con un campo de fuerzas adecuado. No lo es, por una razón concreta y
comprobable en el código:

**El ligando se parametriza con los tipos de átomo de la biblioteca de PROTEÍNA
de AMBER14.** `services/chemistry/molchamb_v2.py::_amber_atom_type` mapea cada
carbono del ligando a `protein-CT` / `protein-CA` / `protein-C`, cada nitrógeno
a `protein-N` / `protein-NB` / `protein-N3`, y así. Son los tipos de una cadena
peptídica. De ahí salen los parámetros de enlace, ángulo y torsión que se
aplican a una molécula orgánica que no es un péptido.

Lo que SÍ es correcto en ese cálculo, y conviene no tirarlo con el agua sucia:

  · la pose es la real del acoplamiento, no un confórmero arbitrario;
  · las cargas parciales del ligando se sustituyen por las de GFN2-xTB
    (`_override_charges`), así que el término electrostático no usa las cargas
    de proteína;
  · la resta `g_complex − g_protein − g_ligand` se hace de verdad, sobre las
    tres topologías, no sobre la energía total del complejo.

Y lo que NO se puede arreglar declarándolo: sin GAFF2 vía antechamber, o sin
`openff-toolkit`, los términos enlazados del ligando seguirán siendo los de un
péptido. Por eso la salida se presenta como una **ordenación relativa entre
poses del mismo ligando contra el mismo receptor**, que es para lo que el error
sistemático se cancela, y no como un ΔG comparable entre ligandos distintos.

# Los elementos

`molchamb_v2` ya rechazaba F, Cl, Br, I y todo lo que no fuera C/H/O/N/S/P
—no hay tipo de proteína para un halógeno—, pero lo hacía **después** de
preparar el receptor y construir el sistema, y devolvía `Unsupported elements:
{'Cl'}` en inglés y por la vía de un error genérico. En química médica los
halógenos son cotidianos, así que ese camino no es un caso raro: es el caso.
Aquí se comprueba antes, y se dice en una frase que explica por qué.
"""

from __future__ import annotations

#: Elementos con tipo de átomo asignable en la biblioteca de proteína AMBER14.
ELEMENTOS_PARAMETRIZABLES: frozenset[str] = frozenset({"C", "H", "O", "N", "S", "P"})

#: La condición bajo la cual el número significa algo. Viaja con el número:
#: a la pantalla, a la respuesta del endpoint y al dossier.
MMGBSA_CONDICION: str = (
    "ΔG obtenido con la pose real del acoplamiento y cargas GFN2-xTB, pero con el "
    "ligando tipado sobre la biblioteca de proteína de AMBER14: sus parámetros de "
    "enlace, ángulo y torsión son los de una cadena peptídica, no los de una "
    "molécula orgánica. Sirve para ORDENAR poses del mismo ligando contra el mismo "
    "receptor, donde ese error sistemático se cancela. No es comparable entre "
    "ligandos distintos ni con un ΔG experimental."
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
