"""
Ojivas covalentes conocidas en un ligando.

Vina acopla el complejo NO covalente. Para un inhibidor covalente eso describe,
como mucho, el paso reversible previo a la reacción; un cálculo de energía libre
del inhibidor unido necesita el aducto, con parámetros para el enlace, o un
protocolo covalente. Preparación lo dice cuando el ligando lleva un grupo
reactivo de la lista.

La lista es de grupos usados a propósito como ojiva en fármacos y sondas
(acrilamidas de ibrutinib u osimertinib, nitrilos de las gliptinas y de
nirmatrelvir, borónicos de bortezomib, β-lactamas…). No es exhaustiva, y que un
grupo esté no demuestra que reaccione en este sitio: depende de que haya un
nucleófilo al alcance. Por eso pide revisión y nunca bloquea.

Se dejan fuera a propósito grupos que en fármacos casi nunca son ojiva y
llenarían la auditoría de falsos positivos: nitrilos alifáticos sin nitrógeno
en α (ruxolitinib, baricitinib), nitrilos aromáticos, enonas y chalconas, y las
arilidenolactamas (el 3-ilidenoxindol del sunitinib y del semaxanib, la
5-arilidenotiazolidinona del epalrestat): su C=C es acíclico y está junto a una
amida, pero el carbonilo es el de un anillo que lo conjuga, y son inhibidores
reversibles. Una α-metileno-lactama (CH2 terminal) sí se conserva.
"""

from __future__ import annotations

from functools import lru_cache

#: (descripción, SMARTS). Los dobles enlaces de los aceptores de Michael son
#: acíclicos (`=!@`): un enlace C=C de anillo con un carbonilo al lado es una
#: lactama o una pirimidinona, no una ojiva.
OJIVAS: tuple[tuple[str, str], ...] = (
    # El enlace Cα–C(=O) es acíclico: así no entra la arilidenolactama (el carbonilo y el Cα son del mismo
    # anillo), y sí la acrilamida de un ibrutinib o un afatinib, cuya amida puede ser cíclica pero cuyo Cα no.
    ("acrilamida (aceptor de Michael)", "[CX3]=!@[CX3]-!@[CX3](=O)[NX3]"),
    ("acrilamida (aceptor de Michael)", "[CH2]=!@[CX3;R]-@[CX3;R](=O)[NX3;R]"),
    ("acrilato (aceptor de Michael)", "[CX3]=!@[CX3]-[CX3](=O)[OX2][#6]"),
    ("alquinamida (aceptor de Michael)", "[CX2]#[CX2]-[CX3](=O)[NX3]"),
    ("vinilsulfona o vinilsulfonamida (aceptor de Michael)", "[CX3]=!@[CX3]-[SX4](=O)(=O)"),
    ("haloacetamida", "[Cl,Br,I][CH2][CX3](=O)[NX3]"),
    ("α-halocetona", "[Cl,Br,I][CH2][CX3](=O)[#6]"),
    ("epóxido", "[#6]1[#8][#6]1"),
    ("aziridina", "[#6]1[#7][#6]1"),
    ("aldehído", "[CX3H1](=O)[#6]"),
    ("ácido o éster borónico", "[BX3]([OX2])[OX2]"),
    ("α-aminonitrilo (ojiva reversible)", "[#7][CX4][CX2]#[NX1]"),
    ("cianamida", "[#7]-[CX2]#[NX1]"),
    # Fusionada (penamas, cefemas, carbapenemas) o con N-sulfonato (monobactámicos): la
    # azetidinona de la ezetimiba, con el N en un solo anillo, no acila.
    ("β-lactama", "[#6]1(=O)[#6][#6][#7;R2]1"),
    ("β-lactama", "[#6]1(=O)[#6][#6][#7]1[SX4](=O)(=O)[OX2H1,OX1-]"),
    ("β-lactona", "[#6]1(=O)[#6][#6][#8]1"),
    ("fluoruro de sulfonilo", "[SX4](=O)(=O)F"),
    ("fluorofosfonato", "[PX4](=O)F"),
    ("α-cetoamida (ojiva reversible)", "[CX3](=O)([#6])[CX3](=O)[NX3]"),
    ("isotiocianato", "[NX2]=C=S"),
)


@lru_cache(maxsize=1)
def _patrones():
    from rdkit import Chem

    patrones = []
    for descripcion, smarts in OJIVAS:
        patron = Chem.MolFromSmarts(smarts)
        if patron is None:  # pragma: no cover — lo vigila una prueba
            raise ValueError(f"SMARTS inválido para «{descripcion}»: {smarts}")
        patrones.append((descripcion, patron))
    return tuple(patrones)


def ojivas(smiles: str) -> list[str] | None:
    """Las ojivas del ligando, en el orden de `OJIVAS`; None si el SMILES no se lee."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
    finally:
        RDLogger.EnableLog("rdApp.*")
    if mol is None:
        return None
    return [descripcion for descripcion, _ in ojivas_en_mol(mol)]


def ojivas_en_mol(mol) -> list[tuple[str, list[int]]]:
    """Cada ojiva de `mol`, en el orden de `OJIVAS`, con los átomos que la forman
    (todas sus coincidencias juntas). Es la búsqueda de `ojivas`, con el dónde."""
    encontradas: dict[str, set[int]] = {}
    for descripcion, patron in _patrones():
        for coincidencia in mol.GetSubstructMatches(patron):
            encontradas.setdefault(descripcion, set()).update(coincidencia)
    return [(descripcion, sorted(atomos)) for descripcion, atomos in encontradas.items()]
