"""
La evidencia estructural persiste, se sirve por la API y no se duplica.

Lo que protegen:

1. **La migración es aditiva.** Una base anterior recibe la columna con
   `ALTER TABLE ADD COLUMN` y sus evaluaciones siguen ahí, con `NULL`, que se
   lee como «no evaluada» y nunca como un fallo de la pose.

2. **Un reintento no duplica ni borra.** El upsert se llama varias veces por
   evaluación; un `None` intermedio no puede tirar la evidencia ya calculada, y
   recalcular escribe el mismo contrato.

3. **El docking sobrevive al validador.** Una etapa `not_evaluated` deja la
   evaluación completada e intacta.

4. **XGBoost no volvió al camino obligatorio de cohortes.** Es la regresión que
   protege el corrigendum de 5C.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from core.models import (
    Base,
    EvaluationResultORM,
    EvaluationResultRead,
    MoleculeORM,
    TargetORM,
    UserORM,
)
from db.repository import Repository
from services.chemistry import structural_evidence as se

EVIDENCIA = {
    "version_schema": se.STRUCTURAL_EVIDENCE_SCHEMA_VERSION,
    "stage_status": se.STAGE_PASSED,
    "reason_code": None,
    "detail": None,
    "pose_strategy": se.POSE_STRATEGY_VINA_TOP1,
    "primary_pose_rank": 1,
    "poses_produced": 3,
    "poses_evaluated": 3,
    "coverage": 1.0,
    "receptor_sha256": "a" * 64,
    "receptor_source": "targets/7E2Y/prepared.pdbqt",
    "validation_engine": "posebusters:1.0:dock",
    "evaluated_at": "2026-08-24T10:00:00+00:00",
    "poses": [
        {
            "rank": 1,
            "observed_vina_affinity_kcal_mol": -8.3,
            "status": "passed",
            "label": "CONTROLES SUPERADOS",
            "engine": "posebusters:1.0:dock",
            "checks": [{"check": "sanitization", "estado": "PASA"}],
            "checks_que_fallan": [],
            "detail": "Ningun control falla.",
            "reason_code": None,
            "canonicalization_invariants": {"mapa_biyectivo": True},
            "provenance": {"template": "meeko_remark_smiles_idx"},
        }
    ],
}


class _Entorno:
    def __init__(self, path):
        self.path = path
        self.engine = None
        self.factory = None

    async def arrancar(self):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.path}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def apagar(self):
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None

    async def semilla(self):
        """Un usuario, un target y una molécula: lo mínimo para un resultado."""
        async with self.factory() as s:
            user = UserORM(id=uuid.uuid4(), email="a@b.c", username="ana",
                           hashed_password="x", is_active=True)
            target = TargetORM(id=uuid.uuid4(), pdb_id="7E2Y", name="T", chain="A",
                               grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
                               grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0)
            mol = MoleculeORM(id=uuid.uuid4(), smiles="CCO", smiles_hash="h" * 64,
                              user_id=user.id, target_id=target.id)
            s.add_all([user, target, mol])
            await s.commit()
            return mol.id


@pytest_asyncio.fixture
async def entorno(tmp_path):
    await db_mod.reset_engine()
    env = _Entorno(tmp_path / "evidencia.db")
    await env.arrancar()
    try:
        yield env
    finally:
        await env.apagar()
        await db_mod.reset_engine()


# ── 12. Persistencia y serialización API ─────────────────────────────


@pytest.mark.asyncio
async def test_la_pose_y_el_receptor_exactos_sobreviven_al_upsert(entorno):
    """El dossier posterior recibe coordenadas y procedencia, no sólo scores."""
    from core.models import DockingPose, DockingResult

    molecule_id = await entorno.semilla()
    bloque = "MODEL 1\nREMARK VINA RESULT: -8.2 0 0\nENDMDL\n"
    docking = DockingResult(
        best_affinity=-8.2,
        poses=[DockingPose(
            rank=1, affinity=-8.2, rmsd_lb=0.0, rmsd_ub=0.0,
            pdbqt_block=bloque, conformer_index=7,
        )],
        poses_file_path=None,
        parsing_source="pdbqt",
        receptor_sha256="a" * 64,
        receptor_path=f"runs/receptors/{'a' * 64}.pdbqt",
    )

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, docking=docking, task_id="run-exacto"
        )
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)
        leido = EvaluationResultRead.model_validate(guardado)

    assert guardado.docking_poses[0]["pdbqt_block"] == bloque
    assert guardado.docking_poses[0]["conformer_index"] == 7
    assert leido.docking_poses[0].pdbqt_block == bloque
    assert leido.docking_poses[0].conformer_index == 7
    assert leido.receptor_sha256 == "a" * 64
    assert leido.receptor_path.endswith(".pdbqt")


@pytest.mark.asyncio
async def test_una_corrida_congelada_no_cambia_al_repetir_la_molecula(entorno):
    """La tabla actual puede avanzar; el expediente histórico no se reescribe."""
    from core.models import DockingPose, DockingResult

    molecule_id = await entorno.semilla()

    def docking(afinidad: float) -> DockingResult:
        return DockingResult(
            best_affinity=afinidad,
            poses=[DockingPose(
                rank=1, affinity=afinidad, rmsd_lb=0.0, rmsd_ub=0.0,
                pdbqt_block=f"REMARK VINA RESULT: {afinidad} 0 0\n",
            )],
            parsing_source="pdbqt",
        )

    async with entorno.factory() as s:
        repo = Repository(s)
        await repo.upsert_evaluation_result(
            molecule_id=molecule_id, docking=docking(-8.0), task_id="run-1"
        )
        primera = await repo.snapshot_evaluation_run(molecule_id, "run-1")
        primera_id = primera.id
        await s.commit()

    async with entorno.factory() as s:
        repo = Repository(s)
        await repo.upsert_evaluation_result(
            molecule_id=molecule_id, docking=docking(-6.0), task_id="run-2"
        )
        segunda = await repo.snapshot_evaluation_run(molecule_id, "run-2")
        segunda_id = segunda.id
        await s.commit()

    async with entorno.factory() as s:
        repo = Repository(s)
        run_1 = await repo.get_evaluation_run("run-1", molecule_id)
        run_2 = await repo.get_evaluation_run("run-2", molecule_id)
        actual = await repo.get_evaluation_result(molecule_id)

    assert primera_id != segunda_id
    assert run_1.snapshot_json["affinity_kcal"] == -8.0
    assert run_2.snapshot_json["affinity_kcal"] == -6.0
    assert actual.affinity_kcal == -6.0


@pytest.mark.asyncio
async def test_la_evidencia_se_persiste_y_se_sirve_por_la_api(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, structural_evidence=EVIDENCIA, task_id="t-1",
        )
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)
        # El contrato vuelve entero, sin perder ni una pose.
        assert guardado.structural_evidence == EVIDENCIA
        leido = EvaluationResultRead.model_validate(guardado)

    assert leido.structural_evidence["stage_status"] == "passed"
    assert leido.structural_evidence["poses"][0]["rank"] == 1
    # Y viaja por JSON sin perder tipos.
    import json

    plano = json.loads(leido.model_dump_json())
    assert plano["structural_evidence"]["coverage"] == 1.0


# ── 13. Reintento idempotente ────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_reintento_no_duplica_ni_borra_la_evidencia(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        repo = Repository(s)
        await repo.upsert_evaluation_result(
            molecule_id=molecule_id, structural_evidence=EVIDENCIA, task_id="t-1")
        await s.commit()

    # Un upsert intermedio SIN evidencia —el de propiedades, por ejemplo— no
    # puede tirar la que ya se calculó.
    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(molecule_id=molecule_id, task_id="t-1")
        await s.commit()

    async with entorno.factory() as s:
        assert (await Repository(s).get_evaluation_result(molecule_id)).structural_evidence == EVIDENCIA

    # Y recalcular escribe el mismo contrato: una fila, no dos.
    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, structural_evidence=EVIDENCIA, task_id="t-1")
        await s.commit()

    with sqlite3.connect(entorno.path) as raw:
        assert raw.execute("SELECT COUNT(*) FROM evaluation_results").fetchone()[0] == 1


# ── 9. Resultado antiguo ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_evaluacion_antigua_lee_null_y_no_es_un_error(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(molecule_id=molecule_id, task_id="viejo")
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)
        leido = EvaluationResultRead.model_validate(guardado)

    assert guardado.structural_evidence is None
    assert leido.structural_evidence is None
    # Y el sustituto que el producto ofrece para presentarlo dice «no evaluada».
    sustituto = se.evidencia_ausente()
    assert sustituto["stage_status"] == se.STAGE_NOT_EVALUATED
    assert sustituto["reason_code"] == se.EVIDENCIA_AUSENTE


# ── 3 (persistencia). El docking sobrevive al validador ──────────────


@pytest.mark.asyncio
async def test_una_etapa_no_evaluada_deja_la_evaluacion_intacta(entorno):
    molecule_id = await entorno.semilla()
    abstencion = se.evidencia_ausente()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id,
            structural_evidence=abstencion,
            task_id="t-2",
        )
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)

    # La evidencia se abstiene…
    assert guardado.structural_evidence["stage_status"] == se.STAGE_NOT_EVALUATED
    # …y el resultado de la evaluación sigue existiendo, sin error registrado.
    assert guardado.error_message is None
    assert guardado.task_id == "t-2"


# ── 20 (5C) / 15. Migración aditiva y XGBoost fuera del camino ───────


def test_la_migracion_anade_la_columna_sin_tocar_lo_guardado(tmp_path):
    """Una base ANTERIOR: la columna aparece y sus filas siguen ahí."""
    db = tmp_path / "vieja.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE evaluation_results (id TEXT PRIMARY KEY, molecule_id TEXT, "
            "affinity_kcal REAL, task_id TEXT)"
        )
        conn.execute(
            "INSERT INTO evaluation_results (id, molecule_id, affinity_kcal, task_id) "
            "VALUES ('r1','m1',-8.3,'viejo')"
        )

    db_mod._migrate_sqlite_db(db)

    with sqlite3.connect(db) as conn:
        columnas = {r[1] for r in conn.execute("PRAGMA table_info(evaluation_results)")}
        fila = conn.execute(
            "SELECT affinity_kcal, task_id, structural_evidence FROM evaluation_results"
        ).fetchone()

    assert "structural_evidence" in columnas
    # Lo que ya estaba, intacto; la evidencia, NULL.
    assert fila == (-8.3, "viejo", None)


def test_xgboost_no_volvio_al_camino_obligatorio_de_cohortes():
    """
    Regresión del corrigendum de 5C: `required_stage_ids` deja fuera a `xgb`
    para cohortes, y esta etapa no puede haberlo reintroducido.
    """
    import inspect

    from services.cohort import execution as ex
    from services.pipeline.registry import resolve_stage_order

    assert "xgb" not in ex.COHORT_RUN_STAGES
    orden = resolve_stage_order(
        list(ex.COHORT_RUN_STAGES),
        list(ex.COHORT_RUN_STAGES),
        required_stage_ids=set(ex.COHORT_RUN_STAGES),
    )
    assert "xgb" not in orden
    assert "clgnn" not in orden

    # Y la etapa nueva no toca el selector ni el rescoring. Se miran el CODIGO y
    # no los comentarios: este modulo EXPLICA por escrito que no los toca, y
    # buscar el nombre en el texto crudo encontraria justo esa explicacion.
    import re

    fuente = inspect.getsource(se)
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    codigo = re.sub(r"^[ 	]*#.*$", "", codigo, flags=re.MULTILINE).lower()
    for prohibido in ("xgb", "clgnn", "total_score", "selector"):
        assert prohibido not in codigo, prohibido


# ── 14. La misma función productiva sirve a casos y a cohortes ───────


def test_casos_y_cohortes_usan_la_MISMA_funcion_productiva():
    """
    No hay dos validaciones. El hook del pipeline es uno, y la corrida de
    cohorte entra por ese mismo pipeline con su receptor congelado.

    Si hubiera dos caminos, uno de los dos envejecería sin que nadie lo notara —
    y sería el de cohortes, que es el que menos se mira.
    """
    import inspect

    from services.cohort import execution as ex
    from services.pipeline import runner

    hook = inspect.getsource(runner.run_pipeline)
    assert "build_structural_evidence" in hook
    # El hook recibe los bytes CONGELADOS cuando los hay: en una cohorte, el
    # receptor no se lee del catálogo mutable.
    assert "receptor_bytes=prepared_receptor_bytes" in hook

    # Y la cohorte entra por ese pipeline pasándoselos.
    cohorte = inspect.getsource(ex._evaluate_one)
    assert "run_pipeline" in cohorte
    assert "prepared_receptor_bytes=receptor.prepared_bytes" in cohorte


@pytest.mark.asyncio
async def test_una_fila_de_cohorte_recupera_la_evidencia_por_su_result_id(entorno):
    """
    La evidencia queda asociada al resultado persistente y se recupera por la
    API de cohorte, por el MISMO `result_id` de esa ejecución — no por «el
    resultado más reciente de esta molécula».
    """
    from core.models import CohortRunRowORM
    from services.cohort import evidence as cohort_ev

    molecule_id = await entorno.semilla()
    async with entorno.factory() as s:
        guardado = await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, structural_evidence=EVIDENCIA, task_id="t-1")
        await s.commit()
        result_id = guardado.id

    fila = CohortRunRowORM(
        id=uuid.uuid4(), run_id=uuid.uuid4(), source_row_index=0,
        canonical_smiles="CCO", control_role="none", status="completed",
        molecule_id=molecule_id, result_id=result_id,
    )

    async with entorno.factory() as s:
        resultado = await Repository(s).get_evaluation_result(molecule_id)
        moleculas = cohort_ev.build_molecule_evidence([fila], {result_id: resultado})

    assert len(moleculas) == 1
    evidencia = moleculas[0]["structural_evidence"]
    assert evidencia["stage_status"] == "passed"
    assert evidencia["poses"][0]["rank"] == 1
    # Y sigue sin publicar ninguna puntuación agregada.
    import json

    assert "total_score" not in json.dumps(moleculas).lower()
