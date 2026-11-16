"""Recuentos de revisión independientes; lee artefactos originales sin modificarlos."""
import ast
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from scipy.stats import binomtest, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ART = ROOT / "scripts/artifacts_science"


def rows(name):
    return [json.loads(s) for s in (ART / name / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()]


def main():
    water = rows("DEC-104-D03-R1")
    success = {arm: [sum(c["rmsd_top1_A"] <= 2 for c in r["brazos"][arm]["casos"]) >= 3
                     for r in water] for arm in ("SIN", "SELECTIVAS", "TODAS")}
    wins = sum(a and not b for a, b in zip(success["SELECTIVAS"], success["SIN"]))
    losses = sum(b and not a for a, b in zip(success["SELECTIVAS"], success["SIN"]))
    d03 = {"n": len(water), "familias": dict(Counter(r["familia"] for r in water)),
           "exitos": {k: sum(v) for k, v in success.items()}, "discordancias": [wins, losses],
           "p_exacto": binomtest(wins, wins + losses, .5).pvalue}
    assert d03["exitos"] == {"SIN": 8, "SELECTIVAS": 11, "TODAS": 13}
    metals = rows("DEC-104-D05-PROLIF")
    positive = [r for r in metals if r["brazo"] == "cristal" and r["cristal_coordina"]]
    negative = [r for r in metals if r["brazo"] == "trasladado" or (r["brazo"] == "cristal" and not r["cristal_coordina"])]
    d05 = {"positivos": len(positive), "detectados": sum(bool(r["hits"]) for r in positive),
           "negativos": len(negative), "falsos_positivos": sum(bool(r["hits"]) for r in negative),
           "tipo_negativos": dict(Counter(r["brazo"] for r in negative))}
    assert (d05["positivos"], d05["detectados"], d05["negativos"], d05["falsos_positivos"]) == (5, 3, 9, 0)
    exhaustive = rows("DEC-104-D06-8HFI")
    states = defaultdict(set)
    d06 = {"corridas": len(exhaustive), "brazos": {}}
    for r in exhaustive:
        if r["pki"] is not None:
            states[r["padre"]].add(r["microestado"])
    for arm in sorted({r["brazo"] for r in exhaustive}):
        group = [r for r in exhaustive if r["brazo"] == arm and r["pki"] is not None]
        d06["brazos"][arm] = {"padres": len(group),
            "rho": spearmanr([-r["energia_kcal"] for r in group], [r["pki"] for r in group]).statistic,
            "mediana_s": median(sum(a["segundos"] for a in r["intentos"]) for r in group)}
    d06["padres_con_microestado_distinto_entre_brazos"] = {k: sorted(v) for k, v in states.items() if len(v) > 1}
    assert d06["corridas"] == 243 and not d06["padres_con_microestado_distinto_entre_brazos"]
    d06["delta_rho_32_8"] = d06["brazos"]["e32"]["rho"] - d06["brazos"]["e8"]["rho"]
    ums = rows("DEC-104-D08-REPLAY")
    positives = [r for r in ums if r["familia_esperada"]]
    negatives = [r for r in ums if not r["familia_esperada"]]
    families = {"sulfonamida", "hidroxamico", "tiol"}
    d08 = {a: {"positivos_reconocidos": sum(r["familia_esperada"] in r[a] for r in positives),
               "negativos_sin_familias_estudiadas": sum(not families.intersection(r[a]) for r in negatives),
               "negativos_sin_ninguna_familia": sum(not r[a] for r in negatives)} for a in ("antes", "despues")}
    assert [d08[a]["positivos_reconocidos"] for a in d08] == [6, 12]
    adjudication = json.loads((HERE.parent / "investigacion-1.0.4/D09-adjudicacion.json").read_bytes())["filas"]
    d09 = {"n": len(adjudication), "acuerdos": sum(r["A"] == r["B"] for r in adjudication),
           "dictamenes": dict(Counter(r["A"] + "/" + r["B"] for r in adjudication))}
    assert d09["n"] == 44 and d09["acuerdos"] == 38
    herg = json.loads((HERE.parent / "herg-umbral-2026-11-15/resultados.json").read_bytes())["piloto"]["semillas_y_fallos"]
    counts = {}
    for seed in (42, 43):
        by_name = {r["compound"]: r for r in herg if r["seed"] == 42}
        if seed == 43:
            by_name.update({r["compound"]: r for r in herg if r["seed"] == 43})
        counts[str(seed)] = {str(cut): {
            "positivos_alertados": sum(r["ic50_um"] <= 10 and not r["lower_bound"] and r["score"] < cut for r in by_name.values()),
            "controles_alertados": sum((r["ic50_um"] > 10 or r["lower_bound"]) and r["score"] < cut for r in by_name.values())}
            for cut in (-7, -7.5)}
    # Ejecutar sólo la función pura del normalizador, sin inicializar servicios del producto.
    tree = ast.parse((ROOT / "backend/scoring/normalizer.py").read_bytes())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"clamp_score", "normalize_affinity"}]
    ns = {"math": math}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "normalizer-funciones", "exec"), ns)
    floor = next(r["affinity_threshold"] for r in json.loads((ROOT / "curated_targets.json").read_bytes()) if r["pdb_id"] == "5VA1")
    counts["normalizador"] = {"parametro_catalogo": floor,
        "score_30_atomos_menos_6_8": {str(t): ns["normalize_affinity"](-6.8, 30, threshold=t) for t in (-7.5, -7)}}
    output = {"base": "4b8eaf3e229b89aa4032c8e6bbd6711cadf0b5aa", "D03": d03, "D05": d05,
              "D06": d06, "D08": d08, "D09": d09, "hERG": counts,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "cifras.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
