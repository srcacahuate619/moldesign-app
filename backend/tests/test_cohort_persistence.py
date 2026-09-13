"""
Cohortes congeladas: durabilidad, inmutabilidad y aislamiento.

Estas pruebas usan una **base SQLite de verdad** en `tmp_path`, no una sesión
falsa. No es rigor decorativo: lo que este sprint promete es que la cohorte
sobrevive al reinicio, y eso no se puede afirmar contra un diccionario en
memoria. La prueba de supervivencia tira el engine, crea otro apuntando al
mismo archivo, y vuelve a leer.

Lo que protegen, en orden de gravedad:

1. **El servidor no se fía del cliente.** El preflight se recalcula siempre
   desde el archivo y el estudio. Un `expected_fingerprint` que no cuadra es un
   409 y CERO escrituras: congelar una cohorte distinta de la que se enseñó
   produciría un registro que afirma describir algo que no describe.

2. **Lo congelado no se toca.** No hay PATCH, no hay PUT, no hay DELETE. Ni
   receptor, ni configuración, ni filas, ni fingerprint cambian nunca.

3. **Nada se pierde por el camino.** El archivo se guarda byte a byte con su
   SHA-256, y el snapshot conserva las filas inválidas y las duplicadas.

4. **Una cohorte ajena no existe.** Ni siquiera se confirma que su
   identificador exista.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from api.dependencies import get_current_user_optional
from api.routers import evaluation_cohorts as router_mod
from core.database import get_db
from core.models import Base, CohortORM, UserORM
from services.cohort import repository as cohort_repo
from services.cohort import taxonomy as tx
from tests.conftest import rdkit_available

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"
#: La aspirina escrita al revés: mismo canónico, otro texto.
ASPIRINA_REESCRITA = "OC(=O)c1ccccc1OC(C)=O"

STUDY = {
    "schema_version": 1,
    "name": "Serie de anilinas · lote 3",
    "receptor": {"pdb_id": "7e2y", "chain": "a"},
    "config": {
        "docking_engine": "vina",
        "exhaustiveness": 8,
        "num_poses": 5,
        "grid_center": [10.0, 11.0, 12.0],
        "grid_size": [22.0, 22.0, 22.0],
        "seed": 42,
    },
}

#: Cinco filas: dos moléculas distintas, un duplicado canónico, una ilegible y
#: una vacía. Sirve para comprobar de una vez que nada se descarta al congelar.
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


# ── Infraestructura: una SQLite real, reiniciable ────────────────────


class _Entorno:
    """Base de datos de archivo + app mínima con el router de cohortes."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = None
        self.factory = None
        self.usuario: UserORM | None = None

    async def arrancar(self) -> None:
        """Abre el engine y crea el esquema. Idempotente: es un 'arranque'."""
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def apagar(self) -> None:
        """Cierra el engine. Lo que sobreviva a esto sobrevive de verdad."""
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self.factory = None

    async def reiniciar(self) -> None:
        await self.apagar()
        await self.arrancar()

    def app(self, usuario: UserORM | None = None) -> TestClient:
        """App con `get_db` apuntando a ESTA base y el usuario que se le diga."""
        aplicacion = FastAPI()
        aplicacion.include_router(router_mod.router, prefix="/evaluation")

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

    async def contar_cohortes(self) -> int:
        from sqlalchemy import func, select

        async with self.factory() as session:
            return int(await session.scalar(select(func.count()).select_from(CohortORM)))


@pytest_asyncio.fixture
async def entorno(tmp_path):
    """
    Base aislada por prueba.

    `reset_engine` antes y después: el singleton de `core.database` es global y
    una prueba que lo deje apuntando a otro sitio contaminaría a las siguientes.
    """
    await db_mod.reset_engine()
    env = _Entorno(tmp_path / "cohortes.db")
    await env.arrancar()
    try:
        yield env
    finally:
        await env.apagar()
        await db_mod.reset_engine()


