"""MOLCHAT-INT-001 / D-08 — el chat lanza evaluaciones por la puerta de siempre.

`docking_tools.run_docking` importaba `run_single_evaluation` de
`services.docking.queue_handler`, una función que **no existe**. El `ImportError`
se capturaba y el chat contestaba «pipeline de docking no disponible en este
modo»: el motivo que el investigador leía no era el motivo real, y la
herramienta no llegaba a comprobar identidad, receptor ni preflight porque no
llegaba a nada.

D-08 lo resolvió por el eje científico, no por capacidad: MolChat evalúa «para
sacar datos exactos y precisos, para no inventar información». Eso fija tres
criterios, y son los que esta prueba vigila:

1. mismo camino que `/evaluation/submit` — identidad, preflight, persistencia y
   procedencia, no una función privada del pipeline;
2. en segundo plano y con estado visible — el turno no se bloquea ni finge que
   ya terminó;
3. el resultado se cita a su `task_id`, y si no existe el chat se abstiene en
   vez de rellenar con una estimación del modelo.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from services.ai.tools import docking_tools

CUENTA = str(uuid.uuid4())
OTRA_CUENTA = str(uuid.uuid4())
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


class _Usuario:
    def __init__(self, uid: str):
        self.id = uuid.UUID(uid)


class _SesionFalsa:
    """Sólo sabe devolver la cuenta que se le pidió."""

    def __init__(self, usuarios):
        self._usuarios = usuarios

    async def get(self, _modelo, uid):
        return self._usuarios.get(uid)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


@pytest.fixture
def sesion(monkeypatch):
    usuarios = {
        uuid.UUID(CUENTA): _Usuario(CUENTA),
        uuid.UUID(OTRA_CUENTA): _Usuario(OTRA_CUENTA),
    }

    import core.database as db_modulo

    monkeypatch.setattr(db_modulo, "get_db_session", lambda: _SesionFalsa(usuarios))
    return usuarios


@pytest.fixture
def registro(monkeypatch):
    """Espía de la única puerta de registro de corridas."""
    llamadas: list[dict] = []

    async def _registrar(**kwargs):
        llamadas.append(kwargs)
        from services.evaluation_submission import CorridaRegistrada

        return CorridaRegistrada(
            task_id="task-de-prueba",
            target_pdb_id=kwargs["data"].target_pdb_id,
            smiles_hash="sha-de-prueba",
            canonical_smiles=kwargs["data"].smiles,
        )

    import services.evaluation_submission as modulo

    monkeypatch.setattr(modulo, "registrar_corrida", _registrar)
    return llamadas


@pytest.fixture
def preflight(monkeypatch):
    """El informe que el servidor «calcula»; el contrato completo vive en
    `test_propuesta_de_docking_molchat.py`."""

    async def _comprobar(**_kwargs):
        return {
            "input_fingerprint": "sha256:" + "d" * 64,
            "technical_blockers": [],
            "receptor": {"pdb_id": "7E2Y", "chain": "A", "origin": "curado"},
            "ligand": {"canonical_smiles": ASPIRINA, "input_smiles": ASPIRINA},
            "effective_config": {
                "docking_engine": "vina", "exhaustiveness": 8, "num_poses": 5,
                "conformers": 1, "seed": 42,
                "grid_center": [0.0, 0.0, 0.0], "grid_size": [22.5, 22.5, 22.5],
                "heteroatom_policy": {},
            },
            "controls": [],
        }

    import api.routers.evaluation as router

    monkeypatch.setattr(router, "comprobar_preparacion", _comprobar)


@pytest.mark.asyncio
async def test_el_chat_propone_y_no_registra_la_corrida(sesion, registro, preflight):
    """LUNA-05. Antes `run_docking` registraba y encolaba en el mismo turno; ahora
    sólo PROPONE, y la corrida entra por `registrar_corrida` cuando el investigador
    la aprueba por otra puerta (`test_propuesta_de_docking_molchat.py`)."""
    texto = await docking_tools.run_docking(
        smiles=ASPIRINA, target_pdb="7E2Y", user_id=CUENTA
    )

    assert registro == [], "run_docking encoló una corrida sin aprobación humana"
    assert "todavía no lanzada" in texto.lower()
    assert "task-de-prueba" not in texto


@pytest.mark.asyncio
async def test_el_turno_no_finge_un_numero_ni_una_corrida(sesion, registro, preflight):
    """Criterio 3 de D-08, ahora desde la propuesta: ni afinidad ni `task_id`."""
    texto = await docking_tools.run_docking(
        smiles=ASPIRINA, target_pdb="7E2Y", user_id=CUENTA
    )

    bajo = texto.lower()
    assert "kcal/mol" not in bajo, "una propuesta no tiene afinidad"
    assert "task_id" not in bajo, "una propuesta no tiene corrida"
    assert "nada está en cola" in bajo


@pytest.mark.asyncio
async def test_sin_identidad_no_se_lanza_y_el_motivo_es_el_real(sesion, registro):
    texto = await docking_tools.run_docking(smiles=ASPIRINA, user_id=None)

    assert registro == [], "no se puede encolar una corrida sin cuenta"
    assert "identidad" in texto.lower()
    assert "no disponible en este modo" not in texto.lower()


@pytest.mark.asyncio
async def test_una_corrida_ajena_no_se_consulta(monkeypatch, sesion):
    """La consulta de estado usa la política de propiedad del endpoint."""
    from fastapi import HTTPException

    async def _prohibido(*_a, **_kw):
        raise HTTPException(status_code=403, detail="No tienes permiso.")

    import api.routers.evaluation as router

    monkeypatch.setattr(router, "_autorizar_corrida", _prohibido)

    texto = await docking_tools.check_docking_status(
        task_id="task-ajena", user_id=OTRA_CUENTA
    )

    assert "permiso" in texto.lower()
    assert "kcal/mol" not in texto.lower()


@pytest.mark.asyncio
async def test_mientras_corre_no_hay_numero_que_citar(monkeypatch, sesion):
    import api.routers.evaluation as router

    async def _autorizada(*_a, **_kw):
        return None

    monkeypatch.setattr(router, "_autorizar_corrida", _autorizada)

    async def _estado(_task_id):
        return SimpleNamespace(
            task_id="task-viva", status="STARTED", progress=42, result=None, error=None
        )

    import services.docking.queue_handler as cola

    monkeypatch.setattr(cola, "get_job_status", _estado)

    texto = await docking_tools.check_docking_status(
        task_id="task-viva", user_id=CUENTA
    )

    assert "task-viva" in texto
    assert "42" in texto
    assert "kcal/mol" not in texto.lower()


@pytest.mark.asyncio
async def test_el_resultado_se_cita_a_su_task_id(monkeypatch, sesion):
    import api.routers.evaluation as router

    async def _autorizada(*_a, **_kw):
        return None

    monkeypatch.setattr(router, "_autorizar_corrida", _autorizada)

    resultado = SimpleNamespace(
        molecule_id=uuid.uuid4(),
        affinity_kcal=-8.4,
        affinity_score=71.0,
        total_score=68.2,
        adme_score=55.0,
        vina_version="1.2.5",
        vina_random_seed=42,
        receptor_sha256="ab" * 32,
    )

    async def _estado(_task_id):
        return SimpleNamespace(
            task_id="task-lista",
            status="SUCCESS",
            progress=100,
            result=resultado,
            error=None,
        )

    import services.docking.queue_handler as cola

    monkeypatch.setattr(cola, "get_job_status", _estado)

    texto = await docking_tools.check_docking_status(
        task_id="task-lista", user_id=CUENTA
    )

    assert "task-lista" in texto
    assert "-8.4" in texto
    assert str(resultado.molecule_id) in texto


@pytest.mark.asyncio
async def test_una_corrida_fallida_no_se_rellena_con_una_estimacion(monkeypatch, sesion):
    import api.routers.evaluation as router

    async def _autorizada(*_a, **_kw):
        return None

    monkeypatch.setattr(router, "_autorizar_corrida", _autorizada)

    async def _estado(_task_id):
        return SimpleNamespace(
            task_id="task-rota",
            status="FAILURE",
            progress=0,
            result=None,
            error="Vina terminó con código 1",
        )

    import services.docking.queue_handler as cola

    monkeypatch.setattr(cola, "get_job_status", _estado)

    texto = await docking_tools.check_docking_status(
        task_id="task-rota", user_id=CUENTA
    )

    assert "falló" in texto.lower() or "fallo" in texto.lower()
    assert "kcal/mol" not in texto.lower()
    assert "no la estimo" in texto.lower()


def test_la_herramienta_declara_que_no_bloquea_el_turno():
    """El contrato que ve el modelo tiene que decir la verdad operativa."""
    from services.ai.tool_registry import get_tool_registry

    docking_tools.register_docking_tools()
    registro = get_tool_registry()

    lanzar = registro.get("run_docking")
    assert lanzar is not None
    assert "segundo plano" in lanzar.description.lower()
    assert "debe esperar" not in lanzar.description.lower()

    consultar = registro.get("check_docking_status")
    assert consultar is not None
    assert "task_id" in consultar.parameters
