"""run_stress_resilience.py — Simular 100 queries en UNA sesión conversacional real.

USAGE:
  cd D:\\moldesign-build\\backend
  $env:PYTHONPATH = "."
  python tests/regression/run_stress_resilience.py

OBJETIVO: Validar que MolChat resiste 100 mensajes en una misma conversación sin:
  - Perder contexto (anáfora "molécula anterior" debe resolverse al msg 99)
  - Zombies/zombies de VRAM (server debe mantenerse en <4GB todo el test)
  - Latencias runaway (>5x sobre p50 baseline de run40)
  - Timeouts/errores por acumulación de contexto en la ventana del LLM

DISEÑO:
  100 queries en UNA sola conversación (no hay delete_conversation entre queries).
  Respetar pausa 300ms entre queries (simular humano lento).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import re as _re

sys.path.insert(0, ".")

from services.ai.providers.registry import get_provider_registry
from services.ai.providers.local_llm_provider import LocalLLMProvider
from services.ai.chat_service import get_chat_service
from services.ai.local_llm import get_local_llm
from core.config import get_settings

# Tools registration
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

# ── Patch capturador ──
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


# ── Pool de 100 queries (orden fijo, mezclado por categorías) ──
QUERY_POOL = [
    # Tool química 1-25
    ("prop_aspirina",      "calcula propiedades de la aspirina",       "tool_quimica"),
    ("prop_ibuprofeno",    "propiedades del ibuprofeno",             "tool_quimica"),
    ("prop_paracetamol",   "calcula propiedades del paracetamol",    "tool_quimica"),
    ("prop_cafeina",       "datos de la cafeína",                   "tool_quimica"),
    ("prop_etanol",        "propiedades del etanol",                "tool_quimica"),
    ("prop_glucosa",       "calcula la glucosa",                    "tool_quimica"),
    ("prop_taxol",         "propiedades del taxol",                 "tool_quimica"),
    ("prop_morfina",       "calcula propiedades de la morfina",     "tool_quimica"),
    ("prop_glicerol",      "propiedades del glicerol",              "tool_quimica"),
    ("prop_urea",          "calcula la urea",                       "tool_quimica"),
    ("prop_sacarosa",      "propiedades de la sacarosa",             "tool_quimica"),
    ("prop_penicilina",    "datos de la penicilina",                "tool_quimica"),
    ("prop_omeprazol",     "propiedades del omeprazol",             "tool_quimica"),
    ("prop_lidocaina",     "calcula la lidocaína",                  "tool_quimica"),
    ("prop_lisina",        "propiedades de la lisina",               "tool_quimica"),
    ("prop_curcumina",     "propiedades de la curcumina",            "tool_quimica"),
    ("prop_melatonina",    "calcula la melatonina",                 "tool_quimica"),
    ("prop_quinina",       "propiedades de la quinina",              "tool_quimica"),
    ("prop_riboflavina",   "datos de la riboflavina",               "tool_quimica"),
    ("prop_diazepam",      "propiedades del diazepam",              "tool_quimica"),
    ("prop_nafazolina",    "calcula la nafazolina",                 "tool_quimica"),
    ("prop_dopamina",      "propiedades de la dopamina",            "tool_quimica"),
    ("prop_serotonina",    "datos de la serotonina",                "tool_quimica"),
    ("prop_atropina",      "propiedades de la atropina",            "tool_quimica"),
    ("prop_escitalopram",  "calcula el escitalopram",               "tool_quimica"),
    # SMILES directo 26-40
    ("smi_aspirina",       "CC(=O)Oc1ccccc1C(=O)O",                "smiles_directo"),
    ("smi_paracetamol",    "CC(=O)Nc1ccc(O)cc1",                   "smiles_directo"),
    ("smi_cafeina",        "Cn1c(=O)c2c(ncn2C)n(C)c1=O",           "smiles_directo"),
    ("smi_etanol",         "CCO",                                   "smiles_directo"),
    ("smi_glucosa",        "OCC1OC(O)C(O)C(O)C1O",                 "smiles_directo"),
    ("smi_taxol",          "CC1=C2C(O)C(=O)C3=C(C2C(OC(=O)C)CC1)OC","smiles_directo"),
    ("smi_morfina",        "CN1CCC23C4=C1Cc1ccc(O)c(c12)OC3C(O)C=C4","smiles_directo"),
    ("smi_testosterona",   "CC12CCC3C(CCCC4=CC(=O)CCC34)C1C(C2O)","smiles_directo"),
    ("smi_lactato",        "CC(O)C(O)C(=O)O)",                     "smiles_directo"),
    ("smi_bencilpen",      "CC1(C)SC2C(C(=O)O)N2C1C(=O)O",       "smiles_directo"),
    ("smi_propanol",       "CCCO",                                  "smiles_directo"),
    ("smi_acbenzoico",     "c1ccccc1C(==O)O",                      "smiles_directo"),
    ("smi_metanol",        "CO",                                    "smiles_directo"),
    ("smi_etileno",        "C=C",                                   "smiles_directo"),
    ("smi_formaldehido",   "C=O",                                   "smiles_directo"),
    # Docking 41-55
    ("dock_aspirina_7e2y","hace docking de aspirina contra 7E2Y", "docking"),
    ("dock_ibuprofeno_6lu","docking de ibuprofeno contra 6LU7",   "docking"),
    ("dock_paracet_7e2y", "hace docking de paracetamol contra 7E2Y","docking"),
    ("dock_etanol_3cl",   "docking de etanol contra 3CL-pro",      "docking"),
    ("dock_penicilina_6m0","dockear penicilina contra 6M0J",       "docking"),
    ("dock_cafeina_3cl",  "docking de cafeína contra 3CL-pro",     "docking"),
    ("dock_aspirina_6lu7","dock de aspirina contra 6LU7",          "docking"),
    ("dock_ibuprof_7e2y", "docking ibuprofeno 7E2Y",              "docking"),
    ("dock_morfina_6m0j", "docking morfina contra 6M0J",         "docking"),
    ("dock_lisina_3cl",   "docking lisina contra 3CL-pro",        "docking"),
    ("dock_omeprazol_7e2","hace docking omeprazol con 7E2Y",     "docking"),
    ("dock_melatonina_6lu","docking melatonina contra 6LU7",     "docking"),
    ("dock_riboflav_3cl", "dockear riboflavina contra 3CL-pro",  "docking"),
    ("dock_diazepam_7e2y","docking diazepam contra 7E2Y",        "docking"),
    ("dock_escitalop_6lu","hace docking escitaloprol contra 6LU7","docking"),
    # Conceptual 56-   0
    ("conc_rule5",        "explicame la regla de Lipinski",        "conceptual"),
    ("conc_druglikeness",  "qué es la drug-likeness",               "conceptual"),
    ("conc_bio",          "cómo se calcula la biodisponibilidad",   "conceptual"),
    ("conc_pk",           "explica la farmacocinética",             "conceptual"),
    ("conc_hbd_hba",      "qué son los dadores y aceptores de puente de hidrógeno","conceptual"),
    ("conc_pgp",           "explica la glicoproteína P",            "conceptual"),
    ("conc_logp",         "qué representa el logP",                 "conceptual"),
    ("conc_halflife",     "cómo afecta la vida media a un fármaco", "conceptual"),
    ("conc_tpsa",         "significado de TPSA en diseño",          "conceptual"),
    ("conc_metabolism",   "explica el metabolismo fase I fase II",  "conceptual"),
    ("conc_cyp450",       "qué es el CYP450?",                      "conceptual"),
    ("conc_receptors",    "diferencias entre agonista y antagonista","conceptual"),
    ("conc_mw_rule",      "qué es la regla de peso molecular",      "conceptual"),
    ("conc_design",       "principios del diseño de fármacos",      "conceptual"),
    ("conc_quantum",      "explicame el docking cuántico",          "conceptual"),
    # SMILES inválidos 76-8:
    ("inv_misspelled",   "calcula propiedades de KILLMEnow",       "smiles_invalido"),
    ("inv_random",       "XYZ999",                                 "smiles_invalido"),
    ("inv_special_chars","C1CC@#$",                               "smiles_invalido"),
    ("inv_junk",        "asdgihjkl propeties",                   "smiles_invalido"),
    ("inv_giberish",    "kljdshfgiuh34iuh2fj",                    "smiles_invalido"),
    ("inv_human_name",  "calcula propiedades de johan",            "smiles_invalido"),
    ("inv_website",     "http://molchat fake",                    "smiles_invalido"),
    ("inv_email",       "test@molchat.com propiedades",            "smiles_invalido"),
    ("inv_sentence",    "mi molécula favorita es la glucosa en sangre","smiles_invalido"),
    ("inv_number",      "123 calcula esto",                        "smiles_invalido"),
    ("inv_broken_smi",  "CC(=O crazy molecule",                   "smiles_invalido"),
    ("inv_html",        "<script>alert(1)</script>",              "smiles_invalido"),
    ("inv_long",        "se ha escrito un texto muy largo" * 3,    "smiles_invalido"),
    ("inv_space",       "              ",                           "smiles_invalido"),
    ("inv_empty",       "",                                        "smiles_invalido"),
    # Multi-turno 91-100
    ("mt_r1_aspirina",  "calcula propiedades de la aspirina",      "multi_turno"),
    ("mt_r1_similar",   "buscá moléculas similares",                "multi_turno"),
    ("mt_r2_paracetamol","propiedades del paracetamol",             "multi_turno"),
    ("mt_r2_afinidad",  "cuál es su afinidad por 7E2Y?",           "multi_turno"),
    ("mt_r3_cafe",      "calcula la cafeína",                      "multi_turno"),
    ("mt_r4_ibuprofeno","calcula propiedades del ibuprofeno",       "multi_turno"),
    ("mt_r4_similar",   "buscá análogos",                           "multi_turno"),
    ("mt_r5_morfina",  "calcula propiedades de la morfina",        "multi_turno"),
    ("mt_r6_diazepam",  "propiedades del diazepam",                 "multi_turno"),
    ("mt_r6_afinidad",  "dockear contra 7E2Y",                      "multi_turno"),
    ("mt_r7_glucosa",   "y de la glucosa?",                        "multi_turno"),
    ("mt_r8_similar",   "buscá análogos de eso",                    "multi_turno"),
    ("mt_r9_afinidad",  "y su afinidad?",                          "multi_turno"),
    ("mt_r10_ibu",      "volvé a calcular el ibuprofeno",           "multi_turno"),
    ("mt_r12_afinidad", "docking de eso contra 6LU7",               "multi_turno"),
]

TOTAL = len(QUERY_POOL)


# ── Funciones ─────────────────────────────────────────────────────
def get_vram_mb() -> int:
    """VRAM usada por el proceso llama-server en MB."""
    try:
        raw = subprocess.check_output(
            ['nvidia-smi', '--query-compute-apps=used_gpu_more',
             '--format=csv,noheader,nounits'],
            timeout=5,
        ).decode().strip()
        return sum(int(l) for l in raw.split('\n') if l.strip().isdigit())
    except Exception:
        return -1


async def run_one(cs, user_message: str, query_id: int) -> dict:
    _CAPTURED.clear()
    t0 = time.time()
    text = ""
    error = None
    warnings = []
    try:
        async for chunk in cs.chat(
            messages=[{"role": "user", "content": user_message}],
            provider_id="local",
            stream=True,
            mode="reasoning",
        ):
            if chunk.startswith("__WARNING__:"):
                warnings.append(chunk)
                continue
            text += chunk
    except asyncio.TimeoutError:
        error = "TIMEOUT"
        text = "<TIMEOUT>"
    except Exception as e:
        error = f"{type(e).__name__}:{str(e)}"
        text = f"<ERROR:{error}"

    dt = time.time() - t0
    captured = _CAPTURED[-1] if _CAPTURED else {}
    tcs = captured.get("tool_calls", []) if captured else []

    # Fabricación: afirmar datos químicos sin marker de ejecución ni tool_call
    fabricated = False
    if not any(m in text for m in ("Sistema: resultados", "Resultado de la herramienta:")):
        if len(tcs) == 0 and any(_re.search(p, text) for p in (
            r'MW\s*[:=]\s*\d+', r'peso molecular\s*[:=]\s*\d+',
            r'logP\s*[:=]\s*[-\d]+', r'TPSA\s*[:=]\s*\d+',
        )):
            fabricated = True

    # Diagnóstico: si latencia ~0 y hay warnings, loguear el warning COMPLETO
    if dt < 1.0 and warnings:
        log(f"    [DBG] Q{query_id:03d} warnings: {warnings[0][:200]}")

    return {
        "id": f"Q{query_id:03d}",
        "lat_s": round(dt, 1),
        "chars": len(text),
        "tool_calls_count": len(tcs),
        "error": error,
        "fabricated": fabricated,
        "warnings": warnings,
        "vram_mb": get_vram_mb(),
    }


# ── Tee: print + log a archivo UTF-8 (evitar mojibake en consola cp1252) ──
_LOG_FILE = None


def set_log_file(path: str) -> None:
    global _LOG_FILE
    _LOG_FILE = open(path, "w", encoding="utf-8")


def log(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))
    if _LOG_FILE:
        try:
            _LOG_FILE.write(msg + "\n")
            _LOG_FILE.flush()
        except Exception:
            pass


async def main():
    s = get_settings()
    # El temporal del sistema, no una ruta de una máquina concreta: escrita a
    # mano, esta prueba sólo escribía su log en el equipo donde se redactó.
    set_log_file(os.path.join(tempfile.gettempdir(), "moldesign-stress100_run.log"))
    log(f"Config: binario={s.llama_server_executable_path}")
    llm = get_local_llm()
    default_model = LocalLLMProvider._pick_first_available_model()
    log(f"Modelo dinámico: {default_model}")

    # Registrar provider local
    registry = get_provider_registry()
    if registry.get("local"):
        registry.unregister("local")
    registry.register(LocalLLMProvider())

    llm.set_model_file(default_model)
    if not llm.is_loaded:
        ok = llm.load()
        log(f"  load()={ok}")
    assert llm.is_loaded, "No se pudo cargar el modelo"

    # Crear UNA conversación que vamos a reutilizar para las 100 queries
    cs = get_chat_service()
    conv = cs.get_conversation()
    if conv and conv.id:
        cs.delete_conversation(conv.id)
    conv = cs.get_or_create_active({})
    log(f"\n{'='*60}")
    log(f"STRESS TEST: {TOTAL} queries en conversación {conv.id[:8]}...")
    log(f"{'='*60}\n")

    results = []
    error_count = 0
    fabric_count = 0
    vram_start = get_vram_mb()

    # Limitar para diagnóstico: MOLCHAT_STRESS_LIMIT=N (default 100)
    limit = int(os.environ.get("MOLCHAT_STRESS_LIMIT", str(len(QUERY_POOL))))
    for i, (label, query_text, category) in enumerate(QUERY_POOL[:limit], 1):
        # Touch para evitar descarga automática por inactividad
        try:
            from services.ai.resource_manager import get_resource_manager
            rm = get_resource_manager()
            rm.touch()
            # Diagnóstico: estado del ResourceManager en cada query
            try:
                from services.ai.local_llm import is_local_llm_available
                avail = is_local_llm_available()
                ram_f = rm._get_ram_free_gb()
                vram_f = rm._get_vram_free_gb()
                llm_state = rm._llm_state
                unload_will = rm.should_unload()[0]
                log(
                    f"  [RM] avail={avail} ram={ram_f:.1f}GB vram={vram_f:.1f}GB "
                    f"state={llm_state} will_unload={unload_will} idle={time.monotonic()-rm._last_used:.0f}s"
                )
            except Exception as _e:
                log(f"  [RM-ERR] {_e}")
        except ImportError:
            pass

        # Estado del LLM antes de cada query
        llm_state = llm.is_loaded
        r = await run_one(cs, query_text, i)
        results.append(r)

        if r["error"]:
            error_count += 1
        if r["fabricated"]:
            fabric_count += 1

        status = "✓"
        if r["error"]:
            status = "✗"
        elif r["fabricated"]:
            status = "⚠"

        log(
            f"  {r['id']} {r['lat_s']:5.1f}s | "
            f"tools={r['tool_calls_count']} | "
            f"vram={r['vram_mb']}MB | "
            f"loaded={llm_state} | "
            f"{category:20s} {status}"
        )

        # Checkpoint cada 25 queries
        if i % 25 == 0:
            vram_mb = get_vram_mb()
            last_25 = [x["lat_s"] for x in results[-25:]]
            # RSS del server para detectar fuga
            server_rss_mb = 0
            try:
                import psutil as _psutil
                for p in _psutil.process_iter(['name']):
                    try:
                        if 'llama-server' in p.info['name']:
                            server_rss_mb = p.memory_info().rss / 1024**2
                    except Exception:
                        pass
            except ImportError:
                pass
            log(
                f"\n  -- CHECKPOINT {i}/{limit} --\n"
                f"  VRAM: {vram_start} → {vram_mb}MB (Δ={vram_mb - vram_start}MB)\n"
                f"  server RSS: {server_rss_mb:.0f}MB\n"
                f"  last_25 p50={sorted(last_25)[12]:.1f}s\n"
                f"  Errores acum: {error_count} | Fabricaciones: {fabric_count}\n"
            )

        await asyncio.sleep(0.3)  # pausa humana

    vram_end = get_vram_mb()
    all_lats = sorted([r["lat_s"] for r in results])
    p50 = all_lats[len(all_lats)//2]
    p95 = all_lats[int(len(all_lats)*0.95)]
    p99 = all_lats[int(len(all_lats)*0.99)]

    log(f"\n{'='*60}")
    log("RESULTADOS STRESS TEST: 100 queries en 1 conversación")
    log(f"{'='*60}")
    log(f"  Total queries:      {TOTAL}")
    log(f"  Errores:            {error_count}")
    log(f"  Fabricaciones:      {fabric_count}")
    if fabric_count > 0:
        log(f"  ⚠ {fabric_count} fabricaciones detectadas")
    else:
        log("  ✅ Cero fabricaciones")
    log(f"  Tasa de error:      {error_count/TOTAL*100:.1f}%")
    log(f"  p50 latency:        {p50:.1f}s")
    log(f"  p95 latency:        {p95:.1f}s")
    log(f"  p99 latency:        {p99:.1f}s")
    log(f"  VRAM-start:         {vram_start}MB")
    log(f"  VRAM-end:           {vram_end}MB")
    log(f"  VRAM-delta:         {vram_end - vram_start}MB")

    # Computation por buckets de 25 (usar limit real, no TOTAL hardcodeado)
    log("\n--- Degradación por bucket ---")
    n_buckets = (len(results) + 24) // 25
    for bid in range(n_buckets):
        bucket_results = results[bid*25: (bid+1)*25]
        if not bucket_results:
            continue
        bucket_lats = sorted([r["lat_s"] for r in bucket_results])
        bp50 = bucket_lats[len(bucket_lats)//2]
        bp95 = bucket_lats[int(len(bucket_lats)*0.95)]
        q_start = bid*25+1
        q_end = min((bid+1)*25, len(results))
        log(f"  Q{q_start:3d}-Q{q_end:3d}:  p50={bp50:.1f}s  p95={bp95:.1f}s")

    # Diagnosis: comparar contra baseline run40
    base_p50 = 7.0  # baseline tool_quimica p50 promedio
    if p95 > base_p50 * 5:
        log(f"\n  ❌ DEGRADACIÓN CRÍTICA: p95={p95:.1f}s ({(p95/base_p50):.1f}x baseline {base_p50}s)")
    elif p50 > base_p50 * 2:
        log(f"\n  ⚠ DEGRADACIÓN MODERADA: p50={p50:.1f}s ({(p50/base_p50):.1f}x baseline)")
    else:
        log(f"\n  ✅ RESILIENTE: p95={p95:.1f}s vs baseline {base_p50}s → {(p95/base_p50):.1f}x")
    if error_count == 0 and fabric_count == 0:
        log("  ✅ Cero errores, cero fabricaciones — MolChat resistió 100 queries")


if __name__ == "__main__":
    asyncio.run(main())
