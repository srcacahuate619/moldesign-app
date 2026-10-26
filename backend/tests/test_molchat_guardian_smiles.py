"""El guardián de SMILES de la ruta nativa ejecuta las herramientas que no llevan SMILES.

EL FALLO QUE VIGILA. El guardián de la ruta nativa (la del modelo local)
exigía `smiles` a TODAS las herramientas: las que no lo llevan
—`query_history`, `check_docking_status`, `query_molgraph`…— y
`compare_molecules`, que lo lleva como `smiles_a`/`smiles_b`, nunca se
ejecutaban por esa ruta. Medido el 2026-10-10 con el arnés de herramientas.
"""
from __future__ import annotations

import pytest

from services.ai.chat_service import validar_smiles_de_la_llamada
from services.ai.tool_registry import ToolDef
from tests.conftest import rdkit_available

pytestmark = pytest.mark.skipif(not rdkit_available(), reason="RDKit no disponible")


def _tool(**parametros) -> ToolDef:
    return ToolDef(name="t", description="", parameters=parametros)


def test_una_herramienta_sin_smiles_se_ejecuta():
    args, error = validar_smiles_de_la_llamada(_tool(target={"required": False}), {"target": "5-HT1A"})
    assert error is None and args == {"target": "5-HT1A"}


def test_los_smiles_con_otro_nombre_se_validan_y_canonizan():
    tool = _tool(smiles_a={"required": True}, smiles_b={"required": True})
    args, error = validar_smiles_de_la_llamada(tool, {"smiles_a": "OCC", "smiles_b": "C1=CC=CC=C1"})
    assert error is None
    assert args == {"smiles_a": "CCO", "smiles_b": "c1ccccc1"}


def test_falta_un_smiles_obligatorio():
    args, error = validar_smiles_de_la_llamada(_tool(smiles={"required": True}), {"n": "5"})
    assert error and "falta el SMILES" in error


def test_un_smiles_invalido_no_se_ejecuta_aunque_sea_opcional():
    args, error = validar_smiles_de_la_llamada(_tool(smiles={"required": False}), {"smiles": "C1CC(("})
    assert error and "SMILES invalido" in error


def test_las_herramientas_reales_sin_smiles_obligatorio_pasan_el_guardian():
    """Las del registro real que no declaran un SMILES obligatorio no se bloquean sin él."""
    from services.ai.tool_registry import get_tool_registry
    from api.routers.ai import _bootstrap_tools

    _bootstrap_tools()
    sin_smiles = [
        t for t in get_tool_registry().list_all()
        if not any("smiles" in k and (v or {}).get("required") for k, v in t.parameters.items())
    ]
    nombres = {t.name for t in sin_smiles}
    assert {"query_history", "check_docking_status", "query_molgraph"} <= nombres
    for t in sin_smiles:
        assert validar_smiles_de_la_llamada(t, {})[1] is None, t.name


# ── El turno: el modelo local pide una herramienta sin SMILES ─────────

class _ModeloLocalEspia:
    id = "local"
    name = "Local (espía)"

    def __init__(self, llamada: dict):
        from services.ai.providers.base import ProviderConfig
        self.config = ProviderConfig(model="m", max_tokens=128)
        self.llamada = llamada

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        yield "Listo."

    async def chat_with_tools(self, *args, **kwargs):
        return {"content": "", "tool_calls": [self.llamada]}


async def _turno(tmp_path, monkeypatch, llamada: dict, herramienta) -> str:
    import uuid

    from services.ai import chat_service as modulo
    from services.ai import memory_store
    from services.ai import provider_config_store as store
    from services.ai import tool_registry
    from services.ai.intent_classifier import Intent
    from services.ai.providers.registry import ProviderRegistry

    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")

    espia = _ModeloLocalEspia(llamada)
    registro = ProviderRegistry()
    registro.register(espia)
    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: espia)

    herramientas = tool_registry.ToolRegistry()
    herramientas.register(herramienta)
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: herramientas)
    # Una intención que deja decidir al modelo: ni ejecuta una herramienta
    # determinista ni se las quita.
    monkeypatch.setattr(modulo, "classify_intent", lambda msg: Intent("abierta"))

    servicio = modulo.ChatService()
    tokens = [t async for t in servicio.chat(
        messages=[{"role": "user", "content": "¿qué corridas hice esta semana?"}],
        user_id=str(uuid.uuid4()),
    )]
    return "".join(t for t in tokens if not t.startswith("__WARNING__:"))


@pytest.mark.asyncio
async def test_el_modelo_local_ejecuta_una_herramienta_sin_smiles(tmp_path, monkeypatch):
    """Lo que no pasaba: `query_history` y compañía acababan en «no se pudo extraer un SMILES»."""
    ejecuciones = []

    async def historial(n: str = "5", user_id: str = "") -> str:
        ejecuciones.append(n)
        return "3 corridas esta semana."

    herramienta = ToolDef(
        name="historial_de_prueba", description="historial", offline=True,
        parameters={"n": {"type": "string", "required": False}}, fn=historial,
    )
    texto = await _turno(tmp_path, monkeypatch, {"name": "historial_de_prueba", "arguments": {"n": "3"}},
                         herramienta)
    assert ejecuciones == ["3"]
    assert "3 corridas esta semana." in texto
    assert "SMILES" not in texto


@pytest.mark.asyncio
async def test_el_modelo_local_no_ejecuta_un_smiles_inventado(tmp_path, monkeypatch):
    """El guardián sigue parando un SMILES que RDKit rechaza."""
    ejecuciones = []

    async def propiedades(smiles: str) -> str:
        ejecuciones.append(smiles)
        return "MW 46"

    herramienta = ToolDef(
        name="propiedades_de_prueba", description="propiedades", offline=True,
        parameters={"smiles": {"type": "string", "required": True}}, fn=propiedades,
    )
    texto = await _turno(tmp_path, monkeypatch,
                         {"name": "propiedades_de_prueba", "arguments": {"smiles": "C1CC(("}}, herramienta)
    assert ejecuciones == []
    assert "SMILES invalido" in texto
