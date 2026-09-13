"""
run_molchat_regression.py — Ejecutar set JSONL contra MolChat local y medir.

USAGE:
  cd D:\\\\moldesign-build\\\\backend
  $env:PYTHONPATH = "."
  python backend/tests/regression/run_molchat_regression.py

MIDE por query:
  - Latencia (segundos)
  - Tool calls (nativa OpenAI function calling)
  - SMILES canónico detectado (si la tool usó el SMILES del RAG)
  - Alucinación de resultado fabricado (el modelo finge tool sin ejecutarla)
  - Longitud de respuesta (chars)

METRICAS agregadas finales:
  - Por categoría (tool_quimica, smiles_directo, smiles_invalido, docking, conceptual, multi_turno)
  - p50/p95 de latencia
  - tool-call rate por categoría
  - tasa de alucinación por categoría

JERARQUIA aplicada: validez cientifica > calidad > eficiencia
(medimos SMILES del RAG y alucinación HOOK para decidir si el modelo es fiable)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from services.ai.providers.registry import get_provider_registry
from services.ai.providers.local_llm_provider import LocalLLMProvider
from services.ai.chat_service import get_chat_service
from services.ai.local_llm import get_local_llm
from core.config import get_settings

# Silenciar warnings de RDKit (la heuristica de SMILES prueba tokens que fallan parse,
# eso es esperable y NO es un error del test).
try:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
except Exception:
    pass
# ── Tools (como en producción) ──
from services.ai.tools.rdkit_tools import register_rdkit_tools
from services.ai.tools.docking_tools import register_docking_tools
from services.ai.tools.admet_tools import register_admet_tools
from services.ai.tools.analog_tools import register_analog_tools
from services.ai.tools.molgraph_tool import register_molgraph_tools
from services.ai.tools.web_tools import register_web_tools
register_rdkit_tools()
register_docking_tools()
register_admet_tools()
register_molgraph_tools()
register_analog_tools(verbose=False)
register_web_tools()

# ── Patch capturador de tool_calls ──
_CAPTURED = []
_orig = LocalLLMProvider.chat_with_tools
async def _patch(self, messages, tools):
    r = await _orig(self, messages=messages, tools=tools)
    _CAPTURED.append({
        "msg_len": len(messages),
        "tool_calls": r.get("tool_calls", []),
        "content": r.get("content", "")[:300],
    })
    return r
LocalLLMProvider.chat_with_tools = _patch

# ── Métricas ──────────────────────────────────────────────────────
def _detect_canon_smiles(tool_calls: list[dict]) -> str | None:
    """Detectar si algun tool_call usó el SMILES canónico inyectado por RAG."""
    ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
    for tc in tool_calls:
        args = tc.get("function", {}).get("arguments", "")
        if ASPIRIN in args:
            return ASPIRIN
        args_json = {}
        try:
            args_json = json.loads(args)
        except Exception:
            pass
        if any(ASPIRIN in str(v) for v in args_json.values()):
            return ASPIRIN
    return None

def _has_fabricated_tool(text: str, captured_call_count: int) -> tuple[bool, bool]:
    """Distinguir ejecución real de fabricación.

    Retorna (fabricated, tool_executed).

    - `tool_executed=True` si el stream lleva el marker oficial del sistema
      emitido por `format_tool_results` (post-ejecución de compute_properties,
      run_docking, etc., tanto vía tool_call nativa COMO vía fallback forzado).
      En ese caso NO puede haber fabricación: la tool se corrió de verdad.

    - `fabricated=True` solo si el texto afirma datos químicos (MW/LogP/TPSA/
      afinidad...) SIN marker de ejecución Y SIN tool_calls nativas capturadas
      → el modelo está inventando valores.

    Bug anterior del runner: trataba el marker "Sistema: resultados" como señal
    de fabricación, cuando es exactamente lo contrario (post-ejecución). Eso
    producía falsos [ALUCINA] cuando el `tool_forced_fallback` ejecutaba la
    tool de verdad pero no había tool_calls nativos en `_CAPTURED`.
    """
    # Marker oficial emitido por format_tool_results — post ejecución, sea
    # nativa o fallback. Es la prueba de que ALGO se ejecutó.
    execution_markers = (
        "[Sistema: resultados de herramientas ejecutadas:]",
        "Resultado de la herramienta:",
        "[Resultado de la herramienta]",
    )
    tool_executed = any(m in text for m in execution_markers)
    if tool_executed:
        return False, True
    # Sin marker de ejecución: si el texto afirma datos químicos y no hubo
    # tool_calls nativas, es fabricación pura.
    if captured_call_count > 0:
        return False, False
    # Same markers que chat_service._FABRICATION_MARKERS para consistencia.
    chemical_claims = (
        r'MW\s*[:=]\s*\d+\.?\d*\s*(?:Da|g/mol)',
        r'[pP]eso molecular\s*[:=]\s*\d+\.?\d*\s*(?:Da|g/mol)',
        r'[lL]og[Pp]\s*[:=]\s*[-\d]+\.?\d*',
        r'TPSA\s*[:=]\s*[\d]+\.?\d*',
        r'afinidad\s*(?:de|:)?\s*[-\d]+\.?\d*\s*kcal',
        r'score\s*(?:total|general)\s*(?:de|:)?\s*\d{2,3}\s*/\s*100',
    )
    import re
    if any(re.search(p, text) for p in chemical_claims):
        return True, False
    return False, False

async def run_one_query(query: dict) -> dict:
    """Ejecutar UNA query con conversacion limpia, medir todo."""
    cs = get_chat_service()
    cur = cs.get_conversation()
    if cur:
        cs.delete_conversation(cur.id)
    # Mantener vivo el LLM: el ResourceManager auto-descarga tras 300s de idle.
    # En producción lo llama provider.chat(); en el runner entre queries el
    # timer puede dispararse a mitad del set → matar el server.
    try:
        from services.ai.resource_manager import get_resource_manager
        get_resource_manager().touch()
    except ImportError:
        pass
    _CAPTURED.clear()
    t0 = time.time()
    text = ""
    warnings = []
    try:
        async for chunk in cs.chat(
            messages=[{"role": "user", "content": query["query"]}],
            provider_id="local",
            stream=True,
            mode="reasoning",
        ):
            if chunk.startswith("__WARNING__:"):
                warnings.append(chunk)
                continue
            text += chunk
    except Exception as e:
        text = f"<ERROR:{type(e).__name__}:{e}>"
    dt = time.time() - t0
    # Debug: si latencia = 0 y hay warnings, imprimir
    if dt < 1.0 and warnings:
        print(f"  [DBG] {query['id']} warnings: {warnings}")
    captured = _CAPTURED[-1] if _CAPTURED else {}
    tcs = captured.get("tool_calls", []) if captured else []
    fabricated, tool_executed = _has_fabricated_tool(text, len(tcs))
    return {
        "id": query["id"],
        "category": query.get("category", ""),
        "lat_s": round(dt, 1),
        "chars": len(text),
        "tool_calls_count": len(tcs),
        "tool_calls_names": [tc.get("function", {}).get("name", "?") for tc in tcs],
        "canon_smiles_detected": _detect_canon_smiles(tcs),
        "alucinacion": fabricated,
        "tool_executed": tool_executed,
        "text_sample": text[:300].strip(),
    }

async def main():
    s = get_settings()
    print(f"Config: binario={s.llama_server_executable_path}")

    # Precargar default dynamic (Bonsai via model_registry)
    llm = get_local_llm()
    default_model = LocalLLMProvider._pick_first_available_model()
    print(f"Modelo dinamico: {default_model}")

    # REGISTRAR provider local explícitamente — en producción lo hace el router
    # HTTP (api/routers/ai.py:77) al primer request; en un runner de CLI no hay
    # router, así que replicamos el contrato: un LocalLLMProvider sin config.
    registry = get_provider_registry()
    if registry.get("local"):
        registry.unregister("local")
    registry.register(LocalLLMProvider())

    llm.set_model_file(default_model)
    if not llm.is_loaded:
        ok = llm.load()
        print(f"  load()={ok}")
    assert llm.is_loaded, "No se pudo cargar el modelo"

    # Permitir apuntar a un set reducido vía env var MOLCHAT_REGRESSION_SET
    # (nombre del archivo .jsonl en el mismo dir, sin extensión). Útil para
    # batch corto de validación antes de correr las 38 completas.
    set_name = os.environ.get("MOLCHAT_REGRESSION_SET", "molchat_v1")
    set_path = Path(__file__).parent / f"{set_name}.jsonl"
    with open(set_path) as f:
        queries = [json.loads(line) for line in f if line.strip()]
    print(f"\n=== SET REGRESION: {len(queries)} queries ({set_name}) ===\n")
    results = []
    for q in queries:
        r = await run_one_query(q)
        results.append(r)
        tc = r["tool_calls_names"]
        tc_str = ",".join(tc) if tc else "-"
        can = f" [CANON:{r['canon_smiles_detected']}]" if r["canon_smiles_detected"] else ""
        aluc = " [ALUCINA]" if r["alucinacion"] else ""
        te = " [TE]" if r.get("tool_executed") else ""
        # TE = Tool Ejecutada (nativa O fallback forzado). Si calls=0 pero
        # TE aparece, fue el fallback. Si ALUCINA sin TE → fabricación real.
        print(f"  {r['id']:6s} {r['lat_s']:5.1f}s | {r['category']:16s} | calls={r['tool_calls_count']} [{tc_str}]{can}{te}{aluc}")

    # ── Agregados ──────────────────────────────────
    print("\n=== METRICAS AGREGADAS ===\n")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"count":0,"tool_hits":0,"aluc_count":0,"latencies":[]}
        categories[cat]["count"] += 1
        categories[cat]["latencies"].append(r["lat_s"])
        if r["tool_calls_count"] > 0 or r.get("tool_executed"):
            categories[cat]["tool_hits"] += 1
        if r["alucinacion"]:
            categories[cat]["aluc_count"] += 1
    for cat, m in sorted(categories.items()):
        lats = sorted(m["latencies"])
        p50 = lats[len(lats)//2]
        p95 = lats[int(len(lats)*0.95)] if len(lats) >= 20 else lats[-1]
        tool_rate = f"{m['tool_hits']}/{m['count']}" if m["count"]>0 else "N/A"
        aluc = f"- {m['aluc_count']} ALUC" if m["aluc_count"] > 0 else ""
        print(f"  {cat:16s} n={m['count']:2d}  tools={tool_rate}  p50={p50:.1f}s  p95={p95:.1f}s{aluc}")

if __name__ == "__main__":
    asyncio.run(main())
