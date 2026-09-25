"""PROV-007/008/009: evidencia tardía por corrida, sin mutar el snapshot."""
import pytest
from sqlalchemy import select

from core.models import EvaluationResultORM, EvaluationRunAddendumORM
from db.repository import Repository
from services.docking.projection_lifecycle import begin_evaluation_projection
from tests.test_sqlite_roundtrip import _seed_user_target_molecule
from tests import test_sqlite_roundtrip as fixtures

engine = fixtures.engine
session_factory = fixtures.session_factory


@pytest.mark.asyncio
async def test_addenda_materializan_solo_la_corrida_sellada(session_factory):
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        molecule_id = molecule.id
        db.add(EvaluationResultORM(
            molecule_id=molecule_id, task_id="run-1", is_control=True,
            error_message="aviso previo", total_score=81,
        ))
        await db.flush()
        repo = Repository(db)
        run = await repo.snapshot_evaluation_run(molecule_id, "run-1")
        base = dict(run.snapshot_json)
        await repo.append_run_addendum(
            molecule_id, "run-1", "selectivity",
            {"selectivity_ran": True, "selectivity_delta_delta_g": 1.7},
        )
        await repo.save_ai_report_for_run(molecule_id, "run-1", "informe")
        await repo.append_run_addendum(molecule_id, "run-1", "certificate", {
            "blockchain_tx_id": "tx-1", "blockchain_hash": "hash-1",
            "certified_task_id": "run-1", "certified_total_score": 81,
        })
        current = await repo.get_evaluation_result(molecule_id)
        current.blockchain_tx_id = "tx-1"
        current.blockchain_hash = "hash-1"
        current.certified_task_id = "run-1"
        current.certified_total_score = 81
        # Dos escrituras independientes, sin clobber ni duplicado por reintento.
        await repo.save_ai_report_for_run(molecule_id, "run-1", "informe")
        rows = (await db.execute(select(EvaluationRunAddendumORM))).scalars().all()
        assert len(rows) == 3
        merged = await repo.materialize_run_snapshot(run)
        assert merged["selectivity_delta_delta_g"] == 1.7
        assert merged["ai_report"] == "informe"
        assert merged["blockchain_tx_id"] == "tx-1"
        assert run.snapshot_json == base
        current = await repo.get_evaluation_result(molecule_id)
        assert current.is_control is True
        assert current.error_message == "aviso previo"
        assert current.evaluated_at == base["evaluated_at"] or current.evaluated_at.isoformat() == base["evaluated_at"]
        await begin_evaluation_projection(repo, molecule_id, "run-2")
        assert (await repo.materialize_run_snapshot(run))["ai_report"] == "informe"
        projection = await repo.get_evaluation_result(molecule_id)
        assert projection.ai_report is None
        assert projection.blockchain_tx_id == "tx-1"
        assert projection.certified_task_id == "run-1"
        assert (await repo.materialize_run_snapshot(run))["blockchain_tx_id"] == "tx-1"


@pytest.mark.asyncio
async def test_un_addendum_con_hash_roto_no_se_presenta(session_factory):
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        db.add(EvaluationResultORM(molecule_id=molecule.id, task_id="run"))
        await db.flush()
        repo = Repository(db)
        run = await repo.snapshot_evaluation_run(molecule.id, "run")
        row = await repo.append_run_addendum(
            molecule.id, "run", "ai_report", {"ai_report": "original"},
        )
        row.payload_json = {"ai_report": "alterado"}
        await db.flush()
        with pytest.raises(ValueError, match="corrupto"):
            await repo.materialize_run_snapshot(run)



def test_poses_peptidicas_separadas_por_ejecucion():
    from services.docking.peptide_docking import peptide_poses_run_path

    first = peptide_poses_run_path("a" * 64, "4NY4", "task-1")
    second = peptide_poses_run_path("a" * 64, "4NY4", "task-2")
    retry = peptide_poses_run_path("a" * 64, "4NY4", "task-1")
    assert len({first, second, retry}) == 3
    assert all(path.startswith("runs/docking/") and path.endswith("/poses.sdf")
               for path in (first, second, retry))
    assert "task-1" not in first  # el identificador externo no se usa como ruta


@pytest.mark.asyncio
async def test_timeout_mmgbsa_permanece_ausente_con_advertencia(session_factory):
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        db.add(EvaluationResultORM(molecule_id=molecule.id, task_id="run", mmgbsa_score=None))
        await db.flush()
        repo = Repository(db)
        run = await repo.snapshot_evaluation_run(molecule.id, "run")
        await repo.append_run_addendum(molecule.id, "run", "mmgbsa", {
            "mmgbsa_score": None, "status": "timeout", "reason": "300 segundos",
        })
        merged = await repo.materialize_run_snapshot(run)
        assert merged["mmgbsa_score"] is None
        assert any(w.get("codigo") == "MMGBSA_TIMEOUT"
                   for w in merged["scientific_warnings"])
        assert run.snapshot_json.get("mmgbsa_score") is None


def test_commit_no_se_atribuye_a_arbol_de_codigo_modificado(monkeypatch):
    from services.docking import vina_service

    monkeypatch.delenv("MOLDESIGN_BUILD_COMMIT", raising=False)
    calls = []

    def fake_run(command, **kwargs):
        from types import SimpleNamespace
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=" M backend/services/docking/vina_service.py\n")

    monkeypatch.setattr(vina_service.subprocess, "run", fake_run)
    assert vina_service._source_commit() is None
    assert len(calls) == 1 and calls[0][1] == "status"
