"""CR-07 + CR-06 — Creación HTTP de propuestas e idempotencia (MolChat).

# El contrato que esta prueba fija

CR-07:
1. `POST /ai/proposals` crea una propuesta revisable sin lanzar nada: no
   llama a `registrar_corrida` y la respuesta trae identidad, huella,
   parámetros efectivos, resumen del preflight y caducidad.
2. Crear → leer (`GET`) → la huella coincide → aprobar lanza exactamente
   una evaluación → una segunda aprobación sin clave es rechazada.
3. Con bloqueantes técnicos, la creación responde 409 con el preflight
   completo y sin propuesta aprobable.
4. Una propuesta caducada no se aprueba; otra cuenta no la lee ni la aprueba.
5. Ningún `user_id` en el cuerpo tiene efecto (modelo cerrado).

CR-06:
6. Misma clave + mismos parámetros ⇒ la operación original (mismo
   `proposal_id`/`task_id`), sin segundo efecto.
7. Misma clave + parámetros distintos ⇒ 409 explícito.
8. Reconciliación: dada la clave, se recupera qué operación y qué trabajo
   existen, aunque la respuesta original se haya perdido.
9. Dos aprobaciones concurrentes con la misma clave lanzan un solo cálculo.

Sin Vina ni preflight real: el informe es un doble con la forma real y la
única puerta de registro es un espía, como en LUNA-05.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from services.evaluation import proposals as propuestas
from tests import test_sqlite_roundtrip as sqlite_fixtures

engine = sqlite_fixtures.engine
session_factory = sqlite_fixtures.session_factory

CUENTA = str(uuid.uuid4())
OTRA_CUENTA = str(uuid.uuid4())
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
HUELLA_PREFLIGHT = "sha256:" + "c" * 64
CUERPO = {"smiles": ASPIRINA, "target_pdb_id": "7E2Y", "chain": "A"}


class _Usuario:
    def __init__(self, uid: str):
        self.id = uuid.UUID(uid)


def _informe(*, bloqueos: list[str] | None = None) -> dict:
    return {
        "input_fingerprint": HUELLA_PREFLIGHT,
        "technical_blockers": list(bloqueos or []),
        "warnings": ["SIN_CALIBRACION"],
        "not_evaluated": ["TAUTOMERIA"],
        "receptor": {"pdb_id": "7E2Y", "chain": "A", "origin": "curado"},
        "ligand": {"canonical_smiles": ASPIRINA, "input_smiles": ASPIRINA},
        "effective_config": {
            "docking_engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 5,
            "conformers": 1,
            "seed": 42,
            "grid_center": [12.5, -3.0, 40.25],
            "grid_size": [22.5, 22.5, 22.5],
            "heteroatom_policy": {
                "waters": "eliminadas",
                "metals": "conservados_solo_whitelist",
                "organic_cofactors": "bloqueados_sin_plantilla_local",
            },
        },
        "controls": [],
    }


@pytest.fixture
def preflight(monkeypatch):
    estado = {"informe": _informe(), "llamadas": 0}

    async def _comprobar(**_kwargs):
        estado["llamadas"] += 1
        return estado["informe"]

    import api.routers.evaluation as router

    monkeypatch.setattr(router, "comprobar_preparacion", _comprobar)
    return estado


@pytest.fixture
def registro(monkeypatch):
    llamadas: list[dict] = []

    async def _registrar(**kwargs):
        llamadas.append(kwargs)
        from services.evaluation_submission import CorridaRegistrada

        return CorridaRegistrada(
            task_id=f"task-{len(llamadas)}",
            target_pdb_id=kwargs["data"].target_pdb_id,
            smiles_hash="sha-de-prueba",
            canonical_smiles=kwargs["data"].smiles,
        )

    import services.evaluation_submission as modulo

    monkeypatch.setattr(modulo, "registrar_corrida", _registrar)
    return llamadas


def _cliente(*, fabrica_sesiones=None, cuenta: str = CUENTA):
    """AsyncClient en el mismo bucle, con sesión y cuenta impuestas."""
    from api.dependencies import get_current_user
    from api.main import app
    from core.database import get_db

    if fabrica_sesiones is None:
        app.dependency_overrides[get_db] = lambda: None
    else:
        async def _db():
            async with fabrica_sesiones() as sesion:
                yield sesion

        app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: _Usuario(cuenta)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
def limpiar_overrides():
    yield
    from api.dependencies import get_current_user
    from api.main import app
    from core.database import get_db

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _cambiar_cuenta(cuenta: str) -> None:
    from api.dependencies import get_current_user
    from api.main import app

    app.dependency_overrides[get_current_user] = lambda: _Usuario(cuenta)


# ── CR-07: creación HTTP de propuestas ───────────────────────────────────


@pytest.mark.asyncio
async def test_crear_propuesta_no_lanza_nada(preflight, registro, limpiar_overrides):
    async with _cliente() as http:
        r = await http.post("/ai/proposals", json=CUERPO)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["proposal_id"] and cuerpo["proposal_id"] == cuerpo["id"]
    assert cuerpo["proposal_hash"].startswith("sha256:")
    assert cuerpo["proposal_hash"] == cuerpo["hash"]
    assert cuerpo["estado"] == "pendiente"
    efectivos = cuerpo["parametros_efectivos"]
    assert efectivos["motor"] == "vina"
    assert efectivos["exhaustividad"] == 8
    assert efectivos["poses"] == 5
    assert efectivos["semilla"] == 42
    assert efectivos["caja"]["centro"] == [12.5, -3.0, 40.25]
    assert cuerpo["preflight"] == {
        "technical_blockers": [],
        "warnings": ["SIN_CALIBRACION"],
        "not_evaluated": ["TAUTOMERIA"],
    }
    assert cuerpo["caduca_en"]
    assert registro == [], "crear la propuesta encoló una corrida"


@pytest.mark.asyncio
async def test_crear_leer_aprobar_y_segunda_aprobacion_rechazada(
    preflight, registro, limpiar_overrides
):
    async with _cliente() as http:
        creada = (await http.post("/ai/proposals", json=CUERPO)).json()
        leida = await http.get(f"/ai/proposals/{creada['proposal_id']}")
        assert leida.status_code == 200, leida.text
        assert leida.json()["proposal_hash"] == creada["proposal_hash"]

        aprobada = await http.post(
            f"/ai/proposals/{creada['proposal_id']}/approve",
            json={"proposal_hash": creada["proposal_hash"]},
        )
        assert aprobada.status_code == 200, aprobada.text
        assert aprobada.json()["task_id"] == "task-1"
        assert len(registro) == 1

        segunda = await http.post(
            f"/ai/proposals/{creada['proposal_id']}/approve",
            json={"proposal_hash": creada["proposal_hash"]},
        )
        assert segunda.status_code == 410
        assert len(registro) == 1, "la segunda aprobación lanzó otra corrida"


@pytest.mark.asyncio
async def test_crear_con_bloqueantes_devuelve_preflight_sin_propuesta(
    preflight, registro, limpiar_overrides
):
    preflight["informe"] = _informe(bloqueos=["RECEPTOR_NO_PREPARADO"])
    async with _cliente() as http:
        r = await http.post("/ai/proposals", json=CUERPO)
    assert r.status_code == 409, r.text
    detalle = r.json()["detail"]
    assert detalle["proposal_id"] is None
    assert detalle["preflight"]["technical_blockers"] == ["RECEPTOR_NO_PREPARADO"]
    assert registro == []


@pytest.mark.asyncio
async def test_propuesta_caducada_no_se_aprueba(preflight, registro, limpiar_overrides):
    from utils.cache import cache

    async with _cliente() as http:
        creada = (await http.post("/ai/proposals", json=CUERPO)).json()
        # La caducidad real es por TTL; borrar la clave la simula, como en LUNA-05.
        await cache.delete(propuestas._clave(creada["proposal_id"]))
        r = await http.post(
            f"/ai/proposals/{creada['proposal_id']}/approve",
            json={"proposal_hash": creada["proposal_hash"]},
        )
    assert r.status_code == 410
    assert registro == []


@pytest.mark.asyncio
async def test_otra_cuenta_no_lee_ni_aprueba(preflight, registro, limpiar_overrides):
    async with _cliente() as http:
        creada = (await http.post("/ai/proposals", json=CUERPO)).json()
        _cambiar_cuenta(OTRA_CUENTA)
        leida = await http.get(f"/ai/proposals/{creada['proposal_id']}")
        aprobada = await http.post(
            f"/ai/proposals/{creada['proposal_id']}/approve",
            json={"proposal_hash": creada["proposal_hash"]},
        )
    assert leida.status_code == 404
    assert aprobada.status_code == 404
    assert registro == []


@pytest.mark.asyncio
async def test_el_cuerpo_no_acepta_user_id(preflight, registro, limpiar_overrides):
    async with _cliente() as http:
        r = await http.post("/ai/proposals", json={**CUERPO, "user_id": OTRA_CUENTA})
    assert r.status_code == 422
    assert registro == []


@pytest.mark.asyncio
async def test_sin_sesion_no_se_crea_ni_se_reconcilia(preflight, registro, session_factory, limpiar_overrides):
    from api.main import app
    from core.database import get_db

    async def _db():
        async with session_factory() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        creada = await http.post("/ai/proposals", json=CUERPO)
        reconciliada = await http.get("/ai/idempotency/algo")
    assert creada.status_code in (401, 403)
    assert reconciliada.status_code in (401, 403)
    assert registro == []


# ── CR-06: idempotencia y reconciliación ─────────────────────────────────


@pytest.mark.asyncio
async def test_crear_con_clave_repite_la_propuesta_original(
    preflight, registro, session_factory, limpiar_overrides
):
    cabecera = {"Idempotency-Key": "crear-1"}
    async with _cliente(fabrica_sesiones=session_factory) as http:
        primera = await http.post("/ai/proposals", json=CUERPO, headers=cabecera)
        segunda = await http.post("/ai/proposals", json=CUERPO, headers=cabecera)
    assert primera.status_code == segunda.status_code == 201
    assert primera.json()["proposal_id"] == segunda.json()["proposal_id"]
    assert preflight["llamadas"] == 1, "el reintento repitió el trabajo de creación"
    assert registro == []


@pytest.mark.asyncio
async def test_misma_clave_con_otro_cuerpo_es_conflicto(
    preflight, registro, session_factory, limpiar_overrides
):
    cabecera = {"Idempotency-Key": "crear-2"}
    async with _cliente(fabrica_sesiones=session_factory) as http:
        primera = await http.post("/ai/proposals", json=CUERPO, headers=cabecera)
        conflicto = await http.post(
            "/ai/proposals", json={**CUERPO, "smiles": "CCO"}, headers=cabecera
        )
    assert primera.status_code == 201
    assert conflicto.status_code == 409


@pytest.mark.asyncio
async def test_aprobar_con_clave_recupera_el_task_original(
    preflight, registro, session_factory, limpiar_overrides
):
    cabecera = {"Idempotency-Key": "aprobar-1"}
    async with _cliente(fabrica_sesiones=session_factory) as http:
        creada = (await http.post("/ai/proposals", json=CUERPO)).json()
        url = f"/ai/proposals/{creada['proposal_id']}/approve"
        cuerpo = {"proposal_hash": creada["proposal_hash"]}
        primera = await http.post(url, json=cuerpo, headers=cabecera)
        # La respuesta se "pierde" y el agente reintenta con la misma clave:
        segunda = await http.post(url, json=cuerpo, headers=cabecera)
    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["task_id"] == segunda.json()["task_id"] == "task-1"
    assert len(registro) == 1, "el reintento lanzó una segunda evaluación"


@pytest.mark.asyncio
async def test_aprobaciones_concurrentes_con_clave_lanzan_una_sola(
    preflight, registro, session_factory, limpiar_overrides
):
    cabecera = {"Idempotency-Key": "aprobar-concurrente"}
    async with _cliente(fabrica_sesiones=session_factory) as http:
        creada = (await http.post("/ai/proposals", json=CUERPO)).json()
        url = f"/ai/proposals/{creada['proposal_id']}/approve"
        cuerpo = {"proposal_hash": creada["proposal_hash"]}
        respuestas = await asyncio.gather(
            http.post(url, json=cuerpo, headers=cabecera),
            http.post(url, json=cuerpo, headers=cabecera),
        )
    codigos = sorted(r.status_code for r in respuestas)
    assert codigos[0] == 200 and all(c in (200, 409) for c in codigos), codigos
    assert len(registro) == 1, "la concurrencia duplicó el cálculo"


@pytest.mark.asyncio
async def test_reconciliar_una_clave_cuenta_que_trabajo_existe(
    preflight, registro, session_factory, limpiar_overrides
):
    async with _cliente(fabrica_sesiones=session_factory) as http:
        creada = (
            await http.post(
                "/ai/proposals", json=CUERPO, headers={"Idempotency-Key": "op-crear"}
            )
        ).json()
        tras_crear = await http.get("/ai/idempotency/op-crear")
        assert tras_crear.status_code == 200, tras_crear.text
        vista = tras_crear.json()
        assert vista["operation"] == "crear_propuesta"
        assert vista["status"] == "COMPLETADA"
        assert vista["proposal_id"] == creada["proposal_id"]
        assert vista["task_id"] is None

        await http.post(
            f"/ai/proposals/{creada['proposal_id']}/approve",
            json={"proposal_hash": creada["proposal_hash"]},
            headers={"Idempotency-Key": "op-aprobar"},
        )
        tras_aprobar = (await http.get("/ai/idempotency/op-aprobar")).json()
        assert tras_aprobar["operation"] == "aprobar_propuesta"
        assert tras_aprobar["task_id"] == "task-1"

        desconocida = await http.get("/ai/idempotency/no-existe")
        assert desconocida.status_code == 404

        _cambiar_cuenta(OTRA_CUENTA)
        ajena = await http.get("/ai/idempotency/op-aprobar")
        assert ajena.status_code == 404, "una clave ajena debe ser indistinguible de ausente"


@pytest.mark.asyncio
async def test_el_servicio_distigue_en_curso_de_completada(session_factory):
    from services import idempotencia

    huella = idempotencia.huella_de_peticion({"smiles": ASPIRINA})
    async with session_factory() as db:
        assert await idempotencia.reclamar(
            db=db, user_id=CUENTA, clave="svc-1", operacion="crear_propuesta",
            request_hash=huella,
        ) is None
        with pytest.raises(idempotencia.IdempotenciaConflicto):
            await idempotencia.reclamar(
                db=db, user_id=CUENTA, clave="svc-1", operacion="crear_propuesta",
                request_hash=huella,
            )
        await idempotencia.completar(
            db=db, user_id=CUENTA, clave="svc-1",
            response={"proposal_id": "p-1"}, proposal_id="p-1",
        )
        previo = await idempotencia.reclamar(
            db=db, user_id=CUENTA, clave="svc-1", operacion="crear_propuesta",
            request_hash=huella,
        )
        assert previo is not None and previo.response_json == {"proposal_id": "p-1"}
        with pytest.raises(idempotencia.IdempotenciaConflicto):
            await idempotencia.reclamar(
                db=db, user_id=CUENTA, clave="svc-1", operacion="crear_propuesta",
                request_hash=idempotencia.huella_de_peticion({"smiles": "CCO"}),
            )
        vista = await idempotencia.reconciliar(db=db, user_id=CUENTA, clave="svc-1")
        assert vista["proposal_id"] == "p-1"
        assert await idempotencia.reconciliar(db=db, user_id=OTRA_CUENTA, clave="svc-1") is None
