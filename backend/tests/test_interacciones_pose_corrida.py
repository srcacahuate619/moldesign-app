"""API-001: las interacciones sólo usan el SDF de la corrida autorizada."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from rdkit import Chem
from rdkit.Chem import AllChem

from api.routers import interactions as ruta
from services.interactions.analyzer import InteractionReport


def _sdf_tres_poses() -> str:
    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    assert AllChem.EmbedMolecule(mol, randomSeed=7) == 0
    bloques = []
    for desplazamiento in (0.0, 5.0, 10.0):
        copia = Chem.Mol(mol)
        conf = copia.GetConformer()
        for i in range(copia.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            conf.SetAtomPosition(i, (pos.x + desplazamiento, pos.y, pos.z))
        bloques.append(Chem.MolToMolBlock(copia) + "\n$$$$\n")
    return "".join(bloques)


def _preparar(monkeypatch, poses: str | None):
    target = SimpleNamespace(pdb_id="1CBS")
    molecule = SimpleNamespace(smiles_hash="ligand-hash", target=target)
    receptor = "ATOM      1  CA  ALA A   1      20.000  20.000  20.000  1.00 20.00     0.000 C\n"
    import hashlib
    evaluation = SimpleNamespace(
        molecule=molecule,
        poses_file_path="runs/docking/caso/poses.sdf",
        receptor_path="runs/receptors/caso.pdbqt",
        receptor_sha256=hashlib.sha256(receptor.encode()).hexdigest(),
    )
    class Repo:
        def __init__(self, _db):
            pass
        async def get_evaluation_result(self, _id):
            return evaluation
    async def authorized(**_kwargs):
        return molecule
    contenido = {
        evaluation.receptor_path: receptor,
    }
    if poses is not None:
        contenido[evaluation.poses_file_path] = poses
    async def exists(path):
        return path in contenido
    async def read_text(path):
        return contenido[path]
    monkeypatch.setattr(ruta, "Repository", Repo)
    monkeypatch.setattr(ruta, "require_owned_molecule", authorized)
    monkeypatch.setattr(ruta, "require_target_object_access", lambda target, _user: target)
    monkeypatch.setattr(ruta, "exists", exists)
    monkeypatch.setattr(ruta, "read_text", read_text)
    return evaluation


@pytest.mark.asyncio
async def test_pose_tres_procede_del_sdf_de_esta_corrida(monkeypatch):
    evaluation = _preparar(monkeypatch, _sdf_tres_poses())
    observado = {}
    def analyze_complex(*, ligand_sdf_path, **kwargs):
        mol = Chem.SDMolSupplier(str(ligand_sdf_path))[0]
        observado["x"] = mol.GetConformer().GetAtomPosition(0).x
        return InteractionReport(
            molecule_id=kwargs["molecule_id"],
            target_pdb_id=kwargs["target_pdb_id"],
            pose_rank=kwargs["pose_rank"],
        )
    import services.interactions.analyzer as analyzer
    monkeypatch.setattr(analyzer, "analyze_complex", analyze_complex)

    respuesta = await ruta.get_interactions(str(uuid4()), pose_rank=3, db=object(), current_user=None)
    referencia = list(Chem.ForwardSDMolSupplier(__import__("io").BytesIO(_sdf_tres_poses().encode())))[2]
    assert abs(observado["x"] - referencia.GetConformer().GetAtomPosition(0).x) < 0.01
    assert respuesta["pose_source_path"] == evaluation.poses_file_path
    assert len(respuesta["pose_source_sha256"]) == 64


@pytest.mark.asyncio
async def test_sin_sdf_de_corrida_se_abstiene(monkeypatch):
    _preparar(monkeypatch, None)
    with pytest.raises(HTTPException) as err:
        await ruta.get_interactions(str(uuid4()), pose_rank=1, db=object(), current_user=None)
    assert err.value.status_code in (404, 409)


def test_respaldo_no_cuenta_agua_ni_ligando_cristalizado(tmp_path):
    from services.interactions.analyzer import _fallback_analysis

    mol = Chem.AddHs(Chem.MolFromSmiles("CC"))
    assert AllChem.EmbedMolecule(mol, randomSeed=11) == 0
    sdf = tmp_path / "ligand.sdf"
    sdf.write_text(Chem.MolToMolBlock(mol) + "\n$$$$\n", encoding="utf-8")
    pdb = tmp_path / "protein.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1       2.500   0.000   0.000  1.00 20.00           C\n"
        "HETATM    2  O   HOH A   2       0.000   0.000   0.000  1.00 20.00           O\n"
        "HETATM    3  C1  REA A   3       0.000   0.000   0.000  1.00 20.00           C\n",
        encoding="utf-8",
    )
    report = _fallback_analysis(pdb, sdf, InteractionReport("", "", 1))
    assert report.engine == "distancias_sin_quimica"
    assert all(i.residue_name == "ALA" for i in report.interactions)
    assert not any(i.type == "hbond" for i in report.interactions)


def test_prolif_se_ejecuta_con_api_real_y_declara_el_motor(tmp_path):
    from services.interactions.analyzer import analyze_complex

    receptor = Chem.AddHs(Chem.MolFromSmiles("CC"))
    ligando = Chem.AddHs(Chem.MolFromSmiles("CC"))
    assert AllChem.EmbedMolecule(receptor, randomSeed=3) == 0
    assert AllChem.EmbedMolecule(ligando, randomSeed=4) == 0
    pdb = tmp_path / "protein.pdb"
    pdb.write_text(Chem.MolToPDBBlock(receptor).replace("HETATM", "ATOM  "), encoding="utf-8")
    sdf = tmp_path / "ligand.sdf"
    sdf.write_text(Chem.MolToMolBlock(ligando) + "\n$$$$\n", encoding="utf-8")

    report = analyze_complex(pdb, sdf)
    assert report.engine.startswith("prolif:"), report.engine
    assert report.hydrogen_model == "rdkit_add_hs_coordinates"


@pytest.mark.asyncio
async def test_receptor_modificado_tras_la_corrida_se_bloquea(monkeypatch):
    evaluation = _preparar(monkeypatch, _sdf_tres_poses())
    evaluation.receptor_sha256 = "0" * 64
    with pytest.raises(HTTPException) as err:
        await ruta.get_interactions(str(uuid4()), pose_rank=1, db=object(), current_user=None)
    assert err.value.status_code == 409


def test_pdbqt_se_convierte_con_elemento_y_sin_heteroatomos():
    pdb = ruta._pdbqt_receptor_a_pdb(
        "ATOM      1  CA  ALA A   1       2.500   0.000   0.000  1.00 20.00     0.000 C\n"
        "HETATM    2  O   HOH A   2       0.000   0.000   0.000  1.00 20.00     0.000 OA\n"
    )
    assert "ATOM" in pdb and "ALA" in pdb
    assert "HOH" not in pdb
    assert Chem.MolFromPDBBlock(pdb, sanitize=False) is not None
