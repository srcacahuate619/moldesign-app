"""MolChat: el bloque de evidencia declara qué es y dónde acaba.

EL FALLO (medido en la cápsula 5 el 2026-10-10 y reproducido el 2026-10-11 con el
servicio real y un proveedor falso). «calcula las propiedades de la aspirina» salía en
blanco en la interfaz. Con un nombre conocido, `chat_service` escribía su propio bloque,
`compute_properties (aspirina): …`, sin la clase ni la fuente que pide MOLCHAT-AUD-01, y
la respuesta determinista llegaba pegada a esa línea: «…Rings: 1Propiedades de
aspirina:». Nada separaba la evidencia de la respuesta, así que la interfaz no podía
saber dónde acababa una y empezaba la otra (`separarEvidencia`, en
`frontend/components/ai/BloqueDeEvidencia.tsx`, las descartaba las dos).

Ahora el bloque lo escribe siempre `format_tool_results`, con la molécula como
`etiqueta`, y todo bloque que va al flujo se cierra con `FIN_DE_EVIDENCIA`.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from services.ai.tool_registry import FIN_DE_EVIDENCIA, format_tool_results
from tests.conftest import rdkit_available

pytestmark = pytest.mark.skipif(not rdkit_available(), reason="RDKit no disponible")


class _ModeloEspia:
    id = "local"
    name = "Local (espía)"

    def __init__(self):
        from services.ai.providers.base import ProviderConfig
        self.config = ProviderConfig(model="m", max_tokens=128)
        self.llamadas = 0

    def validate_config(self):
        return True, ""

    async def chat(self, *args, **kwargs):
        self.llamadas += 1
        yield "Respuesta redactada por el modelo."

    async def chat_with_tools(self, *args, **kwargs):
        self.llamadas += 1
        return {"content": "Respuesta redactada por el modelo.", "tool_calls": []}


@pytest.fixture()
def turno(tmp_path, monkeypatch):
    from api.routers.ai import _bootstrap_tools
    from services.ai import chat_service as modulo
    from services.ai import memory_store
    from services.ai import provider_config_store as store
    from services.ai.providers.registry import ProviderRegistry

    _bootstrap_tools()
    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")

    espia = _ModeloEspia()
    registro = ProviderRegistry()
    registro.register(espia)
    monkeypatch.setattr(modulo, "get_provider_registry", lambda: registro)
    monkeypatch.setattr(registro, "resolve_for_user", lambda pid, uid, her=False: espia)

    async def correr(frase: str) -> str:
        servicio = modulo.ChatService()
        tokens = [t async for t in servicio.chat(
            messages=[{"role": "user", "content": frase}],
            user_id=str(uuid.uuid4()),
        )]
        return "".join(t for t in tokens if not t.startswith("__WARNING__:"))

    correr.espia = espia
    return correr


def _partes(texto: str) -> tuple[str, str]:
    assert texto.count(FIN_DE_EVIDENCIA) == 1, texto
    antes, despues = texto.split(FIN_DE_EVIDENCIA)
    return antes, despues


@pytest.mark.asyncio
async def test_con_nombre_el_bloque_declara_clase_fuente_y_molecula(turno):
    texto = await turno("calcula las propiedades de la aspirina")
    evidencia, _ = _partes(texto)

    assert re.search(
        r"^\[cálculo · RDKit[^\]]*\] compute_properties \(aspirina\): MW: 180\.2 Da",
        evidencia, re.MULTILINE,
    ), evidencia


@pytest.mark.asyncio
async def test_la_respuesta_determinista_va_despues_del_cierre(turno):
    texto = await turno("calcula las propiedades de la aspirina")
    evidencia, respuesta = _partes(texto)

    assert "Propiedades de aspirina:" not in evidencia
    assert respuesta.lstrip("\n").startswith("Propiedades de aspirina:\n- MW: 180.2")
    # El cierre va en su propia línea: nada se le pega delante ni detrás.
    assert f"\n{FIN_DE_EVIDENCIA}\n" in texto
    assert turno.espia.llamadas == 0


@pytest.mark.asyncio
async def test_una_comparacion_por_nombre_lleva_las_dos_moleculas(turno):
    texto = await turno("compara la aspirina con el ibuprofeno")
    evidencia, respuesta = _partes(texto)

    assert "] compare_molecules (A=aspirina | B=ibuprofeno): Comparación:" in evidencia
    assert "MW: A=180.2 | B=206.3" in evidencia
    assert respuesta.lstrip("\n").startswith("Comparación entre aspirina y ibuprofeno:")
    assert turno.espia.llamadas == 0


@pytest.mark.asyncio
async def test_lo_que_redacta_el_modelo_tambien_va_despues_del_cierre(turno):
    # Sin nombre conocido no hay respuesta determinista: la escribe el modelo.
    texto = await turno("calcula las propiedades de CCO")
    evidencia, respuesta = _partes(texto)

    assert "] compute_properties: MW: 46.1 Da" in evidencia
    assert "Respuesta redactada por el modelo." in respuesta
    assert "Respuesta redactada por el modelo." not in evidencia


def test_el_guardian_sigue_leyendo_la_molecula_de_cada_valor():
    from services.ai.chat_service import ChatService

    texto = format_tool_results([
        {"tool": "compute_properties", "result": "MW: 180.2 Da, LogP: 1.31", "etiqueta": "aspirina"},
        {"tool": "compute_properties", "result": "MW: 206.3 Da, LogP: 3.07", "etiqueta": "ibuprofeno"},
    ])
    valores = ChatService._parse_named_tool_values(texto)

    assert valores["aspirina"]["molecular_weight"] == [180.2]
    assert valores["ibuprofeno"]["molecular_weight"] == [206.3]


def test_sin_etiqueta_el_formato_no_cambia():
    texto = format_tool_results([{"tool": "compute_properties", "result": "MW: 46.1 Da"}])
    assert texto.endswith("] compute_properties: MW: 46.1 Da")


# ── Guardián: todo bloque que se emite lleva su cierre ─────────────────

CHAT_SERVICE = Path(__file__).resolve().parents[1] / "services" / "ai" / "chat_service.py"
_EMISION = re.compile(r"^\s*yield\b.*\b(_rtxt|result_text)\b.*$", re.MULTILINE)


def _emisiones_sin_cierre(fuente: str) -> list[str]:
    return [m.group(0).strip() for m in _EMISION.finditer(fuente) if "_al_flujo(" not in m.group(0)]


def test_el_guardian_ve_una_emision_sin_cierre():
    muestra = (
        "        yield _al_flujo(_rtxt)\n"
        '        yield f"\\n\\n{_rtxt}"\n'
        '                yield f"\\n\\n🔧 {result_text}"\n'
        "        yield r\n"
    )
    assert _emisiones_sin_cierre(muestra) == ['yield f"\\n\\n{_rtxt}"', 'yield f"\\n\\n🔧 {result_text}"']


def test_todo_bloque_que_va_al_flujo_lleva_su_cierre():
    fuente = CHAT_SERVICE.read_text(encoding="utf-8")
    assert _EMISION.search(fuente), "el guardián no encuentra ninguna emisión: el patrón ya no casa"
    assert _emisiones_sin_cierre(fuente) == []
