"""
Ejecución durable de una cohorte: qué se congela, qué se reanuda y qué no se inventa.

Base SQLite de archivo, app real, y **el evaluador sustituido de forma
controlada**: sustituir Vina no es aflojar la prueba, es la única forma de
ejercitar el bucle durable sin convertir la suite en un banco de acoplamiento.
Lo que se sustituye es exactamente un punto —`services.cohort.execution._evaluate_one`—
y todo lo demás es el código real.

Lo que protegen, en orden de gravedad:

1. **Se ejecuta lo que se aceptó.** Sólo filas `eligible` del snapshot, con sus
   `canonical_smiles` congelados. El archivo original no se vuelve a leer nunca:
   recanonicalizar con el RDKit de hoy ejecutaría otra cohorte.

2. **Un fallo no se convierte en evidencia negativa.** `failed` y
   `not_evaluated` son cosas distintas, y ninguna de las dos dice nada sobre la
   molécula.

3. **Nada finge seguir vivo.** Una corrida que sobrevive a un cierre queda
   `interrupted`, no `running`, y reanudar no repite lo terminado.

4. **La cohorte congelada no se toca.** Ningún estado de ejecución la modifica.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from api.dependencies import get_current_user_optional
from api.routers import evaluation_cohort_runs as runs_router
from api.routers import evaluation_cohorts as cohorts_router
from core.database import get_db
from core.models import Base, CohortORM, CohortRunORM, CohortRunRowORM, TargetORM, UserORM
from services.cohort import execution as ex
from services.cohort import runs as run_repo
from tests.conftest import rdkit_available

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"
ASPIRINA_REESCRITA = "OC(=O)c1ccccc1OC(C)=O"

STUDY = {
    "schema_version": 1,
    "name": "Serie de anilinas · lote 3",
    "receptor": {"pdb_id": "7E2Y", "chain": "A"},
    "config": {
        "docking_engine": "vina",
        "exhaustiveness": 8,
        "num_poses": 5,
        "grid_center": [10.0, 11.0, 12.0],
        "grid_size": [22.0, 22.0, 22.0],
        "seed": 42,
    },
}

#: 5 filas: 3 elegibles (una de ellas duplicado canónico de la primera), una
#: ilegible y una vacía.
CSV = "\n".join(
    [
        "name,smiles,active,control_role",
        f"aspirina,{ASPIRINA},1,reference",
        f"ibuprofeno,{IBUPROFENO},0,none",
        f"aspirina-bis,{ASPIRINA_REESCRITA},1,none",
        "rota,CCX,,none",
        ",,,",
    ]
).encode("utf-8")


# ── Entorno ──────────────────────────────────────────────────────────


class _Entorno:
    def __init__(self, db_path: Path, data_dir: Path):
        self.db_path = db_path
        self.data_dir = data_dir
        self.engine = None
        self.factory = None

    async def arrancar(self):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # `services/cohort/runs.py` abre SUS PROPIAS sesiones con
        # `get_db_session()`: el ejecutor vive fuera de la petición. Se inyecta
        # el engine en el singleton para que apunte a esta base.
        db_mod.set_engine(self.engine)

    async def apagar(self):
        if self.engine is not None:
            await self.engine.dispose()
        await db_mod.reset_engine()
        self.engine = None
        self.factory = None

    async def reiniciar(self):
        """Cierra y vuelve a abrir. Lo que sobreviva a esto sobrevive de verdad."""
        await self.apagar()
        await self.arrancar()

    def app(self, usuario: UserORM | None = None) -> TestClient:
        aplicacion = FastAPI()
        aplicacion.include_router(cohorts_router.router, prefix="/evaluation")
        aplicacion.include_router(runs_router.cohort_router, prefix="/evaluation")
        aplicacion.include_router(runs_router.router, prefix="/evaluation")

        async def _db():
            async with self.factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        aplicacion.dependency_overrides[get_db] = _db
        aplicacion.dependency_overrides[get_current_user_optional] = lambda: usuario
        return TestClient(aplicacion)

    async def crear_usuario(self, username: str) -> UserORM:
        async with self.factory() as session:
            user = UserORM(
                id=uuid.uuid4(),
                email=f"{username}@moldesign.local",
                username=username,
                hashed_password="x",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            return user

    async def crear_target(self, pdb_id: str = "7E2Y") -> TargetORM:
        async with self.factory() as session:
            target = TargetORM(
                id=uuid.uuid4(),
                pdb_id=pdb_id,
                name=f"Target {pdb_id}",
                chain="A",
                grid_center_x=1.0,
                grid_center_y=2.0,
                grid_center_z=3.0,
                grid_size_x=20.0,
                grid_size_y=20.0,
                grid_size_z=20.0,
                is_prepared=True,
            )
            session.add(target)
            await session.commit()
            return target

    def preparar_receptor(self, pdb_id: str = "7E2Y", contenido: bytes = b"ATOM   PDBQT\n"):
        """Escribe un `.pdbqt` preparado en el almacenamiento del producto."""
        destino = self.data_dir / "targets" / pdb_id.upper()
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "prepared.pdbqt").write_bytes(contenido)
        return contenido

    async def corrida(self, run_id) -> CohortRunORM:
        async with self.factory() as session:
            return await session.get(CohortRunORM, uuid.UUID(str(run_id)))

    async def filas(self, run_id) -> list[CohortRunRowORM]:
        async with self.factory() as session:
            resultado = await session.execute(
                select(CohortRunRowORM)
                .where(CohortRunRowORM.run_id == uuid.UUID(str(run_id)))
                .order_by(CohortRunRowORM.source_row_index)
            )
            return list(resultado.scalars().all())


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    """Base y almacenamiento aislados; `local_data_dir` apunta al tmp."""
    import core.config as core_config
    from types import SimpleNamespace

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    real = core_config.get_settings()
    # `dir(real)` sobre un modelo Pydantic toca `model_fields` y
    # `model_computed_fields` en la instancia, que están deprecados desde 2.11 y
    # producían 104 avisos por corrida — dos tercios del ruido de toda la suite,
    # tapando los avisos que sí importan. Se copian los campos declarados del
    # modelo, que es lo que se quería copiar.
    campos = {nombre: getattr(real, nombre) for nombre in type(real).model_fields}
    falsas = SimpleNamespace(**{**campos, "local_data_dir": str(data_dir)})
    monkeypatch.setattr(core_config, "get_settings", lambda: falsas)
    import utils.local_storage as ls

    monkeypatch.setattr(ls, "data_dir", lambda: data_dir)

    await db_mod.reset_engine()
    env = _Entorno(tmp_path / "cohortes.db", data_dir)
    await env.arrancar()
    try:
        yield env
    finally:
        await env.apagar()


@pytest.fixture
def evaluador(monkeypatch):
    """
    Sustituye el ÚNICO punto que llama al pipeline real.

    Registra qué SMILES se pidieron —para poder afirmar que cada molécula única
    se acopló exactamente una vez— y permite programar la respuesta por SMILES.
    """
    llamadas: list[str] = []
    respuestas: dict[str, dict | Exception] = {}
    encolados: list[tuple] = []

    # El endpoint encola de verdad. Aquí se NEUTRALIZA el encolado y se conduce
    # `execute_run` a mano desde el bucle de la prueba: si no, la tarea del
    # endpoint y la llamada explícita ejecutarían la misma corrida dos veces y
    # la prueba mediría una carrera en vez de un contrato. Que el encolado
    # ocurre —y en el orden correcto— se comprueba aparte.
    async def _no_encolar(run_id, *, workers):
        encolados.append((run_id, workers))

    monkeypatch.setattr(run_repo, "schedule", _no_encolar)

    async def _falso(*, canonical_smiles, molecule_name, receptor, config, user_id):
        llamadas.append(canonical_smiles)
        programada = respuestas.get(canonical_smiles, "ok")
        if isinstance(programada, Exception):
            raise programada
        if programada == "ok":
            return {"molecule_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4())}
        return programada

    monkeypatch.setattr(ex, "_evaluate_one", _falso)
    return type(
        "Evaluador", (), {"llamadas": llamadas, "respuestas": respuestas, "encolados": encolados}
    )()


# ── Helpers ──────────────────────────────────────────────────────────


def _congelar(client: TestClient, contenido: bytes = CSV, study=None) -> dict:
    definicion = json.dumps(study if study is not None else STUDY)
    previo = client.post(
        "/evaluation/cohorts/preflight",
        files={"file": ("cohorte.csv", contenido, "text/csv")},
        data={"study": definicion},
    )
    assert previo.status_code == 200, previo.text
    creada = client.post(
        "/evaluation/cohorts",
        files={"file": ("cohorte.csv", contenido, "text/csv")},
        data={
            "study": definicion,
            "expected_fingerprint": previo.json()["cohort_fingerprint"],
        },
    )
    assert creada.status_code == 201, creada.text
    return creada.json()


async def _abrir_y_esperar(entorno, client, cohort_id, **params):
    """
    Abre la corrida y ejecuta su bucle EN EL LOOP DE LA PRUEBA.

    `TestClient` corre la aplicación en su propio portal, con un bucle que se
    cierra al terminar la petición: una tarea de fondo nacida allí moriría con
    él y la prueba mediría el arnés, no el producto. Aquí se comprueba que el
    endpoint acepta y persiste (202), y después se llama al MISMO
    `execute_run` que encola producción, de forma determinista.

    Que el endpoint encole de verdad se comprueba aparte, en
    `test_el_endpoint_encola_la_ejecucion_despues_de_persistir`.
    """
    respuesta = client.post(f"/evaluation/cohorts/{cohort_id}/runs", params=params)
    if respuesta.status_code != 202:
        return respuesta, None
    run_id = respuesta.json()["run_id"]
    await run_repo.execute_run(
        uuid.UUID(run_id), workers=respuesta.json()["workers"]
    )
    return respuesta, run_id


# ── 1-4. Se ejecuta lo congelado, con la configuración común ─────────


@rdkit_available
@pytest.mark.asyncio
async def test_solo_ejecuta_filas_eligible_del_snapshot(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    respuesta, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    assert respuesta.status_code == 202
    filas = await entorno.filas(run_id)
    # 5 filas en el archivo, 3 elegibles: la ilegible y la vacía NO entran como
    # trabajo científico pendiente.
    assert len(filas) == 3
    assert {fila.source_row_index for fila in filas} == {0, 1, 2}
    corrida = await entorno.corrida(run_id)
    # Pero su cantidad no desaparece: el denominador sigue siendo el del archivo.
    assert corrida.total_rows == 5
    assert corrida.eligible_rows == 3


@rdkit_available
@pytest.mark.asyncio
async def test_usa_los_canonical_smiles_congelados_y_no_reparsea_el_archivo(entorno, evaluador, monkeypatch):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    # Si algo intentara releer el archivo, esto lo delataría.
    from services.cohort import parser as parser_mod

    def _prohibido(*args, **kwargs):
        raise AssertionError("La ejecución NO puede reparsear el archivo de la cohorte.")

    monkeypatch.setattr(parser_mod, "read_cohort_file", _prohibido)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    filas = await entorno.filas(run_id)
    congelados = {
        fila["row_index"]: fila["canonical_smiles"]
        for fila in cohorte["preflight"]["rows"]
        if fila["eligibility"] == "eligible"
    }
    for fila in filas:
        assert fila.canonical_smiles == congelados[fila.source_row_index]
    # Y lo que se mandó al evaluador fue exactamente eso.
    assert set(evaluador.llamadas) <= set(congelados.values())


@rdkit_available
@pytest.mark.asyncio
async def test_la_configuracion_es_comun_a_todas_las_filas(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    corrida = await entorno.corrida(run_id)
    config = corrida.effective_config_json
    assert config["grid_center"] == [10.0, 11.0, 12.0]
    assert config["grid_size"] == [22.0, 22.0, 22.0]
    assert config["grid_origin"] == "cohorte"
    assert config["exhaustiveness"] == 8
    assert config["num_poses"] == 5
    assert config["seed"] == 42


def test_semilla_omitida_se_congela_como_la_semilla_real_del_motor(monkeypatch):
    monkeypatch.setattr(ex.get_settings(), "vina_seed", 73)
    study = {
        **STUDY,
        "config": {k: v for k, v in STUDY["config"].items() if k != "seed"},
    }

    config = ex.resolve_effective_config(study, None)

    assert config.seed == 73


@pytest.mark.asyncio
async def test_evaluador_entrega_la_semilla_efectiva_al_pipeline(monkeypatch):
    recibido = {}

    async def _pipeline(**kwargs):
        recibido.update(kwargs)
        return {"molecule_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4())}

    monkeypatch.setattr("services.pipeline.runner.run_pipeline", _pipeline)
    await ex._evaluate_one(
        canonical_smiles=ASPIRINA,
        molecule_name="aspirina",
        receptor=ex.ReceptorProvenance(
            pdb_id="7E2Y",
            chain="R",
            prepared_sha256="sha256:" + "a" * 64,
            prepared_size_bytes=10,
            prepared_object="targets/7E2Y/prepared.pdbqt",
            source_sha256=None,
            catalog_target_id=None,
            prepared_bytes=b"RECEPTOR\n",
        ),
        config=_config(seed=73),
        user_id=None,
    )

    assert recibido["stage_params"]["docking"]["seed"] == 73
    assert recibido["pipeline_config"]["stage_params"]["docking"]["seed"] == 73


@rdkit_available
@pytest.mark.asyncio
async def test_la_caja_omitida_se_resuelve_del_catalogo_una_sola_vez(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    sin_caja = {
        **STUDY,
        "config": {k: v for k, v in STUDY["config"].items() if k not in ("grid_center", "grid_size")},
    }
    cohorte = _congelar(client, study=sin_caja)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    config = (await entorno.corrida(run_id)).effective_config_json
    assert config["grid_center"] == [1.0, 2.0, 3.0]
    assert config["grid_size"] == [20.0, 20.0, 20.0]
    # Se declara de dónde salió: el lector no tiene que adivinarlo.
    assert config["grid_origin"] == "catalogo"


@rdkit_available
@pytest.mark.asyncio
async def test_el_receptor_preparado_se_congela_por_su_hash(entorno, evaluador):
    await entorno.crear_target()
    contenido = entorno.preparar_receptor(contenido=b"ATOM  receptor preparado v1\n")
    client = entorno.app()
    cohorte = _congelar(client)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    procedencia = (await entorno.corrida(run_id)).receptor_provenance_json
    assert procedencia["pdb_id"] == "7E2Y"
    assert procedencia["prepared_sha256"] == ex._sha256(contenido)
    assert procedencia["prepared_size_bytes"] == len(contenido)
    # Nombre lógico del objeto, no una ruta del disco de nadie.
    assert procedencia["prepared_object"] == "targets/7E2Y/prepared.pdbqt"
    assert ":" not in procedencia["prepared_object"]


@rdkit_available
@pytest.mark.asyncio
async def test_el_endpoint_encola_la_ejecucion_despues_de_persistir(entorno, evaluador, monkeypatch):
    """
    El encolado ocurre DESPUÉS del commit, no antes.

    El espía abre una sesión NUEVA en el momento del encolado: si la corrida y
    sus filas no estuvieran confirmadas, no las vería — que es exactamente lo
    que le pasaría al ejecutor real, que también abre la suya.
    """
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    encolados: list[tuple] = []

    async def _espia(run_id, *, workers):
        # Cuando esto corre, la corrida TIENE que estar visible desde otra sesión.
        async with entorno.factory() as session:
            corrida = await session.get(CohortRunORM, run_id)
            filas = (
                await session.execute(
                    select(CohortRunRowORM).where(CohortRunRowORM.run_id == run_id)
                )
            ).scalars().all()
        encolados.append((run_id, workers, corrida is not None, len(filas)))

    monkeypatch.setattr(run_repo, "schedule", _espia)

    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs", params={"workers": 3})

    assert respuesta.status_code == 202
    assert len(encolados) == 1
    run_id, workers, existia, n_filas = encolados[0]
    assert str(run_id) == respuesta.json()["run_id"]
    assert workers == 3
    # Persistida ANTES de encolar: la corrida y sus 3 filas ya estaban en disco.
    assert existia is True
    assert n_filas == 3


# ── 5. Preparación automática del receptor ──────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_receptor_ausente_se_prepara_una_vez_antes_de_abrir(
    entorno, evaluador, monkeypatch
):
    await entorno.crear_target()
    llamadas = []

    async def _preparar(**kwargs):
        llamadas.append(kwargs)
        entorno.preparar_receptor(contenido=b"ATOM   PREPARADO AUTOMATICO\n")
        return "targets/7E2Y/prepared.pdbqt"

    monkeypatch.setattr("services.docking.preparer.prepare_target", _preparar)
    client = entorno.app()
    cohorte = _congelar(client)

    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")

    assert respuesta.status_code == 202
    assert len(llamadas) == 1
    assert llamadas[0]["center"] == (10.0, 11.0, 12.0)
    corrida = await entorno.corrida(respuesta.json()["run_id"])
    assert corrida.receptor_provenance_json["prepared_sha256"] == ex._sha256(
        b"ATOM   PREPARADO AUTOMATICO\n"
    )


@rdkit_available
@pytest.mark.asyncio
async def test_fallo_de_preparacion_es_409_y_cero_corrida(
    entorno, evaluador, monkeypatch
):
    await entorno.crear_target()

    async def _preparar(**_kwargs):
        raise RuntimeError("Meeko no pudo preparar el receptor")

    monkeypatch.setattr("services.docking.preparer.prepare_target", _preparar)
    client = entorno.app()
    cohorte = _congelar(client)

    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["code"] == ex.BLOQUEO_RECEPTOR_AUSENTE
    async with entorno.factory() as session:
        assert (await session.execute(select(CohortRunORM))).first() is None
        assert (await session.execute(select(CohortRunRowORM))).first() is None


@rdkit_available
@pytest.mark.asyncio
async def test_sin_caja_resoluble_es_409_y_cero_corrida(entorno, evaluador):
    # Receptor preparado en disco pero AUSENTE del catálogo: es el caso real de
    # un PDB auto-ingerido que nadie ha calibrado. Sin caja declarada y sin
    # catálogo del que sacarla, no hay región que acoplar.
    entorno.preparar_receptor()
    client = entorno.app()
    sin_caja = {
        **STUDY,
        "config": {k: v for k, v in STUDY["config"].items() if k not in ("grid_center", "grid_size")},
    }
    cohorte = _congelar(client, study=sin_caja)

    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["code"] == ex.BLOQUEO_CAJA_NO_RESOLUBLE
    async with entorno.factory() as session:
        assert (await session.execute(select(CohortRunORM))).first() is None


# ── 6. Atomicidad ────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_corrida_y_filas_se_crean_en_una_transaccion(entorno, evaluador, monkeypatch):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    llamadas = {"n": 0}
    real = db_mod.flush_with_retry

    async def _explota_en_el_segundo(session):
        llamadas["n"] += 1
        if llamadas["n"] >= 2:  # la corrida ya está; las filas no
            raise RuntimeError("disco lleno al insertar las filas")
        await real(session)

    monkeypatch.setattr(db_mod, "flush_with_retry", _explota_en_el_segundo)

    with pytest.raises(RuntimeError):
        client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")

    monkeypatch.undo()
    # Ni corrida sin filas, ni filas sin corrida.
    async with entorno.factory() as session:
        assert (await session.execute(select(CohortRunORM))).first() is None
        assert (await session.execute(select(CohortRunRowORM))).first() is None


# ── 7. Duplicados ────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_un_duplicado_canonico_se_acopla_una_vez_y_reutiliza(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    # Dos moléculas únicas entre tres filas elegibles: un solo docking por
    # molécula.
    assert sorted(evaluador.llamadas) == sorted({"CC(=O)Oc1ccccc1C(=O)O", "CC(C)Cc1ccc(C(C)C(=O)O)cc1"})
    assert len(evaluador.llamadas) == 2

    filas = {fila.source_row_index: fila for fila in await entorno.filas(run_id)}
    assert filas[0].status == ex.ROW_COMPLETED
    assert filas[1].status == ex.ROW_COMPLETED
    duplicada = filas[2]
    assert duplicada.status == ex.ROW_DUPLICATE_REUSED
    assert duplicada.reused_from_row == 0
    # Hereda el resultado…
    assert duplicada.molecule_id == filas[0].molecule_id
    # …pero conserva SUS etiquetas: es otra fila del archivo.
    assert duplicada.active_label is True
    assert duplicada.control_role == "none"
    assert filas[0].control_role == "reference"
    # Y el duplicado NO desaparece del denominador declarado.
    corrida = await entorno.corrida(run_id)
    assert corrida.eligible_rows == 3


# ── 8, 9, 10. Contadores y estado final ──────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_todo_bien_termina_en_completed_con_sus_contadores(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    corrida = await entorno.corrida(run_id)
    assert corrida.status == ex.RUN_COMPLETED
    assert corrida.completed_rows == 3  # 2 acopladas + 1 reutilizada
    assert corrida.failed_rows == 0
    assert corrida.not_evaluated_rows == 0
    assert corrida.finished_at is not None

    detalle = client.get(f"/evaluation/cohort-runs/{run_id}").json()
    progreso = detalle["progress"]
    assert progreso["total_rows"] == 5
    assert progreso["eligible_rows"] == 3
    assert progreso["completed_rows"] == 2
    assert progreso["duplicate_reused_rows"] == 1
    assert progreso["pending_rows"] == 0


@rdkit_available
@pytest.mark.asyncio
async def test_un_fallo_aislado_deja_completed_with_exceptions(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    evaluador.respuestas["CC(C)Cc1ccc(C(C)C(=O)O)cc1"] = RuntimeError("el motor se cayó")

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    corrida = await entorno.corrida(run_id)
    # NO es una cohorte fallida: hay resultados buenos y se conservan.
    assert corrida.status == ex.RUN_COMPLETED_WITH_EXCEPTIONS
    assert corrida.failed_rows == 1
    filas = {fila.source_row_index: fila for fila in await entorno.filas(run_id)}
    assert filas[1].status == ex.ROW_FAILED
    assert filas[1].error_code == ex.ERROR_PIPELINE
    assert "el motor se cayó" in (filas[1].error_detail or "")
    # La excepción de una fila no canceló a las hermanas.
    assert filas[0].status == ex.ROW_COMPLETED
    assert filas[2].status == ex.ROW_DUPLICATE_REUSED


@rdkit_available
@pytest.mark.asyncio
async def test_una_molecula_no_evaluada_no_es_un_fallo(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    evaluador.respuestas["CC(C)Cc1ccc(C(C)C(=O)O)cc1"] = {
        "skipped": True,
        "reason": "el conformero no convergió",
    }

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    filas = {fila.source_row_index: fila for fila in await entorno.filas(run_id)}
    # `not_evaluated` NO es `failed`: que el motor no pudiera evaluarla no dice
    # nada sobre la molécula.
    assert filas[1].status == ex.ROW_NOT_EVALUATED
    assert filas[1].error_code == ex.ERROR_NO_EVALUADA
    corrida = await entorno.corrida(run_id)
    assert corrida.not_evaluated_rows == 1
    assert corrida.failed_rows == 0
    assert corrida.status == ex.RUN_COMPLETED_WITH_EXCEPTIONS


@rdkit_available
@pytest.mark.asyncio
async def test_sin_ningun_resultado_util_la_corrida_es_failed(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    for smiles in ("CC(=O)Oc1ccccc1C(=O)O", "CC(C)Cc1ccc(C(C)C(=O)O)cc1"):
        evaluador.respuestas[smiles] = RuntimeError("motor caído")

    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    corrida = await entorno.corrida(run_id)
    assert corrida.status == ex.RUN_FAILED
    filas = {fila.source_row_index: fila for fila in await entorno.filas(run_id)}
    # La duplicada tampoco se cuela por la puerta de atrás: su ejecutora no
    # produjo nada y se declara con el mismo motivo.
    assert filas[2].status == ex.ROW_FAILED
    assert filas[2].error_code == ex.ERROR_SIN_RESULTADO


def test_el_estado_final_se_decide_en_un_solo_sitio():
    assert ex.decide_run_status(completed=3, failed=0, not_evaluated=0, cancelled=0, cancel_requested=False) == ex.RUN_COMPLETED
    assert ex.decide_run_status(completed=2, failed=1, not_evaluated=0, cancelled=0, cancel_requested=False) == ex.RUN_COMPLETED_WITH_EXCEPTIONS
    assert ex.decide_run_status(completed=2, failed=0, not_evaluated=1, cancelled=0, cancel_requested=False) == ex.RUN_COMPLETED_WITH_EXCEPTIONS
    assert ex.decide_run_status(completed=0, failed=2, not_evaluated=0, cancelled=0, cancel_requested=False) == ex.RUN_FAILED
    assert ex.decide_run_status(completed=1, failed=0, not_evaluated=0, cancelled=2, cancel_requested=True) == ex.RUN_CANCELLED


# ── 11 y 12. Reinicio y reanudación ──────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_arranque_convierte_running_en_interrupted_y_recuenta(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    # Se simula un cierre a mitad: la corrida vuelve a `running` con una fila
    # acoplando y otra sin empezar. Es lo que un `kill -9` deja en disco.
    async with entorno.factory() as session:
        corrida = await session.get(CohortRunORM, uuid.UUID(run_id))
        corrida.status = ex.RUN_RUNNING
        corrida.finished_at = None
        corrida.completed_rows = 99  # contador mentiroso, a propósito
        filas = (
            await session.execute(
                select(CohortRunRowORM).where(CohortRunRowORM.run_id == uuid.UUID(run_id))
            )
        ).scalars().all()
        filas[1].status = ex.ROW_RUNNING
        filas[2].status = ex.ROW_PENDING
        await session.commit()

    reconciliadas = await run_repo.reconcile_interrupted_runs()

    assert reconciliadas == 1
    corrida = await entorno.corrida(run_id)
    # Ninguna corrida finge que sigue.
    assert corrida.status == ex.RUN_INTERRUPTED
    assert "se cerró" in (corrida.last_error or "")
    filas = {fila.source_row_index: fila for fila in await entorno.filas(run_id)}
    assert filas[1].status == ex.ROW_INTERRUPTED
    assert filas[0].status == ex.ROW_COMPLETED  # lo terminado se conserva
    # Y los contadores se recalculan desde las filas: el 99 no sobrevive.
    assert corrida.completed_rows == 1


@rdkit_available
@pytest.mark.asyncio
async def test_la_corrida_sobrevive_a_tirar_y_recrear_el_engine(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])
    antes = client.get(f"/evaluation/cohort-runs/{run_id}").json()

    await entorno.reiniciar()

    despues = entorno.app().get(f"/evaluation/cohort-runs/{run_id}").json()
    assert despues["run_fingerprint"] == antes["run_fingerprint"]
    assert despues["effective_config"] == antes["effective_config"]
    assert despues["receptor_provenance"] == antes["receptor_provenance"]
    assert [f["status"] for f in despues["rows"]] == [f["status"] for f in antes["rows"]]


@rdkit_available
@pytest.mark.asyncio
async def test_resume_no_repite_las_filas_completed(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    # Primera pasada: el ibuprofeno falla.
    evaluador.respuestas["CC(C)Cc1ccc(C(C)C(=O)O)cc1"] = RuntimeError("caída puntual")
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])
    assert (await entorno.corrida(run_id)).status == ex.RUN_COMPLETED_WITH_EXCEPTIONS

    # Se simula que esa fila quedó interrumpida (no fallida) y se reanuda.
    async with entorno.factory() as session:
        fila = await session.scalar(
            select(CohortRunRowORM).where(
                CohortRunRowORM.run_id == uuid.UUID(run_id),
                CohortRunRowORM.source_row_index == 1,
            )
        )
        fila.status = ex.ROW_INTERRUPTED
        await session.commit()

    evaluador.respuestas.clear()
    evaluador.llamadas.clear()

    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/resume")
    assert respuesta.status_code == 202
    await run_repo.execute_run(uuid.UUID(run_id), workers=2)

    # SÓLO se reintentó la interrumpida. La aspirina, ya completada, no se
    # volvió a acoplar.
    assert evaluador.llamadas == ["CC(C)Cc1ccc(C(C)C(=O)O)cc1"]
    corrida = await entorno.corrida(run_id)
    assert corrida.status == ex.RUN_COMPLETED


@rdkit_available
@pytest.mark.asyncio
async def test_resume_rechaza_una_corrida_que_no_quedo_a_medias(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/resume")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["status"] == ex.RUN_COMPLETED


# ── 13. Cancelación ──────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_cancelar_no_inicia_filas_nuevas_y_conserva_lo_terminado(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    # Se abre la corrida SIN dejar que se ejecute, y se cancela antes.
    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")
    run_id = respuesta.json()["run_id"]
    run_repo._TAREAS.clear()  # la tarea de fondo no llegó a correr

    cancelada = client.post(f"/evaluation/cohort-runs/{run_id}/cancel")

    assert cancelada.status_code == 200
    assert cancelada.json()["cancel_requested"] is True
    assert cancelada.json()["status"] == ex.RUN_CANCELLED

    # Ahora se deja correr al ejecutor: no debe iniciar NINGUNA fila.
    await run_repo.execute_run(uuid.UUID(run_id), workers=2)

    assert evaluador.llamadas == []
    filas = await entorno.filas(run_id)
    assert all(fila.status == ex.ROW_CANCELLED for fila in filas)
    assert (await entorno.corrida(run_id)).status == ex.RUN_CANCELLED


# ── 14 y 15. Concurrencia y propiedad ────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_dos_corridas_activas_de_la_misma_cohorte_es_409(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    primera = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")
    run_repo._TAREAS.clear()  # se deja la corrida `queued` en disco
    segunda = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")

    assert primera.status_code == 202
    assert segunda.status_code == 409
    detalle = segunda.json()["detail"]
    assert detalle["code"] == ex.BLOQUEO_CORRIDA_ACTIVA
    assert detalle["run_id"] == primera.json()["run_id"]
    async with entorno.factory() as session:
        corridas = (await session.execute(select(CohortRunORM))).scalars().all()
    assert len(corridas) == 1


@rdkit_available
@pytest.mark.asyncio
async def test_una_corrida_ajena_no_existe_para_quien_pregunta(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    ana = await entorno.crear_usuario("ana")
    bruno = await entorno.crear_usuario("bruno")

    cliente_ana = entorno.app(ana)
    cohorte = _congelar(cliente_ana)
    _, run_id = await _abrir_y_esperar(entorno, cliente_ana, cohorte["id"])

    cliente_bruno = entorno.app(bruno)
    assert cliente_bruno.get(f"/evaluation/cohort-runs/{run_id}").status_code == 404
    assert cliente_bruno.get(f"/evaluation/cohorts/{cohorte['id']}/runs/latest").status_code == 404
    assert cliente_bruno.post(f"/evaluation/cohort-runs/{run_id}/cancel").status_code == 404
    assert cliente_bruno.post(f"/evaluation/cohort-runs/{run_id}/resume").status_code == 404
    # Y no puede abrir corridas sobre una cohorte que no es suya.
    assert cliente_bruno.post(f"/evaluation/cohorts/{cohorte['id']}/runs").status_code == 404
    assert cliente_ana.get(f"/evaluation/cohort-runs/{run_id}").status_code == 200
    ultima = cliente_ana.get(f"/evaluation/cohorts/{cohorte['id']}/runs/latest")
    assert ultima.status_code == 200
    assert ultima.json()["id"] == run_id


# ── 16 y 17. Run fingerprint ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("engine", "setting_name", "configured_path"),
    [
        ("vina", "vina_executable_path", "tools/vina/vina.exe"),
        ("qvina2", "qvina2_executable_path", "tools/qvina2/qvina2.exe"),
    ],
)
def test_version_del_motor_usa_la_ruta_configurada(
    monkeypatch, engine, setting_name, configured_path
):
    from services.docking import vina_service

    settings = type(
        "Settings",
        (),
        {
            "vina_executable_path": "otra-ruta-vina",
            "qvina2_executable_path": "otra-ruta-qvina2",
            setting_name: configured_path,
        },
    )()
    resolved_paths = []

    monkeypatch.setattr(ex, "get_settings", lambda: settings)
    monkeypatch.setattr(
        vina_service,
        "_resolve_executable",
        lambda path: resolved_paths.append(path) or f"resolved/{engine}",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="AutoDock Vina 1.2.7\n", stderr=""
        ),
    )

    assert ex._engine_version(engine) == "AutoDock Vina 1.2.7"
    assert resolved_paths == [configured_path]


def _config(**over) -> ex.EffectiveConfig:
    base = {
        "grid_center": (10.0, 11.0, 12.0),
        "grid_size": (22.0, 22.0, 22.0),
        "grid_origin": "cohorte",
        "docking_engine": "vina",
        "engine_version": "AutoDock Vina 1.2.5",
        "exhaustiveness": 8,
        "num_poses": 5,
        "seed": 42,
    }
    base.update(over)
    return ex.EffectiveConfig(**base)  # type: ignore[arg-type]


def _receptor(**over) -> ex.ReceptorProvenance:
    base = {
        "pdb_id": "7E2Y",
        "chain": "A",
        "prepared_sha256": "sha256:" + "a" * 64,
        "prepared_size_bytes": 100,
        "prepared_object": "targets/7E2Y/prepared.pdbqt",
        "source_sha256": None,
        "catalog_target_id": None,
        "prepared_bytes": b"RECEPTOR PDBQT CONGELADO",
    }
    base.update(over)
    return ex.ReceptorProvenance(**base)  # type: ignore[arg-type]


def test_el_run_fingerprint_es_determinista():
    args = {"cohort_fingerprint": "sha256:" + "1" * 64, "config": _config(), "receptor": _receptor()}
    assert ex.run_fingerprint(**args) == ex.run_fingerprint(**args)
    assert ex.run_fingerprint(**args).startswith("sha256:")


@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"cohort_fingerprint": "sha256:" + "2" * 64}, id="cohorte"),
        pytest.param({"config": _config(grid_center=(1.0, 2.0, 3.0))}, id="caja"),
        pytest.param({"config": _config(exhaustiveness=16)}, id="exhaustividad"),
        pytest.param({"config": _config(num_poses=9)}, id="poses"),
        pytest.param({"config": _config(seed=7)}, id="semilla"),
        pytest.param({"config": _config(docking_engine="qvina2")}, id="motor"),
        pytest.param({"config": _config(engine_version="AutoDock Vina 1.2.7")}, id="version-motor"),
        pytest.param({"receptor": _receptor(prepared_sha256="sha256:" + "b" * 64)}, id="receptor-repreparado"),
    ],
)
def test_el_run_fingerprint_cambia_con_el_como(cambio):
    base = {"cohort_fingerprint": "sha256:" + "1" * 64, "config": _config(), "receptor": _receptor()}
    assert ex.run_fingerprint(**{**base, **cambio}) != ex.run_fingerprint(**base)


def test_los_workers_no_entran_en_el_run_fingerprint():
    """El paralelismo cambia cuánto tarda, no qué se calcula."""
    documento = ex.canonical_run_document(
        cohort_fingerprint="sha256:" + "1" * 64, config=_config(), receptor=_receptor()
    )
    for prohibido in ("worker", "num_workers", "created_at", "user", "status", "started"):
        assert prohibido not in documento

    assert ex.clamp_workers(99) == ex.MAX_RUN_WORKERS
    assert ex.clamp_workers(0) == 1
    assert ex.clamp_workers(None) == ex.DEFAULT_RUN_WORKERS


@rdkit_available
@pytest.mark.asyncio
async def test_dos_corridas_con_distinto_paralelismo_comparten_run_fingerprint(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    _, primera = await _abrir_y_esperar(entorno, client, cohorte["id"], workers=1)
    _, segunda = await _abrir_y_esperar(entorno, client, cohorte["id"], workers=4)

    una = await entorno.corrida(primera)
    otra = await entorno.corrida(segunda)
    assert una.run_fingerprint == otra.run_fingerprint
    assert una.id != otra.id


# ── 18. Nada de Early Exit, ML/GNN ni scores ─────────────────────────


def test_la_ejecucion_no_pasa_por_early_exit_ni_pide_gnn():
    """
    Comprobación estática del contrato de etapas.

    El Early Exit vive en la rama HEREDADA de `_run_full_evaluation_async`; la
    ejecución de cohortes entra por `run_pipeline` con las etapas explícitas y
    nunca la toca.
    """
    import inspect

    fuente = inspect.getsource(ex._evaluate_one)
    assert "run_pipeline" in fuente
    assert "_run_full_evaluation_async" not in fuente
    assert "predict_early_exit" not in fuente
    assert '"run_admet_ai": False' in fuente
    assert "required_stage_ids=set(COHORT_RUN_STAGES)" in fuente
    assert "prepared_receptor_bytes=receptor.prepared_bytes" in fuente

    assert "clgnn" not in ex.COHORT_RUN_STAGES
    assert "openmm" not in ex.COHORT_RUN_STAGES
    assert "selectivity" not in ex.COHORT_RUN_STAGES
    assert "xgb" not in ex.COHORT_RUN_STAGES


@rdkit_available
@pytest.mark.asyncio
async def test_la_corrida_no_publica_ningun_score(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    plano = json.dumps(client.get(f"/evaluation/cohort-runs/{run_id}").json()).lower()

    for prohibido in ("total_score", "affinity", "ranking", "enrichment", "roc", "auc", "ef_"):
        assert prohibido not in plano


# ── La cohorte congelada no se toca ──────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_ejecutar_no_modifica_la_cohorte_congelada(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    antes = client.get(f"/evaluation/cohorts/{cohorte['id']}").json()

    await _abrir_y_esperar(entorno, client, cohorte["id"])

    despues = client.get(f"/evaluation/cohorts/{cohorte['id']}").json()
    assert despues == antes
    async with entorno.factory() as session:
        fila = await session.get(CohortORM, uuid.UUID(cohorte["id"]))
        assert fila.status == "ready"


# ── 19 y 20. Legado y migración ──────────────────────────────────────


def test_el_batch_historico_sigue_publicado():
    from fastapi.routing import APIRoute

    from api.main import app

    rutas = {
        (metodo, ruta.path)
        for ruta in app.routes
        if isinstance(ruta, APIRoute)
        for metodo in ruta.methods
        if metodo not in {"HEAD", "OPTIONS"}
    }
    for esperada in [
        ("POST", "/evaluation/batch"),
        ("GET", "/evaluation/batch/{batch_id}"),
        ("GET", "/evaluation/batch/{batch_id}/export"),
        ("GET", "/evaluation/batch/{batch_id}/csv"),
        ("POST", "/evaluation/cohorts/{cohort_id}/runs"),
        ("GET", "/evaluation/cohort-runs/{run_id}"),
        ("POST", "/evaluation/cohort-runs/{run_id}/resume"),
        ("POST", "/evaluation/cohort-runs/{run_id}/cancel"),
    ]:
        assert esperada in rutas, esperada


def test_la_migracion_es_aditiva_sobre_una_base_existente(tmp_path):
    """
    Una DB v4 —con cohortes ya guardadas— recibe las tablas nuevas sin perder nada.

    Se construye a mano el esquema anterior, se inserta una cohorte, y se pasa
    `create_all`: las tablas de 5C aparecen y la fila de 5B sigue ahí.
    """
    import sqlite3

    from sqlalchemy import create_engine

    from core.models import Base as B

    db_path = tmp_path / "v4.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE cohorts (id TEXT PRIMARY KEY, schema_version INTEGER, name TEXT, "
            "status TEXT, cohort_fingerprint TEXT, source_filename TEXT, source_content_type TEXT, "
            "source_sha256 TEXT, source_bytes BLOB, source_size_bytes INTEGER, "
            "normalized_study_json TEXT, preflight_snapshot_json TEXT, provenance_json TEXT, "
            "user_id TEXT, created_at TEXT)"
        )
        conn.execute("INSERT INTO users (id) VALUES ('u1')")
        conn.execute(
            "INSERT INTO cohorts (id, name, status, cohort_fingerprint, user_id) "
            "VALUES ('c1', 'previa', 'ready', 'sha256:x', 'u1')"
        )

    engine = create_engine(f"sqlite:///{db_path}")
    B.metadata.create_all(engine)
    engine.dispose()

    with sqlite3.connect(db_path) as conn:
        tablas = {
            fila[0]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        cohortes = conn.execute("SELECT name, status FROM cohorts").fetchall()

    assert "cohort_runs" in tablas
    assert "cohort_run_rows" in tablas
    # Y la cohorte de 5B sigue exactamente como estaba.
    assert cohortes == [("previa", "ready")]


@rdkit_available
@pytest.mark.asyncio
async def test_una_fila_aparece_una_sola_vez_por_corrida(entorno, evaluador):
    """La restricción `unique(run_id, source_row_index)` existe en la base."""
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    from sqlalchemy.exc import IntegrityError

    async with entorno.factory() as session:
        session.add(
            CohortRunRowORM(
                id=uuid.uuid4(),
                run_id=uuid.UUID(run_id),
                source_row_index=0,  # ya existe
                canonical_smiles=ASPIRINA,
                control_role="none",
                status=ex.ROW_PENDING,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
