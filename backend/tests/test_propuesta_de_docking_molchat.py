"""LUNA-05 — MolChat propone un docking; sólo el investigador lo lanza.

# El fallo

`run_docking` registraba y encolaba la corrida en el MISMO turno en que se interpretó
la petición: del texto del investigador a Vina en cola sin que nadie viera qué iba a
ejecutarse. La auditoría pide una confirmación explícita y separada, con receptor,
motor, política efectiva y coste a la vista, y que lo que se lance sea exactamente lo
que se vio. El preflight del servidor valida bloqueantes; no es una aceptación humana.

# El contrato que esta prueba fija

1. `run_docking` **propone**: corre el preflight real, guarda la propuesta y la
   presenta; no llama a `registrar_corrida`, no hay `task_id`, no hay número.
2. Sólo `aprobar` lanza, y entra por la puerta común (`registrar_corrida`, con
   `exigir_preflight=True` y la huella del preflight mostrado).
3. La petición que se ejecuta sale del servidor: el cliente sólo envía el id y la huella.
4. Una propuesta se aprueba **una sola vez** (también bajo concurrencia), sólo la
   aprueba su cuenta, y sólo si la huella es la que se mostró.
5. Un «sí» escrito no aprueba.
6. Ningún otro módulo del chat encola corridas.
"""

from __future__ import annotations

import ast
import asyncio
import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.ai import propuestas_de_docking as propuestas
from services.ai.contexto_de_turno import conversacion_del_turno
from services.ai.tools import docking_tools

CUENTA = str(uuid.uuid4())
OTRA_CUENTA = str(uuid.uuid4())
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
HUELLA_PREFLIGHT = "sha256:" + "c" * 64


class _Usuario:
    def __init__(self, uid: str):
        self.id = uuid.UUID(uid)


class _SesionFalsa:
    def __init__(self, usuarios):
        self._usuarios = usuarios

    async def get(self, _modelo, uid):
        return self._usuarios.get(uid)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


def _informe(*, bloqueos: list[str] | None = None) -> dict:
    controles = [
        {"state": "advertencia", "title": "Respaldo científico del receptor",
         "observation": "Sin calibración medida para este receptor."},
        {"state": "no_evaluado", "title": "Tautomería", "observation": "No evaluada."},
    ]
    for codigo in bloqueos or []:
        controles.append({"state": "bloquea", "title": codigo, "observation": f"{codigo}: bloquea"})
    return {
        "input_fingerprint": HUELLA_PREFLIGHT,
        "technical_blockers": list(bloqueos or []),
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
        "controls": controles,
    }


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
def preflight(monkeypatch):
    """El informe que el servidor 'calcula': sin base de datos ni receptor reales."""
    estado = {"informe": _informe()}

    async def _comprobar(**_kwargs):
        return estado["informe"]

    import api.routers.evaluation as router

    monkeypatch.setattr(router, "comprobar_preparacion", _comprobar)
    return estado


@pytest.fixture
def registro(monkeypatch):
    """Espía de la única puerta de registro de corridas."""
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


async def _proponer(cuenta: str = CUENTA) -> tuple[str, str, str]:
    texto = await docking_tools.run_docking(smiles=ASPIRINA, target_pdb="7E2Y", user_id=cuenta)
    hallazgo = propuestas._RE_MARCADOR.search(texto)
    assert hallazgo, f"la propuesta no trae su marcador:\n{texto}"
    return texto, hallazgo.group(1), hallazgo.group(2)


# ── 1. proponer no lanza ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_docking_propone_y_no_encola(sesion, preflight, registro):
    texto, _id, huella = await _proponer()

    assert registro == [], "run_docking encoló una corrida: tiene que PROPONER, no lanzar"
    assert "todavía no lanzada" in texto.lower()
    assert huella.startswith("sha256:")
    # Lo que la auditoría pide ver ANTES de aprobar:
    for esperado in (
        "7E2Y", "cadena A", "curado", "Vina", "vina",              # receptor y motor
        "exhaustividad 8", "5 poses", "1 conformación", "semilla 42",  # protocolo efectivo
        "12.5", "22.5",                                             # la caja
        "eliminadas", "bloqueados_sin_plantilla_local",             # heteroátomos
        "Coste aproximado",                                         # coste
        "Respaldo científico del receptor",                         # advertencia leída
        "No evaluado",
    ):
        assert esperado in texto, f"la propuesta no muestra: {esperado!r}"
    bajo = texto.lower()
    assert "task_id" not in bajo and "kcal/mol" not in bajo, (
        "una propuesta no tiene corrida: ni identificador ni número"
    )
    assert "escribir «sí»" in bajo and "no" in bajo