def _crear(client: TestClient, *, contenido: bytes = CSV, study=None, fingerprint: str | None = None,
           nombre: str = "cohorte.csv"):
    """POST /evaluation/cohorts con la huella que devolvió el preflight."""
    definicion = json.dumps(study if study is not None else STUDY)
    if fingerprint is None:
        previo = client.post(
            "/evaluation/cohorts/preflight",
            files={"file": (nombre, contenido, "text/csv")},
            data={"study": definicion},
        )
        assert previo.status_code == 200, previo.text
        fingerprint = previo.json()["cohort_fingerprint"]
    return client.post(
        "/evaluation/cohorts",
        files={"file": (nombre, contenido, "text/csv")},
        data={"study": definicion, "expected_fingerprint": fingerprint},
    )


# ── 1. Crear cohorte ready ───────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_crear_cohorte_ready_devuelve_el_registro_congelado(entorno):
    client = entorno.app()

    respuesta = _crear(client)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["status"] == "ready"
    assert cuerpo["schema_version"] == 1
    assert cuerpo["name"] == "Serie de anilinas · lote 3"
    assert cuerpo["cohort_fingerprint"].startswith("sha256:")
    assert uuid.UUID(cuerpo["id"])

    # La definición normalizada viaja dentro del snapshot, una sola vez.
    assert cuerpo["preflight"]["normalized_study"]["receptor"] == {"pdb_id": "7E2Y", "chain": "A"}
    assert cuerpo["preflight"]["decision"] == "ready"
    assert cuerpo["preflight"]["summary"]["total_rows"] == 5

    # Procedencia: lo obtenible de verdad, nada inventado.
    procedencia = cuerpo["provenance"]
    assert procedencia["preflight_contract_version"] == 1
    assert procedencia["fingerprint_contract"] == "cohort_preflight/v1"
    assert procedencia["rdkit_version"]
    assert procedencia["created_at"]

    assert await entorno.contar_cohortes() == 1


@rdkit_available
@pytest.mark.asyncio
async def test_el_registro_no_lleva_los_bytes_del_archivo(entorno):
    cuerpo = _crear(entorno.app()).json()

    plano = json.dumps(cuerpo)
    assert "source_bytes" not in plano
    # Sí lleva con qué cotejarlo.
    assert cuerpo["source"]["sha256"]
    assert cuerpo["source"]["size_bytes"] == len(CSV)


# ── 2. Fingerprint distinto → 409 y cero escrituras ──────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_fingerprint_que_no_cuadra_es_409_y_no_escribe_nada(entorno):
    client = entorno.app()
    ajena = "sha256:" + "0" * 64

    respuesta = _crear(client, fingerprint=ajena)

    assert respuesta.status_code == 409
    detalle = respuesta.json()["detail"]
    assert detalle["expected_fingerprint"] == ajena
    assert detalle["computed_fingerprint"].startswith("sha256:")
    assert detalle["computed_fingerprint"] != ajena
    # Lo que importa: NADA se guardó.
    assert await entorno.contar_cohortes() == 0


@rdkit_available
@pytest.mark.asyncio
async def test_cambiar_el_archivo_tras_comprobar_no_congela_otra_cohorte(entorno):
    """El ataque real: comprobar un archivo y subir otro al aceptar."""
    client = entorno.app()
    previo = client.post(
        "/evaluation/cohorts/preflight",
        files={"file": ("cohorte.csv", CSV, "text/csv")},
        data={"study": json.dumps(STUDY)},
    )
    huella_enseñada = previo.json()["cohort_fingerprint"]

    otro_archivo = f"name,smiles\notra,{PARACETAMOL}\n".encode("utf-8")
    respuesta = _crear(client, contenido=otro_archivo, fingerprint=huella_enseñada)

    assert respuesta.status_code == 409
    assert await entorno.contar_cohortes() == 0


@rdkit_available
@pytest.mark.asyncio
async def test_un_resultado_de_preflight_enviado_por_el_cliente_no_se_acepta(entorno):
    """
    No hay forma de colar un veredicto: el campo no existe.

    El servidor sólo acepta archivo + estudio + huella, y recalcula. Mandar un
    `preflight` inventado es un campo desconocido en el formulario, y ni
    siquiera cambia el resultado.
    """
    client = entorno.app()
    mentira = json.dumps({"decision": "ready", "summary": {"eligible_rows": 500}})
    previo = client.post(
        "/evaluation/cohorts/preflight",
        files={"file": ("cohorte.csv", CSV, "text/csv")},
        data={"study": json.dumps(STUDY)},
    )
    huella = previo.json()["cohort_fingerprint"]

    respuesta = client.post(
        "/evaluation/cohorts",
        files={"file": ("cohorte.csv", CSV, "text/csv")},
        data={
            "study": json.dumps(STUDY),
            "expected_fingerprint": huella,
            "preflight": mentira,
        },
    )

    assert respuesta.status_code == 201
    # El recuento sale del archivo, no de lo que dijo el cliente.
    assert respuesta.json()["preflight"]["summary"]["eligible_rows"] == 3


