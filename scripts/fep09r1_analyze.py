"""FEP-09-R1: el análisis de FEP-09, sin cambios, más lo que R1 añade a su prerregistro.

`fep09_analyze.analyze` (sellado en FEP-09-SENSIBILIDAD) calcula detecciones, IC exactos, falsa
alarma y gate. Aquí se corrige la identidad del experimento y se añaden tres lecturas
preregistradas:

1. `referencia`: el estado de `entorno.referencia` en cada auditoría (P01: en FEP-09 quedó
   NO_EVALUADO en 127 de 127);
2. `frente_a_fep09`: caso a caso, la clasificación del requisito esperado en FEP-09 y en R1;
3. `estereo_por_diana`: las detecciones de estereoquímica por diana, porque los 21 casos están
   agrupados en 7 dianas.

    python scripts/fep09r1_analyze.py [--merge] [--selftest]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import fep09_analyze
from fep09_analyze import CATEGORIES, analyze, detection, requirements

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-R1"
FEP09 = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
NO_DEMUESTRA = [
    "No mide la fracción de problemas reales de preparación que MolDesign detecta.",
    "No demuestra transferencia a FEP, compatibilidad con FEP+ ni ejecución de energía libre.",
    "No valida poblaciones tautoméricas, pKa individuales, protonación del receptor ni identidad experimental.",
    "No audita interfaz, WebView2, runtime staged ni instalador.",
    "No atribuye errores a los autores de PLB. Los estados químicos proxy están fuera del gate.",
    "Los 21 casos de estereoquímica son 3 ligandos por diana en 7 dianas: el IC los trata como independientes.",
    "Las tasas de ausencia previa al upload no evalúan el diff que produce la preparación.",
]


def _filas(ruta: Path) -> list[dict]:
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l] if ruta.exists() else []


def referencia(filas: list[dict]) -> dict:
    """Desde dónde se midió cada auditoría: el ligando (P01 arreglado) o la caja."""
    estados, razones = Counter(), Counter()
    for fila in filas:
        if fila.get("outcome") != "audited":
            continue
        req = requirements(fila).get("entorno.referencia") or {}
        estados[req.get("estado", "ausente")] += 1
        if req.get("estado") != "REGISTRADO":
            razones[str(req.get("razon"))] += 1
    return {"estados": dict(estados), "razones_no_registrado": dict(razones)}


def frente_a_fep09(plan: dict, filas: list[dict], filas_fep09: list[dict]) -> dict:
    """La clasificación del requisito esperado, en FEP-09 y en R1, para cada caso común."""
    r1, antes = {f["case_id"]: f for f in filas}, {f["case_id"]: f for f in filas_fep09}
    casos, resumen = [], defaultdict(Counter)
    for caso in plan["cases"]:
        if caso["arm"] != "A" or caso["category"] not in CATEGORIES or caso["case_id"] not in antes:
            continue
        clave, minimo, _ = CATEGORIES[caso["category"]]
        viejo = detection(antes[caso["case_id"]], antes.get(caso["baseline_id"]), clave, minimo)
        nuevo = (detection(r1[caso["case_id"]], r1.get(caso["baseline_id"]), clave, minimo)
                 if caso["case_id"] in r1 else "not_executed")
        casos.append({
            "case_id": caso["case_id"], "category": caso["category"], "requirement": clave,
            "fep09": viejo, "r1": nuevo,
            "estado_fep09": requirements(antes[caso["case_id"]]).get(clave, {}).get("estado"),
            "estado_r1": requirements(r1.get(caso["case_id"], {})).get(clave, {}).get("estado"),
        })
        resumen[caso["category"]][f"{viejo} -> {nuevo}"] += 1
    return {"casos": casos, "resumen": {k: dict(v) for k, v in sorted(resumen.items())}}


def estereo_por_diana(metricas: dict) -> dict:
    por = defaultdict(Counter)
    for c in metricas["comparisons"]:
        if c["category"] == "estereo_sin_asignar":
            por[c["case_id"].split("__")[0]][c["classification"]] += 1
    return {k: dict(v) for k, v in sorted(por.items())}


def selftest_r1():
    def fila(caso, ref="REGISTRADO", clave="ligando.estereoquimica", estado="REVISAR", outcome="audited"):
        return {"case_id": caso, "outcome": outcome,
                "requirements": [{"clave": clave, "estado": estado}, {"clave": "entorno.referencia", "estado": ref}],
                "blockers": [], "reviews": [clave] if estado == "REVISAR" else [], "routine_reviews": []}
    assert referencia([fila("a"), fila("b", ref="NO_EVALUADO"), fila("c", outcome="infrastructure_failure")])["estados"] \
        == {"REGISTRADO": 1, "NO_EVALUADO": 1}
    plan = {"cases": [{"case_id": "t__estereo_sin_asignar__0", "arm": "A", "category": "estereo_sin_asignar",
                       "baseline_id": "t__baseline__0"},
                      {"case_id": "t__estereo_sin_asignar__4", "arm": "A", "category": "estereo_sin_asignar",
                       "baseline_id": "t__baseline_estereo__4"}]}
    viejo = [fila("t__baseline__0", estado="REGISTRADO"), fila("t__estereo_sin_asignar__0")]
    nuevo = [fila("t__baseline__0", estado="REGISTRADO"), fila("t__estereo_sin_asignar__0", estado="REGISTRADO")]
    comp = frente_a_fep09(plan, nuevo, viejo)
    # Sólo se comparan los casos que existen en FEP-09; uno que dejó de detectarse se ve.
    assert [c["case_id"] for c in comp["casos"]] == ["t__estereo_sin_asignar__0"]
    assert comp["resumen"] == {"estereo_sin_asignar": {"detected_by_auditor -> not_detected": 1}}
    assert frente_a_fep09(plan, [], viejo)["casos"][0]["r1"] == "not_executed"
    print("Autotest R1: referencia, comparación con FEP-09 y casos ausentes verificados")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    fep09_analyze.selftest()
    selftest_r1()
    if args.selftest and not args.merge:
        return
    if args.merge:
        registros, fallos = [], []
        for shard in sorted((ART / "_work").glob("shard-*")):
            registros.extend(_filas(shard / "per_complex.jsonl"))
            fallos.extend(_filas(shard / "failures.jsonl"))
        registros.sort(key=lambda r: r["case_id"])
        fallos.sort(key=lambda r: r["case_id"])
    else:
        registros, fallos = _filas(ART / "per_complex.jsonl"), _filas(ART / "failures.jsonl")
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    # `analyze` detecta duplicados y filas del piloto ANTES de escribir nada.
    metricas = analyze(plan, registros, fallos)
    if args.merge:
        for nombre, valores in (("per_complex.jsonl", registros), ("failures.jsonl", fallos)):
            (ART / nombre).write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in valores),
                                      encoding="utf-8", newline="\n")
    registro = json.loads((ART / "registered_conditions.json").read_text(encoding="utf-8"))
    desviaciones = ART / "protocol_deviations.json"
    metricas.update(
        experiment="FEP-09-R1",
        product_commit=registro["product_under_test"]["commit"],
        preregistration_commit=sorted({r.get("preregistration_commit") for r in registros} - {None}),
        protocol_deviations=json.loads(desviaciones.read_text(encoding="utf-8")) if desviaciones.exists() else [],
        no_demuestra=NO_DEMUESTRA,
    )
    metricas["conditions"].update(
        ligand_selection="primer registro legible; estereoquímica: hasta 3 ligandos con estereocentro asignado por "
                         "diana, en el orden del SDF, cada uno con su línea base",
        tautomer_mode="sin forzar; efectivo «entrada»")
    metricas["r1"] = {"referencia": referencia(registros),
                      "frente_a_fep09": frente_a_fep09(plan, registros, _filas(FEP09 / "per_complex.jsonl")),
                      "estereo_por_diana": estereo_por_diana(metricas)}
    (ART / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({"decision": metricas["decision"], "terminal": metricas["n_terminal"], "outcomes": metricas["outcomes"],
                      "false_alarm": metricas["false_alarm"]["rate"], "referencia": metricas["r1"]["referencia"]["estados"],
                      "categorias": {k: (v["detections_route"], v["n_applicable"], v["decision"])
                                     for k, v in metricas["categories"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
