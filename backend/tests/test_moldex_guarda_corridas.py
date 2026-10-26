"""Moldex guarda EVALUACIONES, no moléculas: guardar una no pisa ni oculta las demás.

Una molécula (receptor + ligando) se reutiliza en cada evaluación y su resultado
vivo es una sola fila mutable (`evaluation_results`). Moldex leía esa fila y
`is_saved` era de la molécula, así que en un mismo caso:

- evaluar A, guardarla, evaluar B → Moldex enseñaba los números de B bajo la ficha
  que el investigador guardó con A;
- no había forma de guardar A y B a la vez;
- el Historial marcaba «Moldex» en TODAS las corridas de la molécula.

El contrato nuevo: guardar es un hecho de la CORRIDA (`evaluation_runs.saved_at`),
Moldex lista una ficha por corrida guardada con las cifras congeladas de esa
corrida, y archivos, PDF y certificación se resuelven por `task_id`.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from api import moldex
from api.dependencies import get_current_user, get_current_user_optional
from api.routers import blockchain, evaluation_files, history
from core.database import get_db
from core.models import (
    Base,
    EvaluationResultORM,
    EvaluationRunORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
from db.repository import Repository
from services.docking.projection_lifecycle import begin_evaluation_projection

SDF_DE = {
    "run-A": "A\n  MolDesign\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n",
    "run-B": "B\n  MolDesign\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n",
}


class Mundo:
    """Un investigador, un receptor y una molécula que se evalúa varias veces."""

    def __init__(self, factory, owner, other, target, molecule_id):
        self.factory = factory
        self.owner = owner
        self.other = other
        self.target = target
        self.molecule_id = molecule_id

    async def evaluar(self, task_id: str, score: float, afinidad: float, *, estado="SUCCESS"):
        """El mismo ciclo que el pipeline: archivar la proyección, escribirla, congelarla."""
        async with self.factory() as db:
            repo = Repository(db)
            await begin_evaluation_projection(repo, self.molecule_id, task_id)
            await repo.upsert_evaluation_result(
                molecule_id=self.molecule_id,
                scores={"total_score": score},
                task_id=task_id,
            )
            resultado = await repo.get_evaluation_result(self.molecule_id)
            resultado.affinity_kcal = afinidad
            resultado.poses_file_path = f"poses/{task_id}.sdf"
            resultado.evaluated_at = datetime.now(timezone.utc)
            await repo.snapshot_evaluation_run(self.molecule_id, task_id)
            if estado != "SUCCESS":
                corrida = await repo.get_evaluation_run(task_id, self.molecule_id)
                corrida.status = estado
            await db.commit()


@pytest_asyncio.fixture
async def mundo():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    owner = UserORM(id=uuid.uuid4(), email="o@local", username="owner", hashed_password="x")
    other = UserORM(id=uuid.uuid4(), email="x@local", username="other", hashed_password="x")
    target = TargetORM(
        id=uuid.uuid4(), pdb_id="1HSG", name="HIV protease",
        grid_center_x=0, grid_center_y=0, grid_center_z=0,
    )
    molecula = MoleculeORM(
        id=uuid.uuid4(), user_id=owner.id, target_id=target.id, smiles="CCO",
        smiles_hash="h" * 64, status=MoleculeStatus.EVALUATED,
    )
    async with factory() as db:
        db.add_all([owner, other, target, molecula])
        await db.commit()
    yield Mundo(factory, owner, other, target, molecula.id)
    await engine.dispose()


def _app(mundo: Mundo, usuario=None) -> FastAPI:
    async def database():
        async with mundo.factory() as db:
            yield db

    app = FastAPI()
    app.include_router(history.router)
    app.include_router(moldex.router)
    app.include_router(evaluation_files.router, prefix="/evaluation")
    app.include_router(blockchain.router)
    app.dependency_overrides[get_db] = database
    quien = usuario or mundo.owner
    app.dependency_overrides[get_current_user] = lambda: quien
    app.dependency_overrides[get_current_user_optional] = lambda: quien
    return app


@pytest_asyncio.fixture
async def cliente(mundo):
    async with AsyncClient(transport=ASGITransport(app=_app(mundo)), base_url="http://t") as c:
        yield c


async def _guardar(cliente, mundo, task_id=None, name=None):
    params = {}
    if task_id:
        params["task_id"] = task_id
    if name:
        params["name"] = name
    return await cliente.post(f"/history/save/{mundo.molecule_id}", params=params)


async def _fichas(cliente):
    return (await cliente.get("/moldex")).json()["results"]


# ── El defecto: reevaluar pisaba lo guardado ──────────────────────────────────


@pytest.mark.asyncio
async def test_moldex_congela_traza_independiente_por_corrida(mundo):
    for task, archive in (("run-A", "runs/vina-search/a.zip"), ("run-B", "runs/vina-search/b.zip")):
        async with mundo.factory() as db:
            repo = Repository(db)
            await begin_evaluation_projection(repo, mundo.molecule_id, task)
            await repo.upsert_evaluation_result(molecule_id=mundo.molecule_id,
                scores={"total_score":50}, task_id=task,
                docking_protocol={"execution_provenance":{"search_trace":{
                    "archive_path":archive,"archive_sha256":task*16,"replicas":8}}})
            await repo.snapshot_evaluation_run(mundo.molecule_id,task)
            await db.commit()
    async with mundo.factory() as db:
        repo = Repository(db)
        for task, archive in (("run-A","runs/vina-search/a.zip"),("run-B","runs/vina-search/b.zip")):
            run = await repo.get_evaluation_run(task,mundo.molecule_id)
            snapshot = await repo.materialize_run_snapshot(run)
            trace = snapshot["docking_protocol"]["execution_provenance"]["search_trace"]
            assert trace["archive_path"]==archive
            assert trace["replicas"]==8


@pytest.mark.asyncio
async def test_reevaluar_no_pisa_la_evaluacion_guardada(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    assert (await _guardar(cliente, mundo, "run-A")).status_code == 200
    await mundo.evaluar("run-B", 55.0, -7.5)

    (ficha,) = await _fichas(cliente)

    assert ficha["provenance"]["task_id"] == "run-A"
    assert ficha["metrics"]["score"] == 40.0
    assert ficha["metrics"]["affinity"] == -6.0


@pytest.mark.asyncio
async def test_guardar_una_evaluacion_no_guarda_las_demas(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)

    await _guardar(cliente, mundo, "run-A")

    fichas = await _fichas(cliente)
    assert [f["provenance"]["task_id"] for f in fichas] == ["run-A"]


@pytest.mark.asyncio
async def test_el_historial_marca_moldex_solo_en_la_corrida_guardada(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    await _guardar(cliente, mundo, "run-A")

    filas = {i["task_id"]: i for i in (await cliente.get("/history/evaluations")).json()["items"]}

    assert set(filas) == {"run-A", "run-B"}
    assert filas["run-A"]["is_saved"] is True
    assert filas["run-B"]["is_saved"] is False
    # Y cada fila conserva SUS cifras: el historial nunca las mezcló.
    assert filas["run-A"]["total_score"] == 40.0
    assert filas["run-B"]["total_score"] == 55.0


# ── Varias evaluaciones de la misma molécula ──────────────────────────────────


@pytest.mark.asyncio
async def test_varias_evaluaciones_de_la_misma_molecula_son_varias_fichas(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    await _guardar(cliente, mundo, "run-A", "exh 8")
    await _guardar(cliente, mundo, "run-B", "exh 32")

    fichas = await _fichas(cliente)

    por_corrida = {f["provenance"]["task_id"]: f for f in fichas}
    assert set(por_corrida) == {"run-A", "run-B"}
    assert por_corrida["run-A"]["metrics"]["score"] == 40.0
    assert por_corrida["run-B"]["metrics"]["score"] == 55.0
    # Misma molécula, fichas distintas: `id` es de la molécula y `entry_id` de la ficha.
    assert {f["id"] for f in fichas} == {str(mundo.molecule_id)}
    assert len({f["entry_id"] for f in fichas}) == 2
    assert por_corrida["run-A"]["name"] == "exh 8"
    assert por_corrida["run-B"]["name"] == "exh 32"


@pytest.mark.asyncio
async def test_guardar_dos_veces_la_misma_evaluacion_no_duplica_la_ficha(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await _guardar(cliente, mundo, "run-A", "primero")
    await _guardar(cliente, mundo, "run-A", "segundo")

    (ficha,) = await _fichas(cliente)

    assert ficha["name"] == "segundo"


@pytest.mark.asyncio
async def test_sin_task_id_se_guarda_la_evaluacion_vigente(mundo, cliente):
    """Compatibilidad: un cliente anterior no manda `task_id`."""
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)

    respuesta = await _guardar(cliente, mundo)

    assert respuesta.status_code == 200
    assert respuesta.json()["task_id"] == "run-B"
    assert [f["provenance"]["task_id"] for f in await _fichas(cliente)] == ["run-B"]


@pytest.mark.asyncio
async def test_las_fichas_se_ordenan_por_score_dentro_del_receptor(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    await _guardar(cliente, mundo, "run-A")
    await _guardar(cliente, mundo, "run-B")

    fichas = await _fichas(cliente)

    assert [f["metrics"]["score"] for f in fichas] == [55.0, 40.0]


@pytest.mark.asyncio
async def test_la_paginacion_cuenta_fichas_no_moleculas(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    await _guardar(cliente, mundo, "run-A")
    await _guardar(cliente, mundo, "run-B")

    pagina = (await cliente.get("/moldex", params={"limit": 1, "offset": 1})).json()

    assert pagina["total"] == 2
    assert pagina["count"] == 1
    assert pagina["results"][0]["provenance"]["task_id"] == "run-A"
    assert pagina["has_next"] is False


# ── Lo que no se puede guardar ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_corrida_fallida_no_se_guarda(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0, estado="FAILURE")

    respuesta = await _guardar(cliente, mundo, "run-A")

    assert respuesta.status_code == 409
    assert await _fichas(cliente) == []


@pytest.mark.asyncio
async def test_una_corrida_inexistente_o_ajena_no_se_guarda(mundo, cliente):
    await mundo.evaluar("run-A", 40.0, -6.0)

    assert (await _guardar(cliente, mundo, "no-existe")).status_code == 404
    assert await _fichas(cliente) == []


@pytest.mark.asyncio
async def test_otra_cuenta_no_puede_guardar_ni_ve_la_ficha(mundo):
    await mundo.evaluar("run-A", 40.0, -6.0)
    async with AsyncClient(
        transport=ASGITransport(app=_app(mundo, mundo.other)), base_url="http://t"
    ) as ajeno:
        assert (await _guardar(ajeno, mundo, "run-A")).status_code == 404
        assert await _fichas(ajeno) == []


@pytest.mark.asyncio
async def test_un_addendum_corrupto_no_tumba_la_biblioteca(mundo, cliente):
    """La ficha sale con lo que congeló su corrida (sin lo posterior) y las demás intactas."""
    from core.models import EvaluationRunAddendumORM

    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    await _guardar(cliente, mundo, "run-A")
    await _guardar(cliente, mundo, "run-B")
    async with mundo.factory() as db:
        db.add(EvaluationRunAddendumORM(
            task_id="run-A", molecule_id=mundo.molecule_id, kind="certificate",
            payload_json={"blockchain_tx_id": "falsa", "certified_task_id": "run-A",
                          "certified_total_score": 40.0},
            sha256="0" * 64,  # no es el hash de su contenido
        ))
        await db.commit()

    respuesta = await cliente.get("/moldex")

    assert respuesta.status_code == 200
    por_corrida = {f["provenance"]["task_id"]: f for f in respuesta.json()["results"]}
    assert set(por_corrida) == {"run-A", "run-B"}
    # Lo que no se puede verificar no se afirma: la ficha no hereda un sello dudoso.
    assert por_corrida["run-A"]["blockchain"]["certified"] is False


# ── Moléculas guardadas antes de las fichas por corrida ───────────────────────


@pytest.mark.asyncio
async def test_una_molecula_guardada_por_la_via_anterior_sigue_en_moldex(mundo, cliente):
    """Proyección sin snapshot (anterior a v11): sólo existe la fila viva."""
    async with mundo.factory() as db:
        repo = Repository(db)
        await repo.upsert_evaluation_result(
            molecule_id=mundo.molecule_id, scores={"total_score": 33.0}, task_id=None,
        )
        molecula = await db.get(MoleculeORM, mundo.molecule_id)
        molecula.is_saved = True
        await db.commit()

    (ficha,) = await _fichas(cliente)

    assert ficha["metrics"]["score"] == 33.0
    assert ficha["entry_id"] == ficha["id"] == str(mundo.molecule_id)


# ── Archivos de la ficha ──────────────────────────────────────────────────────


@pytest.fixture
def poses_en_disco(monkeypatch):
    async def leer(ruta, *args, **kwargs):
        return SDF_DE[ruta.split("/")[-1].removesuffix(".sdf")]

    monkeypatch.setattr("utils.local_storage.read_text", leer)


@pytest.mark.asyncio
async def test_las_poses_de_una_ficha_son_las_de_su_corrida(mundo, cliente, poses_en_disco):
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)
    base = f"/evaluation/files/poses/{mundo.molecule_id}"

    de_a = await cliente.get(base, params={"task_id": "run-A"})
    vigente = await cliente.get(base)

    assert de_a.status_code == 200 and de_a.text.startswith("A\n")
    assert vigente.status_code == 200 and vigente.text.startswith("B\n")
    assert (await cliente.get(base, params={"task_id": "no-existe"})).status_code == 404


# ── Certificado y sello de una ficha anterior ─────────────────────────────────


@pytest.mark.asyncio
async def test_el_dossier_de_una_ficha_describe_su_corrida(mundo, cliente, monkeypatch):
    capturado = {}

    def pdf(molecula, evaluacion, *args, **kwargs):
        import io

        capturado[evaluacion.task_id] = evaluacion.total_score
        return io.BytesIO(b"%PDF-1.4 prueba")

    monkeypatch.setattr(blockchain, "generate_certificate_pdf", pdf)
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)

    assert (await cliente.get(f"/blockchain/certificate/{mundo.molecule_id}",
                              params={"task_id": "run-A"})).status_code == 200
    assert (await cliente.get(f"/blockchain/certificate/{mundo.molecule_id}")).status_code == 200

    assert capturado == {"run-A": 40.0, "run-B": 55.0}


@pytest.mark.asyncio
async def test_certificar_una_ficha_anterior_sella_su_score_y_no_toca_la_vigente(
    mundo, cliente, monkeypatch,
):
    async def verificar(firma):
        return SimpleNamespace(
            smiles_hash="h" * 64, total_score=40.0, target_pdb_id="1HSG", user_wallet="",
        )

    monkeypatch.setattr(blockchain, "verify_certification_onchain", verificar)
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)

    # El score del memo es el de A: contra la proyección vigente (B, 55) sería inválido.
    sin_corrida = await cliente.post("/blockchain/certify/link", json={
        "molecule_id": str(mundo.molecule_id), "signature": "firma-A"})
    assert sin_corrida.status_code == 400

    enlazado = await cliente.post("/blockchain/certify/link", json={
        "molecule_id": str(mundo.molecule_id), "signature": "firma-A", "task_id": "run-A"})
    assert enlazado.status_code == 200

    async with mundo.factory() as db:
        vigente = await Repository(db).get_evaluation_result(mundo.molecule_id)
        assert vigente.task_id == "run-B"
        assert vigente.blockchain_tx_id is None  # el sello de A no se pega a B
    # Certificar guarda: A es ahora una ficha, ya sellada y vigente respecto de sí misma.
    (ficha,) = await _fichas(cliente)
    assert ficha["provenance"]["task_id"] == "run-A"
    assert ficha["blockchain"]["certified"] is True
    assert ficha["blockchain"]["tx_signature"] == "firma-A"
    assert ficha["blockchain"]["matches_current_run"] is True


# ── Migración v29 ─────────────────────────────────────────────────────────────


def _base_v28(ruta) -> None:
    """Una base como la que deja 1.0.1: sin `saved_at` ni `saved_name`."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    motor = create_engine(f"sqlite:///{ruta}")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        usuario = UserORM(id=uuid.uuid4(), email="m@l", username="m", hashed_password="x")
        receptor = TargetORM(
            id=uuid.uuid4(), pdb_id="1HSG", name="HIV",
            grid_center_x=0, grid_center_y=0, grid_center_z=0,
        )
        sesion.add_all([usuario, receptor])
        sesion.flush()
        for nombre, guardada in (("guardada", True), ("no guardada", False)):
            molecula = MoleculeORM(
                id=uuid.uuid4(), user_id=usuario.id, target_id=receptor.id, smiles="CCO",
                smiles_hash=nombre, status=MoleculeStatus.EVALUATED, is_saved=guardada,
                name=nombre,
            )
            sesion.add(molecula)
            sesion.flush()
            sesion.add(EvaluationResultORM(molecule_id=molecula.id, task_id=f"vigente-{nombre}"))
            for tarea in (f"vigente-{nombre}", f"anterior-{nombre}"):
                sesion.add(EvaluationRunORM(
                    task_id=tarea, molecule_id=molecula.id, snapshot_json={}, status="SUCCESS",
                ))
        sesion.commit()
    motor.dispose()
    conexion = sqlite3.connect(ruta)
    conexion.execute("ALTER TABLE evaluation_runs DROP COLUMN saved_at")
    conexion.execute("ALTER TABLE evaluation_runs DROP COLUMN saved_name")
    conexion.commit()
    conexion.close()


