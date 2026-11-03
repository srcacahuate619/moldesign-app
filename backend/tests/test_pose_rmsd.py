"""RMSD directo entre dos poses de una corrida, de las coordenadas del SDF guardado.

Las cotas de Vina son contra su mejor pose; para decir cuánto se separan la pose 2 y la 3 hace falta medirlo. Con la
corrida real de 8T69 (clopidogrel, 21 átomos pesados) el valor con el orden de átomos coincide con la cota superior de
Vina de cada pose (4,259 y 2,438 Å) y queda dentro de [l.b., u.b.]; aquí se fijan los casos con moléculas pequeñas.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from api.routers import evaluation
from services.evaluation.pose_rmsd import rmsd_between_poses


def _tolueno() -> Chem.Mol:
    mol = Chem.AddHs(Chem.MolFromSmiles("Cc1ccccc1"))
    assert AllChem.EmbedMolecule(mol, randomSeed=3) == 0
    return mol


def _mover(mol: Chem.Mol, dx: float) -> Chem.Mol:
    copia = Chem.Mol(mol)
    conformador = copia.GetConformer()
    for i in range(copia.GetNumAtoms()):
        p = conformador.GetAtomPosition(i)
        conformador.SetAtomPosition(i, (p.x + dx, p.y, p.z))
    return copia


def _girar_anillo(mol: Chem.Mol) -> Chem.Mol:
    """La misma geometría con los dos carbonos orto (y los dos meta) intercambiados: equivalente por simetría."""
    copia = Chem.Mol(mol)
    orto = [n.GetIdx() for n in copia.GetAtomWithIdx(0).GetNeighbors()[0].GetNeighbors() if n.GetIdx() != 0]
    meta = [n.GetIdx() for o in orto for n in copia.GetAtomWithIdx(o).GetNeighbors()
            if n.GetAtomicNum() > 1 and n.GetIdx() not in orto and n.GetIdx() != 1]
    assert len(orto) == 2 and len(meta) == 2
    conformador = copia.GetConformer()
    for a, b in (orto, meta):
        pa, pb = conformador.GetAtomPosition(a), conformador.GetAtomPosition(b)
        conformador.SetAtomPosition(a, (pb.x, pb.y, pb.z))
        conformador.SetAtomPosition(b, (pa.x, pa.y, pa.z))
    return copia


def _sdf(*mols: Chem.Mol) -> str:
    return "".join(Chem.MolToMolBlock(m) + "\n$$$$\n" for m in mols)


def test_dos_poses_desplazadas_3_angstrom_distan_3_angstrom():
    base = _tolueno()
    medido = rmsd_between_poses(_sdf(base, _mover(base, 3.0), _mover(base, 7.0)), 1, 2)
    assert medido["available"] is True and medido["reason_code"] is None
    assert medido["rmsd_angstrom"] == pytest.approx(3.0, abs=1e-3) and medido["rmsd_atom_order_angstrom"] == pytest.approx(3.0, abs=1e-3)
    assert medido["heavy_atoms"] == 7 and "sin superponer" in medido["method"]
    # Entre dos que no son la primera: 7 − 3 = 4 Å, que ninguna cota contra la pose 1 diría.
    assert rmsd_between_poses(_sdf(base, _mover(base, 3.0), _mover(base, 7.0)), 2, 3)["rmsd_angstrom"] == pytest.approx(4.0, abs=1e-3)


def test_el_orden_de_los_rangos_no_cambia_la_distancia():
    base = _tolueno()
    sdf = _sdf(base, _mover(base, 2.0))
    assert rmsd_between_poses(sdf, 1, 2)["rmsd_angstrom"] == pytest.approx(rmsd_between_poses(sdf, 2, 1)["rmsd_angstrom"], abs=1e-3)


def test_la_simetria_de_la_molecula_no_cuenta_como_una_diferencia_de_pose():
    """Un anillo girado 180° ocupa los mismos lugares con los átomos equivalentes intercambiados: RMSD 0 con simetría."""
    base = _tolueno()
    medido = rmsd_between_poses(_sdf(base, _girar_anillo(base)), 1, 2)
    assert medido["rmsd_angstrom"] == pytest.approx(0.0, abs=1e-3)
    assert medido["rmsd_atom_order_angstrom"] > 0.1  # el mismo orden de átomos sí lo vería como un cambio


def test_una_pose_comparada_consigo_misma_o_fuera_del_archivo_no_tiene_distancia():
    base = _tolueno()
    sdf = _sdf(base, _mover(base, 1.0))
    assert rmsd_between_poses(sdf, 1, 1)["reason_code"] == "SAME_POSE"
    fuera = rmsd_between_poses(sdf, 1, 5)
    assert fuera["available"] is False and fuera["reason_code"] == "POSE_NOT_IN_SDF" and fuera["poses_in_file"] == 2


def test_dos_moleculas_distintas_no_se_comparan_como_si_fueran_la_misma():
    """Control negativo: mismo número de átomos pesados, otro grafo (metilciclohexano frente a tolueno)."""
    otra = Chem.AddHs(Chem.MolFromSmiles("CC1CCCCC1"))
    assert AllChem.EmbedMolecule(otra, randomSeed=3) == 0
    assert rmsd_between_poses(_sdf(_tolueno(), otra), 1, 2)["reason_code"] == "POSES_NOT_THE_SAME_MOLECULE"
    benceno = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1"))
    assert AllChem.EmbedMolecule(benceno, randomSeed=3) == 0
    assert rmsd_between_poses(_sdf(_tolueno(), benceno), 1, 2)["reason_code"] == "POSES_NOT_THE_SAME_MOLECULE"


# ── El endpoint añade la medida sin tumbar la comparación ───────────

def _request():
    from starlette.requests import Request
    return Request({"type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
                    "path": "/evaluation/pose-comparison/task-1", "raw_path": b"/evaluation/pose-comparison/task-1",
                    "query_string": b"", "headers": [], "client": ("127.0.0.1", 43210), "server": ("testserver", 80)})


@pytest.fixture
def corrida(monkeypatch):
    from core.models import EvaluationResultRead, JobStatus
    from tests.test_pose_comparison import SCENARIOS

    payload = {key: None for key, field in EvaluationResultRead.model_fields.items() if field.is_required()}
    payload.update(id=str(uuid.uuid4()), molecule_id=str(uuid.uuid4()), evaluated_at="2026-08-24T10:00:00+00:00")
    payload.update(SCENARIOS["todas_pasan"]["result"])
    model = EvaluationResultRead.model_validate(payload)

    async def authorize(*_args, **_kwargs):
        return None

    async def get_job_status(_task_id):
        return JobStatus(task_id="task-1", status="SUCCESS", progress=100, result=model)

    monkeypatch.setattr(evaluation, "_authorize_task_access", authorize)
    monkeypatch.setattr("services.docking.queue_handler.get_job_status", get_job_status)
    return model


async def _call(left, right):
    return await evaluation.get_pose_comparison("task-1", _request(), left=left, right=right,
                                                current_user=SimpleNamespace(id=uuid.uuid4()), db=object())


@pytest.mark.asyncio
async def test_el_endpoint_mide_la_distancia_entre_las_dos_poses_del_sdf_guardado(corrida, monkeypatch):
    from services.docking import result_sdf

    base = _tolueno()
    contenido = _sdf(base, _mover(base, 3.0), _mover(base, 7.0))

    async def leer(_selected, *, reader=None):
        return result_sdf.ResultSdf(contenido, "ab" * 32, "runs/docking/x/poses.sdf", "stored")

    monkeypatch.setattr(result_sdf, "read_result_sdf", leer)
    medido = (await _call(2, 3))["difference"]["pose_rmsd_between_poses"]
    assert medido["available"] is True and medido["rmsd_angstrom"] == pytest.approx(4.0, abs=1e-3)
    assert medido["poses_sha256"] == "ab" * 32 and medido["pose_source_kind"] == "stored"


@pytest.mark.asyncio
async def test_sin_sdf_la_comparacion_sigue_en_pie_y_lo_dice(corrida, monkeypatch):
    from services.docking import result_sdf

    async def no_hay(_selected, *, reader=None):
        raise result_sdf.ResultSdfUnavailable("No se pudo leer el SDF de esta corrida.", 404)

    monkeypatch.setattr(result_sdf, "read_result_sdf", no_hay)
    comparison = await _call(1, 2)
    assert comparison["difference"]["pose_rmsd_between_poses"]["reason_code"] == "POSES_NOT_AVAILABLE"
    assert comparison["difference"]["lower_vina_energy"] == 1  # lo demás de la comparación no se pierde


@pytest.mark.asyncio
async def test_un_fallo_inesperado_al_medir_no_tumba_la_comparacion(corrida, monkeypatch):
    from services.docking import result_sdf
    from services.evaluation import pose_rmsd

    async def leer(_selected, *, reader=None):
        return result_sdf.ResultSdf("x", "cd" * 32, None, "stored")

    def romper(*_args, **_kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(result_sdf, "read_result_sdf", leer)
    monkeypatch.setattr(pose_rmsd, "rmsd_between_poses", romper)
    comparison = await _call(1, 2)
    assert comparison["difference"]["pose_rmsd_between_poses"]["reason_code"] == "RMSD_NOT_COMPUTABLE"
    assert comparison["difference"]["physical_agreement"] == "both_passed"


@pytest.mark.asyncio
async def test_una_pose_que_la_corrida_no_tiene_no_pide_medida(corrida):
    comparison = await _call(1, 7)
    assert "pose_rmsd_between_poses" not in comparison["difference"]