@pytest.mark.asyncio
async def test_un_preflight_bloqueante_no_produce_propuesta(sesion, preflight, registro):
    preflight["informe"] = _informe(bloqueos=["COFACTOR_SIN_PLANTILLA"])
    texto = await docking_tools.run_docking(smiles=ASPIRINA, target_pdb="7E2Y", user_id=CUENTA)

    assert registro == []
    assert propuestas._RE_MARCADOR.search(texto) is None, (
        "no hay nada que aprobar cuando el servidor bloquea la corrida"
    )
    assert "COFACTOR_SIN_PLANTILLA" in texto and "bloquea" in texto.lower()
    assert "no la sustituyo por una estimación" in texto.lower()


@pytest.mark.asyncio
async def test_sin_identidad_no_hay_propuesta(sesion, preflight, registro):
    texto = await docking_tools.run_docking(smiles=ASPIRINA, user_id=None)
    assert registro == []
    assert "identidad" in texto.lower()


@pytest.mark.asyncio
async def test_la_propuesta_recuerda_la_conversacion_donde_nacio(sesion, preflight, registro):
    from utils.cache import cache

    conversacion_del_turno.set("conv-123")
    try:
        _texto, propuesta_id, _huella = await _proponer()
    finally:
        conversacion_del_turno.set(None)
    guardada = await cache.get(propuestas._clave(propuesta_id))
    assert guardada["conversation_id"] == "conv-123"
    assert guardada["user_id"] == CUENTA


# ── 2. aprobar lanza exactamente lo propuesto ────────────────────────────


@pytest.mark.asyncio
async def test_aprobar_lanza_por_la_puerta_comun_con_la_huella_mostrada(sesion, preflight, registro):
    _texto, propuesta_id, huella = await _proponer()
    corrida, _ = await propuestas.aprobar(
        propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
    )

    assert corrida.task_id == "task-1"
    assert len(registro) == 1
    llamada = registro[0]
    assert llamada["exigir_preflight"] is True
    peticion = llamada["data"]
    assert str(llamada["current_user"].id) == CUENTA
    assert peticion.target_pdb_id == "7E2Y"
    assert peticion.preflight_fingerprint == HUELLA_PREFLIGHT, (
        "la puerta común tiene que comparar contra la huella del preflight que se mostró"
    )
    docking = peticion.pipeline_config.stage_params["docking"]
    assert docking == {"exhaustiveness": 8, "num_poses": 5}
    assert peticion.pipeline_config.docking_engine == "vina"


@pytest.mark.asyncio
async def test_la_propuesta_se_aprueba_una_sola_vez(sesion, preflight, registro):
    _t, propuesta_id, huella = await _proponer()
    await propuestas.aprobar(propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None)
    with pytest.raises(propuestas.PropuestaNoAplicable) as salida:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
        )
    assert salida.value.status_code == 410
    assert len(registro) == 1, "una segunda aprobación encoló una segunda corrida"


@pytest.mark.asyncio
async def test_dos_aprobaciones_simultaneas_lanzan_una_sola_corrida(sesion, preflight, registro):
    _t, propuesta_id, huella = await _proponer()
    resultados = await asyncio.gather(
        *[
            propuestas.aprobar(
                propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
            )
            for _ in range(5)
        ],
        return_exceptions=True,
    )
    exitos = [r for r in resultados if not isinstance(r, Exception)]
    fallos = [r for r in resultados if isinstance(r, propuestas.PropuestaNoAplicable)]
    assert len(exitos) == 1 and len(fallos) == 4
    assert len(registro) == 1