@pytest.mark.asyncio
async def test_una_huella_con_otra_forma_se_rechaza_antes_de_leer_el_archivo(entorno):
    client = entorno.app()

    for invalida in ["", "   ", "no-es-una-huella", "sha256:abc", "md5:" + "a" * 64,
                     "sha256:" + "A" * 64]:
        respuesta = _crear(client, fingerprint=invalida)
        assert respuesta.status_code == 422, invalida

    assert await entorno.contar_cohortes() == 0


# ── 3. Preflight bloqueado → no persistir ────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_una_cohorte_bloqueada_no_se_congela(entorno):
    client = entorno.app()
    sin_elegibles = b"name,smiles\nrota,CCX\nvacia,\n"

    respuesta = _crear(client, contenido=sin_elegibles)

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    assert detalle["decision"] == "blocked"
    assert tx.SIN_MOLECULAS_ELEGIBLES in detalle["blockers"]
    assert await entorno.contar_cohortes() == 0


@rdkit_available
@pytest.mark.asyncio
async def test_un_archivo_ilegible_no_se_congela(entorno):
    respuesta = _crear(entorno.app(), contenido=b"smiles\n\xff\xfe\x00\x01")

    assert respuesta.status_code == 422
    assert tx.ARCHIVO_ILEGIBLE in respuesta.json()["detail"]["blockers"]
    assert await entorno.contar_cohortes() == 0


# ── 4. Archivo original y SHA-256 conservados ────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_archivo_se_guarda_byte_a_byte_con_su_sha256(entorno):
    cuerpo = _crear(entorno.app()).json()
    cohort_id = uuid.UUID(cuerpo["id"])

    async with entorno.factory() as session:
        owner = await cohort_repo.resolve_owner_id(session, None)
        guardado = await cohort_repo.load_cohort_source(
            session, cohort_id=cohort_id, owner_id=owner
        )

    assert guardado is not None
    contenido, nombre, sha = guardado
    assert contenido == CSV
    assert sha == cohort_repo.sha256_of(CSV)
    assert sha == cuerpo["source"]["sha256"]
    assert nombre == "cohorte.csv"


@rdkit_available
@pytest.mark.asyncio
async def test_el_nombre_del_archivo_se_reduce_a_su_base_sin_rutas(entorno):
    cuerpo = _crear(entorno.app(), nombre=r"C:\Users\ana\Escritorio\cohorte final.csv").json()

    guardado = cuerpo["source"]["filename"]
    # Ni el nombre de usuario de nadie, ni una ruta que se pueda seguir.
    assert guardado == "cohorte-final.csv"
    assert "ana" not in guardado
    assert "\\" not in guardado and "/" not in guardado


def test_el_saneado_del_nombre_no_deja_escapar_una_ruta():
    assert cohort_repo.sanitize_source_filename("../../etc/passwd") == "passwd"
    assert cohort_repo.sanitize_source_filename("/home/ana/c.csv") == "c.csv"
    assert cohort_repo.sanitize_source_filename(None) == "cohorte"
    assert cohort_repo.sanitize_source_filename("   ") == "cohorte"


# ── 5. El snapshot conserva filas inválidas y duplicadas ─────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_snapshot_congela_todas_las_filas_incluidas_las_que_no_corren(entorno):
    cuerpo = _crear(entorno.app()).json()
    filas = cuerpo["preflight"]["rows"]
    resumen = cuerpo["preflight"]["summary"]

    assert len(filas) == 5
    assert [fila["row_index"] for fila in filas] == [0, 1, 2, 3, 4]

    # El duplicado canónico sigue ahí y sigue apuntando a su original.
    assert filas[2]["duplicate_of_row"] == 0
    assert tx.SMILES_DUPLICADO in filas[2]["warnings"]

    # Las inválidas también, con su razón.
    assert filas[3]["reasons"] == [tx.SMILES_ILEGIBLE]
    assert filas[4]["reasons"] == [tx.SMILES_AUSENTE]

    # Y la cobertura conserva su denominador: 3 de 5.
    assert resumen["eligible_rows"] == 3
    assert resumen["invalid_rows"] == 2
    assert resumen["input_coverage"] == 0.6
    assert resumen["input_coverage_denominator"] == 5
    assert resumen["duplicate_rows"] == 1


