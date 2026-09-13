"""MOLCHAT-NET-005 — no se envía nada fuera de la máquina sin consentimiento.

Búsqueda de `consent`, `autoriz` y `allow_remote` en el router, el servicio de
chat y los proveedores: cero coincidencias. No había puerta alguna — si había un
proveedor remoto configurado, el turno salía, y con él el contexto de caso y
molécula, que es el trabajo del investigador y no sólo el texto del chat.

Y la mitad que MOLCHAT-BE-003 dejó abierta vive aquí: autenticar
`providers/configure` impidió que un anónimo redirigiera el tráfico, pero
cambiar el `base_url` seguía siendo un cambio de **destino de los datos**
invisible. El consentimiento se otorga a la huella `proveedor@host`, así que el
destino nuevo no hereda la autorización del anterior.

El destino se calcula, no se supone: `ollama` apuntado al servidor de otra
persona sale de la máquina, y un `openai` apuntado a `localhost` no.
"""

from __future__ import annotations

import uuid

import pytest

from services.ai import consent, provider_config_store as store
from services.ai.chat_service import ChatService
from services.ai.providers.base import ProviderConfig
from services.ai.providers.registry import ProviderRegistry

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("b" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)

    from services.ai import memory_store
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


# ── El destino se calcula ────────────────────────────────────────────────


def _ollama(base_url: str):
    from services.ai.providers.ollama_provider import OllamaProvider
    return OllamaProvider(config=ProviderConfig(base_url=base_url))


def _local():
    from services.ai.providers.local_llm_provider import LocalLLMProvider
    return LocalLLMProvider(config=ProviderConfig(model="modelo.gguf"))


def test_el_motor_local_no_sale_de_la_maquina():
    destino = consent.destino_de(_local())
    assert destino.es_remoto is False


def test_ollama_en_esta_maquina_no_es_remoto():
    assert consent.destino_de(_ollama("http://localhost:11434")).es_remoto is False
    assert consent.destino_de(_ollama("http://127.0.0.1:11434")).es_remoto is False


def test_ollama_apuntado_a_otra_maquina_si_es_remoto():
    """El nombre del proveedor no decide; el host del destino sí."""
    destino = consent.destino_de(_ollama("http://servidor-ajeno.example:11434"))
    assert destino.es_remoto is True
    assert destino.host == "servidor-ajeno.example"


def test_una_ip_de_la_red_local_es_otra_computadora():
    assert consent.destino_de(_ollama("http://192.168.1.50:11434")).es_remoto is True


def test_un_destino_sin_declarar_se_trata_como_remoto():
    """La duda no se resuelve a favor de enviar.

    `OllamaProvider` se autocompleta a `localhost` cuando no le dan `base_url`,
    así que este caso se comprueba con un proveedor que deja el destino vacío.
    """

    class SinDestino:
        id = "openai"
        config = ProviderConfig(base_url="")

    assert consent.destino_de(SinDestino()).es_remoto is True


def test_los_proveedores_de_api_fija_son_remotos():
    from services.ai.providers.claude_provider import ClaudeProvider

    destino = consent.destino_de(ClaudeProvider(config=ProviderConfig()))
    assert destino.es_remoto is True
    assert destino.host == "api.anthropic.com"


# ── La puerta ────────────────────────────────────────────────────────────


class _ProveedorEspia:
    """Un proveedor remoto que anota si alguien le mandó el turno."""

    id = "ollama"
    name = "Ollama"

    def __init__(self, base_url: str = "http://servidor-ajeno.example:11434"):
        self.config = ProviderConfig(base_url=base_url, model="m")
        self.recibio = []

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        self.recibio.append(kwargs or args)
        yield "respuesta del servidor remoto"

    async def chat_with_tools(self, *args, **kwargs):
        self.recibio.append(kwargs or args)
        yield "respuesta del servidor remoto"


@pytest.fixture
def registro_espia(monkeypatch):
    espia = _ProveedorEspia()
    registro = ProviderRegistry()
    registro.register(espia)
    registro.set_active("ollama")

    from services.ai import chat_service as modulo

    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: espia)
    return espia


async def _turno(user_id: str) -> list[str]:
    servicio = ChatService()
    return [
        token
        async for token in servicio.chat(
            messages=[{"role": "user", "content": "hola"}],
            user_id=user_id,
        )
    ]


@pytest.mark.asyncio
async def test_sin_consentimiento_el_turno_no_sale(registro_espia):
    tokens = await _turno(ALICE)

    assert registro_espia.recibio == [], (
        "el turno se envió a un servidor remoto que esta cuenta nunca autorizó"
    )
    assert any(t.startswith("__WARNING__:") for t in tokens)


@pytest.mark.asyncio
async def test_el_aviso_dice_a_donde_iba_y_como_seguir(registro_espia):
    tokens = await _turno(ALICE)
    aviso = next(t for t in tokens if t.startswith("__WARNING__:"))

    assert "servidor-ajeno.example" in aviso
    assert "local" in aviso.lower()


@pytest.mark.asyncio
async def test_con_consentimiento_el_turno_sale(registro_espia):
    consent.otorgar(consent.destino_de(registro_espia), ALICE)

    await _turno(ALICE)

    assert registro_espia.recibio, "la cuenta autorizó el destino y aun así no se envió"


@pytest.mark.asyncio
async def test_el_consentimiento_es_de_una_cuenta_y_no_de_la_maquina(registro_espia):
    consent.otorgar(consent.destino_de(registro_espia), ALICE)

    await _turno(BOB)

    assert registro_espia.recibio == [], "Bob salió a la red con el permiso de Alice"


