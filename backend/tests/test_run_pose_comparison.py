"""Comparar la pose de una molécula entre dos evaluaciones.

Lo que protege, en orden de gravedad:

1. **Sin marco común no hay RMSD.** Con otro receptor preparado (o sin declararlo) la distancia entre coordenadas no
   significa nada; se abstiene con su motivo y la energía sigue enseñándose.
2. **Sólo la misma molécula.** Moléculas distintas no tienen correspondencia atómica; no se inventa un RMSD.
3. **La distancia es la geométrica.** Un desplazamiento rígido de 1 Å da 1 Å.
4. **Se nombra lo que difiere** entre las dos corridas (semilla, exhaustividad, receptor...).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.evaluation.run_pose_comparison import (
    compare_runs,
    frame_status,
    protocol_differences,
    rmsd_between_sdfs,
)

GOLDEN = json.loads((Path(__file__).parent / "data" / "pose_comparison_golden.json").read_text(encoding="utf-8"))


def _sdf(smiles: str, shift: float = 0.0) -> str:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    conformer = mol.GetConformer()
    for i in range(mol.GetNumAtoms()):
        p = conformer.GetAtomPosition(i)
        conformer.SetAtomPosition(i, (p.x + shift, p.y, p.z))
    return Chem.MolToMolBlock(mol) + "$$$$\n"


def test_desplazamiento_rigido_de_un_angstrom_da_un_angstrom():
    medida = rmsd_between_sdfs(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CC(=O)Nc1ccccc1", shift=1.0), 1)
    assert medida["available"] is True
    assert medida["rmsd_angstrom"] == pytest.approx(1.0, abs=0.01)


def test_moleculas_distintas_no_se_miden():
    medida = rmsd_between_sdfs(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CCO"), 1)
    assert medida["available"] is False
    assert medida["reason_code"] == "NOT_THE_SAME_MOLECULE"
    assert medida["rmsd_angstrom"] is None


def test_una_pose_que_no_existe_se_dice_y_de_que_lado():
    medida = rmsd_between_sdfs(_sdf("CCO"), 1, _sdf("CCO"), 3)
    assert medida["available"] is False
    assert medida["reason_code"] == "POSE_NOT_IN_SDF"
    assert medida["side"] == "b"


def test_marco_comun_exige_el_mismo_receptor_declarado():
    assert frame_status({"receptor_sha256": "x"}, {"receptor_sha256": "x"}) == "same"
    assert frame_status({"receptor_sha256": "x"}, {"receptor_sha256": "y"}) == "different"
    assert frame_status({"receptor_sha256": "x"}, {}) == "undeclared"
    assert frame_status({}, {}) == "undeclared"


def test_diferencias_de_protocolo_nombran_ambos_valores():
    a = {"receptor_sha256": "r1", "vina_random_seed": 42, "docking_protocol": {"exhaustiveness": 8, "num_poses": 9}}
    b = {"receptor_sha256": "r1", "vina_random_seed": 7, "docking_protocol": {"exhaustiveness": 32, "num_poses": 9}}
    assert {d["field"]: (d["a"], d["b"]) for d in protocol_differences(a, b)} == {
        "seed": (42, 7), "exhaustiveness": (8, 32),
    }
    assert protocol_differences(a, copy.deepcopy(a)) == []


def _resultado() -> dict:
    return copy.deepcopy(GOLDEN["scenarios"][0]["result"])


def test_con_otro_receptor_abstiene_del_rmsd_pero_enseña_la_energia():
    a, b = _resultado(), _resultado()
    a["receptor_sha256"], b["receptor_sha256"] = "r1", "r2"
    medida = {"available": True, "reason_code": None, "rmsd_angstrom": 0.4, "heavy_atoms": 10}
    comparacion = compare_runs(a, b, 1, 1, medida)
    assert comparacion["frame"] == "different"
    rmsd = comparacion["difference"]["pose_rmsd_between_runs"]
    assert rmsd["available"] is False and rmsd["reason_code"] == "DIFFERENT_RECEPTOR"
    assert rmsd["rmsd_angstrom"] is None
    assert comparacion["a"]["found"] and comparacion["b"]["found"]
    assert comparacion["difference"]["b_minus_a_vina_kcal_mol"] == 0
    assert {d["field"] for d in comparacion["protocol_differences"]} == {"receptor_sha256"}


def test_con_el_mismo_receptor_conserva_la_distancia_medida():
    a, b = _resultado(), _resultado()
    a["receptor_sha256"] = b["receptor_sha256"] = "r1"
    medida = {"available": True, "reason_code": None, "rmsd_angstrom": 0.4, "heavy_atoms": 10}
    comparacion = compare_runs(a, b, 1, 1, medida)
    assert comparacion["frame"] == "same"
    assert comparacion["difference"]["pose_rmsd_between_runs"]["rmsd_angstrom"] == 0.4


# ── Análogos: RMSD del núcleo común ───────────────────────────────────────────

from services.evaluation.run_pose_comparison import compare_analogs, rmsd_core_between_sdfs  # noqa: E402


def _par_alineado(base: str, analogo: str, shift: float = 0.0):
    """El análogo se construye a partir de la base para que el núcleo comparta coordenadas (más un desplazamiento)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol_base = Chem.AddHs(Chem.MolFromSmiles(base))
    AllChem.EmbedMolecule(mol_base, randomSeed=11)
    mol_analogo = Chem.AddHs(Chem.MolFromSmiles(analogo))
    AllChem.ConstrainedEmbed(mol_analogo, Chem.RemoveHs(mol_base), randomseed=11)
    conformer = mol_analogo.GetConformer()
    for i in range(mol_analogo.GetNumAtoms()):
        p = conformer.GetAtomPosition(i)
        conformer.SetAtomPosition(i, (p.x + shift, p.y, p.z))
    return Chem.MolToMolBlock(mol_base) + "$$$$\n", Chem.MolToMolBlock(mol_analogo) + "$$$$\n"