# ── 6. Supervivencia al reinicio ─────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_la_cohorte_sobrevive_a_tirar_y_recrear_el_engine(entorno):
    creada = _crear(entorno.app()).json()
    cohort_id = creada["id"]

    # Se tira el engine entero y se abre otro contra el MISMO archivo de base.
    await entorno.reiniciar()

    recuperada = entorno.app().get(f"/evaluation/cohorts/{cohort_id}")

    assert recuperada.status_code == 200
    despues = recuperada.json()
    assert despues["cohort_fingerprint"] == creada["cohort_fingerprint"]
    assert despues["preflight"]["rows"] == creada["preflight"]["rows"]
    assert despues["preflight"]["summary"] == creada["preflight"]["summary"]
    assert despues["source"]["sha256"] == creada["source"]["sha256"]
    assert despues["provenance"] == creada["provenance"]


@rdkit_available
@pytest.mark.asyncio
async def test_el_archivo_tambien_sobrevive_al_reinicio(entorno):
    cohort_id = uuid.UUID(_crear(entorno.app()).json()["id"])

    await entorno.reiniciar()

    async with entorno.factory() as session:
        owner = await cohort_repo.resolve_owner_id(session, None)
        guardado = await cohort_repo.load_cohort_source(
            session, cohort_id=cohort_id, owner_id=owner
        )

    assert guardado is not None
    assert guardado[0] == CSV


# ── 7 y 8. Listado y detalle ─────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_listado_resume_sin_filas_y_sin_bytes(entorno):
    client = entorno.app()
    _crear(client)

    respuesta = client.get("/evaluation/cohorts")

    assert respuesta.status_code == 200
    listado = respuesta.json()
    assert len(listado) == 1
    fila = listado[0]

    # Lo justo para orientarse.
    assert fila["receptor_pdb_id"] == "7E2Y"
    assert fila["docking_engine"] == "vina"
    assert fila["summary"]["total_rows"] == 5
    assert fila["source"]["sha256"]

    # Y NADA más: ni filas, ni archivo, ni estudio completo.
    assert "rows" not in fila
    assert "preflight" not in fila
    assert "source_bytes" not in json.dumps(fila)


@rdkit_available
@pytest.mark.asyncio
async def test_el_listado_va_de_la_mas_reciente_a_la_mas_antigua(entorno):
    client = entorno.app()
    _crear(client, study={**STUDY, "name": "primera"})
    _crear(client, study={**STUDY, "name": "segunda"})

    nombres = [fila["name"] for fila in client.get("/evaluation/cohorts").json()]

    assert nombres == ["segunda", "primera"]


@rdkit_available
@pytest.mark.asyncio
async def test_el_detalle_trae_definicion_snapshot_resumen_y_filas(entorno):
    client = entorno.app()
    creada = _crear(client).json()

    detalle = client.get(f"/evaluation/cohorts/{creada['id']}").json()

    assert detalle["preflight"]["normalized_study"]["config"]["exhaustiveness"] == 8
    assert detalle["preflight"]["decision"] == "ready"
    assert detalle["preflight"]["summary"]["eligible_rows"] == 3
    assert len(detalle["preflight"]["rows"]) == 5
    assert detalle == creada


# ── 9. Cohorte inexistente ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_una_cohorte_inexistente_es_404(entorno):
    respuesta = entorno.app().get(f"/evaluation/cohorts/{uuid.uuid4()}")

    assert respuesta.status_code == 404


# ── 10. Aislamiento entre usuarios ───────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_una_cohorte_ajena_no_existe_para_quien_pregunta(entorno):
    ana = await entorno.crear_usuario("ana")
    bruno = await entorno.crear_usuario("bruno")

    de_ana = _crear(entorno.app(ana)).json()

    cliente_bruno = entorno.app(bruno)
    detalle = cliente_bruno.get(f"/evaluation/cohorts/{de_ana['id']}")

    # 404 y no 403: un 403 confirmaría que ese identificador existe.
    assert detalle.status_code == 404
    assert cliente_bruno.get("/evaluation/cohorts").json() == []
    # Y Ana la sigue viendo.
    assert entorno.app(ana).get(f"/evaluation/cohorts/{de_ana['id']}").status_code == 200