@pytest.mark.asyncio
async def test_el_camino_local_nunca_pide_permiso(monkeypatch):
    """El §8 pide que el camino local sea inequívoco y sin fricción."""
    espia = _ProveedorEspia()
    espia.id = "local"
    espia.config = ProviderConfig()

    registro = ProviderRegistry()
    from services.ai import chat_service as modulo
    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: espia)

    await _turno(ALICE)

    assert espia.recibio, "el motor local pidió un consentimiento que no le toca"


# ── El destino cambia, el permiso no viaja con él ────────────────────────


def test_cambiar_el_base_url_deja_el_destino_sin_autorizar():
    """La mitad abierta de MOLCHAT-BE-003, comprobada donde se decide."""
    antes = consent.destino_de(_ollama("http://servidor-a.example:11434"))
    consent.otorgar(antes, ALICE)
    assert consent.hay_consentimiento(antes, ALICE) is True

    despues = consent.destino_de(_ollama("http://servidor-b.example:11434"))
    assert consent.hay_consentimiento(despues, ALICE) is False, (
        "el consentimiento del destino anterior autorizó a uno nuevo"
    )


def test_revocar_retira_todos_los_destinos_del_proveedor():
    consent.otorgar(consent.destino_de(_ollama("http://servidor-a.example:11434")), ALICE)
    consent.otorgar(consent.destino_de(_ollama("http://servidor-b.example:11434")), ALICE)

    assert consent.revocar("ollama", ALICE) is True
    assert store.cargar_consentimientos(ALICE) == {}


def test_el_invitado_no_hereda_consentimientos():
    """Heredarlo sería afirmar que alguien aceptó algo que nadie comprobó."""
    destino = consent.destino_de(_ollama("http://servidor-a.example:11434"))
    consent.otorgar(destino, ALICE)

    # La herencia de D-07 llega a la configuración, no al permiso.
    assert consent.hay_consentimiento(destino, BOB) is False


# ── El contrato HTTP ─────────────────────────────────────────────────────


@pytest.fixture
def cliente(monkeypatch):
    """Un cliente con sesión de Alice sobre el router real."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user
    from api.main import app

    alice = SimpleNamespace(id=ALICE, email="alice@ejemplo.test")
    app.dependency_overrides[get_current_user] = lambda: alice
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _configurar(cliente, **payload):
    return cliente.post("/ai/providers/configure", json={"provider_id": "ollama", **payload})


def test_cambiar_el_destino_sin_confirmar_se_rechaza(cliente):
    """MOLCHAT-BE-003: el `base_url` no es un ajuste, es a dónde van los datos."""
    respuesta = _configurar(cliente, base_url="http://servidor-ajeno.example:11434")

    assert respuesta.status_code == 409
    detalle = respuesta.json()["detail"]
    assert detalle["motivo"] == "cambio_de_destino"
    assert detalle["destino_propuesto"]["host"] == "servidor-ajeno.example"
    assert detalle["destino_propuesto"]["es_remoto"] is True


def test_confirmado_se_aplica_y_declara_el_destino(cliente):
    respuesta = _configurar(
        cliente, base_url="http://servidor-ajeno.example:11434", confirmar_destino=True
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["destino"]["host"] == "servidor-ajeno.example"
    assert cuerpo["consentido"] is False, (
        "aplicar el cambio de destino no puede dar por autorizado el destino nuevo"
    )


def test_mover_el_destino_retira_el_consentimiento_anterior(cliente):
    _configurar(cliente, base_url="http://servidor-a.example:11434", confirmar_destino=True)
    assert cliente.post("/ai/consent", json={"provider_id": "ollama"}).status_code == 200

    movido = _configurar(
        cliente, base_url="http://servidor-b.example:11434", confirmar_destino=True
    )

    assert movido.json()["consentimiento_revocado"] is True
    assert movido.json()["consentido"] is False


def test_autorizar_un_destino_distinto_del_que_se_vio_se_rechaza(cliente):
    _configurar(cliente, base_url="http://servidor-a.example:11434", confirmar_destino=True)

    respuesta = cliente.post(
        "/ai/consent", json={"provider_id": "ollama", "host": "servidor-que-ya-no-es.example"}
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["motivo"] == "destino_cambiado"


def test_el_estado_declara_a_donde_iria_cada_proveedor(cliente):
    respuesta = cliente.get("/ai/consent")

    assert respuesta.status_code == 200
    destinos = {d["provider_id"]: d for d in respuesta.json()["destinos"]}
    assert destinos["local"]["es_remoto"] is False
    assert destinos["local"]["consentido"] is True
    assert destinos["claude"]["host"] == "api.anthropic.com"
    assert destinos["claude"]["consentido"] is False


def test_revocar_deja_el_destino_sin_autorizar(cliente):
    _configurar(cliente, base_url="http://servidor-a.example:11434", confirmar_destino=True)
    cliente.post("/ai/consent", json={"provider_id": "ollama"})

    assert cliente.delete("/ai/consent/ollama").json()["revocado"] is True

    destinos = {d["provider_id"]: d for d in cliente.get("/ai/consent").json()["destinos"]}
    assert destinos["ollama"]["consentido"] is False


def test_las_rutas_de_consentimiento_exigen_sesion():
    """No tendría sentido que el permiso lo pudiera dar cualquiera."""
    from tests.test_ai_endpoints_exigen_sesion import ABIERTAS, _exige_sesion, _rutas

    for nombre, ruta in _rutas():
        if "/ai/consent" in nombre:
            assert nombre not in ABIERTAS
            assert _exige_sesion(ruta), nombre
