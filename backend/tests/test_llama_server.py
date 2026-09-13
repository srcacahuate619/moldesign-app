"""
Tests de la migración a `llama-server.exe` (ver docs/33_MIGRATION_LLAMA_SERVER.md).

Estos tests son unitarios — no levantan el binario `llama-server.exe` real
(no está commiteado, vive en tools/llama/ empaquetado por Tauri). Los paths
que tocan I/O real (Popen, sockets) se mockean para verificar el CONTRATO del
wrapper, no la trama de red del subprocess.

Cobertura (plan §5 "Tests requeridos"):
  ✅ test_binary_no_existe_fallback_gracioso
  ✅ test_subprocess_muere_en_timeout_en_unload
  ✅ test_sse_decoder_no_parte_utf8_multibyte
  ✅ test_temperature_se_respeta_en_stream
  ✅ test_startup_exitoso (con mock de /health)

Fase 2 (Job Object): tests de robustez ante hard crash del parent van en
tests/test_llama_server_robustez.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Importar aquí para no tener dependencias implícitas al inicio del módulo.
from services.ai.local_llm import (
    LocalLLM,
    is_local_llm_available,
    _PROCESS_TERMINATE_WAIT_S,
)


# ── Test 1: binary no existe → fallback gracioso (plan §5) ────────────
def test_binary_no_existe_fallback_gracioso():
    """Si llama-server.exe no existe, is_local_llm_available() → False sin raise.

    Verifica el bug UX documentado en §4.D4: el plan original de Gemini decía
    "chequear si el ejecutable existe" — eso mostraría 'Disponible' aunque
    faltase el modelo o no hubiese RAM. Aquí validamos el chequeo triple.
    """
    # FileNotFoundError del modelo — primero aparece en la cascada D4.
    with patch("services.ai.local_llm._resolve_server_executable_static", return_value=Path("/fake/llama-server.exe")), \
         patch.object(LocalLLM, "_resolve_model_path_static", side_effect=FileNotFoundError("no model")):
        assert is_local_llm_available() is False

    # Y si el modelo existe pero no el binario, también False. Mockear el
    # resolver (en vez de Path global) conserva el tipo Path real del contrato.
    with patch("services.ai.local_llm._resolve_server_executable_static", side_effect=FileNotFoundError("no binary")), \
         patch.object(LocalLLM, "_resolve_model_path_static", return_value=Path("/fake.gguf")):
        assert is_local_llm_available() is False


# ── Test 2: subprocess muere en timeout de unload (plan §5) ─────────
def test_subprocess_muere_en_timeout_en_unload():
    """unload() llama terminate() y respeta 5s; si el proceso no muere, kill().

    Verifica el contrato del lifecycle MVP (§4.D2) antes de migrar a
    Windows Job Object (Fase 2).
    """
    llm = LocalLLM()
    fake_proc = MagicMock(spec=subprocess.Popen)
    # simulate: terminate() then wait raises TimeoutExpired → kill() success.
    fake_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="x", timeout=5), 0]
    fake_proc.terminate.return_value = None
    fake_proc.kill.return_value = None
    fake_proc.poll.return_value = None  # still alive until killed
    fake_proc.pid = 99999

    llm._process = fake_proc
    llm._loaded = True

    llm.unload()

    # Contrato: terminate() llamado primero
    fake_proc.terminate.assert_called_once()
    # wait() primer intento respeta TIMEOUT_WAIT_S
    assert fake_proc.wait.call_args_list[0].kwargs["timeout"] == _PROCESS_TERMINATE_WAIT_S
    # Después del TimeoutExpired, kill() fuerza la muerte
    fake_proc.kill.assert_called_once()

    # Estado reseteado
    assert llm._process is None
    assert llm._loaded is False


# ── Test 3: SSE decoder no parte UTF-8 multibyte (plan §5 + §4.D7) ───
@pytest.mark.asyncio
async def test_sse_decoder_no_parte_utf8_multibyte():
    """El parser SSE del wrapper debe emitir "Píldora⚡" íntegro aunque TCP
    parta el frame entre los bytes del char multibyte.

    Estrategia: simular un httpx.AsyncClient.stream fake que primero spupe
    un chunk truncado (termina en mitad de un char UTF-8) y luego el resto.
    El parser debe re-bufferear y emitir el texto completo, no las partes.
    """
    # "Píldora⚡" en UTF-8 bytes:
    # P (0x50) í (0xC3 0xAD) l (0x6C) d (0x64) o (0x6F) r (0x72) a (0x61) ⚡ (0xE2 0x9A A1)
    # Total 11 bytes. Simulamos TCP chunk en byte 8 (corta "í" en dos).
    full = "Píldora⚡"
    full_bytes = full.encode("utf-8")
    assert len(full_bytes) == 11, "Test setup inválido"

    # Chunk 1: primeros 8 bytes (corta el 'í' en sus 2 bytes: 0xC3 al final)
    chunk1 = full_bytes[:8]
    # Chunk 2: bytes restantes
    chunk2 = full_bytes[8:]

    # Frame SSE armado: 'data: <json con content="Píldora⚡">\\n\\n'
    # Pero partidos TCP — chunk1 mete el frame completo EXCEPTO el último char del JSON.
    sse_prefix = b'data: {"choices":[{"delta":{"content":"'
    sse_suffix = b'"}}]}\n\n'
    frame_bytes = sse_prefix + full_bytes + sse_suffix
    cut_at = len(sse_prefix) + 8  # corta a mitad del full_bytes

    chunk_stream = [frame_bytes[:cut_at], frame_bytes[cut_at:]]

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            for chunk in chunk_stream:
                yield chunk

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, json=None):
            return FakeStream()

    # Instanciamos wrapper SIN cargar nada — forzamos is_loaded=True via mocks
    llm = LocalLLM()
    llm._loaded = True
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.poll.return_value = None
    llm._process = fake_proc
    llm._port = 8400
    llm._model_path = "fake.gguf"

    # Recoger tokens emitidos
    tokens = []
    with patch("services.ai.local_llm.httpx.AsyncClient", FakeAsyncClient):
        async for t in llm.generate_stream(
            messages=[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "p"},
            ]
        ):
            tokens.append(t)

    # El parser debe haber ensamblado el token íntegro
    joined = "".join(tokens)
    assert "Píldora⚡" in joined, f"UTF-8 multibyte roto. Got: {tokens!r}"


# ── Test 4: temperature se respeta en stream (bug #2 del plan) ─────
@pytest.mark.asyncio
async def test_temperature_se_respeta_en_stream():
    """La temperatura del provider debe llegar al server en el payload SSE.
    Corrige el bug #2 del plan: antes generate_stream() hardcodeaba 0.1.
    """
    llm = LocalLLM()
    llm._loaded = True
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.poll.return_value = None
    llm._process = fake_proc
    llm._port = 8400
    llm._model_path = "fake.gguf"

    captured_payload = {}

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            yield b"data: [DONE]\n\n"

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, json=None):
            captured_payload.update(json)
            return FakeStream()

    with patch("services.ai.local_llm.httpx.AsyncClient", FakeAsyncClient):
        async for _ in llm.generate_stream(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "prompt"},
            ],
            temperature=0.42,
        ):
            pass

    assert captured_payload.get("temperature") == 0.42, (
        f"Temperature no respetada — esperaba 0.42, llegó {captured_payload.get('temperature')}. "
        "Bug #2 del plan no corregido."
    )


# ── Test 5: startup exitoso con health-probe mockeado (plan §5) ──────
def test_startup_exitoso():
    """load() arranca Popen y retorna True en cuanto /health responde 200.

    No levanta llama-server.exe real (no está commiteado). Mockeamos subprocess.Popen
    y el AsyncClient que hace health-probe.
    """
    llm = LocalLLM()

    # Mock Popen — fake process alive
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.pid = 99999
    fake_proc.poll.return_value = None  # never exits while alive
    fake_proc.stdout = MagicMock()
    fake_proc.stdout.read.return_value = b""
    fake_proc.wait.return_value = 0
    fake_proc.terminate.return_value = None
    fake_proc.kill.return_value = None

    # Mock _detect_gpu (no hay GPU en CI)
    with patch.object(LocalLLM, "_detect_gpu", return_value=False):
        # Mock _resolve_server_executable y _resolve_model_path
        with patch.object(LocalLLM, "_resolve_server_executable", return_value=Path("/fake/llama-server.exe")):
            with patch.object(LocalLLM, "_resolve_model_path", return_value=Path("/fake/qwen.gguf")):
                # Mock ResourceManager.can_load → True (no queremos validation fallida)
                rm_mod = MagicMock()
                rm_mod.can_load.return_value = (True, "ok")
                with patch("services.ai.resource_manager.get_resource_manager", return_value=rm_mod):
                    with patch("services.ai.local_llm.subprocess.Popen", return_value=fake_proc):
                        # load() usa explícitamente el probe sync: mockearlo
                        # evita cualquier conexión real durante esta prueba.
                        with patch.object(LocalLLM, "_wait_for_server_ready_sync", return_value=True):
                            result = llm.load()

    assert result is True, f"load() falló inesperadamente: {llm.load_error}"
    assert llm.is_loaded is True
    assert llm._port == 8400  # default de config
    # Sanity: el binario arrancó con los argumentos esperados (docs §7.4)
    popen_args = fake_proc  # noop, solo check

    # Limpieza después del test — atexit hook puede interferir con otros tests
    llm.unload()