@rdkit_available
@pytest.mark.asyncio
async def test_la_sesion_anonima_no_ve_las_cohortes_de_una_cuenta(entorno):
    ana = await entorno.crear_usuario("ana")
    de_ana = _crear(entorno.app(ana)).json()

    anonimo = entorno.app(None)

    assert anonimo.get(f"/evaluation/cohorts/{de_ana['id']}").status_code == 404
    assert anonimo.get("/evaluation/cohorts").json() == []


# ── 11 y 12. Inmutabilidad y coexistencia ────────────────────────────


def test_no_existe_ninguna_ruta_que_edite_una_cohorte():
    """
    La inmutabilidad no se vigila: no se implementa el verbo que la rompería.

    Un PATCH que cambiara el receptor dejaría una cohorte cuyo fingerprint ya no
    describe su contenido, y el fingerprint es lo único que permite afirmar que
    lo ejecutado es lo que se aceptó.
    """
    from api.main import app
    from fastapi.routing import APIRoute

    verbos = {
        (metodo, ruta.path)
        for ruta in app.routes
        if isinstance(ruta, APIRoute)
        for metodo in ruta.methods
        if "cohort" in ruta.path
    }

    assert ("POST", "/evaluation/cohorts") in verbos
    assert ("GET", "/evaluation/cohorts") in verbos
    assert ("GET", "/evaluation/cohorts/{cohort_id}") in verbos
    for prohibido in ("PATCH", "PUT", "DELETE"):
        assert not [par for par in verbos if par[0] == prohibido], prohibido


@rdkit_available
@pytest.mark.asyncio
async def test_lo_congelado_no_cambia_aunque_se_vuelva_a_pedir(entorno):
    client = entorno.app()
    creada = _crear(client).json()

    primera = client.get(f"/evaluation/cohorts/{creada['id']}").json()
    segunda = client.get(f"/evaluation/cohorts/{creada['id']}").json()

    for campo in ("cohort_fingerprint", "schema_version", "name", "status", "created_at"):
        assert primera[campo] == creada[campo] == segunda[campo]
    assert primera["preflight"] == segunda["preflight"] == creada["preflight"]
    assert primera["source"] == segunda["source"]


@rdkit_available
@pytest.mark.asyncio
async def test_dos_cohortes_con_la_misma_huella_coexisten(entorno):
    client = entorno.app()

    primera = _crear(client)
    segunda = _crear(client)

    assert primera.status_code == 201
    assert segunda.status_code == 201
    a, b = primera.json(), segunda.json()
    # Misma ciencia, dos registros. No se deduplica en silencio: alguien creó
    # los dos a conciencia y retirarle uno sería decidir por él.
    assert a["cohort_fingerprint"] == b["cohort_fingerprint"]
    assert a["id"] != b["id"]
    assert await entorno.contar_cohortes() == 2
    assert len(client.get("/evaluation/cohorts").json()) == 2


@rdkit_available
@pytest.mark.asyncio
async def test_cambiar_la_configuracion_produce_otra_cohorte_no_una_edicion(entorno):
    client = entorno.app()
    original = _crear(client).json()

    otra_config = {**STUDY, "config": {**STUDY["config"], "exhaustiveness": 16}}
    modificada = _crear(client, study=otra_config).json()

    assert modificada["id"] != original["id"]
    assert modificada["cohort_fingerprint"] != original["cohort_fingerprint"]
    # La original sigue exactamente como estaba.
    vigente = client.get(f"/evaluation/cohorts/{original['id']}").json()
    assert vigente["preflight"]["normalized_study"]["config"]["exhaustiveness"] == 8
    assert vigente["cohort_fingerprint"] == original["cohort_fingerprint"]


