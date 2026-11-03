"""Regresión con datos reales: las poses 1-3 de la corrida de 8T69 dan 5, 7 y 9 contactos, con residuo, tipo y distancia.

La corrida (clopidogrel contra VMAT2, Vina 1.2.7, exhaustividad 8, 9 poses, semilla 42) daba CERO contactos en las poses 1
y 2 antes de que el receptor llegara a ProLIF con la química de sus residuos (2026-11-02). `interacciones_8t69/` guarda el
bolsillo (los residuos a 12 Å o menos de las tres poses) y las tres poses; `esperado.json` lo que ProLIF 2.1.0 midió sobre
el receptor entero, comprobado idéntico sobre este bolsillo. Una ejecución afortunada no basta: la prueba exige la lista
exacta, y su control negativo muestra que sin la química los contactos desaparecen.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from rdkit import Chem

from api.routers.interactions import _pdbqt_receptor_a_pdb
from services.interactions import analyzer
from services.interactions.analyzer import analyze_complex

DATOS = Path(__file__).parent / "data" / "interacciones_8t69"
ESPERADO = json.loads((DATOS / "esperado.json").read_text(encoding="utf-8"))["poses"]
POSES = [m for m in Chem.SDMolSupplier(str(DATOS / "poses_1_a_3.sdf"), removeHs=False)]
TOLERANCIA_A = 0.011  # la distancia se guarda redondeada a dos decimales


def _analizar(tmp_path: Path, rank: int, desplazamiento: float = 0.0):
    receptor = tmp_path / "receptor.pdb"
    receptor.write_text(_pdbqt_receptor_a_pdb((DATOS / "bolsillo.pdbqt").read_text(encoding="utf-8")), encoding="utf-8")
    mol = Chem.Mol(POSES[rank - 1])
    if desplazamiento:
        conformador = mol.GetConformer()
        for i in range(mol.GetNumAtoms()):
            p = conformador.GetAtomPosition(i)
            conformador.SetAtomPosition(i, (p.x + desplazamiento, p.y, p.z))
    ligando = tmp_path / "pose.sdf"
    ligando.write_text(Chem.MolToMolBlock(mol) + "\n$$$$\n", encoding="utf-8")
    return analyze_complex(receptor, ligando, molecule_id="clopidogrel", target_pdb_id="8T69", pose_rank=rank)


def _contactos(informe) -> list[tuple[str, str, float]]:
    return sorted((i.type, f"{i.residue_name}{i.residue_number}{i.residue_chain}", i.distance) for i in informe.interactions)


@pytest.mark.parametrize("rank,cuantos", [(1, 5), (2, 7), (3, 9)])
def test_las_poses_de_la_corrida_real_dan_sus_contactos_con_residuo_tipo_y_distancia(tmp_path, rank, cuantos):
    informe = _analizar(tmp_path, rank)
    esperado = ESPERADO[str(rank)]
    assert informe.engine.startswith("prolif:") and informe.receptor_chemistry == esperado["receptor_chemistry"]
    obtenido = _contactos(informe)
    assert len(obtenido) == cuantos == len(esperado["contacts"])
    assert [(tipo, residuo) for tipo, residuo, _ in obtenido] == [(tipo, residuo) for tipo, residuo, _ in esperado["contacts"]]
    for (_, residuo, medida), (_, _, previsto) in zip(obtenido, esperado["contacts"]):
        assert medida == pytest.approx(previsto, abs=TOLERANCIA_A), residuo


def test_la_pose_1_toca_el_bolsillo_aromatico_y_la_2_agrega_el_puente_salino_con_glu312(tmp_path):
    """Lo que el investigador lee: la pose 1 apila con Tyr433; la 2 con Phe334 y además puentea con Glu312."""
    uno, dos = _contactos(_analizar(tmp_path, 1)), _contactos(_analizar(tmp_path, 2))
    assert ("pi_stacking", "TYR433A") in [(t, r) for t, r, _ in uno]
    assert ("pi_stacking", "PHE334A") in [(t, r) for t, r, _ in dos]
    assert ("salt_bridge", "GLU312A") in [(t, r) for t, r, _ in dos] and not [c for c in uno if c[0] == "salt_bridge"]


def test_sin_la_quimica_del_receptor_los_mismos_datos_pierden_los_contactos(tmp_path, monkeypatch):
    """Control negativo: es la química de los residuos lo que produce los contactos, no un artefacto de la entrada."""
    def sin_plantilla(mol):
        raise RuntimeError("plantilla desactivada por la prueba")

    monkeypatch.setattr(analyzer, "_aplicar_quimica_estandar", sin_plantilla)
    informe = _analizar(tmp_path, 1)
    assert informe.engine.startswith("prolif:") and informe.receptor_chemistry == "bonds_by_distance_only"
    assert len(informe.interactions) < len(ESPERADO["1"]["contacts"])
    assert not [i for i in informe.interactions if i.type in ("pi_stacking", "salt_bridge")]


def _angulo(a, vertice, b) -> float:
    u, v = np.array(a) - np.array(vertice), np.array(b) - np.array(vertice)
    return float(np.degrees(np.arccos(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v))))


def _moleculas_con_hidrogenos(tmp_path: Path, rank: int):
    """El ligando y el receptor tal como ProLIF los recibe, para medir la geometría sin ProLIF."""
    ligando = Chem.AddHs(Chem.Mol(POSES[rank - 1]), addCoords=True)
    receptor, _ = analyzer._leer_receptor(_pdbqt_receptor_a_pdb((DATOS / "bolsillo.pdbqt").read_text(encoding="utf-8")))
    analyzer._renumerar_residuos_negativos(receptor)
    return ligando, analyzer._hidrogenos_en_su_residuo(Chem.AddHs(receptor, addCoords=True))


def _posicion(mol, i: int):
    p = mol.GetConformer().GetAtomPosition(i)
    return (p.x, p.y, p.z)


def test_en_la_pose_3_el_puente_salino_y_el_enlace_de_hidrogeno_con_glu312_son_el_mismo_par_de_atomos(tmp_path):
    """Un N+–H y un carboxilato cumplen a la vez el criterio iónico y el de enlace de hidrógeno: dos criterios, un contacto."""
    informe = _analizar(tmp_path, 3)
    glu = {i.type: i for i in informe.interactions if i.type in ("hbond", "salt_bridge") and i.residue_number == 312}
    assert set(glu) == {"hbond", "salt_bridge"}
    assert glu["hbond"].ligand_atom == glu["salt_bridge"].ligand_atom and glu["hbond"].protein_atom == glu["salt_bridge"].protein_atom
    assert set(glu["salt_bridge"].ligand_atom_indices) <= set(glu["hbond"].ligand_atom_indices)
    assert glu["salt_bridge"].distance == glu["hbond"].distance
    # El N de la pose está protonado (N+ con un H): es la especie que se acopló, no la que se escribió.
    ligando, _ = _moleculas_con_hidrogenos(tmp_path, 3)
    nitrogeno = ligando.GetAtomWithIdx(glu["salt_bridge"].ligand_atom_indices[0])
    assert nitrogeno.GetSymbol() == "N" and nitrogeno.GetFormalCharge() == 1
    assert sum(1 for vecino in nitrogeno.GetNeighbors() if vecino.GetAtomicNum() == 1) == 1


def test_la_distancia_y_el_angulo_del_enlace_de_hidrogeno_de_la_pose_3_se_reproducen_sin_prolif(tmp_path):
    informe = _analizar(tmp_path, 3)
    enlace = next(i for i in informe.interactions if i.type == "hbond" and i.residue_number == 312)
    ligando, receptor = _moleculas_con_hidrogenos(tmp_path, 3)
    donante, hidrogeno = enlace.ligand_atom_indices
    (aceptor,) = enlace.protein_atom_indices
    assert np.linalg.norm(np.array(_posicion(ligando, donante)) - np.array(_posicion(receptor, aceptor))) == pytest.approx(
        enlace.geometry["distance"], abs=0.01)
    angulo = _angulo(_posicion(ligando, donante), _posicion(ligando, hidrogeno), _posicion(receptor, aceptor))
    assert angulo == pytest.approx(enlace.geometry["DHA_angle"], abs=0.5) and 130 <= angulo <= 180


def test_el_contacto_halogeno_de_la_pose_3_apunta_a_un_carbono_aromatico_de_la_phe429_y_sus_angulos_se_reproducen(tmp_path):
    """Cl···C(anillo): ProLIF lo llama halógeno; el átomo de la proteína no es un O, N ni S con par solitario."""
    informe = _analizar(tmp_path, 3)
    halogeno = next(i for i in informe.interactions if i.type == "halogen")
    assert (halogeno.residue_name, halogeno.residue_number) == ("PHE", 429)
    ligando, receptor = _moleculas_con_hidrogenos(tmp_path, 3)
    carbono, cloro = halogeno.ligand_atom_indices
    aceptor, vecino = halogeno.protein_atom_indices
    assert ligando.GetAtomWithIdx(cloro).GetSymbol() == "Cl"
    assert receptor.GetAtomWithIdx(aceptor).GetSymbol() == "C" and receptor.GetAtomWithIdx(aceptor).GetIsAromatic()
    assert _angulo(_posicion(ligando, carbono), _posicion(ligando, cloro), _posicion(receptor, aceptor)) == pytest.approx(
        halogeno.geometry["AXD_angle"], abs=0.5)
    assert _angulo(_posicion(ligando, cloro), _posicion(receptor, aceptor), _posicion(receptor, vecino)) == pytest.approx(
        halogeno.geometry["XAR_angle"], abs=0.5)


def test_una_pose_lejos_del_bolsillo_da_cero_contactos_y_el_motor_no_inventa_ninguno(tmp_path):
    """Control negativo geométrico con el receptor real: la misma pose, 60 Å lejos, no toca nada."""
    informe = _analizar(tmp_path, 1, desplazamiento=60.0)
    assert informe.engine.startswith("prolif:")
    assert informe.interactions == []