@pytest.mark.asyncio
async def test_una_huella_distinta_no_lanza_ni_consume_la_propuesta(sesion, preflight, registro):
    _t, propuesta_id, huella = await _proponer()
    otra = "sha256:" + "0" * 64
    with pytest.raises(propuestas.PropuestaNoAplicable) as salida:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=otra, usuario=_Usuario(CUENTA), db=None,
        )
    assert salida.value.status_code == 409
    assert registro == []
    # La propuesta sigue pendiente: equivocarse de huella no la destruye.
    await propuestas.aprobar(propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None)
    assert len(registro) == 1


@pytest.mark.asyncio
async def test_otra_cuenta_no_puede_aprobar_ni_ver_la_propuesta(sesion, preflight, registro):
    _t, propuesta_id, huella = await _proponer()
    with pytest.raises(propuestas.PropuestaNoAplicable) as salida:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(OTRA_CUENTA), db=None,
        )
    assert salida.value.status_code == 404, "no se revela que la propuesta existe"
    with pytest.raises(propuestas.PropuestaNoAplicable):
        await propuestas.consultar(propuesta_id, _Usuario(OTRA_CUENTA))
    assert registro == []
    await propuestas.aprobar(propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None)
    assert len(registro) == 1


@pytest.mark.asyncio
async def test_una_propuesta_caducada_no_se_aprueba(sesion, preflight, registro):
    from utils.cache import cache

    _t, propuesta_id, huella = await _proponer()
    await cache.delete(propuestas._clave(propuesta_id))   # lo que hace el TTL al vencer
    with pytest.raises(propuestas.PropuestaNoAplicable) as salida:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
        )
    assert salida.value.status_code == 410
    assert registro == []


@pytest.mark.asyncio
async def test_la_propuesta_se_guarda_con_ttl(sesion, preflight, registro, monkeypatch):
    from utils.cache import cache

    ttls: list = []
    original = cache.set

    async def _set(clave, valor, ttl=None):
        ttls.append((clave, ttl))
        return await original(clave, valor, ttl=ttl)

    monkeypatch.setattr(cache, "set", _set)
    await _proponer()
    assert any(c.startswith(propuestas._PREFIJO) and t == propuestas.TTL_PROPUESTA_S for c, t in ttls)
    assert propuestas.TTL_PROPUESTA_S == 15 * 60


@pytest.mark.asyncio
async def test_rechazar_la_retira(sesion, preflight, registro):
    _t, propuesta_id, huella = await _proponer()
    await propuestas.rechazar(propuesta_id, _Usuario(CUENTA))
    with pytest.raises(propuestas.PropuestaNoAplicable):
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
        )
    assert registro == []


@pytest.mark.asyncio
async def test_si_la_puerta_comun_rechaza_la_propuesta_ya_no_se_puede_reusar(
    sesion, preflight, monkeypatch
):
    """La preparación cambió entre la propuesta y la aprobación (409 de la puerta
    común): se consumió, y hay que pedirla de nuevo con el preflight nuevo."""
    from fastapi import HTTPException

    async def _rechaza(**_kw):
        raise HTTPException(status_code=409, detail="La preparación cambió.")

    import services.evaluation_submission as modulo

    monkeypatch.setattr(modulo, "registrar_corrida", _rechaza)
    _t, propuesta_id, huella = await _proponer()
    with pytest.raises(HTTPException) as salida:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
        )
    assert salida.value.status_code == 409
    with pytest.raises(propuestas.PropuestaNoAplicable) as de_nuevo:
        await propuestas.aprobar(
            propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None,
        )
    assert de_nuevo.value.status_code == 410


# ── 3. el HTTP: sesión, cuerpo cerrado, constancia ───────────────────────


