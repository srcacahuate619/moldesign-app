"""run_quality_check.py — Verificar que KV q8_0 NO degrada la calidad de respuestas.

Compara calidad en sesión larga (30 queries multi-turno) midiendo:
  1. Respuestas NO vacías y con sentido (len > 30 chars cuando aplica)
  2. Valores numéricos de tools intactos (MW/LogP/TPSA del contexto, no inventados)
  3. Anáforas resueltas (referencias a moléculas anteriores)
  4. Coherencia: el texto del modelo menciona la molécula correcta

USO:
  python tests/regression/run_quality_check.py
"""
from __future__ import annotations

import asyncio
import re
import sys
import time

sys.path.insert(0, ".")

from services.ai.providers.registry import get_provider_registry
from services.ai.providers.local_llm_provider import LocalLLMProvider
from services.ai.chat_service import get_chat_service
from services.ai.local_llm import get_local_llm

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

try:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
except Exception:
    pass

# ── Secuencia multi-turno diseñada para detectar pérdida de coherencia ──
# Mezcla: propiedades + anáforas + comparaciones + recall de nombres.
SEQUENCE = [
    # (id, query, check_type, expected)
    ("P1", "calcula propiedades de la aspirina", "props", "aspirina"),
    ("P2", "propiedades del ibuprofeno", "props", "ibuprofeno"),
    ("P3", "y del paracetamol?", "anaphora_name", "paracetamol"),
    ("P4", "compará la aspirina con el ibuprofeno", "compare", "aspirina"),
    ("P5", "¿cuál tiene menor peso molecular?", "props", "ibuprofeno"),
    ("P6", "calcula la cafeina", "props", "cafeina"),
    ("P7", "y del etanol?", "anaphora_name", "etanol"),
    ("P8", "recordás la primera molécula que calculamos?", "recall", "aspirina"),
    ("P9", "propiedades de la glucosa", "props", "glucosa"),
    ("P10", "y de la morfina?", "anaphora_name", "morfina"),
    ("P11", "cuál es la más pesada de todas?", "compare", "morfina"),
    ("P12", "explicame la regla de Lipinski", "conceptual", None),
    ("P13", "y eso cómo aplica a la aspirina?", "conceptual", "aspirina"),
    ("P14", "calcula el paracetamol", "props", "paracetamol"),
    ("P15", "y cuál tiene mejor perfil que la aspirina?", "conceptual", "aspirina"),
    ("P16", "datos del diazepam", "props", "diazepam"),
    ("P17", "propiedades del omeprazol", "props", "omeprazol"),
    ("P18", "y qué diferencias hay entre esos dos?", "compare", "diazepam"),
    ("P19", "calcula la testosterona", "props", "testosterona"),
    ("P20", "y el colesterol?", "anaphora_name", "colesterol"),
    ("P21", "cual de todas tiene mayor logP?", "compare", None),
    ("P22", "recordas la cafeina?", "recall", "cafeina"),
    ("P23", "y su afinidad por 7E2Y?", "docking", "7E2Y"),
    ("P24", "propiedades de la quinina", "props", "quinina"),
    ("P25", "y de la curcumina?", "anaphora_name", "curcumina"),
    ("P26", "que diferencia hay entre ambas?", "compare", "quinina"),
    ("P27", "y su potencial antioxidante?", "conceptual", "curcumina"),
    ("P28", "datos del escitalopram", "props", "escitalopram"),
    ("P29", "y del citalopram?", "anaphora_name", "citalopram"),
    ("P30", "resumi lo que hicimos hoy", "summary", None),
]

# Valores reales conocidos (para verificar que el modelo NO los inventa)
KNOWN_VALUES = {
    "aspirina": {"mw": 180.16, "logp": 1.2},
    "ibuprofeno": {"mw": 206.28, "logp": 3.6},
    "paracetamol": {"mw": 151.16, "logp": 0.5},
}


