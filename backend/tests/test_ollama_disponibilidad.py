"""Ollama: disponible quiere decir que responde Y tiene el modelo elegido.

LOS FALLOS QUE VIGILA.

1. `validate_config` sólo miraba si Ollama respondía. Con el modelo por defecto
   sin descargar (`gemma3:1b`) el turno salía, Ollama contestaba 404 y MolChat
   escribía «Error Ollama (404)» como si fuera su respuesta.
2. Esos errores viajaban como texto del asistente: se guardaban en la
   conversación y se reenviaban al modelo en el turno siguiente. Ahora son
   avisos (`__WARNING__:`), y un turno que sólo trae un aviso no se guarda.
3. El modal sólo conocía los valores por defecto (`localhost`, `gemma3:1b`): al
   reabrirlo enseñaba otra cosa que la que la cuenta tenía guardada.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from services.ai import provider_config_store as store
from services.ai.providers import ollama_provider as modulo
from services.ai.providers.base import ProviderConfig
from services.ai.providers.ollama_provider import OllamaProvider, _nombre_instalado
from services.ai.providers.registry import ProviderRegistry

URL = "http://localhost:11434"


def _tags(monkeypatch, responde: bool, modelos: list[str]):
    motivo = "OK" if responde else "No se pudo conectar a Ollama: rechazada"
    monkeypatch.setattr(modulo, "_sondear_tags", lambda url: (responde, list(modelos), motivo))


def _ollama(modelo: str = "gemma3:1b") -> OllamaProvider:
    return OllamaProvider(ProviderConfig(base_url=URL, model=modelo, temperature=0.1, max_tokens=64))


def test_un_nombre_sin_etiqueta_es_el_latest():
    assert _nombre_instalado("llama3.2", ["llama3.2:latest"]) == "llama3.2:latest"
    assert _nombre_instalado("qwen3:4b", ["qwen3:4b", "qwen3:8b"]) == "qwen3:4b"
    assert _nombre_instalado("qwen3:4b", ["qwen3:8b"]) is None
    assert _nombre_instalado("", ["qwen3:8b"]) is None


def test_sin_respuesta_no_esta_disponible_y_dice_donde_mira(monkeypatch):
    _tags(monkeypatch, responde=False, modelos=[])
    ok, motivo = _ollama().validate_config()
    assert not ok
    assert URL in motivo and "no responde" in motivo


def test_responde_sin_el_modelo_elegido_no_esta_disponible(monkeypatch):
    _tags(monkeypatch, responde=True, modelos=["qwen3:4b", "llama3.2:latest"])
    ok, motivo = _ollama("gemma3:1b").validate_config()
    assert not ok
    assert "gemma3:1b" in motivo
    assert "qwen3:4b" in motivo  # dice cuáles hay
    assert "ollama pull gemma3:1b" in motivo


def test_responde_sin_ningun_modelo_no_esta_disponible(monkeypatch):
    _tags(monkeypatch, responde=True, modelos=[])
    ok, motivo = _ollama().validate_config()
    assert not ok
    assert "ningún modelo" in motivo


def test_con_el_modelo_instalado_esta_disponible(monkeypatch):
    _tags(monkeypatch, responde=True, modelos=["llama3.2:latest"])
    ok, _ = _ollama("llama3.2").validate_config()
    assert ok
    info = _ollama("llama3.2").get_info()
    assert info.configured
    assert info.available_models == ["llama3.2:latest"]


def test_sugiere_un_modelo_instalado_en_vez_de_uno_ausente(monkeypatch):
    _tags(monkeypatch, responde=True, modelos=["qwen3:4b"])
    info = _ollama("gemma3:1b").get_info()
    assert info.default_model == "qwen3:4b"
    assert not info.configured


@pytest.mark.asyncio
async def test_un_404_de_ollama_es_un_aviso_accionable_no_una_respuesta(monkeypatch):
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'gemma3:1b' not found"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        modulo.httpx, "AsyncClient",
        lambda *a, **k: original(*a, transport=httpx.MockTransport(responder), **k),
    )

    for stream in (True, False):
        tokens = [t async for t in _ollama().chat([{"role": "user", "content": "hola"}], stream=stream)]
        assert len(tokens) == 1
        assert tokens[0].startswith("__WARNING__:")
        assert "gemma3:1b" in tokens[0] and "ollama pull gemma3:1b" in tokens[0]


def test_el_catalogo_declara_lo_aplicado_y_por_que_no_esta_disponible(monkeypatch):
    _tags(monkeypatch, responde=True, modelos=["qwen3:4b"])
    registro = ProviderRegistry()
    registro.register(_ollama("gemma3:1b"))

    (fila,) = registro.list_providers()

    assert fila["model"] == "gemma3:1b"
    assert fila["base_url"] == URL
    assert "gemma3:1b" in fila["estado"]
    assert "api_key" not in fila


# ── El aviso no se guarda como respuesta ──────────────────────────────

ALICE = str(uuid.uuid4())


@pytest.fixture
def entorno_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    from services.ai import memory_store
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")


class _OllamaSinModelo:
    id = "ollama"
    name = "Ollama"

    def __init__(self):
        # En esta máquina: un destino remoto sin autorizar cortaría el turno antes.
        self.config = ProviderConfig(base_url=URL, model="gemma3:1b", max_tokens=64)

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        yield "__WARNING__:Ollama no tiene el modelo «gemma3:1b»."


@pytest.mark.asyncio
async def test_un_turno_que_solo_trae_un_aviso_no_se_guarda_como_respuesta(entorno_aislado, monkeypatch):
    from services.ai import chat_service
    from services.ai.chat_service import ChatService

    proveedor = _OllamaSinModelo()
    registro = ProviderRegistry()
    registro.register(proveedor)
    monkeypatch.setattr(chat_service, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: proveedor)

    servicio = ChatService()
    tokens = [
        t async for t in servicio.chat(
            messages=[{"role": "user", "content": "Explícame qué es una interacción de apilamiento"}],
            provider_id="ollama",
            user_id=ALICE,
        )
    ]

    assert any(t.startswith("__WARNING__:") and "gemma3:1b" in t for t in tokens), tokens
    conv = servicio.get_conversation(user_id=ALICE)
    assert any(m.get("role") == "user" for m in conv.messages)
    respuestas = [m["content"] for m in conv.messages if m.get("role") == "assistant"]
    assert not any("__WARNING__" in r for r in respuestas), respuestas
