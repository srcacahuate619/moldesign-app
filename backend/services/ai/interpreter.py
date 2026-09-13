"""
services/ai/interpreter.py

Interpretacion narrativa de resultados usando IA.

Proveedores (en orden de fallback):
  1. Local LLM (llama-server.exe, Qwen2.5 1.5B) — default, offline, gratis
  2. Ollama (si esta instalado) — mas rapido, mas modelos
  3. Claude (Anthropic API) — mejor calidad
  4. Gemini (Google API)
  5. OpenAI-compatible (configurable)

Regla: la IA no calcula quimica ni altera numeros. Solo transforma
resultados ya calculados en una explicacion farmacologica prudente.

Los cuatro escalones de arriba son cuatro destinos, y tres de ellos pueden estar
fuera de esta máquina. Hasta MOLCHAT-NET-006 ninguno pasaba por la puerta de
`services/ai/consent.py`: el reporte IA era el tercer camino a la red —después
del turno de MolChat y de las herramientas de `services/ai/red.py`— y el único
sin autorizar. Lo que salía por él no es poco: el SMILES de la molécula, el
receptor, la afinidad y, cuando la cuenta tiene memoria, un extracto de sus
evaluaciones anteriores.
"""

from __future__ import annotations

import httpx
import anthropic

from core.config import get_settings
from core.models import AIReportRequest
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

import json


class ReporteBloqueado(RuntimeError):
    """El reporte habría salido de esta máquina sin que la cuenta lo autorizara.

    Se distingue de «no disponible» a propósito. Devolver `None` aquí sería el
    mismo error que ya costó cuatro componentes en este árbol: un fallo con
    causa accionable convertido en un hueco silencioso.

    Y sobre todo: lo que se responde por este camino **no se persiste**. El
    reporte se cachea en `ai_report` y se sirve desde ahí para siempre; guardar
    un aviso de consentimiento en ese campo dejaría a la molécula sin reporte
    incluso después de autorizar el destino.
    """


def _bloqueo(provider_id: str, base_url: str | None, user_id: str | None) -> str:
    """Qué impide mandar este reporte hacia ese proveedor, o `""` si nada.

    Misma puerta que el turno de MolChat, y el destino se calcula igual que
    allí: `ollama` apuntado a otra máquina sale de aquí, y apuntado a
    `localhost` —que es el valor por defecto— no. Así el camino local, que es el
    que el §8 pide inequívoco, sigue sin fricción.
    """
    from services.ai.consent import destino_propuesto, motivo_de_bloqueo

    return motivo_de_bloqueo(destino_propuesto(provider_id, base_url), user_id)

def build_ai_messages(request: AIReportRequest, include_memory: bool = True) -> list[dict]:
    smiles = request.molecule_smiles
    receptor = request.target_name
    score = round(request.score_breakdown.total_score, 1) if request.score_breakdown else "N/A"
    afinidad = round(request.affinity_kcal, 2)
    le = round(request.score_breakdown.ligand_efficiency, 3) if request.score_breakdown and request.score_breakdown.ligand_efficiency else "N/A"
    lle = round(request.score_breakdown.lipophilic_efficiency, 2) if request.score_breakdown and request.score_breakdown.lipophilic_efficiency else "N/A"
    sa_score = round(request.properties.sa_score, 2)
    hotspots = request.hotspots_hit if request.hotspots_hit else []

    # ── Inject AI memory context ────────────────────────────────────
    memory_context = ""
    if include_memory and request.user_id:
        # La memoria inyectada es la de la cuenta dueña del reporte. Sin
        # `user_id` no se inyecta nada: `build_context_for_llm` leía el
        # catálogo entero de la máquina, así que el reporte de una cuenta podía
        # compararse con las evaluaciones de otra.
        try:
            from services.ai.memory_store import build_context_for_llm
            memory_context = build_context_for_llm(
                target_pdb=None, max_tokens=3000, user_id=request.user_id
            )
        except ImportError:
            pass

    system_prompt = f"""Eres un experto en quimica medicinal. Escribe un unico parrafo analizando el potencial de la molecula como farmaco contra el receptor {receptor}, basandote ESTRICTAMENTE en el JSON proporcionado.
REGLAS CRITICAS:
1. NUNCA inventes numeros. Usa exactamente los valores del JSON.
2. Si la lista "residuos_clave_alcanzados" esta vacia ([]), DEBES decir explicitamente que la molecula fracaso en tocar los hotspots.
3. No uses saludos, vinetas ni titulos. Escribe un solo parrafo continuo.
4. Puedes comparar con evaluaciones previas del usuario si estan disponibles abajo."""

    data = {
        "molecula": smiles,
        "score_general_sobre_100": score,
        "afinidad_kcal_mol": afinidad,
        "eficiencia_ligando_LE": le,
        "eficiencia_lipofilica_LLE": lle,
        "accesibilidad_sintetica_SA": sa_score,
        "residuos_clave_alcanzados": hotspots,
    }

    user_prompt = f"```json\n{json.dumps(data, indent=2)}\n```"
    if memory_context:
        user_prompt = memory_context + "\n\n---\n\n" + user_prompt

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

def build_ai_prompt(request: AIReportRequest) -> str:
    messages = build_ai_messages(request)
    return messages[0]["content"] + "\n\n" + messages[1]["content"]