def test_la_migracion_conserva_exactamente_lo_que_moldex_ya_mostraba(tmp_path):
    from core.database import _migrate_sqlite_db

    ruta = tmp_path / "v28.db"
    _base_v28(ruta)

    _migrate_sqlite_db(ruta)

    conexion = sqlite3.connect(ruta)
    guardadas = dict(conexion.execute(
        "SELECT task_id, saved_name FROM evaluation_runs WHERE saved_at IS NOT NULL"
    ).fetchall())
    conexion.close()
    # Sólo la corrida vigente de la molécula guardada: lo que Moldex mostraba.
    assert guardadas == {"vigente-guardada": "guardada"}


def test_la_migracion_no_resucita_fichas_en_el_siguiente_arranque(tmp_path):
    from core.database import _migrate_sqlite_db

    ruta = tmp_path / "v28.db"
    _base_v28(ruta)
    _migrate_sqlite_db(ruta)
    conexion = sqlite3.connect(ruta)
    conexion.execute("UPDATE evaluation_runs SET saved_at = NULL, saved_name = NULL")
    conexion.commit()
    conexion.close()

    _migrate_sqlite_db(ruta)  # segundo arranque: la columna ya existe

    conexion = sqlite3.connect(ruta)
    n = conexion.execute(
        "SELECT COUNT(*) FROM evaluation_runs WHERE saved_at IS NOT NULL"
    ).fetchone()[0]
    conexion.close()
    assert n == 0


def test_el_modelo_declara_las_columnas_de_la_ficha():
    columnas = EvaluationRunORM.__table__.columns
    assert "saved_at" in columnas and "saved_name" in columnas
    assert columnas["saved_at"].nullable and columnas["saved_name"].nullable
