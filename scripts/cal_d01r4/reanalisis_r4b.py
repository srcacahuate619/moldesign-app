r"""CAL-D-01 R4B: reanálisis enmendado de R4 sin el compuesto 4-67. No acopla nada.

Lee los resultados sellados de R4 (per_complex.jsonl, failures.jsonl, puerta_pose.json) y recalcula P1/P2 con la
única enmienda de `entrada/REGISTRO_R4B.md`. Comprueba que los números coinciden con los de R4 (mismos datos, mismo
estadístico, misma semilla). La decisión es INCONCLUSIVE por construcción: el criterio se enmendó tras ver los scores.

    python scripts/cal_d01r4/reanalisis_r4b.py congelar
    python scripts/cal_d01r4/reanalisis_r4b.py analizar
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = next(p for p in AQUI.parents if (p / "curated_targets.json").is_file())
ART = RAIZ / "scripts" / "artifacts_science"
R4 = ART / "CAL-D-01-R4-VMAT2-8T69"
EXP = ART / "CAL-D-01-R4B-VMAT2-8T69"
ENTRADA = EXP / "entrada"
EXCLUIDO = "4-67"
CAUSA = ("el pipeline del producto no completa el compuesto (biciclo[1.1.1]pentano): 'Timeout: evaluación excedió 1200s' "
         "en los dos intentos")
MIN_PADRES = 85
sys.path.insert(0, str(AQUI))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _leer(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _escribir(p: Path, o) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def congelar() -> None:
    man = _leer(R4 / "manifest.json")
    if man.get("decision") != "NO_GO" or not man.get("sealed"):
        raise SystemExit("R4 tiene que estar sellado y cerrado")
    _escribir(ENTRADA / "protocolo.json", {
        "experimento": EXP.name, "congelado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "no_acopla": True, "reanaliza": R4.name, "r4_decision": man["decision"],
        "enmienda": "un fallo persistente del producto en un compuesto, declarado, no impide el criterio si quedan >= 85 padres",
        "excluido": {"padre": EXCLUIDO, "causa": CAUSA}, "minimo_padres": MIN_PADRES,
        "decision_por_construccion": "INCONCLUSIVE (criterio enmendado tras ver los scores)",
        "hashes": {"REGISTRO_R4B.md": _sha(ENTRADA / "REGISTRO_R4B.md"),
                   "reanalisis_r4b.py": _sha(Path(__file__)), "rho_peor.py": _sha(AQUI / "rho_peor.py"),
                   "r4/per_complex.jsonl": _sha(R4 / "per_complex.jsonl"), "r4/failures.jsonl": _sha(R4 / "failures.jsonl"),
                   "r4/metrics.json": _sha(R4 / "metrics.json"), "r4/puerta_pose.json": _sha(R4 / "puerta_pose.json"),
                   "r4/entrada/protocolo.json": _sha(R4 / "entrada" / "protocolo.json")}})
    print("R4B congelado")


def analizar() -> None:
    import rho_peor as rp
    proto = _leer(ENTRADA / "protocolo.json")
    for k, p in {"REGISTRO_R4B.md": ENTRADA / "REGISTRO_R4B.md", "reanalisis_r4b.py": Path(__file__),
                 "rho_peor.py": AQUI / "rho_peor.py", "r4/per_complex.jsonl": R4 / "per_complex.jsonl",
                 "r4/metrics.json": R4 / "metrics.json", "r4/puerta_pose.json": R4 / "puerta_pose.json"}.items():
        if proto["hashes"][k] != _sha(p):
            raise SystemExit(f"{k} cambió desde que se congeló")
    filas = [json.loads(l) for l in (R4 / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    fallos = [json.loads(l) for l in (R4 / "failures.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if [f["id"] for f in fallos] != [f"panel-{EXCLUIDO}"]:
        raise SystemExit(f"los fallos de R4 no son sólo {EXCLUIDO}: {fallos}")
    puerta = _leer(R4 / "puerta_pose.json")
    q = [f["Q"] for f in filas]
    ki = [f["ki_nM"] for f in filas]
    pki = [f["pki"] for f in filas]
    panel = rp.Panel(ki)
    rho = rp.spearman(q, pki)
    peor = rp.rho_peor(panel, q)
    comp = rp.pares_comparables(ki)
    conc = rp.concordancia(comp, q)
    ic = rp.bootstrap(ki, q)
    r4 = _leer(R4 / "metrics.json")
    iguales = {"rho": math.isclose(rho, r4["rho_Q_pKi"], abs_tol=1e-12), "rho_peor": math.isclose(peor, r4["rho_peor"], abs_tol=1e-12),
               "ic95_rho": ic["rho"] == r4["ic95_rho"], "ic95_rho_peor": ic["rho_peor"] == r4["ic95_rho_peor"],
               "concordancia": math.isclose(conc, r4["p2"]["concordancia"], abs_tol=1e-12)}
    if not all(iguales.values()):
        raise SystemExit(f"los números no coinciden con R4: {iguales}")
    n = len(q)
    cumple = (puerta["decision"] == "GO" and n >= MIN_PADRES and ic["rho"][0] > 0 and ic["rho_peor"][0] > 0)
    metrics = {
        "experimento": EXP.name, "reanaliza": R4.name, "no_acopla": True,
        "analizado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocolo_sha256": _sha(ENTRADA / "protocolo.json"),
        "n_evaluados": n, "excluidos": [{"padre": EXCLUIDO, "causa": CAUSA}],
        "rho_Q_pKi": rho, "rho_peor": peor, "ic95_rho": ic["rho"], "ic95_rho_peor": ic["rho_peor"],
        "bootstrap": {k: ic[k] for k in ("n_replicas", "descartadas", "semilla")},
        "p2": {"concordancia": conc, "pares_comparables": int(comp.sum()), "ic95": ic["concordancia"]},
        "coincide_con_r4": iguales, "puerta_pose": puerta["decision"],
        "criterio_enmendado_cumplido": bool(cumple), "confirmatorio": False,
        "decision": "INCONCLUSIVE",
        "razon": ("criterio enmendado cumplido pero enmendado tras ver los scores: no confirmatorio, no promociona"
                  if cumple else "criterio enmendado no cumplido"),
    }
    _escribir(EXP / "metrics.json", metrics)
    with (EXP / "per_complex.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with (EXP / "failures.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"id": f"panel-{EXCLUIDO}", "excluido_por_enmienda": True, "causa": CAUSA}, ensure_ascii=False) + "\n")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    {"congelar": congelar, "analizar": analizar}[sys.argv[1]]()