def test_el_nucleo_comun_de_dos_analogos_se_mide_sin_contar_el_sustituyente():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    medida = rmsd_core_between_sdfs(base, 1, analogo, 1)
    assert medida["available"] is True
    assert medida["core_heavy_atoms"] >= 9
    assert medida["rmsd_angstrom"] < 0.5
    assert medida["heavy_atoms_b"] == medida["heavy_atoms_a"] + 1


def test_un_desplazamiento_rigido_del_analogo_es_la_distancia_del_nucleo():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1", shift=2.0)
    medida = rmsd_core_between_sdfs(base, 1, analogo, 1)
    assert medida["available"] is True
    assert medida["rmsd_angstrom"] == pytest.approx(2.0, abs=0.5)


def test_sin_nucleo_comun_suficiente_se_abstiene_y_dice_cuanto_compartian():
    medida = rmsd_core_between_sdfs(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CCCCCCCCO"), 1)
    assert medida["available"] is False
    assert medida["reason_code"] == "CORE_TOO_SMALL"
    assert medida["rmsd_angstrom"] is None
    assert "core_heavy_atoms" in medida


def test_analogos_con_otro_receptor_no_miden_el_nucleo_pero_enseñan_la_energia():
    a, b = _resultado(), _resultado()
    a["receptor_sha256"], b["receptor_sha256"] = "r1", "r2"
    nucleo = {"available": True, "reason_code": None, "rmsd_angstrom": 0.4, "heavy_atoms": 10}
    comparacion = compare_analogs(a, b, 1, 1, nucleo)
    assert comparacion["difference"]["core_rmsd"]["reason_code"] == "DIFFERENT_RECEPTOR"
    assert comparacion["difference"]["core_rmsd"]["rmsd_angstrom"] is None
    assert comparacion["a"]["found"] and comparacion["b"]["found"]


def test_la_diferencia_de_afinidad_entre_moleculas_solo_es_comparable_con_el_mismo_protocolo():
    a, b = _resultado(), _resultado()
    a["receptor_sha256"] = b["receptor_sha256"] = "r1"
    nucleo = {"available": True, "reason_code": None, "rmsd_angstrom": 0.4, "heavy_atoms": 10}
    assert compare_analogs(a, b, 1, 1, nucleo)["difference"]["affinity_delta_comparable"] is True
    b["vina_random_seed"] = 99
    comparado = compare_analogs(a, b, 1, 1, nucleo)
    assert comparado["difference"]["affinity_delta_comparable"] is False
    assert {d["field"] for d in comparado["protocol_differences"]} == {"seed"}


# ── Qué átomos son del núcleo (para que el visor 3D los distinga de lo que cambia) ─────────────────────────────────

def _leer(sdf: str):
    from rdkit import Chem

    supplier = Chem.SDMolSupplier()
    supplier.SetData(sdf, removeHs=False)
    return supplier[0]


def _desordenar(sdf: str) -> str:
    """El mismo registro con los átomos en otro orden (los hidrógenos mezclados con los pesados): el índice del SDF no
    es el del grafo sin hidrógenos, y el visor numera por el del SDF."""
    from rdkit import Chem

    mol = _leer(sdf)
    orden = list(range(mol.GetNumAtoms()))[::-1]
    return Chem.MolToMolBlock(Chem.RenumberAtoms(mol, orden)) + "$$$$\n"


def _no_nucleo(sdf: str, nucleo: list[int]) -> list[tuple[int, str]]:
    mol = _leer(sdf)
    return [(i, mol.GetAtomWithIdx(i).GetSymbol()) for i in range(mol.GetNumAtoms()) if i not in set(nucleo)]


def test_el_nucleo_dice_que_atomos_de_cada_pose_lo_forman_y_deja_fuera_el_sustituyente():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    medida = rmsd_core_between_sdfs(base, 1, analogo, 1)
    nucleo = medida["core_atoms"]
    assert nucleo["index_basis"] == "sdf_atom_index_zero_based"
    # En el análogo sólo el cloro queda fuera: el resto de pesados, y los hidrógenos que cuelgan del núcleo, dentro.
    assert [simbolo for _, simbolo in _no_nucleo(analogo, nucleo["b"])] == ["Cl"]
    # La base entera es núcleo: no tiene nada que el análogo no tenga.
    assert _no_nucleo(base, nucleo["a"]) == []


def test_los_hidrogenos_de_un_sustituyente_no_son_del_nucleo():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(C)cc1")
    nucleo = rmsd_core_between_sdfs(base, 1, analogo, 1)["core_atoms"]["b"]
    fuera = _no_nucleo(analogo, nucleo)
    assert sorted(simbolo for _, simbolo in fuera) == ["C", "H", "H", "H"]  # el metilo y sus tres hidrógenos
    mol = _leer(analogo)
    metilo = next(i for i, simbolo in fuera if simbolo == "C")
    assert {i for i, _ in fuera} == {metilo} | {n.GetIdx() for n in mol.GetAtomWithIdx(metilo).GetNeighbors() if n.GetAtomicNum() == 1}


def test_el_indice_es_el_del_sdf_aunque_los_atomos_vengan_en_otro_orden():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    analogo = _desordenar(analogo)
    base = _desordenar(base)
    medida = rmsd_core_between_sdfs(base, 1, analogo, 1)
    assert medida["available"] is True
    assert [simbolo for _, simbolo in _no_nucleo(analogo, medida["core_atoms"]["b"])] == ["Cl"]
    assert _no_nucleo(base, medida["core_atoms"]["a"]) == []


def test_sin_distancia_no_hay_atomos_de_nucleo_que_ensenar():
    muy_distintos = rmsd_core_between_sdfs(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CCCCCCCCO"), 1)
    assert "core_atoms" not in muy_distintos
    a, b = _resultado(), _resultado()
    a["receptor_sha256"], b["receptor_sha256"] = "r1", "r2"
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    medida = rmsd_core_between_sdfs(base, 1, analogo, 1)
    assert "core_atoms" in medida
    # Con otro receptor el «núcleo» se elegiría por una distancia que no significa nada: no se enseña.
    assert "core_atoms" not in compare_analogs(a, b, 1, 1, medida)["difference"]["core_rmsd"]


# ── Cuál de las poses de la otra evaluación se parece más ──────────────────────────────────────────────────────────

from services.evaluation.run_pose_comparison import pose_matches  # noqa: E402


def test_la_pose_mas_cercana_es_la_de_menor_distancia_y_se_miden_todas():
    base = _sdf("CC(=O)Nc1ccccc1")
    otras = _sdf("CC(=O)Nc1ccccc1", shift=3.0) + _sdf("CC(=O)Nc1ccccc1", shift=0.5) + _sdf("CC(=O)Nc1ccccc1", shift=2.0)
    resultado = pose_matches(base, 1, otras, kind="molecule")
    assert resultado["available"] is True
    assert [m["rank"] for m in resultado["matches"]] == [1, 2, 3]
    assert [m["rmsd_angstrom"] for m in resultado["matches"]] == pytest.approx([3.0, 0.5, 2.0], abs=0.02)
    assert resultado["closest_rank"] == 2
    assert resultado["closest_rmsd_angstrom"] == pytest.approx(0.5, abs=0.02)


def test_otra_molecula_no_se_mide_pose_a_pose():
    resultado = pose_matches(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CCO") + _sdf("CCO", shift=1.0), kind="molecule")
    assert resultado["available"] is False
    assert resultado["closest_rank"] is None
    assert {m["reason_code"] for m in resultado["matches"]} == {"NOT_THE_SAME_MOLECULE"}


def test_en_analogos_se_mide_el_nucleo_y_la_mas_cercana_es_la_del_nucleo():
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    _, analogo_lejos = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1", shift=2.0)
    resultado = pose_matches(base, 1, analogo_lejos + analogo, kind="core")
    assert resultado["available"] is True
    assert resultado["closest_rank"] == 2
    assert resultado["matches"][0]["rmsd_angstrom"] == pytest.approx(2.0, abs=0.5)
    assert resultado["core_heavy_atoms"] >= 9


def test_sin_nucleo_suficiente_las_poses_cercanas_se_abstienen_y_dicen_cuanto_compartian():
    resultado = pose_matches(_sdf("CC(=O)Nc1ccccc1"), 1, _sdf("CCCCCCCCO"), kind="core")
    assert resultado["available"] is False
    assert resultado["reason_code"] == "CORE_TOO_SMALL"
    assert resultado["matches"] == [] and "core_heavy_atoms" in resultado


def test_una_pose_de_origen_que_no_existe_se_dice_y_de_que_lado():
    resultado = pose_matches(_sdf("CCO"), 4, _sdf("CCO"), kind="molecule")
    assert resultado["reason_code"] == "POSE_NOT_IN_SDF" and resultado["side"] == "a"
    assert pose_matches(_sdf("CCO"), 1, "", kind="molecule")["side"] == "b"


# ── El endpoint: qué molécula es, y sin el mismo receptor no se mide ───────────────────────────────────────────────

from types import SimpleNamespace  # noqa: E402


async def _pedir_coincidencias(monkeypatch, result_a, result_b, sdf_a, sdf_b, rank_a=1):
    from api.routers import evaluation as ruta

    async def cargar(*_args, **_kwargs):
        envolver = lambda c: SimpleNamespace(content=c, sha256="h") if c is not None else None  # noqa: E731
        return [], [result_a, result_b], [envolver(sdf_a), envolver(sdf_b)]

    monkeypatch.setattr(ruta, "_cargar_dos_corridas", cargar)
    return await ruta.get_pose_matches("a", "b", raw_request=None, rank_a=rank_a, current_user=None, db=None)


@pytest.mark.asyncio
async def test_endpoint_la_misma_molecula_con_el_mismo_receptor_mide_cada_pose(monkeypatch):
    a = {"molecule_id": "m", "receptor_sha256": "r"}
    base = _sdf("CC(=O)Nc1ccccc1")
    otras = _sdf("CC(=O)Nc1ccccc1", shift=3.0) + _sdf("CC(=O)Nc1ccccc1", shift=0.5)
    r = await _pedir_coincidencias(monkeypatch, a, dict(a), base, otras)
    assert (r["kind"], r["frame"], r["closest_rank"]) == ("molecule", "same", 2)
    assert r["poses_sha256"] == {"a": "h", "b": "h"}


@pytest.mark.asyncio
async def test_endpoint_dos_moleculas_distintas_se_miden_por_el_nucleo(monkeypatch):
    base, analogo = _par_alineado("CC(=O)Nc1ccccc1", "CC(=O)Nc1ccc(Cl)cc1")
    r = await _pedir_coincidencias(
        monkeypatch, {"molecule_id": "m1", "receptor_sha256": "r"}, {"molecule_id": "m2", "receptor_sha256": "r"}, base, analogo,
    )
    assert r["kind"] == "core" and r["available"] is True and r["closest_rank"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("sha_b,motivo", [("otro", "DIFFERENT_RECEPTOR"), (None, "RECEPTOR_NOT_DECLARED")])
async def test_endpoint_sin_el_mismo_receptor_declarado_no_mide_nada(monkeypatch, sha_b, motivo):
    r = await _pedir_coincidencias(
        monkeypatch, {"molecule_id": "m", "receptor_sha256": "r"}, {"molecule_id": "m", "receptor_sha256": sha_b},
        _sdf("CCO"), _sdf("CCO"),
    )
    assert r["available"] is False and r["reason_code"] == motivo
    assert r["matches"] == [] and r["closest_rank"] is None


@pytest.mark.asyncio
async def test_endpoint_sin_poses_en_disco_lo_dice(monkeypatch):
    a = {"molecule_id": "m", "receptor_sha256": "r"}
    r = await _pedir_coincidencias(monkeypatch, a, dict(a), _sdf("CCO"), None)
    assert r["available"] is False and r["reason_code"] == "POSES_NOT_AVAILABLE"
