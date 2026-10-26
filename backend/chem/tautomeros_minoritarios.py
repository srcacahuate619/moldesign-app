"""Tautómeros con población despreciable en agua, por reglas con base química.

# Qué problema resuelve

El enumerador de RDKit (`chem/declaracion_tautomeros.py`) genera candidatos sin
saber cuáles existen. Para la aspirina daba dos (el éster y su enol) y para la
acetona también, así que casi todo fármaco salía «multiestado» y el aviso dejaba
de distinguir nada. Y al revés: si lo acoplado ERA una forma sin población (el
hidroxamato de vorinostat como iminol), no había regla que lo dijera.

# Las reglas

Sólo clases con equilibrio conocido y muy desplazado en agua, del orden de 10⁻³ o
menos para la forma minoritaria:

    iminol         amida o hidroxamato como ácido imídico, C(OH)=N
    enol           enol de cetona, aldehído, éster o ácido sin conjugar con un
                   carbonilo (los 1,3-dicarbonílicos y los ácidos vinílogos, como
                   oxicams o 4-hidroxicumarinas, se excluyen: ahí el enol pesa)
    hidroxiazina   OH en orto o para de un N piridínico de un anillo de seis
                   (2- y 4-hidroxipiridina, lactimas de uracilo o guanina): en
                   agua domina la forma oxo
    imino          heteroaromático con =N exocíclico (2-iminopiridina): domina
                   la forma amino
    nitroso        C-nitroso con H en el carbono: tautomeriza a oxima o, en un
                   hidroxamato, a la forma ceto
    desaromatizado el candidato tiene menos átomos aromáticos que el más
                   aromático (la forma ceto de un fenol)

Lo que no casa con ninguna regla no se juzga: el N1-H y el N3-H de una guanina,
o los 1H/2H de un tetrazol, siguen siendo varios estados. Esto no es un modelo de
poblaciones: dice qué candidatos se pueden descartar con química de manual, no
cuál domina entre los que quedan.
"""

from __future__ import annotations

from functools import lru_cache

#: (regla, SMARTS de la forma minoritaria). El orden es el del mensaje.
_REGLAS: tuple[tuple[str, str], ...] = (
    ("iminol", "[C;!a](-[OX2H1])=[N;!a]"),
    ("enol", "[C;!a](-[OX2H1])=[C;!a]"),
    ("hidroxiazina", "[OX2H1]-[c;r6]:[nX2;r6]"),
    ("hidroxiazina", "[OX2H1]-[c;r6]:[c;r6]:[c;r6]:[nX2;r6]"),
    ("imino", "[NX2;!R]=[c,n]"),
    ("nitroso", "[CX4;!H0]-[NX2]=[OX1]"),
)

#: Enoles que sí pesan: conjugados con un carbonilo (1,3-dicarbonílicos, ácidos vinílogos).
_ENOL_CONJUGADO = "[OX2H1]-[C;!a]=[C;!a]-[C,S]=[O,N]"

DESCRIPCION = {
    "iminol": "amida o hidroxamato como ácido imídico (iminol)",
    "enol": "enol de un carbonilo sin conjugar",
    "hidroxiazina": "hidroxiazina en vez de su forma oxo",
    "imino": "imina exocíclica en vez de la amina aromática",
    "nitroso": "nitroso en vez de oxima o hidroxamato",
    "desaromatizado": "pierde aromaticidad",
}


@lru_cache(maxsize=1)
def _patrones():
    from rdkit import Chem

    return ([(regla, Chem.MolFromSmarts(smarts)) for regla, smarts in _REGLAS],
            Chem.MolFromSmarts(_ENOL_CONJUGADO))


def _aromaticos(mol) -> int:
    return sum(1 for atomo in mol.GetAtoms() if atomo.GetIsAromatic())


def reglas_que_cumple(smiles: str, max_aromaticos: int | None = None) -> list[str]:
    """Las reglas de forma minoritaria que cumple `smiles`; vacía si ninguna o si no se puede leer."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    patrones, enol_conjugado = _patrones()
    conjugados = {coincidencia[0] for coincidencia in mol.GetSubstructMatches(enol_conjugado)}
    reglas: list[str] = []
    for regla, patron in patrones:
        coincidencias = mol.GetSubstructMatches(patron)
        if regla == "enol":
            coincidencias = [c for c in coincidencias if c[1] not in conjugados]
        if coincidencias and regla not in reglas:
            reglas.append(regla)
    if max_aromaticos is not None and _aromaticos(mol) < max_aromaticos:
        reglas.append("desaromatizado")
    return reglas


def clasificar(candidatos: list[str]) -> dict[str, list[str]]:
    """{SMILES: reglas} para cada candidato; una lista vacía es un candidato plausible."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    mols = [Chem.MolFromSmiles(s) for s in candidatos]
    maximo = max((_aromaticos(m) for m in mols if m is not None), default=0)
    return {s: reglas_que_cumple(s, maximo) for s in candidatos}
