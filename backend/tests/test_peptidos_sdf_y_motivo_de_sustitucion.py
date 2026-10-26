"""Ruta peptídica: el SDF lleva sólo lo acoplado y el aviso dice por qué se sustituyó.

- SCI-A-034: el SDF «poses de docking» se escribía con todas las conformaciones del
  servicio, también las que no pasaron por Vina y el resultado descartaba.
- SCI-A-032: `aviso()` devuelve un diccionario y el código se leía con `getattr`,
  así que el aviso de sustitución decía «Sin respuesta del servicio» también cuando
  el servicio había plegado la estructura.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.avisos import Severidad, aviso
from services.docking.peptide_docking import (
    codigo_de_aviso,
    motivo_de_la_sustitucion,
    poses_acopladas_y_sdf,
)

rdkit = pytest.importorskip("rdkit")


def _molblock(smiles="CC(=O)NCC(=O)O"):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    return Chem.MolToMolBlock(mol)


def _pose(rank, afinidad, origen="vina", sdf=True):
    return SimpleNamespace(rank=rank, vina_affinity_kcal_mol=afinidad, origen=origen,
                           ligand_sdf=_molblock() if sdf else None, ligand_pdb=None,
                           complex_pdb="", rmsd=None)


def _nombres(sdf: str) -> list[str]:
    return [bloque.strip().splitlines()[0] for bloque in sdf.split("$$$$") if bloque.strip()]


# ── SCI-A-034 ────────────────────────────────────────────────────────────────

def test_una_conformacion_sin_docking_no_entra_en_el_sdf():
    aceptadas, sdf, cuentas = poses_acopladas_y_sdf(
        [_pose(1, -7.2), _pose(2, None, origen="folded_structure_only")], "CC(=O)NCC(=O)O")
    assert [p.rank for p in aceptadas] == [1]
    assert _nombres(sdf) == ["Pose_1"]
    assert cuentas == {"sin_afinidad": 1, "solo_plegado": 1, "sin_geometria": 0}


def test_el_registro_i_del_sdf_es_la_pose_i_del_resultado():
    aceptadas, sdf, _ = poses_acopladas_y_sdf(
        [_pose(1, -7.2), _pose(2, None), _pose(3, -6.1)], "CC(=O)NCC(=O)O")
    assert [p.rank for p in aceptadas] == [1, 3]
    assert _nombres(sdf) == ["Pose_1", "Pose_3"]


def test_una_pose_sin_geometria_legible_sale_de_las_dos_colecciones():
    rota = _pose(2, -6.5, sdf=False)          # sin SDF y sin PDB
    aceptadas, sdf, cuentas = poses_acopladas_y_sdf([_pose(1, -7.2), rota], "CC(=O)NCC(=O)O")
    assert [p.rank for p in aceptadas] == [1]
    assert _nombres(sdf) == ["Pose_1"]
    assert cuentas["sin_geometria"] == 1


def test_sin_poses_acopladas_el_sdf_queda_vacio():
    aceptadas, sdf, _ = poses_acopladas_y_sdf([_pose(1, None, origen="folded_structure_only")], "CCO")
    assert aceptadas == [] and sdf == ""


# ── SCI-A-032 ────────────────────────────────────────────────────────────────

def test_el_codigo_se_lee_del_diccionario_que_devuelve_aviso():
    emitido = aviso("PEPTIDO_SIN_ACOPLAMIENTO", Severidad.CRITICA, "x")
    assert isinstance(emitido, dict)
    assert codigo_de_aviso(emitido) == "PEPTIDO_SIN_ACOPLAMIENTO"
    assert codigo_de_aviso(SimpleNamespace(codigo="OTRO")) == "OTRO"


def test_tres_causas_distintas_dan_tres_motivos_distintos():
    plego = motivo_de_la_sustitucion(None, [aviso("PEPTIDO_SIN_ACOPLAMIENTO", Severidad.CRITICA, "x")])
    error = motivo_de_la_sustitucion(SimpleNamespace(error="transferencia rechazada"), [])
    nada = motivo_de_la_sustitucion(None, [])
    assert plego == ("el modelo plegó la estructura pero ninguna pose pasó por acoplamiento", True)
    assert error == ("transferencia rechazada", True)
    assert nada == ("Sin respuesta del servicio", False)


@pytest.mark.parametrize("respondio, motivo", [
    (True, "el modelo plegó la estructura pero ninguna pose pasó por acoplamiento"),
    (False, "Sin respuesta del servicio"),
])
def test_el_aviso_de_sustitucion_sale_en_ingles_con_su_causa(respondio, motivo):
    from core.i18n_plantillas import traducir
    causa = (f"el servicio respondió, pero {motivo}" if respondio
             else f"ese servicio no está disponible en esta instalación ({motivo})")
    mensaje = (f"MOTOR SUSTITUIDO: se pidió 'esmfold' y {causa}. La pose NO "
               "viene de un modelo de plegamiento: la produjo AutoDock Vina con exhaustividad "
               "reducida (4) sobre la caja declarada en el caso. No compares este resultado con "
               "uno plegado.")
    ingles = traducir(mensaje, "en")
    assert ingles.startswith("SUBSTITUTED ENGINE: 'esmfold' was requested")
    assert ("responded, but the model folded" in ingles) is respondio
    assert ("not available in this installation (No response" in ingles) is (not respondio)
