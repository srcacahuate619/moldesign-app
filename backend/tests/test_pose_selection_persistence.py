"""
La selección de pose persiste, se sirve por la API y no se duplica.

Lo que protegen:

1. **Un resultado antiguo abre como `unavailable`.** En la columna sigue
   habiendo NULL —la migración es aditiva y no reescribe historia—, pero el
   lector recibe el contrato con su razón y con Vina top-1 declarado como
   fallback. Un `null` obligaría a cada cliente a decidir por su cuenta si el
   selector no existía, se abstuvo o falló, y esas tres cosas no son la misma.

2. **Un reintento no duplica ni borra.** El upsert se llama varias veces por
   evaluación; un `None` intermedio no puede tirar la recomendación ya
   calculada, y recalcular escribe el mismo contrato sobre la misma fila.

3. **Casos y cohortes pasan por la MISMA etapa**, después de generar y validar
   las poses, y la cohorte LEE lo persistido en lugar de volver a ejecutar el
   selector: dos caminos que opinan sobre la misma pose acabarían discrepando.

4. **El docking sobrevive al selector.** La etapa va envuelta: si falla, la
   evaluación se conserva intacta y la referencia sigue siendo Vina top-1.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from core.models import (
    Base,
    EvaluationResultRead,
    MoleculeORM,
    TargetORM,
    UserORM,
)
from db.repository import Repository
from services.chemistry import pose_selection as ps

#: Un contrato REAL de la etapa: recomendación con procedencia y física leída.
SELECCION = {
    "version_schema": ps.POSE_SELECTION_SCHEMA_VERSION,
    "contract": ps.POSE_SELECTION_CONTRACT,
    "status": ps.STATUS_SELECTED,
    "strategy": ps.STRATEGY_SELECTOR,
    "strategy_is_fallback": False,
    "vina_top1_rank": 1,
    "selected_pose_rank": 2,
    "confidence": 0.412233,
    "abstained": False,
    "abstention_reason": None,
    "detail": "El selector recomienda la pose 2 con un margen de 0.412233.",
    "pose_scores": [
        {"rank": 1, "score": 0.11}, {"rank": 2, "score": 0.52}, {"rank": 3, "score": 0.09},
    ],
    "model": {
        "name": "pose_selector_v06",
        "version": "pose_selector_v06",
        "model_path": "pose_selector_v06.xgb",
        "model_sha256": "b" * 64,
        "meta_sha256": "c" * 64,
        "abstention_threshold": 0.097663,
    },
    "inputs": {
        "n_poses": 3,
        "pose_ranks": [1, 2, 3],
        "vina_affinities": [-8.3, -7.9, -7.1],
        "pose_pdbqt_source": "docking_poses[].pdbqt_block",
        "receptor_source": "prepared.pdb",
        "structural_evidence_contract": 1,
    },
    "warnings": [],
    "suggested_pose_physical_status": "failed",
    "physical_review": True,
    "physically_valid_alternatives": [
        {"rank": 1, "physical_status": "passed"},
        {"rank": 3, "physical_status": "passed"},
    ],
    "evaluated_at": "2026-08-24T10:00:00+00:00",
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
    env = _Entorno(tmp_path / "seleccion.db")
    await env.arrancar()
    try:
        yield env
    finally:
        await env.apagar()
        await db_mod.reset_engine()


# ── 11. La API serializa el contrato ─────────────────────────────────


@pytest.mark.asyncio
async def test_la_seleccion_se_persiste_y_se_sirve_por_la_api(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=SELECCION, task_id="t-1",
        )
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)
        # El contrato vuelve entero, sin perder ni un score ni la procedencia.
        assert guardado.pose_selection == SELECCION
        leido = EvaluationResultRead.model_validate(guardado)

    # Y viaja por JSON —que es como sale de la API— sin perder tipos.
    plano = json.loads(leido.model_dump_json())["pose_selection"]
    assert plano["status"] == "selected"
    assert plano["vina_top1_rank"] == 1
    assert plano["confidence"] == 0.412233
    assert plano["model"]["model_sha256"] == "b" * 64
    assert plano["model"]["abstention_threshold"] == 0.097663
    assert plano["pose_scores"] == SELECCION["pose_scores"]
    assert plano["inputs"]["pose_pdbqt_source"] == "docking_poses[].pdbqt_block"
    # La pose sugerida falla los controles: revisión declarada y alternativas
    # MOSTRADAS, no seleccionadas. La sugerida no cambió al persistirse.
    assert plano["physical_review"] is True
    assert plano["selected_pose_rank"] == 2
    assert [a["rank"] for a in plano["physically_valid_alternatives"]] == [1, 3]


@pytest.mark.asyncio
async def test_una_abstencion_persistida_no_se_lee_como_recomendacion(entorno):
    """Una abstención guardada sigue siendo una abstención al releerla."""
    molecule_id = await entorno.semilla()
    abstenido = dict(SELECCION, status=ps.STATUS_ABSTAINED, abstained=True,
                     strategy=ps.STRATEGY_VINA_TOP1, strategy_is_fallback=True,
                     selected_pose_rank=None, abstention_reason=ps.MARGEN_BAJO_UMBRAL)

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=abstenido, task_id="t-1")
        await s.commit()

    async with entorno.factory() as s:
        leido = EvaluationResultRead.model_validate(
            await Repository(s).get_evaluation_result(molecule_id))

    assert leido.pose_selection["status"] == ps.STATUS_ABSTAINED
    assert leido.pose_selection["selected_pose_rank"] is None
    # Y la referencia se declara como FALLBACK, no como un éxito del selector.
    assert leido.pose_selection["strategy"] == ps.STRATEGY_VINA_TOP1
    assert leido.pose_selection["strategy_is_fallback"] is True
    assert leido.pose_selection["vina_top1_rank"] == 1


# ── 10. Reintento idempotente ────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_reintento_no_duplica_ni_borra_la_seleccion(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=SELECCION, task_id="t-1")
        await s.commit()

    # Un upsert intermedio SIN selección —el de propiedades, por ejemplo— no
    # puede tirar la recomendación ya calculada.
    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(molecule_id=molecule_id, task_id="t-1")
        await s.commit()

    async with entorno.factory() as s:
        assert (await Repository(s).get_evaluation_result(molecule_id)).pose_selection == SELECCION

    # Y recalcular escribe el mismo contrato: una fila, no dos.
    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=SELECCION, task_id="t-1")
        await s.commit()

    async with entorno.factory() as s:
        assert (await Repository(s).get_evaluation_result(molecule_id)).pose_selection == SELECCION

    with sqlite3.connect(entorno.path) as raw:
        assert raw.execute("SELECT COUNT(*) FROM evaluation_results").fetchone()[0] == 1


# ── Resultado antiguo ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_resultado_antiguo_abre_como_unavailable(entorno):
    """
    La regla del sprint para lo ya guardado.

    En la columna hay NULL y ahí se queda: la migración es aditiva y no
    reescribe historia. Lo que cambia es la LECTURA — el cliente recibe
    `unavailable` con su razón, no un `null` que tendría que interpretar.
    """
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(molecule_id=molecule_id, task_id="viejo")
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)
        leido = EvaluationResultRead.model_validate(guardado)

    # La fila no se tocó…
    assert guardado.pose_selection is None
    with sqlite3.connect(entorno.path) as raw:
        assert raw.execute(
            "SELECT pose_selection FROM evaluation_results").fetchone()[0] is None

    # …y aun así el lector recibe el contrato completo.
    seleccion = leido.pose_selection
    assert seleccion["status"] == ps.STATUS_UNAVAILABLE
    assert seleccion["abstention_reason"] == ps.SELECCION_AUSENTE
    assert seleccion["strategy"] == ps.STRATEGY_VINA_TOP1
    assert seleccion["strategy_is_fallback"] is True
    # `unavailable` NO es `abstained`: nadie se abstuvo, la etapa no existía.
    assert seleccion["abstained"] is False
    assert seleccion["selected_pose_rank"] is None

    # Y el sustituto es estable: dos lecturas del mismo resultado antiguo dan
    # el mismo contrato. Si llevara `now()`, el hash de un dossier se movería
    # sin que nada hubiera cambiado.
    assert ps.seleccion_ausente() == ps.seleccion_ausente()
    assert ps.seleccion_ausente()["evaluated_at"] is None


def test_lo_guardado_se_devuelve_tal_cual_y_solo_se_normaliza_la_ausencia():
    """`pose_selection_para_lectura` no reinterpreta lo medido."""
    assert ps.pose_selection_para_lectura(SELECCION) is SELECCION
    for vacio in (None, {}, "", []):
        assert ps.pose_selection_para_lectura(vacio)["status"] == ps.STATUS_UNAVAILABLE


# ── Migración aditiva ────────────────────────────────────────────────


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
            "SELECT affinity_kcal, task_id, pose_selection FROM evaluation_results"
        ).fetchone()

    assert "pose_selection" in columnas
    # Lo que ya estaba, intacto; la selección, NULL.
    assert fila == (-8.3, "viejo", None)
    assert db_mod.SCHEMA_VERSION >= 8


# ── Cohortes ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_fila_de_cohorte_recupera_la_seleccion_por_su_result_id(entorno):
    """
    La recomendación queda asociada al resultado persistente y se recupera por
    el MISMO `result_id` de esa ejecución — no por «el resultado más reciente de
    esta molécula», y sin volver a ejecutar el selector.
    """
    from core.models import CohortRunRowORM
    from services.cohort import evidence as cohort_ev

    molecule_id = await entorno.semilla()
    async with entorno.factory() as s:
        guardado = await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=SELECCION, task_id="t-1")
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
    seleccion = moleculas[0]["pose_selection"]
    assert seleccion["status"] == ps.STATUS_SELECTED
    assert seleccion["selected_pose_rank"] == 2
    assert seleccion["vina_top1_rank"] == 1
    # La afinidad observada de la fila sigue siendo la de Vina: la recomendación
    # viaja al lado, no sustituye la medida.
    assert moleculas[0]["observed_vina_affinity_kcal_mol"] == resultado.affinity_kcal
    # Y la cohorte sigue sin publicar ninguna puntuación agregada.
    assert "total_score" not in json.dumps(moleculas).lower()


@pytest.mark.asyncio
async def test_una_fila_de_cohorte_sin_seleccion_abre_como_unavailable(entorno):
    """Una fila que no llegó a acoplar, o anterior a la etapa, no dice `null`."""
    from core.models import CohortRunRowORM
    from services.cohort import evidence as cohort_ev

    fila = CohortRunRowORM(
        id=uuid.uuid4(), run_id=uuid.uuid4(), source_row_index=0,
        canonical_smiles="CCO", control_role="none", status="failed",
        molecule_id=None, result_id=None,
    )

    moleculas = cohort_ev.build_molecule_evidence([fila], {})

    seleccion = moleculas[0]["pose_selection"]
    assert seleccion["status"] == ps.STATUS_UNAVAILABLE
    assert seleccion["abstention_reason"] == ps.SELECCION_AUSENTE
    assert seleccion["strategy_is_fallback"] is True


# ── La etapa en el pipeline: dónde va y qué no puede tumbar ──────────


def test_casos_y_cohortes_usan_la_MISMA_etapa_de_seleccion():
    """
    No hay dos selectores. El hook del pipeline es uno, y la corrida de cohorte
    entra por ese mismo pipeline con su receptor congelado.

    Si hubiera dos caminos, uno de los dos envejecería sin que nadie lo notara —
    y sería el de cohortes, que es el que menos se mira.
    """
    import inspect

    from services.cohort import execution as ex
    from services.pipeline import runner

    hook = inspect.getsource(runner.run_pipeline)
    assert "build_pose_selection_for_run" in hook
    # Con los bytes CONGELADOS del receptor cuando los hay: en una cohorte, el
    # receptor no se relee del catálogo mutable.
    assert "receptor_bytes=prepared_receptor_bytes" in hook

    cohorte = inspect.getsource(ex._evaluate_one)
    assert "run_pipeline" in cohorte
    assert "prepared_receptor_bytes=receptor.prepared_bytes" in cohorte


def test_la_seleccion_ocurre_DESPUES_de_generar_y_validar_las_poses():
    """
    El orden es parte del contrato: la recomendación necesita el veredicto
    físico para poder decir si la pose que sugiere pasa los controles y para
    listar alternativas que sí pasan. Invertirlo dejaría
    `suggested_pose_physical_status` permanentemente en `None`, es decir, todo
    en revisión.
    """
    import inspect

    from services.pipeline import runner

    hook = inspect.getsource(runner.run_pipeline)
    assert hook.index("build_structural_evidence") < hook.index("build_pose_selection_for_run")
    # Y ambas antes del upsert FINAL —el del docking—, que es donde las dos se
    # guardan juntas. `rindex`: el pipeline persiste antes las propiedades, y
    # esa llamada temprana no es la que cierra la evaluación.
    assert hook.index("build_pose_selection_for_run") < hook.rindex(
        "_quick_upsert_evaluation_result")
    assert "pose_selection=pose_selection" in hook


def test_un_fallo_del_selector_no_puede_tumbar_una_evaluacion():
    """
    La etapa va envuelta y su fallo se degrada a `None` —que la lectura abre
    como `unavailable`—. Un docking que ya terminó no puede perderse porque una
    recomendación opcional reventara.
    """
    import inspect
    import re

    from services.pipeline import runner

    hook = inspect.getsource(runner.run_pipeline)
    bloque = hook[
        hook.index("pose_selection = None"):hook.rindex("_quick_upsert_evaluation_result")
    ]
    assert re.search(r"except Exception[\s\S]*pose_selection = None", bloque)
    assert "pose_selection_fallo_no_fatal" in bloque


@pytest.mark.asyncio
async def test_una_seleccion_ausente_deja_la_evaluacion_intacta(entorno):
    molecule_id = await entorno.semilla()

    async with entorno.factory() as s:
        await Repository(s).upsert_evaluation_result(
            molecule_id=molecule_id, pose_selection=ps.seleccion_ausente(), task_id="t-2")
        await s.commit()

    async with entorno.factory() as s:
        guardado = await Repository(s).get_evaluation_result(molecule_id)

    # La selección se declara ausente…
    assert guardado.pose_selection["status"] == ps.STATUS_UNAVAILABLE
    # …y el resultado de la evaluación sigue ahí, sin error registrado.
    assert guardado.error_message is None
    assert guardado.task_id == "t-2"
