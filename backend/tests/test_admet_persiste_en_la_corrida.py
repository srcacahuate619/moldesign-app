"""El perfil ADMET calculado después del docking sobrevive al reabrir la corrida.

Defecto que fija (2026-11-08): `POST /pro/admet/{id}` escribía el perfil sólo en la
fila de proyección de `evaluation_results`. Pero `GET /evaluation/result/{id}?task_id=`
—el camino del Historial, de Moldex y de cualquier corrida reabierta— sirve el
SNAPSHOT inmutable de la corrida más sus addenda, y ahí el ADMET no estaba. El
investigador calculaba el perfil, lo veía, y al volver la pestaña decía que no
había: tenía que recalcularlo cada vez.

Cada prueba parte de una respuesta conocida: el perfil que se escribe es el que se
lee, y una corrida distinta no hereda el perfil de otra.
"""

import pytest

from core.models import EvaluationResultORM, PhysicochemicalProperties
from db.repository import Repository
from tests import test_sqlite_roundtrip as fixtures
from tests.test_sqlite_roundtrip import _seed_user_target_molecule

engine = fixtures.engine
session_factory = fixtures.session_factory

CAMPOS_ADMET = (
    "blood_viability_score", "blood_solubility_logs", "blood_ppb_category",
    "blood_bbb_permeable", "blood_bbb_motivo", "blood_cns_mpo",
    "blood_hia_permeable", "blood_systemic_reactivity", "blood_tabpfn_estado",
)


def _propiedades_con_admet() -> PhysicochemicalProperties:
    return PhysicochemicalProperties(
        molecular_weight=206.28, log_p=3.07, tpsa=37.3, hbd=1, hba=1,
        rotatable_bonds=4, heavy_atom_count=15, ring_count=1, qed=0.82,
        sa_score=2.1, lipinski_pass=True, veber_pass=True,
        blood_viability_score=76.5, blood_solubility_logs=-2.75,
        blood_ppb_category="low", blood_bbb_permeable=False,
        blood_bbb_motivo="Aniónica a pH 7.4", blood_cns_mpo=4.5,
        blood_hia_permeable=True, blood_systemic_reactivity=["CYP2C9"],
        blood_tabpfn_estado="evaluado",
    )


async def _corrida_sin_admet(db, task_id="run-1"):
    _, _, molecule = await _seed_user_target_molecule(db)
    db.add(EvaluationResultORM(molecule_id=molecule.id, task_id=task_id))
    await db.flush()
    repo = Repository(db)
    run = await repo.snapshot_evaluation_run(molecule.id, task_id)
    return repo, molecule.id, run


@pytest.mark.asyncio
async def test_a01_el_snapshot_de_la_corrida_incluye_el_admet_calculado_despues(session_factory):
    async with session_factory() as db:
        repo, molecule_id, run = await _corrida_sin_admet(db)
        assert (await repo.materialize_run_snapshot(run)).get("blood_viability_score") is None

        guardado = await repo.guardar_admet_de_la_corrida(
            molecule_id, "run-1", _propiedades_con_admet(),
        )

        assert guardado is True
        reabierta = await repo.materialize_run_snapshot(run)
        assert reabierta["blood_viability_score"] == 76.5
        assert reabierta["blood_solubility_logs"] == -2.75
        assert reabierta["blood_ppb_category"] == "low"
        assert reabierta["blood_bbb_permeable"] is False
        assert reabierta["blood_bbb_motivo"] == "Aniónica a pH 7.4"
        assert reabierta["blood_cns_mpo"] == 4.5
        assert reabierta["blood_hia_permeable"] is True
        assert reabierta["blood_systemic_reactivity"] == ["CYP2C9"]
        assert reabierta["blood_tabpfn_estado"] == "evaluado"


@pytest.mark.asyncio
async def test_a02_la_proyeccion_y_el_snapshot_dicen_lo_mismo(session_factory):
    async with session_factory() as db:
        repo, molecule_id, run = await _corrida_sin_admet(db)
        await repo.guardar_admet_de_la_corrida(molecule_id, "run-1", _propiedades_con_admet())

        proyeccion = await repo.get_evaluation_result(molecule_id)
        snapshot = await repo.materialize_run_snapshot(run)
        for campo in CAMPOS_ADMET:
            assert snapshot[campo] == getattr(proyeccion, campo), campo


@pytest.mark.asyncio
async def test_a03_el_snapshot_base_sigue_inmutable(session_factory):
    async with session_factory() as db:
        repo, molecule_id, run = await _corrida_sin_admet(db)
        base = dict(run.snapshot_json)
        await repo.guardar_admet_de_la_corrida(molecule_id, "run-1", _propiedades_con_admet())
        assert run.snapshot_json == base


@pytest.mark.asyncio
async def test_a04_repetirlo_no_duplica_y_una_corrida_ajena_no_hereda_el_perfil(session_factory):
    from sqlalchemy import select

    from core.models import EvaluationRunAddendumORM

    async with session_factory() as db:
        repo, molecule_id, run = await _corrida_sin_admet(db, "run-1")
        await repo.guardar_admet_de_la_corrida(molecule_id, "run-1", _propiedades_con_admet())
        await repo.guardar_admet_de_la_corrida(molecule_id, "run-1", _propiedades_con_admet())
        filas = (await db.execute(select(EvaluationRunAddendumORM).where(
            EvaluationRunAddendumORM.kind == "admet"))).scalars().all()
        assert len(filas) == 1

        # Una segunda corrida de la misma molécula reemplaza la proyección; su
        # snapshot no hereda el perfil de la primera, y la primera lo conserva.
        from services.docking.projection_lifecycle import begin_evaluation_projection

        await begin_evaluation_projection(repo, molecule_id, "run-2")
        otra = await repo.snapshot_evaluation_run(molecule_id, "run-2")
        assert (await repo.materialize_run_snapshot(otra)).get("blood_viability_score") is None
        assert (await repo.materialize_run_snapshot(run))["blood_viability_score"] == 76.5


@pytest.mark.asyncio
async def test_a05_un_perfil_sin_indice_no_se_guarda_como_si_lo_fuera(session_factory):
    async with session_factory() as db:
        repo, molecule_id, run = await _corrida_sin_admet(db)
        vacio = _propiedades_con_admet().model_copy(update={"blood_viability_score": None})
        assert await repo.guardar_admet_de_la_corrida(molecule_id, "run-1", vacio) is False
        assert (await repo.materialize_run_snapshot(run)).get("blood_viability_score") is None