async def generate_claude_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Claude (Anthropic)."""
    if not settings.anthropic_api_key:
        return None
    falta = _bloqueo("claude", None, request.user_id)
    if falta:
        raise ReporteBloqueado(falta)
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=800,
            temperature=0.5,
            messages=[{"role": "user", "content": build_ai_prompt(request)}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.warning("Fallo en Anthropic (posible falta de saldo)", error=str(e))
        return None

async def generate_gemini_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Google Gemini 1.5 Flash vía REST API."""
    if not settings.gemini_api_key:
        log.error("Clave de API de Gemini no configurada.")
        return None

    falta = _bloqueo("gemini", None, request.user_id)
    if falta:
        raise ReporteBloqueado(falta)

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"x-goog-api-key": settings.gemini_api_key}
    payload = {
        "contents": [{
            "parts": [{"text": build_ai_prompt(request)}]
        }],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 800
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                log.error("Error en Gemini API", status=res.status_code, body=res.text)
                return None

            data = res.json()
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        log.error("Excepción en Gemini API", error=str(e))
        return None

async def generate_local_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando el LLM local Qwen2.5 (llama-server.exe, sin Ollama)."""
    try:
        from services.ai.local_llm import get_local_llm, is_local_llm_available
        if not is_local_llm_available():
            return None

        llm = get_local_llm()
        if llm is None or not llm.load():
            return None

        # Multi-turno nativo: pasamos messages directo al wrapper.
        # ANTES: aplanaba en system+user y llamaba `generate_with_cache` (MÉTODO
        # QUE NUNCA EXISTIÓ → AttributeError silencioso涝aba el path del reporte
        # local desde la migration a llama-server).
        # AHORA: llama a `generate(messages=...)` que manda directo a
        # /v1/chat/completions con la estructura de turnos preservada.
        messages = build_ai_messages(request)
        if not messages:
            return None

        result = llm.generate(messages=messages, max_tokens=512, temperature=0.1)
        return result or None
    except ImportError:
        return None
    except Exception as e:
        log.warning("local_llm_failed", error=str(e))
        return None


async def generate_ollama_report(request: AIReportRequest) -> str | None:
    """Genera reporte usando Ollama localmente en el servidor Ubuntu."""
    if not settings.ollama_base_url:
        return None

    falta = _bloqueo("ollama", settings.ollama_base_url, request.user_id)
    if falta:
        raise ReporteBloqueado(falta)

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": build_ai_messages(request),
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 800
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                log.error("Error en Ollama API", status=res.status_code, body=res.text)
                return None

            data = res.json()
            return data.get('message', {}).get('content', '').strip()
    except Exception as e:
        log.error("Excepción en Ollama API", error=str(e))
        return None

async def stream_ollama_report(request: AIReportRequest):
    """
    Generador asincrono para streaming de IA local.
    Prueba Local LLM primero, luego Ollama, luego APIs.
    """
    # 1. Local LLM (llama-server.exe + Qwen2.5 1.5B)
    try:
        from services.ai.local_llm import get_local_llm, is_local_llm_available
        if is_local_llm_available():
            llm = get_local_llm()
            if llm and llm.load():
                # Multi-turno nativo: pasamos messages directo.
                # ANTES: `for token in llm.generate_stream(...)` (SINCRONO) → TypeError
                # porque generate_stream es `async def` desde la migration.
                # AHORA: `async for token in llm.generate_stream(messages=...)`.
                messages = build_ai_messages(request)
                if messages:
                    async for token in llm.generate_stream(messages=messages):
                        yield token
                    return
    except Exception:
        pass

    # 2. Ollama — sólo si el destino no sale de la máquina o la cuenta lo autorizó.
    # El SSE no es un camino distinto por ser SSE: manda lo mismo que el síncrono.
    falta = _bloqueo("ollama", settings.ollama_base_url, request.user_id)
    if falta:
        raise ReporteBloqueado(falta)

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": build_ai_messages(request),
        "stream": True,
        "options": {"temperature": 0.1, "num_predict": 800},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    yield "Error conectando con la IA local."
                    return
                async for line in response.aiter_lines():
                    if not line: continue
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                    except json.JSONDecodeError:
                        pass
    except Exception:
        yield "Error en la generacion del reporte (Timeout/Desconexion)."

async def generate_ai_report(request: AIReportRequest) -> str | None:
    """
    Orquestador de reportes con fallback automatico.
    Prioridad: Local LLM -> Ollama -> Claude -> Gemini.

    Un destino sin autorizar no es un proveedor caído, así que no corta la
    cadena: se anota y se sigue probando, por si el siguiente sí está
    autorizado. Pero si al final no hubo reporte y sí hubo destinos bloqueados,
    se dice cuál y por qué. Devolver `None` en ese caso sería contar como «no se
    pudo generar» lo que en realidad fue «no te dejé mandarlo».
    """
    # 1. Local LLM (llama-server.exe + Qwen2.5 1.5B, default, offline)
    report = await generate_local_report(request)
    if report:
        log.info("Reporte generado con Local LLM (llama-server + Qwen2.5)")
        return report

    bloqueos: list[str] = []
    for nombre, generar in (
        (f"Ollama ({settings.ollama_model})", generate_ollama_report),
        ("Claude", generate_claude_report),
        ("Gemini", generate_gemini_report),
    ):
        try:
            report = await generar(request)
        except ReporteBloqueado as bloqueo:
            log.info("reporte_ia_no_enviado", proveedor=nombre)
            bloqueos.append(str(bloqueo))
            continue
        if report:
            log.info(f"Reporte generado con {nombre}")
            return report

    if bloqueos:
        raise ReporteBloqueado(bloqueos[0])
    return None


async def safe_generate_ai_report(request: AIReportRequest) -> str | None:
    """Wrapper con manejo de errores para endpoints HTTP.

    `ReporteBloqueado` no se traga: es la única respuesta de este módulo que el
    investigador puede accionar, y este `except Exception` la convertiría en el
    `None` que la interfaz muestra como «no se pudo generar el reporte».
    """
    try:
        return await generate_ai_report(request)
    except ReporteBloqueado:
        raise
    except Exception as e:
        log.error("ai_report_generation_failed", error=str(e))
        return None
