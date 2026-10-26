"""
Cobertura del campo de fuerzas: qué del sistema necesita parámetros que no vienen de serie.

Un cálculo de energía libre parametriza el sistema entero. Lo que un campo de uso
común no cubre hay que parametrizarlo aparte y declararlo, y es la causa más
frecuente de que un sistema «preparado» no arranque en el cálculo siguiente.

- **Ligando**: OpenFF 2 (Sage) y GAFF2 cubren H, C, N, O, F, P, S, Cl, Br e I.
  Cualquier otro elemento (B, Si, Se, un metal) necesita parámetros propios o
  un campo que lo cubra. Un radical tampoco tiene tipos de átomo.
- **Receptor**: los 20 aminoácidos y sus estados de protonación están en los
  campos de proteína de uso común (AMBER ff14SB y ff19SB, CHARMM36m, OPLS). Un
  metal, un cofactor o un fosforresiduo, no: necesitan parámetros adicionales.

Se mira por elemento y por nombre de residuo. Que todo esté cubierto no
garantiza que la parametrización funcione: tipos de átomo y cargas se asignan
al parametrizar y pueden fallar con grupos poco comunes. Por eso lo cubierto
queda REGISTRADO, nunca PASA.
"""

from __future__ import annotations

ELEMENTOS_CUBIERTOS = ("H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I")
FOSFORRESIDUOS = frozenset({"SEP", "TPO", "PTR"})


def elementos_del_ligando(smiles: str) -> tuple[list[str], list[str], bool] | None:
    """(elementos, los que quedan fuera de la cobertura, si es un radical); None si no se lee."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
    finally:
        RDLogger.EnableLog("rdApp.*")
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    presentes = sorted({a.GetSymbol() for a in mol.GetAtoms()},
                       key=lambda e: (ELEMENTOS_CUBIERTOS.index(e) if e in ELEMENTOS_CUBIERTOS else 99, e))
    fuera = [e for e in presentes if e not in ELEMENTOS_CUBIERTOS]
    radical = any(a.GetNumRadicalElectrons() for a in mol.GetAtoms())
    return presentes, fuera, radical


def clase_del_residuo(nombre: str) -> str:
    """«metal», «cofactor», «fosforresiduo» u «otro» para un residuo no estándar del receptor."""
    from services.docking.preflight import _es_metal
    from services.docking.preparer import ORGANIC_COFACTORS_KEPT

    if _es_metal(nombre):
        return "metal"
    if nombre in ORGANIC_COFACTORS_KEPT:
        return "cofactor"
    if nombre in FOSFORRESIDUOS:
        return "fosforresiduo"
    return "otro"
