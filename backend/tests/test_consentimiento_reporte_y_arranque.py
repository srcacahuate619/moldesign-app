"""MOLCHAT-NET-006 — los dos caminos a la red que no pasaban por la puerta.

MOLCHAT-NET-005 puso consentimiento por cuenta y destino para el **turno de
MolChat**, y `services/ai/red.py` lo hizo para las **herramientas**. Quedaban
dos salidas fuera:

* el **reporte IA** de una evaluación (`services/ai/interpreter.py`), con su
  cadena de respaldo local → Ollama → Claude → Gemini. Lo que sale por ahí es el
  SMILES de la molécula, el receptor, la afinidad y, si la cuenta tiene memoria,
  un extracto de sus evaluaciones anteriores;
* la **sonda de arranque** (`/ai/startup`), que es peor porque es la primera:
  el `health_check` de un proveedor cloud manda un turno real a `api.anthropic.com`,
  a Google o al `base_url` de OpenAI, y corría al montarse `ChatPanel`, sin
  cuenta, sin mirar el consentimiento y sin mirar `MOLDESIGN_OFFLINE`.

Y una tercera grieta, en la puerta que sí existía: `MOLDESIGN_OFFLINE=1` está
documentado como «niega toda salida aunque haya permiso», pero sólo lo miraba
`red.py`. El proveedor de chat salía igual.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import evaluation_reports
from services.ai import consent, interpreter, provider_config_store as store
from services.ai import startup_detection
from services.ai.providers.base import HealthCheckResult, HealthStatus, ProviderConfig
from services.ai.providers.registry import ProviderRegistry

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())

AJENO = "http://servidor-ajeno.example:11434"
AQUI = "http://localhost:11434"


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("b" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.delenv("MOLDESIGN_OFFLINE", raising=False)
    yield


def _peticion(user_id: str | None = None) -> SimpleNamespace:
    """Lo que `interpreter` lee de una `AIReportRequest`. Duck typing a propósito:
    la puerta se cruza antes de construir el prompt, y el prompt no es lo que se
    está probando."""
    return SimpleNamespace(
        user_id=user_id,
        molecule_smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_name="3F75",
        affinity_kcal=-5.665,
        score_breakdown=SimpleNamespace(
            total_score=61.0, ligand_efficiency=0.41, lipophilic_efficiency=2.1
        ),
        properties=SimpleNamespace(sa_score=1.23),
        hotspots_hit=[],
    )


def _ajustes(**kwargs) -> SimpleNamespace:
    base = {
        "anthropic_api_key": None,
        "anthropic_model": "claude-haiku-4-5-20251001",
        "gemini_api_key": None,
        "ollama_base_url": AQUI,
        "ollama_model": "gemma3:1b",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


# ── El modo offline manda sobre el permiso, también en el chat ───────────


def _destino_ollama(base_url: str):
    return consent.destino_propuesto("ollama", base_url)


def test_el_modo_offline_bloquea_un_destino_ya_autorizado(monkeypatch):
    """La afirmación «este equipo no habla con nadie» valía sólo para las
    herramientas; el proveedor de chat nunca miró el interruptor."""
    destino = _destino_ollama(AJENO)
    consent.otorgar(destino, ALICE)
    assert consent.motivo_de_bloqueo(destino, ALICE) == ""

    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")
    motivo = consent.motivo_de_bloqueo(destino, ALICE)

    assert motivo != "", "el modo offline no detuvo una salida ya consentida"
    assert "offline" in motivo.lower()
    assert "servidor-ajeno.example" in motivo


def test_el_modo_offline_no_estorba_al_camino_local(monkeypatch):
    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")

    assert consent.motivo_de_bloqueo(_destino_ollama(AQUI), ALICE) == ""
    assert consent.motivo_de_bloqueo(_destino_ollama(AQUI), None) == ""


def test_hay_consentimiento_sigue_siendo_el_hecho_guardado(monkeypatch):
    """Las dos preguntas son distintas y conviene que lo sigan siendo: una es
    «¿lo autorizó?», que es un hecho persistido y lo que muestra la interfaz;
    la otra es «¿puede salir ahora?»."""
    destino = _destino_ollama(AJENO)
    consent.otorgar(destino, ALICE)
    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")

    assert consent.hay_consentimiento(destino, ALICE) is True
    assert consent.motivo_de_bloqueo(destino, ALICE) != ""


# ── El reporte IA: la tercera salida ─────────────────────────────────────


def test_el_ollama_de_esta_maquina_no_pide_permiso_para_el_reporte():
    """El valor por defecto es `localhost`: el camino local sigue sin fricción."""
    assert interpreter._bloqueo("ollama", AQUI, None) == ""


def test_el_ollama_de_otra_maquina_si_lo_pide():
    motivo = interpreter._bloqueo("ollama", AJENO, ALICE)
    assert motivo != ""
    assert "servidor-ajeno.example" in motivo


@pytest.mark.asyncio
async def test_el_reporte_no_sale_a_anthropic_sin_permiso(monkeypatch):
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))

    with pytest.raises(interpreter.ReporteBloqueado) as exc:
        await interpreter.generate_claude_report(_peticion(ALICE))

    assert "api.anthropic.com" in str(exc.value)


@pytest.mark.asyncio
async def test_el_reporte_no_sale_a_google_sin_permiso(monkeypatch):
    monkeypatch.setattr(interpreter, "settings", _ajustes(gemini_api_key="falsa"))

    with pytest.raises(interpreter.ReporteBloqueado) as exc:
        await interpreter.generate_gemini_report(_peticion(ALICE))

    assert "generativelanguage.googleapis.com" in str(exc.value)


@pytest.mark.asyncio
async def test_sin_cuenta_el_reporte_tampoco_sale(monkeypatch):
    """El permiso es de alguien, no del proceso. Una evaluación sin dueño
    conocido no autoriza nada."""
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))

    with pytest.raises(interpreter.ReporteBloqueado):
        await interpreter.generate_claude_report(_peticion(None))


@pytest.mark.asyncio
async def test_el_permiso_de_una_cuenta_no_sirve_para_otra(monkeypatch):
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))
    consent.otorgar(consent.destino_propuesto("claude", None), ALICE)

    assert interpreter._bloqueo("claude", None, ALICE) == ""
    with pytest.raises(interpreter.ReporteBloqueado):
        await interpreter.generate_claude_report(_peticion(BOB))


@pytest.mark.asyncio
async def test_el_orquestador_no_convierte_el_bloqueo_en_un_hueco(monkeypatch):
    """Devolver `None` contaría como «no se pudo generar» lo que en realidad fue
    «no te dejé mandarlo». Es el error que ya costó cuatro componentes aquí."""
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))

    async def sin_local(_req):
        return None

    monkeypatch.setattr(interpreter, "generate_local_report", sin_local)

    with pytest.raises(interpreter.ReporteBloqueado):
        await interpreter.generate_ai_report(_peticion(ALICE))


@pytest.mark.asyncio
async def test_un_destino_bloqueado_no_corta_la_cadena(monkeypatch):
    """Bloqueado no es caído: si el siguiente proveedor sí está autorizado, el
    reporte se genera."""
    monkeypatch.setattr(
        interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa", gemini_api_key="falsa")
    )

    async def sin_local(_req):
        return None

    async def gemini_contesta(_req):
        return "un párrafo."

    monkeypatch.setattr(interpreter, "generate_local_report", sin_local)
    monkeypatch.setattr(interpreter, "generate_gemini_report", gemini_contesta)

    assert await interpreter.generate_ai_report(_peticion(ALICE)) == "un párrafo."


@pytest.mark.asyncio
async def test_el_camino_local_no_pide_permiso_a_nadie(monkeypatch):
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))

    async def local_contesta(_req):
        return "un párrafo escrito aquí."

    monkeypatch.setattr(interpreter, "generate_local_report", local_contesta)

    assert await interpreter.generate_ai_report(_peticion(None)) == "un párrafo escrito aquí."


@pytest.mark.asyncio
async def test_el_envoltorio_seguro_no_se_traga_el_bloqueo(monkeypatch):
    """`safe_generate_ai_report` existe para que un fallo del proveedor no tumbe
    el endpoint. Un `except Exception` ahí convertía el único mensaje accionable
    del módulo en el `None` que la interfaz muestra como «no se pudo generar»."""
    monkeypatch.setattr(interpreter, "settings", _ajustes(anthropic_api_key="sk-falsa"))

    async def sin_local(_req):
        return None

    monkeypatch.setattr(interpreter, "generate_local_report", sin_local)

    with pytest.raises(interpreter.ReporteBloqueado):
        await interpreter.safe_generate_ai_report(_peticion(ALICE))


@pytest.mark.asyncio
async def test_el_sse_manda_lo_mismo_que_el_sincrono(monkeypatch):
    """No es un camino distinto por ser SSE."""
    from services.ai import local_llm

    monkeypatch.setattr(local_llm, "is_local_llm_available", lambda: False)
    monkeypatch.setattr(interpreter, "settings", _ajustes(ollama_base_url=AJENO))

    with pytest.raises(interpreter.ReporteBloqueado):
        async for _ in interpreter.stream_ollama_report(_peticion(ALICE)):
            pass


# ── El contrato HTTP del reporte ─────────────────────────────────────────


class _Base:
    def __init__(self, fila):
        self.fila = fila

    async def get(self, _modelo, _id):
        return self.fila


class _RepositorioEspia:
    def __init__(self, resultado):
        self.resultado = resultado
        self.persistido: list[str] = []

    async def get_evaluation_result(self, _molecule_id):
        return self.resultado

    async def get_or_create_test_user(self):
        return SimpleNamespace(id=uuid.uuid4())

    async def upsert_evaluation_result(self, *, molecule_id, ai_report):
        self.persistido.append(ai_report)


@pytest.mark.asyncio
async def test_el_endpoint_responde_409_y_no_cachea_el_aviso(monkeypatch):
    """409 y no 500: no falló nada. Y sobre todo no se persiste — el reporte se
    sirve desde `ai_report` en cuanto existe, así que guardar aquí el aviso
    dejaría a esta molécula sin reporte incluso después de autorizar."""
    dueño = uuid.uuid4()
    fila = SimpleNamespace(
        user_id=dueño, smiles="CCO", target_id=uuid.uuid4(),
        mutation_type=None, name="3F75", hotspots=[],
    )
    repo = _RepositorioEspia(SimpleNamespace(ai_report=None))
    monkeypatch.setattr(evaluation_reports, "Repository", lambda _db: repo)

    from services.ai import report_context

    monkeypatch.setattr(
        report_context, "build_evaluation_report_request", lambda **kw: _peticion(str(dueño))
    )

    async def bloquea(_req):
        raise interpreter.ReporteBloqueado("saldría hacia api.anthropic.com")

    monkeypatch.setattr(interpreter, "safe_generate_ai_report", bloquea)

    with pytest.raises(HTTPException) as exc:
        await evaluation_reports.generate_ai_report_endpoint.__wrapped__(
            uuid.uuid4(),
            request=SimpleNamespace(),
            current_user=SimpleNamespace(id=dueño),
            db=_Base(fila),
        )

    assert exc.value.status_code == 409
    assert "api.anthropic.com" in str(exc.value.detail)
    assert repo.persistido == [], "el aviso de consentimiento quedó cacheado como reporte"


# ── La sonda de arranque ─────────────────────────────────────────────────


class _NubeEspia:
    """Un proveedor cloud que anota cuántas veces alguien lo sondeó de verdad."""

    id = "claude"
    name = "Claude"

    def __init__(self):
        self.config = ProviderConfig(api_key="sk-falsa", model="m")
        self.sondas = 0

    def validate_config(self):
        return True, ""

    async def health_check(self):
        self.sondas += 1
        return HealthCheckResult(status=HealthStatus.OK, message="ok", latency_ms=1.0)


@pytest.fixture
def nube_espia(monkeypatch):
    espia = _NubeEspia()
    registro = ProviderRegistry()
    registro.register(espia)
    monkeypatch.setattr(startup_detection, "get_provider_registry", lambda: registro)
    return espia


@pytest.mark.asyncio
async def test_el_arranque_no_sondea_un_destino_sin_autorizar(nube_espia):
    estado = await startup_detection.detect_startup_mode(ALICE)

    assert nube_espia.sondas == 0, (
        "la sonda de arranque llamó a api.anthropic.com antes de que nadie lo autorizara"
    )
    assert estado["mode"] == "auto_start"
    assert estado["auto_start_local"] is True
    assert [f["status"] for f in estado["failed_providers"]] == ["sin_consentimiento"]


@pytest.mark.asyncio
async def test_sin_sesion_el_arranque_tampoco_sondea(nube_espia):
    await startup_detection.detect_startup_mode(None)

    assert nube_espia.sondas == 0


@pytest.mark.asyncio
async def test_un_destino_no_consultado_no_se_cuenta_como_clave_sin_saldo(nube_espia):
    """Era el mensaje que salía: «Las claves de API no tienen saldo disponible».
    De un destino que no se preguntó, eso es una afirmación inventada."""
    estado = await startup_detection.detect_startup_mode(ALICE)

    assert "saldo" not in estado["reason"]
    assert "autorizado" in estado["reason"]


@pytest.mark.asyncio
async def test_con_permiso_el_arranque_si_sondea(nube_espia):
    consent.otorgar(consent.destino_de(nube_espia), ALICE)

    estado = await startup_detection.detect_startup_mode(ALICE)

    assert nube_espia.sondas == 1, "la cuenta autorizó el destino y aun así no se consultó"
    assert [w["id"] for w in estado["working_providers"]] == ["claude"]
    assert estado["mode"] == "manual_only"


@pytest.mark.asyncio
async def test_el_modo_offline_apaga_la_sonda(nube_espia, monkeypatch):
    consent.otorgar(consent.destino_de(nube_espia), ALICE)
    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")

    await startup_detection.detect_startup_mode(ALICE)

    assert nube_espia.sondas == 0


@pytest.mark.asyncio
async def test_sin_clave_el_mensaje_sigue_siendo_el_de_siempre(monkeypatch):
    """La ruta más común no cambia: sin clave configurada no hay nada que
    sondear, y el arranque local se explica igual que antes."""

    class _SinClave(_NubeEspia):
        def validate_config(self):
            return False, "Falta la clave de API"

    espia = _SinClave()
    espia.config = ProviderConfig(api_key="", model="m")
    registro = ProviderRegistry()
    registro.register(espia)
    monkeypatch.setattr(startup_detection, "get_provider_registry", lambda: registro)

    estado = await startup_detection.detect_startup_mode(ALICE)

    assert espia.sondas == 0
    assert estado["mode"] == "auto_start"
    assert "No se configuró ninguna clave de API" in estado["reason"]
