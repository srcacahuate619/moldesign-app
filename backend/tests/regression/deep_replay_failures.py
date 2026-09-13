"""deep_replay_failures.py — Diagnostico puntual de queries fallidas.

SCRIPT DESCARTABLE de diagnostico (Paso A del plan determinismo).
Reejecuta las 9 queries marcadas como fallo en el run 38/38 y captura
evidencia COMPLETA para validar las hipotesis del arbol de decision:
  - respuesta completa (no solo 300 chars)
  - molecule_context (SMILES inyectado por RAG)
  - tool_was_executed (si se ejecuto tool nativa O fallback)
  - guard esperado (shadow check via _verify_numerical_claims)
  - guard emitido en stream (match del marker del chat_service en el texto)

USAGE:
  cd D:\\moldesign-build\\backend
  $env:PYTHONPATH = "."
  python tests/regression/deep_replay_failures.py

Output: D:\\moldesign-build\\logs\\deep_replay.jsonl (una linea por query).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from services.ai.providers.registry import get_provider_registry
from services.ai.providers.local_llm_provider import LocalLLMProvider
from services.ai.chat_service import get_chat_service
from services.ai.local_llm import get_local_llm

try:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
except Exception:
    pass

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

# ── Patch capturador de tool_calls nativas (igual que el runner) ──
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

# ── Las 9 queries fallidas del run 38/38 ──
# R001, R006 = tool_quimica sin tool (SMILES viene del RAG, no del user msg)
# S006  = smiles_directo con SMILES trivial "C"
# D001  = docking con fallback tiro compute_properties (no run_docking)
# D002  = docking con SMILES en RAG (ibuprofeno) NO tooleado
# D004  = docking sin SMILES ni target explicitos
# MT003 = multi_turno anáfora "esa primera molecula" ALUCINA real
# MT005 = multi_turno anáfora "y del paracetamol?" sin tool
# I003  = smiles_invalido "C#CHHHH#$##@" (verificar conducta)
# ── Las queries que AUN fallan tras F1/F2/F3/F5/F7 (run 38/38 del 2026-07-31 22:55) ──
# D001  = docking SMILES explicito + "contra 7E2Y" → calls=0 (¿F2 no dispara? ¿guard F3 abortó?)
# D002  = docking nombre "ibuprofeno" + "contra 6LU7" → calls=0 (¿F1+F2 no disparan?)
# MT003 = multi_turno anáfora "esa primera molecula" → ALUCINA real persistente
# MT005 = multi_turno "y del paracetamol?" → calls=0 (¿qué respondió? alucina o se calla?)
# D004  excluido: comportamiento correcto ("necesito molecula+target"), F7 ya ajusta expectativa
# R001/R006/S006/I003 excluidos: estocásticos / expectativas corregidas por F7
FAILURE_IDS = {"D001", "D002", "MT003", "MT005"}

# Markers del guard que el chat_service emite al stream:
#   fabricación: "[Sistema: detecté valores incorrectos" ... "no están verificados"
#   discordancia vs context: "[Sistema: detecté valores incorrectos" ... "valor real es"
GUARD_MARKERS = (
    "[Sistema: detecté valores incorrectos",
    "no están verificados",
    "el valor real es",
)

# ── Cargar set completo, filtrar las 9 ──
set_path = Path(__file__).parent / "molchat_v1.jsonl"
with open(set_path) as f:
    all_queries = [json.loads(line) for line in f if line.strip()]
queries = [q for q in all_queries if q["id"] in FAILURE_IDS]
# MT queries son multi-turno pero las corremos aisladas (no en secuencia)
# para reproducir el fallo puntual de cada una.


async def replay_one(query: dict, cs) -> dict:
    """Reejecutar UNA query con captura completa."""
    cur = cs.get_conversation()
    if cur:
        cs.delete_conversation(cur.id)
    # Touch ResourceManager (mismo fix que el runner).
    try:
        from services.ai.resource_manager import get_resource_manager
        get_resource_manager().touch()
    except ImportError:
        pass
    _CAPTURED.clear()
    t0 = time.time()
    full_text = ""
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
            full_text += chunk
    except Exception as e:
        full_text = f"<ERROR:{type(e).__name__}:{e}>"
    dt = time.time() - t0

    captured = _CAPTURED[-1] if _CAPTURED else {}
    tcs = captured.get("tool_calls", []) if captured else []

    # molecule_context activo (lo que el RAG inyecto)
    conv = cs.get_conversation()
    mol_ctx = conv.molecule_context if conv else None

    # Shadow check: invocar _verify_numerical_claims como oraculo
    # para ver si el guard DEBERIA haber corregido.
    tool_was_executed_native = len(tcs) > 0
    # Detectar si el stream trajo resultado de tool (fallback forzado).
    fallback_marker = "[Sistema: resultados de herramientas ejecutadas:" in full_text
    tool_was_executed_any = tool_was_executed_native or fallback_marker

    guard_expected = ""
    try:
        # Shadow check: NO modificamos el stream, solo vemos qué debería decir.
        guard_expected = cs._verify_numerical_claims(
            full_text,
            mol_ctx,
            tool_was_executed=tool_was_executed_any,
        )
    except Exception as e:
        guard_expected = f"<GUARD_ERR:{e}>"

    # Guard emitido en stream: buscar los markers del chat_service en el texto.
    guard_emitted = any(m in full_text for m in GUARD_MARKERS)

    return {
        "id": query["id"],
        "category": query.get("category", ""),
        "query": query["query"][:200],
        "lat_s": round(dt, 1),
        "tool_calls_native_count": len(tcs),
        "tool_calls_native_names": [tc.get("function", {}).get("name", "?") for tc in tcs],
        "fallback_executed": fallback_marker,
        "tool_was_executed_any": tool_was_executed_any,
        "mol_ctx_smiles": (mol_ctx or {}).get("smiles", "") if mol_ctx else "",
        "mol_ctx_target": (mol_ctx or {}).get("target_name", "") if mol_ctx else "",
        "mol_ctx_keys": list(mol_ctx.keys()) if mol_ctx else [],
        "guard_expected": guard_expected[:500] if guard_expected else "",
        "guard_emitted_in_stream": guard_emitted,
        "warnings": warnings,
        "full_response": full_text,  # respuesta COMPLETA
    }


async def main():
    # Registrar provider local (igual que el runner principal).
    print("Cargando LLM...")
    llm = get_local_llm()
    default_model = LocalLLMProvider._pick_first_available_model()
    print(f"Modelo: {default_model}")
    registry = get_provider_registry()
    if registry.get("local"):
        registry.unregister("local")
    registry.register(LocalLLMProvider())
    llm.set_model_file(default_model)
    if not llm.is_loaded:
        ok = llm.load()
        print(f"  load()={ok}")
    assert llm.is_loaded

    print(f"\n=== DEEP REPLAY: {len(queries)} queries fallidas ===\n")
    results = []
    for q in queries:
        r = await replay_one(q, get_chat_service())
        results.append(r)
        print(f"\n--- {r['id']} [{r['category']}] lat={r['lat_s']}s ---")
        print(f"  query: {r['query']}")
        print(f"  mol_ctx.smiles: {r['mol_ctx_smiles']!r}")
        print(f"  mol_ctx.target: {r['mol_ctx_target']!r}")
        print(f"  tools_native: {r['tool_calls_native_names']} (count={r['tool_calls_native_count']})")
        print(f"  fallback_executed: {r['fallback_executed']}")
        print(f"  tool_was_executed_any: {r['tool_was_executed_any']}")
        print(f"  guard_expected: {r['guard_expected'][:200] if r['guard_expected'] else '(none)'}")
        print(f"  guard_emitted_in_stream: {r['guard_emitted_in_stream']}")
        print(f"  warnings: {r['warnings']}")
        resp_preview = r['full_response'][:500].replace('\n', ' ')
        print(f"  full_response[0..500]: {resp_preview}")

    # Persistir todo a JSONL para analisis.
    out_path = Path(__file__).resolve().parents[3] / "logs" / "deep_replay.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False).encode("utf-8"))
            f.write(b"\n")
    print(f"\n=== Persistido a {out_path} ({len(results)} records) ===")


if __name__ == "__main__":
    asyncio.run(main())
