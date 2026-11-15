"""Constructores compartidos por los controles de explicabilidad (extractor y SHAP).

Módulo plano (sin `test_`): pytest no lo recoge y los dos archivos de controles lo importan.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

Chem = pytest.importorskip("rdkit.Chem")
from rdkit.Chem import AllChem  # noqa: E402

from feature_extractor import InteractionFeatureExtractor  # noqa: E402


def embeber_peptido(secuencia: str, semilla: int = 7):
    # `addResidueInfo=True`: sin ella los H salen como HETATM, y el analizador de contactos (que sólo
    # lee registros ATOM, como el receptor real, cuyos H polares del PDBQT son ATOM) los descartaría
    # y los regeneraría en otra posición.
    m = Chem.AddHs(Chem.MolFromSequence(secuencia), addCoords=True, addResidueInfo=True)
    p = AllChem.ETKDGv3()
    p.useRandomCoords = True
    p.randomSeed = semilla
    p.maxIterations = 2000
    assert AllChem.EmbedMolecule(m, p) == 0, "el péptido de control no se pudo incrustar en 3D"
    AllChem.MMFFOptimizeMolecule(m, maxIters=2000)
    return m


def construir_peptidos(tmp_path_factory):
    """Dos péptidos que juntos tienen los 20 aminoácidos, con y sin hidrógenos explícitos."""
    d = tmp_path_factory.mktemp("peptidos")
    salida = {}
    for nombre, seq in (("A", "ACDEFGHIKL"), ("B", "MNPQRSTVWY")):
        mol = embeber_peptido(seq)
        con_h, sin_h = d / f"{nombre}_h.pdb", d / f"{nombre}_noh.pdb"
        Chem.MolToPDBFile(mol, str(con_h))
        Chem.MolToPDBFile(Chem.RemoveHs(mol), str(sin_h))
        salida[nombre] = {"mol": mol, "h": str(con_h), "noh": str(sin_h), "seq": seq}
    return salida


def extractor_geometrico() -> InteractionFeatureExtractor:
    ex = InteractionFeatureExtractor()
    ex._prolif_ok = False  # los controles son geométricos; ProLIF no interviene
    return ex


def colocar(mol, centro: np.ndarray, desplazamiento=(4.0, 0.0, 0.0)):
    """Centra el ligando en `centro` + desplazamiento, con coordenadas a 3 decimales
    (la precisión de un PDBQT), para que SDF y PDBQT describan EXACTAMENTE la misma geometría."""
    conf = mol.GetConformer()
    pos = conf.GetPositions()
    pos = pos - pos.mean(axis=0) + centro + np.array(desplazamiento)
    for i, p in enumerate(np.round(pos, 3)):
        conf.SetAtomPosition(i, p.tolist())
    return mol


def ligando_3d(smiles: str, semilla: int = 11):
    m = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(m, randomSeed=semilla) == 0, smiles
    return m


def escribir_sdf(mol, ruta: Path) -> str:
    w = Chem.SDWriter(str(ruta))
    w.write(mol)
    w.close()
    return str(ruta)


def modelos_pdbqt(ruta: Path) -> list[str]:
    modelos, actual, dentro = [], [], False
    for ln in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("MODEL"):
            dentro, actual = True, [ln]
        elif ln.startswith("ENDMDL"):
            actual.append(ln)
            modelos.append("\n".join(actual))
            dentro = False
        elif dentro:
            actual.append(ln)
    return modelos
