"""Análisis determinista FEP-09, biblioteca estándar, con autotest adversarial."""
from __future__ import annotations
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
CATEGORIES = {
    "hueco_en_el_sitio": ("receptor.huecos", 2, "declared"),
    "estereo_sin_asignar": ("ligando.estereoquimica", 1, "declared"),
    "tautomero_minoritario": ("ligando.tautomero", 1, "declared"),
    "especie_del_ligando": ("ligando.especie", 1, "declared"),
    "cadena_del_sitio_ausente": ("receptor.cadenas_excluidas", 1, "limit"),
    "metal_o_cofactor_retirado": ("entorno.metales_cofactores", 2, "limit"),
    "agua_puente_retirada": ("entorno.aguas", 1, "limit"),
    "protonacion_del_sitio": ("receptor.protonacion", 1, "limit"),
    "tautomero_alternativo_proxy": ("ligando.tautomero", 1, "diagnostic"),
    "especie_opuesta_proxy": ("ligando.especie", 1, "diagnostic"),
}
RISKS = {"REGISTRADO": 0, "PASA": 0, "NO_APLICA": 0, "REVISAR": 1, "ABSTENCION": 2}


def cp(k, n):
    if n == 0:
        return [None, None]
    if not 0 <= k <= n:
        raise ValueError("binomial inválida")
    def tail(p, start, end):
        return sum(math.comb(n, j)*p**j*(1-p)**(n-j) for j in range(start, end+1))
    lower, upper = 0.0, 1.0
    if k:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a+b)/2
            if tail(mid, k, n) < .025:
                a = mid
            else:
                b = mid
        lower = (a+b)/2
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a+b)/2
            if tail(mid, 0, k) > .025:
                a = mid
            else:
                b = mid
        upper = (a+b)/2
    return [round(lower, 10), round(upper, 10)]


def requirements(row):
    return {r["clave"]: r for r in row.get("requirements", [])}


def signature(row, key):
    req = requirements(row)[key]
    return (req["estado"], key in row.get("blockers", []),
            key in row.get("reviews", []) and key not in row.get("routine_reviews", []))


def detection(row, base, key, minimum):
    if not base or base.get("outcome") != "audited":
        return "baseline_unavailable"
    if row.get("outcome") == "detected_before":
        return "detected_before"
    if row.get("outcome") != "audited":
        return "not_measured"
    old, new = requirements(base).get(key), requirements(row).get(key)
    if not old or not new:
        return "missing_requirement"
    rold, rnew = RISKS.get(old["estado"]), RISKS.get(new["estado"])
    if rold is None or rnew is None:
        return "absence_not_detection"
    # La rutina que pasa a ser del caso es aumento de riesgo relevante para protonación.
    if key == "receptor.protonacion" and old["estado"] == new["estado"] == "REVISAR":
        routine_old = key in base.get("routine_reviews", [])
        routine_new = key in row.get("routine_reviews", [])
        if routine_old and not routine_new:
            return "detected_by_auditor"
    if rnew >= minimum and rnew > rold:
        return "detected_by_auditor"
    if rold >= minimum:
        return "baseline_saturated"
    return "not_detected"


def differences(base, row):
    if base.get("outcome") != "audited" or row.get("outcome") != "audited":
        return []
    return [{"requirement": key, "baseline": list(signature(base, key)), "variant": list(signature(row, key))}
            for key in sorted(requirements(base).keys() & requirements(row).keys())
            if signature(base, key) != signature(row, key)]