# ── 13. Fallo transaccional ──────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_si_la_escritura_falla_no_queda_una_cohorte_a_medias(entorno, monkeypatch):
    """
    La atomicidad no es una promesa: es que sólo hay un `INSERT`.

    Se hace estallar el flush para comprobar que el `rollback` de la sesión deja
    la tabla como estaba, sin archivo huérfano ni fila sin snapshot.
    """
    from core import database as core_db

    def _explota(_session):
        raise RuntimeError("disco lleno a mitad de la escritura")

    monkeypatch.setattr(core_db, "flush_with_retry", _explota)

    client = entorno.app()
    with pytest.raises(RuntimeError):
        _crear(client)

    assert await entorno.contar_cohortes() == 0

    # Y la base sigue utilizable: la siguiente cohorte se crea con normalidad.
    monkeypatch.undo()
    assert _crear(entorno.app()).status_code == 201
    assert await entorno.contar_cohortes() == 1


# ── 14. Nada se ejecuta ──────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_congelar_una_cohorte_no_ejecuta_docking(entorno, monkeypatch):
    import services.docking.vina_service as vina

    def _prohibido(*args, **kwargs):
        raise AssertionError("Congelar una cohorte NO ejecuta docking.")

    monkeypatch.setattr(vina, "run_vina_docking", _prohibido)

    respuesta = _crear(entorno.app())

    assert respuesta.status_code == 201
    plano = json.dumps(respuesta.json()).lower()
    for prohibido in ("total_score", "affinity", "task_id", "batch_id", "ef_metrics"):
        assert prohibido not in plano


def test_el_paquete_de_cohortes_no_encola_ni_importa_docking():
    """
    Nada del camino de cohortes puede lanzar trabajo de fondo.

    Es una comprobación ESTÁTICA sobre el código, no un `monkeypatch` de
    `asyncio.create_task`: parchear esa función globalmente revienta la
    fontanería del propio banco de pruebas —SQLAlchemy cierra sus sesiones con
    ella—, así que el fallo no distinguiría entre «el endpoint encoló algo» y
    «el arnés cerró una sesión». Lo que sí se puede afirmar sin ambigüedad es
    que estos módulos ni siquiera mencionan el mecanismo.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    # Sólo el camino de COMPROBAR y CONGELAR. `execution.py` y `runs.py` son de
    # Sprint 5C y su trabajo es justamente ejecutar: encolan a propósito, con su
    # corrida ya persistida detrás. Mezclarlos aquí convertiría esta guardia en
    # una que hay que desactivar, que es como se pierden las guardias.
    congelacion = ("taxonomy.py", "schemas.py", "parser.py", "fingerprint.py",
                   "preflight.py", "repository.py", "__init__.py")
    fuentes = [
        *(
            raiz / "services" / "cohort" / nombre
            for nombre in congelacion
        ),
        raiz / "api" / "routers" / "evaluation_cohorts.py",
    ]

    prohibidos = ("create_task", "BackgroundTasks", "run_vina_docking", "total_score")
    for fuente in fuentes:
        texto = fuente.read_text(encoding="utf-8")
        # Se quitan los comentarios: estos archivos EXPLICAN por escrito que no
        # encolan nada, y buscar el nombre en el texto crudo encontraría la
        # explicación de su ausencia.
        codigo = re.sub(r"^\s*#.*$", "", texto, flags=re.MULTILINE)
        codigo = re.sub(r'"""[\s\S]*?"""', "", codigo)
        for prohibido in prohibidos:
            assert prohibido not in codigo, f"{fuente.name} menciona {prohibido}"


# ── Procedencia ──────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_la_procedencia_omite_lo_que_no_puede_leer_en_vez_de_inventarlo(entorno):
    cuerpo = _crear(entorno.app()).json()
    procedencia = cuerpo["provenance"]

    # Nada se rellena con una etiqueta que después se leería como un dato.
    for valor in procedencia.values():
        assert valor != "desconocida"
        assert valor != "unknown"
        assert valor != ""

    # Y lo que sí se puede leer, se lee del runtime.
    import rdkit

    assert procedencia["rdkit_version"] == rdkit.__version__


def test_una_version_ausente_no_se_fabrica(monkeypatch):
    """Si RDKit no se puede consultar, el campo se OMITE."""
    import builtins

    real = builtins.__import__

    def _sin_rdkit(name, *args, **kwargs):
        if name == "rdkit":
            raise ImportError("simulado")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _sin_rdkit)
    procedencia = cohort_repo.build_provenance(cohort_repo.utc_now())
    monkeypatch.undo()

    assert procedencia.rdkit_version is None
