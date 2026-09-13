"""MOLCHAT-INT-007 — una sola capacidad, no una por rama de transporte.

`POST /ai/chat` tenía dos implementaciones distintas detrás del mismo contrato:
`chat()` para `stream=true` y `chat_with_info()` para `stream=false`. La segunda
lo decía en su propia docstring —*«por ahora esta path NO expone tools nativas al
modelo»*— y aceptaba `allow_web` «por simetría de contrato», sin efecto.

El daño no es de contrato, es del eje SCI. La misma pregunta respondida con
`stream=true` podía resolverse con una herramienta determinista, y con
`stream=false` la contestaba el modelo por su cuenta: **un parámetro de
transporte decidía si la respuesta era cálculo o generación**, y el cliente no
tenía forma de saberlo.

D-08 lo vuelve una contradicción del producto, no un detalle: si MolChat evalúa
en segundo plano «para no inventar información», una rama que responde sin
herramientas es exactamente lo que el producto dice no hacer.

La corrección no es copiar la lógica a la segunda rama —dos implementaciones se
desincronizan— sino que haya **una sola**: la rama no-streaming acumula lo que
produce la de streaming.
"""

from __future__ import annotations

import uuid

import pytest

from services.ai import provider_config_store as store
from services.ai.chat_service import ChatService
from services.ai.providers.base import ProviderConfig
from services.ai.providers.registry import ProviderRegistry
from services.ai.tool_registry import ToolDef, get_tool_registry

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)

    from services.ai import memory_store
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


class _ProveedorEspia:
    """Anota **cómo** se le habló: con herramientas o sin ellas."""

    id = "local"
    name = "Local (espía)"

    def __init__(self):
        self.config = ProviderConfig(model="m", max_tokens=256)
        self.llamadas: list[str] = []

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        self.llamadas.append("chat")
        yield "texto del modelo"

    async def chat_with_tools(self, *args, **kwargs):
        self.llamadas.append("chat_with_tools")
        return {"content": "texto del modelo", "tool_calls": []}


@pytest.fixture
def espia(monkeypatch):
    proveedor = _ProveedorEspia()
    registro = ProviderRegistry()
    registro.register(proveedor)

    from services.ai import chat_service as modulo

    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: proveedor)

    # Una herramienta cualquiera: sin nada registrado, ninguna rama expondría
    # herramientas y la prueba pasaría en vacío.
    registro_tools = get_tool_registry()
    if not registro_tools.get("prueba_paridad"):
        registro_tools.register(
            ToolDef(
                name="prueba_paridad",
                description="Herramienta de prueba",
                parameters={},
                offline=True,
            )
        )
    return proveedor


MENSAJES = [{"role": "user", "content": "¿cuál es el peso molecular de la aspirina?"}]


async def _streaming(espia: _ProveedorEspia, user_id: str = ALICE) -> str:
    """Un turno por la rama de streaming, sobre una conversación recién creada.

    Cada rama arranca con estado equivalente a propósito: comparar el turno 1 de
    una con el turno 2 de la otra mediría el historial, no la rama.
    """
    espia.llamadas.clear()
    servicio = ChatService()
    return "".join(
        [
            t
            async for t in servicio.chat(messages=MENSAJES, user_id=user_id)
            if not t.startswith("__WARNING__:")
        ]
    )


@pytest.mark.asyncio
async def test_las_dos_ramas_exponen_las_mismas_herramientas(espia):
    """El corazón del hallazgo, comprobado por cómo se le habla al proveedor."""
    await _streaming(espia)
    con_streaming = list(espia.llamadas)

    espia.llamadas.clear()
    await ChatService().chat_with_info(messages=MENSAJES, user_id=BOB)
    sin_streaming = list(espia.llamadas)

    assert sin_streaming == con_streaming, (
        "un parámetro de transporte cambia si el modelo recibe herramientas: "
        f"la rama que emite usó {con_streaming} y la que acumula usó {sin_streaming}"
    )


@pytest.mark.asyncio
async def test_las_dos_ramas_devuelven_el_mismo_texto(espia):
    texto_streaming = await _streaming(espia)
    texto_directo, _ = await ChatService().chat_with_info(messages=MENSAJES, user_id=BOB)

    assert texto_directo == texto_streaming
    assert texto_streaming != "", (
        "las dos ramas coinciden en no responder nada; la comparación no diría nada"
    )