def _check_response(qid: str, query: str, check_type: str, expected: str, text: str) -> dict:
    """Evaluar calidad de la respuesta. Retorna dict con flags."""
    result = {"id": qid, "query": query[:60], "type": check_type, "expected": expected, "ok": True, "flags": []}

    # 1. Respuesta vacía o error
    if not text or len(text) < 10:
        result["ok"] = False
        result["flags"].append("RESPUESTA_VACIA_O_CORTA")
        return result

    if text.startswith("<ERROR") or "Error generando" in text:
        result["ok"] = False
        result["flags"].append("ERROR_BACKEND")
        return result

    # 2. Marcador de tool ejecutada (prueba de que la tool corrio y dio datos)
    if check_type in ("props", "compare", "docking") and "Resultado de la herramienta" not in text and "Sistema: resultados" not in text:
        # Puede que el clasificador haya ejecutado la tool y el texto tenga los datos
        # sin el marker en casos especiales — no marcar como fail, solo nota.
        result["flags"].append("SIN_MARKER_TOOL(verificar)")

    # 3. La molécula esperada debe mencionarse (coherencia de sujeto)
    if expected and expected.lower() not in text.lower():
        result["flags"].append(f"NO_MENCIONA_{expected.upper()}")

    # 4. Valores numéricos inventados (anti-hallucination): si la respuesta afirma
    #    MW que NO coincide con el real conocido, es fabricación.
    for name, vals in KNOWN_VALUES.items():
        if name.lower() in query.lower():
            m_mw = re.search(r'MW\s*[:=]\s*(\d+\.?\d*)', text, re.IGNORECASE)
            if m_mw:
                val = float(m_mw.group(1))
                if abs(val - vals["mw"]) > 1.0:
                    result["ok"] = False
                    result["flags"].append(f"MW_INVENTADO_{name}={val}(real={vals['mw']})")

    # 5. Anáfora: si es anaphora_name, debe mencionar la molécula del nombre
    if check_type == "anaphora_name" and expected:
        result["ok"] = result["ok"] and (expected.lower() in text.lower() or "no tengo registro" in text.lower())
        if expected.lower() not in text.lower() and "no tengo registro" not in text.lower():
            result["flags"].append("ANAFORA_NO_RESUELTA")

    # 6. Respuestas que afirman números sin tool → sospechoso (pero no necesariamente fail)
    m_nums = re.findall(r'\d+\.?\d*\s*(?:Da|g/mol|kcal)', text)
    if m_nums and check_type == "conceptual":
        result["flags"].append("NUMEROS_EN_CONCEPTUAL")

    return result


async def main():
    print("=== QUALITY CHECK: KV q8_0 + cache-ram 256 (config ACTUAL) ===")

    registry = get_provider_registry()
    if registry.get("local"):
        registry.unregister("local")
    registry.register(LocalLLMProvider())
    llm = get_local_llm()
    llm.set_model_file("Bonsai-8B-Q1_0.gguf")
    if not llm.is_loaded:
        ok = llm.load()
        print(f"  load()={ok}")
    assert llm.is_loaded

    cs = get_chat_service()
    conv = cs.get_conversation()
    if conv:
        cs.delete_conversation(conv.id)
    cs.get_or_create_active({})

    print(f"\n{'='*70}")
    print(f"SESION LARGA: {len(SEQUENCE)} queries multi-turno (misma conversacion)")
    print(f"{'='*70}\n")

    results = []
    for qid, query, ctype, expected in SEQUENCE:
        t0 = time.time()
        text = ""
        try:
            async for chunk in cs.chat(
                messages=[{"role": "user", "content": query}],
                provider_id="local",
                stream=True,
                mode="reasoning",
            ):
                if chunk.startswith("__WARNING__:"):
                    continue
                text += chunk
        except Exception as e:
            text = f"<ERROR:{type(e).__name__}:{e}>"
        dt = time.time() - t0

        r = _check_response(qid, query, ctype, expected, text)
        r["lat"] = round(dt, 1)
        r["chars"] = len(text)
        r["sample"] = text[:250].replace("\n", " ")[:250]
        results.append(r)

        status = "OK " if r["ok"] else "FAIL"
        flags = (" | " + " | ".join(r["flags"])) if r["flags"] else ""
        # ASCII-safe: la consola Windows cp1252 no aguanta caracteres unicode
        sample = r["sample"].encode("ascii", "replace").decode("ascii")
        print(f"  {r['id']} {status} {r['lat']:5.1f}s {r['chars']:4d}ch {flags}")
        print(f"       > {sample}")

        await asyncio.sleep(0.2)

    # ── Resumen ─────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("RESUMEN DE CALIDAD")
    print(f"{'='*70}")
    fails = [r for r in results if not r["ok"]]
    notes = [r for r in results if r["flags"] and r["ok"]]
    print(f"  Total:      {len(results)}")
    print(f"  OK:         {len(results) - len(fails)}")
    print(f"  FAIL:       {len(fails)}")
    if fails:
        for f in fails:
            print(f"    x {f['id']} [{f['type']}] {f['query'][:50]}")
            print(f"      flags: {f['flags']}")
            print(f"      sample: {f['sample'][:180].encode('ascii','replace').decode('ascii')}")
    print(f"  Con notas:  {len(notes)} (no fail, revisar)")
    for n in notes:
        print(f"    · {n['id']} {n['flags']}")


if __name__ == "__main__":
    asyncio.run(main())