@pytest.fixture
def cliente(sesion, preflight, registro, monkeypatch):
    from fastapi.testclient import TestClient

    import api.routers.ai as router_ai
    from api.dependencies import get_current_user
    from api.main import app
    from core.database import get_db

    anotados: list[str] = []

    class _Conv:
        def add_message(self, rol, contenido):
            anotados.append(f"{rol}:{contenido}")

    class _Servicio:
        def get_conversation(self, conv_id=None, user_id=None):
            return _Conv() if conv_id == "conv-123" and user_id == CUENTA else None

        def load_conversation_from_db(self, *_a, **_k):
            return None

        def _persist_conv(self, _conv):
            anotados.append("persistida")

    monkeypatch.setattr(router_ai, "get_chat_service", lambda: _Servicio())
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: _Usuario(CUENTA)
    try:
        yield TestClient(app, raise_server_exceptions=False), anotados, app
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_http_aprobar_lanza_y_deja_constancia_en_la_conversacion(cliente, registro):
    http, anotados, _app = cliente
    conversacion_del_turno.set("conv-123")
    try:
        _t, propuesta_id, huella = await _proponer()
    finally:
        conversacion_del_turno.set(None)

    respuesta = await asyncio.to_thread(
        http.post, f"/ai/proposals/{propuesta_id}/approve", json={"proposal_hash": huella}
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["task_id"] == "task-1"
    assert "todavía no hay afinidad" in cuerpo["message"].lower()
    assert len(registro) == 1
    assert any(a.startswith("assistant:") and "task-1" in a for a in anotados), (
        "el lanzamiento no quedó anotado en la conversación"
    )


@pytest.mark.asyncio
async def test_http_el_cliente_no_puede_inyectar_la_peticion(cliente, registro):
    """El cuerpo de la aprobación es cerrado: sólo la huella. La corrida sale del servidor."""
    http, _anotados, _app = cliente
    _t, propuesta_id, huella = await _proponer()

    r = await asyncio.to_thread(
        http.post, f"/ai/proposals/{propuesta_id}/approve",
        json={"proposal_hash": huella, "request": {"smiles": "CCO", "target_pdb_id": "1ABC"}},
    )
    assert r.status_code == 422
    r2 = await asyncio.to_thread(
        http.post, f"/ai/proposals/{propuesta_id}/approve", json={"proposal_hash": "no-es-una-huella"}
    )
    assert r2.status_code == 422
    assert registro == []


@pytest.mark.asyncio
async def test_http_sin_sesion_no_se_aprueba(sesion, preflight, registro):
    from fastapi.testclient import TestClient

    from api.main import app
    from core.database import get_db

    _t, propuesta_id, huella = await _proponer()
    # Sin override de `get_current_user`: la sesión real, que sin credenciales rechaza.
    # La base se sustituye para no abrir la del usuario.
    app.dependency_overrides[get_db] = lambda: None
    try:
        http = TestClient(app, raise_server_exceptions=False)
        r = await asyncio.to_thread(
            http.post, f"/ai/proposals/{propuesta_id}/approve", json={"proposal_hash": huella}
        )
        sin_token_consulta = await asyncio.to_thread(http.get, f"/ai/proposals/{propuesta_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code in (401, 403)
    assert sin_token_consulta.status_code in (401, 403)
    assert registro == []


@pytest.mark.asyncio
async def test_http_codigos_para_propuesta_ajena_y_desaparecida(cliente, registro):
    http, _a, app = cliente
    from api.dependencies import get_current_user

    _t, propuesta_id, huella = await _proponer(OTRA_CUENTA)   # propuesta de OTRA cuenta
    r = await asyncio.to_thread(
        http.post, f"/ai/proposals/{propuesta_id}/approve", json={"proposal_hash": huella}
    )
    assert r.status_code == 404                              # la sesión es CUENTA

    fantasma = await asyncio.to_thread(
        http.post, "/ai/proposals/no-existe/approve", json={"proposal_hash": "sha256:" + "a" * 64}
    )
    assert fantasma.status_code == 410
    assert "ya no está pendiente" in fantasma.json()["detail"]
    assert registro == []


# ── 4. un «sí» escrito no aprueba ────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_si_escrito_no_aprueba_y_explica_donde_se_aprueba(sesion, preflight, registro):
    texto, propuesta_id, _huella = await _proponer()
    historial = [
        {"role": "user", "content": f"dockea {ASPIRINA} contra 7E2Y"},
        {"role": "assistant", "content": texto},
    ]
    for si in ("sí", "Si.", "dale", "OK", "lanza", "¡Adelante!"):
        aviso = await propuestas.respuesta_a_un_si_escrito(
            mensajes=historial, mensaje_del_usuario=si, user_id=CUENTA
        )
        assert aviso and "no lanza" in aviso.lower() and "Aprobar y lanzar" in aviso, si
    assert registro == []


@pytest.mark.asyncio
async def test_el_si_es_de_otra_cosa_si_no_hay_propuesta_vigente_de_esta_cuenta(
    sesion, preflight, registro
):
    texto, propuesta_id, huella = await _proponer()
    historial = [{"role": "assistant", "content": texto}]

    async def aviso(mensajes=historial, mensaje="sí", cuenta=CUENTA):
        return await propuestas.respuesta_a_un_si_escrito(
            mensajes=mensajes, mensaje_del_usuario=mensaje, user_id=cuenta
        )

    assert await aviso(mensaje="no") is None
    assert await aviso(mensaje="¿qué es el exhaustiveness?") is None
    assert await aviso(cuenta=OTRA_CUENTA) is None
    # El investigador ya dijo otra cosa después de la propuesta: el «sí» es de esa otra cosa.
    seguido = historial + [
        {"role": "user", "content": "¿qué es el exhaustiveness?"},
        {"role": "assistant", "content": "Es el esfuerzo de búsqueda de Vina."},
    ]
    assert await aviso(mensajes=seguido) is None
    assert await aviso(mensajes=[{"role": "assistant", "content": "sin propuesta"}]) is None
    # Y una vez aprobada, el «sí» ya no se refiere a ella.
    await propuestas.aprobar(propuesta_id=propuesta_id, huella=huella, usuario=_Usuario(CUENTA), db=None)
    assert await aviso() is None


@pytest.mark.asyncio
async def test_el_si_tambien_se_reconoce_por_el_camino_del_clasificador(sesion, preflight, registro):
    """El gate runtime real lo encontró: por el clasificador determinista el asistente
    guarda un marcador de posición y la propuesta —con su marcador— vive en el mensaje
    del SISTEMA. Un «sí» no puede generar una segunda propuesta ni lanzar nada."""
    texto, _id, _huella = await _proponer()
    historial = [
        {"role": "user", "content": f"haz un docking de {ASPIRINA} contra 7E2Y"},
        {"role": "assistant", "content": "[run_docking — clasificador determinista]"},
        {"role": "system", "content": "\n[Sistema: resultados de herramientas ejecutadas:]\n" + texto},
    ]
    aviso = await propuestas.respuesta_a_un_si_escrito(
        mensajes=historial, mensaje_del_usuario="sí", user_id=CUENTA
    )
    assert aviso and "no lanza" in aviso.lower()
    assert registro == []


# ── 5. ningún otro camino del chat encola ────────────────────────────────


def test_solo_la_aprobacion_llama_a_registrar_corrida():
    """La garantía estructural: el chat no tiene una segunda puerta de lanzamiento.

    Se recorre el AST de todo `services/ai` y del router de IA: la única referencia a
    `registrar_corrida` que invoca la función es `propuestas_de_docking.aprobar`.
    """
    raiz = Path(__file__).resolve().parents[1]
    archivos = sorted((raiz / "services" / "ai").rglob("*.py")) + [raiz / "api" / "routers" / "ai.py"]
    llamadores: list[str] = []
    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for funcion in ast.walk(arbol):
            if not isinstance(funcion, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for nodo in ast.walk(funcion):
                if isinstance(nodo, ast.Call):
                    f = nodo.func
                    nombre = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                    if nombre == "registrar_corrida":
                        llamadores.append(f"{archivo.relative_to(raiz).as_posix()}::{funcion.name}")
    assert llamadores == ["services/ai/propuestas_de_docking.py::aprobar"], llamadores


def test_la_herramienta_declara_que_propone_y_no_lanza():
    from services.ai.tool_registry import get_tool_registry

    docking_tools.register_docking_tools()
    herramienta = get_tool_registry().get("run_docking")
    descripcion = herramienta.description.lower()
    assert "propone" in descripcion and "no la lanza" in descripcion
    assert "aprueba" in descripcion
    assert "lanza una evaluación real" not in descripcion


def test_el_marcador_no_se_confunde_con_el_permiso_web():
    """Dos marcadores distintos en el mismo chat: cada uno con su propio botón."""
    assert propuestas.MARCADOR != "__PENDING_WEB_ASK__"
    assert re.fullmatch(r"__[A-Z_]+__", propuestas.MARCADOR)