@pytest.mark.asyncio
async def test_la_rama_no_streaming_no_tiene_implementacion_propia(espia, monkeypatch):
    """Dos implementaciones se desincronizan; por eso tiene que haber una."""
    servicio = ChatService()
    usadas: list[dict] = []

    async def _chat_espia(**kwargs):
        usadas.append(kwargs)
        yield "delegado"

    monkeypatch.setattr(servicio, "chat", _chat_espia)

    texto, _ = await servicio.chat_with_info(
        messages=MENSAJES, user_id=ALICE, allow_web=True, mode="reasoning"
    )

    assert texto == "delegado"
    assert usadas, "`chat_with_info` sigue teniendo su propio camino al proveedor"
    # Y lo que recibe no se pierde por el camino: `allow_web` era el ejemplo que
    # la docstring reconocía aceptar «por simetría» y no usar.
    assert usadas[0]["allow_web"] is True
    assert usadas[0]["mode"] == "reasoning"


@pytest.mark.asyncio
async def test_las_dos_ramas_niegan_igual_un_destino_sin_autorizar(monkeypatch):
    """MOLCHAT-NET-005 no puede depender de por dónde entró la petición."""
    proveedor = _ProveedorEspia()
    proveedor.id = "ollama"
    proveedor.config = ProviderConfig(base_url="http://servidor-ajeno.example:11434")

    registro = ProviderRegistry()
    from services.ai import chat_service as modulo
    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: proveedor)

    servicio = ChatService()

    avisos = [
        t
        async for t in servicio.chat(messages=MENSAJES, user_id=ALICE)
        if t.startswith("__WARNING__:")
    ]
    texto, info = await servicio.chat_with_info(messages=MENSAJES, user_id=ALICE)

    assert avisos, "la rama de streaming dejó de negar el destino"
    assert texto == ""
    assert info.warning == avisos[0][len("__WARNING__:"):]
    assert proveedor.llamadas == [], "el turno salió por una de las dos ramas"


@pytest.mark.asyncio
async def test_fallback_used_describe_el_turno_y_no_la_conversacion(espia):
    """`fallback_provider` se marcaba y no se limpiaba nunca.

    Si el turno de ayer cayó al motor local, el de hoy no puede seguir
    declarándose como respondido por un respaldo: es una afirmación falsa sobre
    de dónde salió esta respuesta.
    """
    servicio = ChatService()

    await servicio.chat_with_info(messages=MENSAJES, user_id=ALICE)
    conv = servicio.get_conversation(user_id=ALICE)
    conv.fallback_provider = "local"

    _, info = await servicio.chat_with_info(messages=MENSAJES, user_id=ALICE)

    assert info.fallback_used is False
    assert servicio.get_conversation(user_id=ALICE).fallback_provider is None


# ── D-05: sin identidad no se lee el historial de nadie ──────────────────


@pytest.mark.asyncio
async def test_la_consulta_de_evaluaciones_sin_identidad_se_abstiene():
    """Antes caía a `get_or_create_test_user()` y contestaba igual.

    Devolver el historial de una cuenta sintética compartida como si fuera el
    tuyo es peor que no contestar: es una respuesta falsa que parece correcta.
    """
    from services.ai.tools.evaluation_tools import query_evaluation_details

    respuesta = await query_evaluation_details(user_id="")

    assert "no trae identidad" in respuesta
    assert "no voy a leer el de otra" in respuesta


@pytest.mark.asyncio
async def test_el_historial_de_sesion_sin_identidad_se_abstiene():
    from services.ai.tools.session_tools import query_history

    respuesta = await query_history(user_id="")

    assert "no trae identidad" in respuesta


def test_ninguna_herramienta_resuelve_a_una_cuenta_de_prueba():
    """El guardarraíl: que no vuelva por otra puerta."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "services" / "ai"
    culpables = [
        str(f.relative_to(raiz))
        for f in raiz.rglob("*.py")
        if "get_or_create_test_user(" in f.read_text(encoding="utf-8")
    ]

    assert culpables == [], f"vuelven a resolver a la cuenta de prueba: {culpables}"
