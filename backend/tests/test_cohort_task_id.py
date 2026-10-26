"""QA-S06: Batch abre su snapshot, nunca la proyección de otra corrida."""
import uuid
from datetime import datetime, timezone

import pytest
from core.models import CohortRunRowORM, EvaluationRunORM, EvaluationResultORM, EvaluationResultRead, MoleculeORM
from tests.test_cohort_execution import entorno, evaluador, _congelar, _abrir_y_esperar


async def _run_with_results(entorno, evaluador, *, legacy=False):
    target=await entorno.crear_target()
    entorno.preparar_receptor()
    owner=await entorno.crear_usuario("owner")
    other=await entorno.crear_usuario("other")
    client=entorno.app(owner)
    from tests.test_cohort_execution import ASPIRINA
    evaluador.respuestas[ASPIRINA]={"molecule_id":str(uuid.uuid4()),"evaluation_result_id":str(uuid.uuid4())}
    cohort=_congelar(client)
    _,run_id=await _abrir_y_esperar(entorno,client,cohort["id"])
    rows=await entorno.filas(run_id)
    row=rows[0]
    snapshot={k:None for k,f in EvaluationResultRead.model_fields.items() if f.is_required()}
    snapshot.update(id=str(row.result_id),molecule_id=str(row.molecule_id),task_id="batch-exact",affinity_kcal=-6.1,total_score=1.0,evaluated_at="2026-10-01T00:00:00Z")
    async with entorno.factory() as db:
        db.add(MoleculeORM(id=row.molecule_id,user_id=owner.id,target_id=target.id,smiles=row.canonical_smiles,smiles_hash="a"*64))
        await db.flush()
        if legacy:
            db.add(EvaluationResultORM(id=row.result_id,molecule_id=row.molecule_id,task_id="batch-exact",affinity_kcal=-6.1))
        else:
            db.add(EvaluationRunORM(id=row.result_id,molecule_id=row.molecule_id,task_id="batch-exact",snapshot_json=snapshot,created_at=datetime(2026,10,1,tzinfo=timezone.utc)))
            db.add(EvaluationRunORM(molecule_id=row.molecule_id,task_id="batch-newer",snapshot_json={**snapshot,"affinity_kcal":-9.5,"task_id":"batch-newer"},created_at=datetime(2026,10,2,tzinfo=timezone.utc)))
            db.add(EvaluationResultORM(molecule_id=row.molecule_id,task_id="batch-newer",affinity_kcal=-9.5,total_score=2.0))
        await db.commit()
    from api.routers import evaluation
    client.app.include_router(evaluation.router)
    return client,other,run_id,row


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy",[False,True])
async def test_fila_expone_task_id_exacto_y_duplicado(entorno,evaluador,legacy):
    client,_,run_id,row=await _run_with_results(entorno,evaluador,legacy=legacy)
    response=client.get(f"/evaluation/cohort-runs/{run_id}")
    assert response.status_code == 200
    rows=response.json()["rows"]
    assert rows[0]["task_id"] == "batch-exact"
    assert rows[2]["task_id"] == "batch-exact"
    evidence=client.get(f"/evaluation/cohort-runs/{run_id}/evidence").json()
    assert evidence["molecules"][0]["task_id"] == "batch-exact"


@pytest.mark.asyncio
async def test_resultado_de_fila_abre_snapshot_aunque_haya_otro(entorno,evaluador):
    client,_,run_id,row=await _run_with_results(entorno,evaluador)
    exact=client.get(f"/evaluation/result/{row.molecule_id}",params={"task_id":"batch-exact"})
    assert exact.status_code == 200,exact.text
    assert exact.json()["affinity_kcal"] == -6.1
    latest=client.get(f"/evaluation/result/{row.molecule_id}")
    assert latest.status_code == 200,latest.text
    assert latest.json()["affinity_kcal"] == -9.5
    assert client.get(f"/evaluation/result/{row.molecule_id}",params={"task_id":"absent"}).status_code == 404


@pytest.mark.asyncio
async def test_otra_cuenta_no_lee_fila_ni_task_id_ni_resultado(entorno,evaluador):
    client,other,run_id,row=await _run_with_results(entorno,evaluador)
    from api.dependencies import get_current_user_optional
    client.app.dependency_overrides[get_current_user_optional]=lambda:other
    response=client.get(f"/evaluation/cohort-runs/{run_id}")
    assert response.status_code == 404
    assert "batch-exact" not in response.text
    assert client.get(f"/evaluation/cohort-runs/{run_id}/evidence").status_code == 404
    assert client.get(f"/evaluation/result/{row.molecule_id}",params={"task_id":"batch-exact"}).status_code == 403


@pytest.mark.asyncio
async def test_referencia_cruzada_no_filtra_task_id_o_score(entorno,evaluador):
    client,other,run_id,row=await _run_with_results(entorno,evaluador)
    async with entorno.factory() as db:
        mol=await db.get(MoleculeORM,row.molecule_id)
        mol.user_id=other.id
        await db.commit()
    rows=client.get(f"/evaluation/cohort-runs/{run_id}").json()["rows"]
    assert rows[0]["task_id"] is None
    evidence=client.get(f"/evaluation/cohort-runs/{run_id}/evidence").json()
    assert evidence["molecules"][0]["observed_vina_affinity_kcal_mol"] is None
    assert "batch-exact" not in str(evidence)


@pytest.mark.asyncio
async def test_resultado_de_otra_molecula_no_se_atribuye_a_la_fila(entorno,evaluador):
    client,other,run_id,row=await _run_with_results(entorno,evaluador)
    another=uuid.uuid4()
    async with entorno.factory() as db:
        mol=await db.get(MoleculeORM,row.molecule_id)
        db.add(MoleculeORM(id=another,user_id=mol.user_id,target_id=mol.target_id,smiles="CCN",smiles_hash="b"*64))
        await db.flush()
        run=await db.get(EvaluationRunORM,row.result_id)
        run.molecule_id=another
        await db.commit()
    rows=client.get(f"/evaluation/cohort-runs/{run_id}").json()["rows"]
    assert rows[0]["task_id"] is None
    evidence=client.get(f"/evaluation/cohort-runs/{run_id}/evidence").json()
    assert evidence["molecules"][0]["observed_vina_affinity_kcal_mol"] is None