def analyze(plan, rows, failures):
    ids = [r["case_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("case_id duplicado: no se unen resultados sobrescritos")
    if any(r.get("phase") == "pilot" for r in rows):
        raise ValueError("el piloto no entra en tasas confirmatorias")
    byid = {r["case_id"]: r for r in rows}
    comparisons, categories, controls, noise, public, collateral = [], {}, [], [], [], []
    inventory_cases = [c for c in plan["cases"] if c["arm"] == "A"]
    for category, (key, minimum, coverage) in CATEGORIES.items():
        cases = [c for c in inventory_cases if c["category"] == category]
        counts = Counter()
        audited, comparable, infrastructure = 0, 0, 0
        for case in cases:
            row = byid.get(case["case_id"])
            base = byid.get(case["baseline_id"])
            audited += bool(row and row["outcome"] == "audited")
            infrastructure += bool(row and row["outcome"] == "infrastructure_failure")
            comparable += bool(row and base and row["outcome"] == base["outcome"] == "audited"
                               and key in requirements(base) and key in requirements(row))
            outcome = detection(row, base, key, minimum) if row else "not_executed"
            counts[outcome] += 1
            comparisons.append({"case_id": case["case_id"], "category": category, "requirement": key, "classification": outcome,
                                "baseline_state": requirements(base).get(key, {}).get("estado") if base else None,
                                "variant_state": requirements(row).get(key, {}).get("estado") if row else None})
            if row and base:
                collateral.extend({"case_id": case["case_id"], **d} for d in differences(base, row) if d["requirement"] != key)
        n = len(cases)
        k = counts["detected_by_auditor"]+counts["detected_before"]
        unknown = sum(counts[c] for c in ("not_executed", "baseline_unavailable", "not_measured", "missing_requirement"))
        categories[category] = {"coverage": coverage, "requirement": key, "minimum_risk": minimum, "n_applicable": n,
                                "counts": dict(counts), "detections_by_auditor": counts["detected_by_auditor"],
                                "detected_before": counts["detected_before"], "detections_route": k,
                                "sensitivity_route": k/n if n and not unknown else None,
                                "sensitivity_auditor": counts["detected_by_auditor"]/n if n and not unknown else None,
                                "cp95_route": cp(k, n) if not unknown else [None, None],
                                "n_audited": audited, "n_expected_requirement_comparable": comparable,
                                "n_baseline_saturated": counts["baseline_saturated"],
                                "n_absence_not_detection": counts["absence_not_detection"],
                                "n_infrastructure_failure": infrastructure,
                                "unknown": unknown, "best_case_cp95_lower": cp(k+unknown, n)[0] if n else None,
                                "worst_case_cp95_lower": cp(k, n)[0] if n else None}
    for case in plan["cases"]:
        row = byid.get(case["case_id"])
        if not row:
            continue
        if case["arm"] == "C":
            public.append({"case_id": row["case_id"], "target": row["target"], "ligand": row["ligand"],
                           "source": case["defect"]["source"], "outcome": row["outcome"], "global_state": row["global_state"],
                           "requirements": row.get("requirements", [])})
            continue
        base = byid.get(case["baseline_id"])
        if not base or not case["arm"] == "B" or case["case_id"] == case["baseline_id"]:
            continue
        changes = differences(base, row)
        common = len(requirements(base).keys() & requirements(row).keys()) if base["outcome"] == row["outcome"] == "audited" else 0
        if case["category"] == "baseline":
            noise.append({"case_id": case["case_id"], "n_requirements": common, "changes": changes,
                          "same_receptor_sha256": base.get("receptor_sha256") == row.get("receptor_sha256"),
                          "same_ligand_state": base.get("ligand_state") == row.get("ligand_state")})
        else:
            expected_far = case["category"] == "hueco_lejano"
            unexpected = [d for d in changes if not (expected_far and d["requirement"] == "receptor.huecos" and d["variant"][0] == "REVISAR" and not d["variant"][1])]
            controls.append({"case_id": case["case_id"], "category": case["category"], "n_requirements": common,
                             "n_unexpected_changes": len(unexpected), "changes": changes, "unexpected": unexpected,
                             "outcome": row["outcome"], "baseline_outcome": base["outcome"]})
    strict = [c for c in controls if c["category"] == "seriales_renumerados"]
    count_requirements = sum(c["n_requirements"] for c in strict)
    count_changed = sum(c["n_unexpected_changes"] for c in strict)
    rate = count_changed/count_requirements if count_requirements else None
    control_complete = len(strict) == plan["applicable"].get("seriales_renumerados", 0) and all(c["n_requirements"] for c in strict)
    for data in categories.values():
        if data["coverage"] != "declared":
            data["decision"] = "OUTSIDE_GATE"
        elif data["n_applicable"] < 8:
            data["decision"] = "INCONCLUSIVE"
        elif data["best_case_cp95_lower"] < .5 or rate is not None and rate > .10:
            data["decision"] = "NO_GO"
        elif data["unknown"] or not control_complete:
            data["decision"] = "INCONCLUSIVE"
        else:
            data["decision"] = "GO"
    declared = [d["decision"] for d in categories.values() if d["coverage"] == "declared"]
    overall = "NO_GO" if "NO_GO" in declared else "GO" if all(d == "GO" for d in declared) else "INCONCLUSIVE"
    total_noise = sum(r["n_requirements"] for r in noise)
    changed_noise = sum(len(r["changes"]) for r in noise)
    noise_by_key = Counter(d["requirement"] for r in noise for d in r["changes"])
    return {"experiment": "FEP-09-SENSIBILIDAD", "product_commit": "f183e0af", "preregistration_commit": "9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638",
            "conditions": {"plb_commit": plan["plb_commit"], "receptor_mode": "respetar", "python_backend": "3.11.9",
                           "vina": "1.2.7", "exhaustiveness": 8, "num_poses": 9, "seed": 42, "ph": 7.4,
                           "ligand_selection": "primer registro legible", "n_targets": len(plan["systems"])},
            "tautomer_modes_observed": dict(sorted(Counter(r.get("ligand_state", {}).get("tautomeria", {}).get("modo", "sin dato") for r in rows if r["outcome"] == "audited").items())),
            "protocol_deviations": ["El prerregistro llama canónico al modo por defecto. Las peticiones no lo fuerzan y la API aplica entrada. Se conserva el protocolo original y se declara la condición real; no se cambia el gate."],
            "n_planned": len(plan["cases"]), "n_terminal": len(rows), "outcomes": dict(Counter(r["outcome"] for r in rows)),
            "categories": categories, "comparisons": comparisons, "collateral": collateral,
            "false_alarm": {"n_changed": count_changed, "n_requirements": count_requirements, "rate": rate, "complete": control_complete, "controls": controls},
            "baseline_noise": {"n_comparable": total_noise, "n_changed": changed_noise, "agreement": 1-changed_noise/total_noise if total_noise else None,
                               "changed_by_requirement": dict(sorted(noise_by_key.items())), "pairs": noise},
            "arm_c": {"decision": "INCONCLUSIVE", "n_opened_concerns": len(plan.get("public_sources", [])), "n_measured": len(public), "cases": public,
                      "rates": None, "reason": "menos de cinco preocupaciones verificables; las incidencias no establecen errores en el commit fijado"},
            "failures": failures, "decision": overall,
            "no_demuestra": ["No mide la fracción de problemas reales de preparación que MolDesign detecta.",
                             "No demuestra transferencia a FEP, compatibilidad con FEP+ ni ejecución de energía libre.",
                             "No valida poblaciones tautoméricas, pKa individuales, protonación del receptor ni identidad experimental.",
                             "No audita interfaz, WebView2, runtime staged o instalador.",
                             "No atribuye errores a los autores de PLB. Los estados químicos proxy están fuera del gate.",
                             "No prueba un protocolo forzado a tautómero canónico: la API usó entrada por defecto, discrepante con la descripción del prerregistro.",
                             "La variación de procedencia.commit está confundida por ediciones y commits del arnés durante la medición; no demuestra no determinismo químico.",
                             "Las tasas de ausencia previa al upload no evalúan el diff que produce la preparación."]}


def selftest():
    def row(case, state, outcome="audited", key="receptor.huecos", routine=False):
        return {"case_id": case, "outcome": outcome, "requirements": [{"clave": key, "estado": state}],
                "blockers": [key] if state == "ABSTENCION" else [], "reviews": [key] if state == "REVISAR" else [],
                "routine_reviews": [key] if routine else []}
    base = row("base", "REGISTRADO")
    assert detection(row("defect", "ABSTENCION"), base, "receptor.huecos", 2) == "detected_by_auditor"
    assert detection(row("defect", "REVISAR"), base, "receptor.huecos", 2) == "not_detected"
    assert detection(row("defect", "REGISTRADO"), base, "receptor.huecos", 2) == "not_detected"
    assert detection(row("defect", "ABSTENCION"), row("base", "ABSTENCION"), "receptor.huecos", 2) == "baseline_saturated"
    assert detection(row("defect", "NO_EVALUADO"), base, "receptor.huecos", 2) == "absence_not_detection"
    assert detection(row("defect", None, "detected_before"), base, "receptor.huecos", 2) == "detected_before"
    assert detection(row("defect", None, "infrastructure_failure"), base, "receptor.huecos", 2) == "not_measured"
    assert detection(row("defect", None, "detected_before"), None, "receptor.huecos", 2) == "baseline_unavailable"
    assert detection(row("defect", "REVISAR", key="receptor.protonacion"), row("base", "REVISAR", key="receptor.protonacion", routine=True), "receptor.protonacion", 1) == "detected_by_auditor"
    assert differences(base, row("control", "REGISTRADO")) == []
    assert len(differences(base, row("control", "REVISAR"))) == 1
    assert cp(0, 0) == [None, None]
    assert abs(cp(0, 10)[1]-(1-.025**.1)) < 1e-9
    assert abs(cp(10, 10)[0]-.025**.1) < 1e-9
    assert abs(cp(1, 1)[0]-.025) < 1e-9
    assert cp(14, 15)[0] > .5 and cp(0, 15)[1] < .5
    # Conjunto adversarial: 15 defectos suficientes, 15 controles y bases repetidas.
    cases, records = [], []
    for i in range(15):
        b, d, c = f"t{i}__baseline__0", f"t{i}__gap__0", f"t{i}__control__0"
        cases.extend([{"case_id": b, "arm": "B", "category": "baseline", "baseline_id": b},
                      {"case_id": d, "arm": "A", "category": "hueco_en_el_sitio", "baseline_id": b},
                      {"case_id": c, "arm": "B", "category": "seriales_renumerados", "baseline_id": b}])
        records.extend([row(b, "REGISTRADO"), row(d, "ABSTENCION"), row(c, "REGISTRADO")])
    plan = {"cases": cases, "systems": [{}]*15, "applicable": {"seriales_renumerados": 15}, "plb_commit": "synthetic"}
    metrics = analyze(plan, records, [])
    assert metrics["categories"]["hueco_en_el_sitio"]["decision"] == "GO"
    assert metrics["categories"]["hueco_en_el_sitio"]["n_expected_requirement_comparable"] == 15
    assert metrics["categories"]["hueco_en_el_sitio"]["n_infrastructure_failure"] == 0
    assert metrics["decision"] == "INCONCLUSIVE"  # demás categorías sin n, jamás GO global
    assert metrics["false_alarm"]["rate"] == 0
    alarm_records = [json.loads(json.dumps(r)) for r in records]
    for r in alarm_records:
        if "__control__" in r["case_id"]:
            r.update(row(r["case_id"], "REVISAR"))
    alarms = analyze(plan, alarm_records, [])
    assert alarms["false_alarm"]["rate"] == 1 and alarms["decision"] == "NO_GO"
    noise_plan = {**plan, "cases": plan["cases"]+[{"case_id": "t0__baseline__1", "arm": "B", "category": "baseline", "baseline_id": "t0__baseline__0"}]}
    noisy = analyze(noise_plan, records+[row("t0__baseline__1", "REVISAR")], [])
    assert noisy["baseline_noise"]["agreement"] == 0 and noisy["baseline_noise"]["changed_by_requirement"] == {"receptor.huecos": 1}
    for r in records:
        if "__gap__" in r["case_id"]:
            r.update(row(r["case_id"], "REGISTRADO"))
    metrics = analyze(plan, records, [])
    assert metrics["decision"] == "NO_GO" and metrics["categories"]["hueco_en_el_sitio"]["detections_route"] == 0
    try:
        analyze(plan, records+[records[0]], [])
    except ValueError:
        pass
    else:
        raise AssertionError("no detectó duplicado")
    try:
        analyze(plan, [{**records[0], "phase": "pilot"}], [])
    except ValueError:
        pass
    else:
        raise AssertionError("no detectó contaminación de piloto")
    print("Autotest: detección, no detección, saturación, ausencias, rechazo, fallo, controles, CP y gates verificados")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    selftest()
    if args.selftest and not args.merge:
        return
    if args.merge:
        records, failures = [], []
        for shard in sorted((ART / "_work").glob("shard-*")):
            records.extend(json.loads(l) for l in (shard / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l)
            failures.extend(json.loads(l) for l in (shard / "failures.jsonl").read_text(encoding="utf-8").splitlines() if l)
        records.sort(key=lambda r: r["case_id"])
        failures.sort(key=lambda r: r["case_id"])
        # analyze detecta duplicados ANTES de sobrescribir la unión.
        metrics = analyze(json.loads((ART / "inventory.json").read_text(encoding="utf-8")), records, failures)
        for name, values in (("per_complex.jsonl", records), ("failures.jsonl", failures)):
            (ART / name).write_text("".join(json.dumps(v, ensure_ascii=False, sort_keys=True)+"\n" for v in values), encoding="utf-8", newline="\n")
    else:
        records = [json.loads(l) for l in (ART / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l]
        failures = [json.loads(l) for l in (ART / "failures.jsonl").read_text(encoding="utf-8").splitlines() if l]
        metrics = analyze(json.loads((ART / "inventory.json").read_text(encoding="utf-8")), records, failures)
    (ART / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": metrics["decision"], "terminal": metrics["n_terminal"], "outcomes": metrics["outcomes"], "false_alarm": metrics["false_alarm"]["rate"]}))


if __name__ == "__main__":
    main()
