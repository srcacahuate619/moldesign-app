"""Piezas comunes de E1, E2 y E3 (ver REGISTRO_PREVIO.md).

`candidatos` reproduce `chem.elevacion._conformadores` conservando la molécula
con hidrógenos (E2 la necesita para xTB); `comprobar_reproduccion` verifica que
elige lo mismo que el producto antes de medir nada.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
logging.disable(logging.CRITICAL)

import numpy as np  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from chem.elevacion import (  # noqa: E402
    SEMILLAS_CRITERIO,
    _ajuste,
    _candidatos,
    _pesos,
    dibujo_2d,
    modelo_desde_conformador,
)

ABSTENCION = AQUI.parent / "elevacion-abstencion-2026-10-24"


def g37() -> list[dict]:
    return [json.loads(l) for l in open(ABSTENCION / "grandes.jsonl", encoding="utf-8")]


def o167() -> list[dict]:
    return [json.loads(l) for l in open(ABSTENCION / "moleculas.jsonl", encoding="utf-8")]


def longitud_media(mol: Chem.Mol, plano: np.ndarray) -> float:
    return float(np.mean([np.linalg.norm(plano[e.GetBeginAtomIdx()] - plano[e.GetEndAtomIdx()])
                          for e in mol.GetBonds()]))


def razon(mol: Chem.Mol, xyz: np.ndarray, plano: np.ndarray, pesos: np.ndarray) -> float:
    """Desajuste del ajuste del producto frente a la longitud media de enlace del dibujo."""
    return _ajuste(xyz, plano, pesos)[1] / longitud_media(mol, plano)


def candidatos(mol: Chem.Mol, semilla: int, n: int, coord_map: dict | None = None):
    """Como `_conformadores` (mismos parámetros), devolviendo la molécula con H,
    los ids y la energía MMFF94 de cada candidato."""
    con_h = Chem.AddHs(mol)
    parametros = AllChem.ETKDGv3()
    parametros.randomSeed = semilla
    parametros.pruneRmsThresh = 0.1
    if coord_map:
        parametros.SetCoordMap(coord_map)
    ids = list(AllChem.EmbedMultipleConfs(con_h, numConfs=n, params=parametros))
    if not ids:
        parametros.useRandomCoords = True
        ids = list(AllChem.EmbedMultipleConfs(con_h, numConfs=n, params=parametros))
    if not ids:
        return con_h, [], []
    resultado = AllChem.MMFFOptimizeMoleculeConfs(con_h, maxIters=200)
    por_id = {conf.GetId(): e for conf, (_, e) in zip(con_h.GetConformers(), resultado)}
    return con_h, ids, [float(por_id[i]) for i in ids]


def pesados(con_h: Chem.Mol, cid: int, n: int) -> np.ndarray:
    return con_h.GetConformer(cid).GetPositions()[:n]


def comprobar_reproduccion(smiles: str) -> None:
    """El elegido aquí tiene el mismo desajuste que el del producto."""
    mol = Chem.MolFromSmiles(smiles)
    dib = dibujo_2d(Chem.Mol(mol))
    pesos = _pesos(mol)
    n = mol.GetNumAtoms()
    mejor = min(_ajuste(pesados(h, c, n), dib.plano, pesos)[1]
                for s in SEMILLAS_CRITERIO
                for h, ids, _ in [candidatos(mol, s, _candidatos(n))] for c in ids)
    producto = modelo_desde_conformador(smiles)
    a = producto["desajuste_px"]
    # El producto da el desajuste en px del lienzo; se compara la razón, que no depende de la escala.
    assert abs(mejor / longitud_media(mol, dib.plano) * producto["enlace_px"] - a) < 0.15, (smiles, mejor, a)
