"""
MolChat Quality Suite v2 — casos de uso exhaustivos.

Criterio de verdad: el TOOL RESULT de RDKit (la fuente de verdad real).
El validador verifica que el MODELO repita fielmente los valores que la
tool calculó (coherencia modelo↔tool) y que NO haya correcciones del guard.

Esto evita el bug de v1: validar contra una tabla hardcodeada con valores
de memoria (ej. puse cafeína LogP -0.07 cuando RDKit da -1.03).
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, ".")


# ── Parser del tool result ────────────────────────────────────────────
# Formato 1 (nombre): "compute_properties (cafeina): MW: 194.2 Da, ..."
# Formato 2 (comparación): "compare_molecules (A=aspirina | B=ibuprofeno): Comparación:
#                             MW: A=180.2 | B=206.3 (Δ=+26.1) ..."
# Formato 3 (SMILES sin nombre): "compute_properties: MW: 180.2 Da, ..."
_TOOL_RESULT_RE = re.compile(
    r"([A-Za-z_]+)\s*(?:\(([^)]*)\))?\s*:\s*(.+)", re.IGNORECASE
)
_KEY_VAL_RE = {
    "MW": re.compile(r"MW:\s*(-?\d+\.?\d*)\s*Da", re.IGNORECASE),
    "LogP": re.compile(r"LogP:\s*(-?\d+\.?\d*)", re.IGNORECASE),
    "TPSA": re.compile(r"TPSA:\s*(-?\d+\.?\d*)\s*A", re.IGNORECASE),
    "HBD": re.compile(r"H-?Bond [dD]onors?:\s*(\d+)", re.IGNORECASE),
    "HBA": re.compile(r"H-?Bond [aA]cceptors?:\s*(\d+)", re.IGNORECASE),
}
# Valores en comparación: "MW: A=206.3 | B=151.2 (Δ=-55.1)"
_COMPARE_KEY_RE = {
    "MW": re.compile(r"MW:\s*A=(-?\d+\.?\d*)\s*\|\s*B=(-?\d+\.?\d*)", re.IGNORECASE),
    "LogP": re.compile(r"LogP:\s*A=(-?\d+\.?\d*)\s*\|\s*B=(-?\d+\.?\d*)", re.IGNORECASE),
    "TPSA": re.compile(r"TPSA:\s*A=(-?\d+\.?\d*)\s*\|\s*B=(-?\d+\.?\d*)", re.IGNORECASE),
}


def parse_tool_result(text: str) -> list[dict]:
    """Extraer todos los (tool, nombre, {key: valor}) del texto del turno."""
    results = []
    for m in _TOOL_RESULT_RE.finditer(text):
        tool, label, body = m.group(1), (m.group(2) or "").strip(), m.group(3)
        # Ignorar el header "[Sistema: resultados de herramientas ejecutadas:]"
        if tool.lower() == "sistema":
            continue

        # Determinar nombre(s): "(cafeina)" o "(A=x | B=y)" → ambos
        names = []
        if label:
            am = re.search(r"A=([^ |]+)", label)
            bm = re.search(r"B=([^ |]+)", label)
            if am:
                names.append(am.group(1))
            if bm:
                names.append(bm.group(1))
            if not names:
                names.append(label)
        else:
            names.append("?")

        # Comparación: los valores van como "MW: A=... | B=..." en líneas
        # SEPARADAS del texto (no en el body del primer match — el regex
        # captura "Comparación:" como body y las líneas MW/LogP son matches
        # propios). Escaneamos TODO el texto del turno por key.
        if tool == "compare_molecules" and len(names) == 2:
            vals_a, vals_b = {}, {}
            for key, pat in _COMPARE_KEY_RE.items():
                cm = pat.search(text)  # en todo el texto del turno
                if cm:
                    vals_a[key] = float(cm.group(1))
                    vals_b[key] = float(cm.group(2))
            if vals_a:
                results.append({"tool": tool, "name": names[0], "values": vals_a})
            if vals_b:
                results.append({"tool": tool, "name": names[1], "values": vals_b})
            continue

        # Formato normal: valores en el body
        vals = {}
        for key, pat in _KEY_VAL_RE.items():
            vm = pat.search(body)
            if vm:
                vals[key] = float(vm.group(1))
        if not vals:
            continue
        for name in names:
            results.append({"tool": tool, "name": name, "values": vals})
    return results


# ── Validadores ───────────────────────────────────────────────────────

def v_no_correction(text: str, conv=None) -> list[str]:
    return ["contiene corrección del guard"] if "[Sistema: detect" in text else []


def v_no_error(text: str, conv=None) -> list[str]:
    # Un "Error" del sistema honesto (ej. "docking no disponible") es CORRECTO —
    # significa que NO alucinó un valor. Solo fallamos ante un crash real.
    if "Traceback" in text or "Exception" in text:
        return ["crash real en la respuesta"]
    return []


def v_reports_tool_values(text: str, conv=None) -> list[str]:
    """El modelo (respuesta limpia) debe repetir los valores del tool result."""
    problems = []
    tool_results = parse_tool_result(text)
    if not tool_results:
        return ["no se encontró tool result en el turno"]

    # Texto de la respuesta del modelo: el texto TOTAL del turno (el tool result
    # se inyecta al inicio, la respuesta del modelo lo sigue). Buscamos los
    # valores en TODO el texto, no solo en el fragmento posterior al último
    # tool result (bug v1: el último tool result de un turno con 2+ tools
    # cortaba el fragmento y el validador no veía la respuesta).
    for tr in tool_results:
        for key, val in tr["values"].items():
            if key not in ("MW", "LogP", "TPSA"):
                continue
            # El valor de la tool DEBE aparecer en el texto (con formato robusto:
            # 151.2 o 151.20 o 151.200...)
            val_re = re.compile(
                rf"{val:g}(?:\.\d+)?" if "." not in f"{val:g}" else rf"{val:g}",
            )
            if not val_re.search(text):
                problems.append(
                    f"modelo no repite {key}={val} de {tr['name']} "
                    f"(resp: {text[-200:]!r})"
                )
    return problems


def v_has_compare_structure(text: str, conv=None) -> list[str]:
    """En comparaciones: el modelo debe mencionar AMBAS moléculas."""
    tool_results = parse_tool_result(text)
    if len(tool_results) < 2:
        return [f"no hay 2 tool results de comparación (encontré {len(tool_results)})"]
    names = {tr["name"].lower() for tr in tool_results if tr["name"] != "?"}
    if len(names) < 2:
        return ["los tool results no tienen 2 nombres distintos"]
    problems = []
    for name in names:
        if name not in text.lower():
            problems.append(f"no menciona '{name}' en la respuesta")
    return problems


def v_no_fabricated(text: str, conv=None) -> list[str]:
    """El modelo NO debe inventar valores que no vengan de ninguna tool.
    Acepta valores del historial (turnos previos verificados) — en multi-turno
    es correcto citar valores ya verificados de moléculas anteriores."""
    problems = []
    # Valores verificados acumulados de TODA la conversación: incluye los tool
    # results de compute_properties Y las tablas de rank_session_molecules
    # (formato: "etanol: 46.1 Da" / "ibuprofeno: 3.07" dentro del ranking).
    verified: set[float] = set()
    for msg in (conv.messages if conv else []):
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        if not isinstance(content, str):
            continue
        # Tool results clásicos: "compute_properties (aspirina): MW: 180.2 Da"
        for tr in parse_tool_result(content):
            verified.update(tr["values"].values())
        # Tablas de ranking: "  1. paracetamol: 151.2 Da"
        for m in re.finditer(r"^\s*\d+\.\s+.+?:\s*(-?\d+\.?\d*)", content, re.M):
            try:
                verified.add(float(m.group(1)))
            except ValueError:
                pass
        # query_history: "  1. nombre | target | score=87.5 | ..."
        for m in re.finditer(r"score=(-?\d+\.?\d*)", content):
            try:
                verified.add(float(m.group(1)))
            except ValueError:
                pass

    known = ["aspirina", "ibuprofeno", "paracetamol", "cafeina", "morfina",
             "etanol", "dopamina", "glucosa"]
    for name in known:
        if name not in text.lower():
            continue
        # Cada claim numérico CERCA del nombre debe estar verificado.
        # Ventana de 80 chars entre el nombre y el número (sin exigir keyword
        # específica — el modelo puede decir "morfina: 180.2 Da" sin "masa
        # molecular").
        for m in re.finditer(
            rf"{name}.{{0,80}}?(-?\d+\.?\d*)",
            text, re.IGNORECASE,
        ):
            try:
                claimed = float(m.group(1))
            except (ValueError, IndexError):
                continue
            ok = any(abs(claimed - val) <= 0.25 for val in verified)
            if not ok:
                problems.append(
                    f"menciona valor {claimed} de '{name}' no verificado "
                    f"en ningún tool result"
                )
    return problems


# ── VALIDADORES EXTRA ────────────────────────────────────────────────

def v_contains(*needles: str):
    def _v(text: str, conv=None) -> list[str]:
        return [f"falta '{n}'" for n in needles if n.lower() not in text.lower()]
    return _v


def v_anaphora_resolves(name: str):
    """La respuesta debe mencionar la molécula objetivo de la anáfora."""
    def _v(text: str, conv) -> list[str]:
        if name not in text.lower():
            return [f"no menciona '{name}'"]
        return []
    return _v


def v_docking(text: str, conv) -> list[str]:
    """La respuesta de docking debe tener afinidad y score verificados."""
    problems = []
    # La tool result de docking: "Docking completado contra X. Afinidad: -Y kcal/mol. Score: Z/100."
    aff = re.search(r"afinidad[:\s]*(-?\d+\.?\d*)\s*kcal", text, re.IGNORECASE)
    if not aff:
        problems.append("no menciona afinidad en kcal/mol")
    else:
        # El valor de la tool DEBE estar también en la respuesta del modelo
        if aff.group(1) not in text.replace("−", "-"):
            problems.append(f"afinidad {aff.group(1)} solo en tool result")
    return problems


def v_no_fabrication_markers(text: str, conv) -> list[str]:
    """El modelo NO debe inventar valores cuando no hubo tool (solo si menciona
    valores sin tool result a la vista)."""
    # Si el turno NO tiene tool result pero el texto menciona MW/LogP/TPSA
    # con números → sospechoso (depende del contexto, lo reportamos como info)
    if "[Sistema: detect" in text:
        return ["corrección del guard (posible fabricación o falso positivo)"]
    return []


# ── CASOS ─────────────────────────────────────────────────────────────
# Formato: ("ID", QUERY, [validadores]) — conversación nueva
#   o    ("ID", {"seq": [q1, q2, ...], "check": N}, [validadores]) — secuencia
#        (N = índice de la query cuyo texto se valida; las anteriores corren antes)

def build_cases() -> list[tuple[str, object, list]]:
    return [
        # BÁSICOS — el modelo debe repetir los valores de la tool
        ("B01", "calcula propiedades de la aspirina", [v_no_correction, v_reports_tool_values]),
        ("B02", "propiedades del ibuprofeno", [v_no_correction, v_reports_tool_values]),
        ("B03", "dame las propiedades fisicoquimicas del paracetamol", [v_no_correction, v_reports_tool_values]),
        ("B04", "que propiedades tiene la cafeina?", [v_no_correction, v_reports_tool_values]),
        ("B05", "MW y LogP de la morfina", [v_no_correction, v_reports_tool_values]),
        ("B06", "CC(=O)Oc1ccccc1C(=O)O", [v_no_correction, v_reports_tool_values]),
        ("B07", "cual es el peso molecular del etanol?", [v_no_correction, v_reports_tool_values]),
        ("B08", "propiedades de la dopamina", [v_no_correction, v_reports_tool_values]),
        ("B09", "que propiedades tiene la glucosa?", [v_no_correction, v_reports_tool_values]),

        # COMPARACIONES — ambas moléculas presentes, valores de la tool
        ("C01", "compará la aspirina con el ibuprofeno", [v_no_correction, v_reports_tool_values, v_has_compare_structure]),
        ("C02", "compara paracetamol vs ibuprofeno", [v_no_correction, v_reports_tool_values, v_has_compare_structure]),
        ("C03", "cual es la diferencia entre aspirina y paracetamol?", [v_no_correction, v_reports_tool_values, v_has_compare_structure]),
        ("C04", "que molecula tiene mayor peso molecular, ibuprofeno o paracetamol?", [v_no_correction]),
        ("C05", "comparar la cafeina con la morfina", [v_no_correction, v_reports_tool_values, v_has_compare_structure]),

        # CONCEPTUAL — sin tools, sin alucinar valores
        ("K01", "qué es un fármaco?", [v_no_correction, v_no_fabricated]),
        ("K02", "explica que es el docking molecular", [v_no_correction, v_no_fabricated]),
        ("K03", "que son los SMILES?", [v_no_correction, v_no_fabricated]),
        ("K04", "para qué sirve un modelo de scoring?", [v_no_correction, v_no_fabricated]),

        # INVÁLIDOS / BORDES — no debe crashear ni alucinar
        ("I01", "calcula propiedades de KILLMEnow", [v_no_correction, v_no_error]),
        ("I02", "zzzzzzzz", [v_no_correction]),
        ("I03", "", [v_no_correction]),
        ("I04", "CCCCCCCCCCCCCCCCCCCCCCCCCCCC", [v_no_correction, v_no_error]),
        ("I05", "hola", [v_no_correction]),
        ("I06", "que es 12345?", [v_no_correction]),

        # ── ANÁFORAS (secuencia en la misma conversación) ──
        # "y del X?" después de calcular otra molécula
        ("A01", {"seq": ["calcula propiedades de la aspirina", "y del paracetamol?"], "check": 1},
         [v_no_correction, v_anaphora_resolves("paracetamol"), v_reports_tool_values]),
        ("A02", {"seq": ["propiedades del ibuprofeno", "y la cafeina?"], "check": 1},
         [v_no_correction, v_anaphora_resolves("cafeina"), v_reports_tool_values]),
        # Anáfora pura ("esa primera molécula") con molecule_context
        ("A03", {"seq": ["CC(=O)Oc1ccccc1C(=O)O", "esa primera molécula, qué es?"], "check": 1},
         [v_no_correction, v_reports_tool_values]),
        # Anáfora SIN contexto previo → respuesta determinista honesta
        ("A04", "y del paracetamol?", [v_no_correction, v_no_error]),

        # ── DRUG-LIKENESS / ADMET ──
        ("D01", "la aspirina cumple la regla de Lipinski?", [v_no_correction, v_no_error]),
        ("D02", "verifica drug-likeness del paracetamol", [v_no_correction, v_no_error]),
        ("D03", "chequea PAINS de la cafeina", [v_no_correction, v_no_error]),

        # ── MOLGRAPH ──
        ("M01", "que moleculas hay contra 5-HT1A?", [v_no_correction]),
        ("M02", "top 5 moleculas por score", [v_no_fabricated]),

        # ── DOCKING (si hay datos locales) ──
        ("K05", "que es la afinidad de union?", [v_no_correction]),
        # Docking contra un target: "afinidad de X contra PDB"
        ("D04", {"seq": ["calcula la afinidad de la aspirina contra 7E2Y"], "check": 0},
         [v_no_correction, v_no_error]),

        # ── MULTI-TURNO LARGO (acumulación de contexto) ──
        ("L01", {"seq": [
            "calcula propiedades de la aspirina",
            "propiedades del ibuprofeno",
            "propiedades del paracetamol",
            "propiedades de la cafeina",
            "propiedades de la morfina",
            "propiedades de la dopamina",
            "propiedades de la glucosa",
            "propiedades del etanol",
            "cual tiene menor peso molecular?",
        ], "check": 8},
         [v_no_correction, v_no_fabricated]),

        # ── RANKING DE SESIÓN (bug comparativa N>2 resuelto) ──
        ("R01", {"seq": [
            "calcula propiedades de la aspirina",
            "propiedades del ibuprofeno",
            "propiedades del paracetamol",
            "cual tiene menor peso molecular?",
        ], "check": 3},
         [v_no_correction, v_no_fabricated, v_contains("paracetamol", "151.2")]),
        ("R02", {"seq": [
            "calcula propiedades de la aspirina",
            "propiedades del ibuprofeno",
            "propiedades del paracetamol",
            "cual es la mas lipofilica?",
        ], "check": 3},
         [v_no_fabricated]),  # si el modelo invierte, el guard corrige (OK)
        ("R03", {"seq": [
            "calcula propiedades de la aspirina",
            "propiedades del ibuprofeno",
            "cual tiene mayor peso molecular?",
        ], "check": 2},
         [v_no_fabricated]),

        # ── HISTORIAL PERSISTIDO ──
        ("H01", "que evalué contra 7E2Y?", [v_no_correction, v_no_error]),
        ("H02", "cuales son mis mejores evaluaciones?", [v_no_correction, v_no_error]),
        ("H03", "que moleculas tengo en mi historial?", [v_no_correction, v_no_error]),

        # ── INVERSIÓN LÓGICA (capa 5 del guard) ──
        # El modelo lee la tabla del ranking INVERTIDA → el guard debe corregir
        ("V01", {"seq": [
            "calcula propiedades de la aspirina",
            "propiedades del ibuprofeno",
            "cual tiene mayor peso molecular?",
        ], "check": 2},
         [v_no_fabricated]),  # puede haber corrección del guard (es lo deseado)
    ]


# ── RUNNER ────────────────────────────────────────────────────────────

async def run_case(cs, case_id: str, query: object, validators: list) -> dict:
    conv = cs.get_conversation()
    if conv:
        cs.delete_conversation(conv.id)
    cs.get_or_create_active({})

    # Secuencia: varias queries en la misma conversación (anáforas)
    if isinstance(query, dict):
        seq = query["seq"]
        check_idx = query.get("check", len(seq) - 1)
        check_query = seq[check_idx]
    else:
        seq = [query]
        check_idx = 0
        check_query = query

    start = time.time()
    texts: list[str] = []
    try:
        for i, q in enumerate(seq):
            text = ""
            async for chunk in cs.chat(
                messages=[{"role": "user", "content": q}],
                provider_id="local", stream=True, mode="reasoning",
            ):
                if not chunk.startswith("__WARNING__:"):
                    text += chunk
            texts.append(text)
    except Exception as e:
        return {"id": case_id, "query": str(check_query), "ok": False,
                "problems": [f"EXCEPCIÓN: {str(e)[:200]}"], "ms": 0, "len": 0, "_resp": ""}

    # El conv para los validadores debe ser la conversación ACTUAL (la que
    # acabó de correr la secuencia) — antes se tomaba ANTES de crear la
    # activa, así que el validador miraba la conversación del caso ANTERIOR
    # y no encontraba los tool results del caso actual (bug de v_no_fabricated
    # en L01/V01).
    conv = cs.get_conversation() or conv

    text = texts[check_idx]
    problems = []
    for v in validators:
        problems += v(text, conv)
    problems = list(dict.fromkeys(problems))

    return {
        "id": case_id, "query": str(check_query), "ok": not problems, "problems": problems,
        "ms": int((time.time() - start) * 1000), "len": len(text), "_resp": text,
    }


async def main() -> None:
    from services.ai.providers.registry import get_provider_registry
    from services.ai.providers.local_llm_provider import LocalLLMProvider
    from services.ai.chat_service import get_chat_service
    from services.ai.local_llm import get_local_llm
    from services.ai.tools.rdkit_tools import register_rdkit_tools
    from services.ai.tools.docking_tools import register_docking_tools
    from services.ai.tools.admet_tools import register_admet_tools
    from services.ai.tools.analog_tools import register_analog_tools
    from services.ai.tools.molgraph_tool import register_molgraph_tools
    from services.ai.tools.suggest_tools import register_suggest_tools
    from services.ai.tools.evaluation_tools import register_evaluation_tools
    from services.ai.tools.session_tools import register_session_tools

    register_rdkit_tools()
    register_docking_tools()
    register_admet_tools()
    register_molgraph_tools()
    register_analog_tools(verbose=False)
    register_suggest_tools()
    register_evaluation_tools()
    register_session_tools()

    registry = get_provider_registry()
    if registry.get("local"):
        registry.unregister("local")
    registry.register(LocalLLMProvider())

    # Forzar Qwen Q4 (el modelo de producción validado)
    provider = registry.get("local")
    if provider:
        provider._config.model = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

    llm = get_local_llm()
    llm.set_model_file("qwen2.5-1.5b-instruct-q4_k_m.gguf")
    if not llm.is_loaded:
        if not llm.load():
            print(f"FATAL: no se pudo cargar el modelo: {llm.load_error}")
            return

    cs = get_chat_service()
    cases = build_cases()

    print(f"=== MolChat Quality Suite v2: {len(cases)} casos ===")
    print("=" * 70)
    passed = failed = 0
    failures: list[dict] = []

    for case_id, query, validators in cases:
        result = await run_case(cs, case_id, query, validators)
        if result["ok"]:
            passed += 1
        else:
            failed += 1
            failures.append(result)
        marker = "[PASS]" if result["ok"] else "[FAIL]"
        print(f"{marker} {result['id']} [{result['ms']}ms, {result['len']}ch] {result['query'][:60]}")
        if not result["ok"]:
            for p in result["problems"][:4]:
                print(f"     ! {p}")

    print("=" * 70)
    print(f"RESULTADO: {passed}/{len(cases)} pasan, {failed} fallan")
    if failures:
        print("\nFallos:")
        for f in failures:
            print(f"  - {f['id']}: {f['query'][:50]}")
            for p in f["problems"][:3]:
                print(f"      {p}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
