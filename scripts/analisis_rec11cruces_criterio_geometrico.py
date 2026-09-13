#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REC-11-CRUCES: el criterio geometrico de REC-09, contrastado contra el de novo.

MEDICION DESCRIPTIVA POST-HOC DECLARADA. La tabla de contingencia se inspecciono al
proponer este analisis, ANTES de escribir su registro. No es un prerregistro ciego y no
se presenta como tal: no hay gate, no hay decision que dependa de un umbral, y el
resultado genera una hipotesis en vez de contrastarla. Se registra para que el cruce
quede auditable y con su limitacion escrita, igual que MF-33-CRUCES.

La pregunta: REC-09 marco como "agua bloqueante" la que tiene algun atomo a <=2.6 A de un
atomo pesado del ligando CRISTALOGRAFICO. Ese criterio necesita conocer la pose. REC-11
midio el efecto de quitar TODAS las aguas sobre el docking DE NOVO, donde esa pose no se
conoce. Si el criterio capturase el mecanismo, los complejos donde quitar las aguas gana
en de novo deberian estar enriquecidos en aguas bloqueantes.

Sin computo: cruza dos artefactos sellados.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from math import comb
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ART = ROOT / "scripts" / "artifacts_science"
OUT = ART / "REC-11-CRUCES"


def fisher_exacto_bilateral(a: int, b: int, c: int, d: int) -> float:
    """p bilateral por el metodo de sumar las tablas no mas probables que la observada."""
    fila1, fila2 = a + b, c + d
    col1, n = a + c, a + b + c + d

    def prob(x: int) -> float:
        return (comb(fila1, x) * comb(fila2, col1 - x)) / comb(n, col1)

    p_obs = prob(a)
    lo = max(0, col1 - fila2)
    hi = min(fila1, col1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p_obs * (1 + 1e-9)))


def main() -> int:
    r09 = {}
    for l in (ART / "REC-09" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            r09[r["pid"]] = r
    r11 = [json.loads(l) for l in
           (ART / "REC-11" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
           if l.strip()]

    filas: List[Dict[str, Any]] = []
    for r in r11:
        pid = r["pid"]
        ref = r09.get(pid, {})
        bloq = ref.get("n_aguas_bloqueantes")
        filas.append({
            "pid": pid, "estrato": r["estrato"],
            "n_aguas_bloqueantes_REC09": bloq,
            "tiene_bloqueante": None if bloq is None else bloq > 0,
            "atomos_agua_quitados_REC11": r["atomos_agua_quitados"],
            "oraculo_CON": r["CON"]["oraculo"], "oraculo_SIN": r["SIN"]["oraculo"],
            "delta_oraculo": r["delta_oraculo"],
            "gana_SIN": bool(r.get("gana_SIN")), "gana_CON": bool(r.get("gana_CON")),
            "discordante": bool(r.get("discordante")),
            "absurdo_REC09": ref.get("absurdo"),
            "delta_score_REC09": ref.get("delta"),
        })

    ok = [f for f in filas if f["tiene_bloqueante"] is not None]
    con_b = [f for f in ok if f["tiene_bloqueante"]]
    sin_b = [f for f in ok if not f["tiene_bloqueante"]]

    def cuenta(g, k): return sum(1 for f in g if f[k])

    # Tabla A: sobre los 116. Enriquecimiento de "quitarlas gana" entre los que tienen
    # agua bloqueante frente a los que no.
    a, b = cuenta(con_b, "gana_SIN"), len(con_b) - cuenta(con_b, "gana_SIN")
    c, d = cuenta(sin_b, "gana_SIN"), len(sin_b) - cuenta(sin_b, "gana_SIN")
    pA = fisher_exacto_bilateral(a, b, c, d)
    tasa_con = a / len(con_b) if con_b else 0.0
    tasa_sin = c / len(sin_b) if sin_b else 0.0

    # Tabla B: solo los 18 discordantes. Entre quienes SI se movieron, el criterio
    # predice la DIRECCION del movimiento?
    disc = [f for f in ok if f["discordante"]]
    a2 = sum(1 for f in disc if f["tiene_bloqueante"] and f["gana_SIN"])
    b2 = sum(1 for f in disc if f["tiene_bloqueante"] and f["gana_CON"])
    c2 = sum(1 for f in disc if not f["tiene_bloqueante"] and f["gana_SIN"])
    d2 = sum(1 for f in disc if not f["tiene_bloqueante"] and f["gana_CON"])
    pB = fisher_exacto_bilateral(a2, b2, c2, d2)

    rescatados_sin_bloqueante = sorted(f["pid"] for f in ok if f["gana_SIN"]
                                       and not f["tiene_bloqueante"])

    out = {
        "analisis_id": "REC-11-CRUCES",
        "tipo": "medicion descriptiva POST-HOC declarada; sin gate y sin decision por umbral",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "advertencia_de_procedencia": (
            "La tabla de contingencia se inspecciono al proponer este analisis, ANTES de "
            "escribir su registro. NO es un prerregistro ciego. Los p que siguen son "
            "descriptivos y no sostienen ninguna afirmacion confirmatoria."),
        "fuentes": ["scripts/artifacts_science/REC-09/per_complex.jsonl",
                    "scripts/artifacts_science/REC-11/per_complex.jsonl"],
        "n": len(ok),
        "tabla_A_sobre_los_116": {
            "definicion": "quitar las aguas GANA el oraculo, segun tenga o no agua bloqueante por el criterio de 2.6 A de REC-09",
            "con_bloqueante": {"gana_SIN": a, "resto": b, "n": len(con_b), "tasa": round(tasa_con, 4)},
            "sin_bloqueante": {"gana_SIN": c, "resto": d, "n": len(sin_b), "tasa": round(tasa_sin, 4)},
            "enriquecimiento": round(tasa_con / tasa_sin, 2) if tasa_sin else None,
            "fisher_p_bilateral": round(pA, 6)},
        "tabla_B_solo_los_18_discordantes": {
            "definicion": "entre los que SI se movieron, el criterio predice la direccion?",
            "con_bloqueante": {"gana_SIN": a2, "gana_CON": b2},
            "sin_bloqueante": {"gana_SIN": c2, "gana_CON": d2},
            "fisher_p_bilateral": round(pB, 6)},
        "hallazgo_nominal": {
            "rescatados_por_quitar_aguas_con_CERO_bloqueantes": rescatados_sin_bloqueante,
            "de_cuantos_rescatados_en_total": cuenta(ok, "gana_SIN")},
        "limites_declarados": [
            "POST-HOC: la tabla se vio antes de escribir el registro; los p son descriptivos",
            "n muy pequeno en las celdas: 18 discordantes en total y celdas de 1 a 7",
            "no refuta REC-09, que midio scoring del cristal y no docking de novo; contrasta el ALCANCE de su criterio, no su resultado",
            "no autoriza cambiar la politica de aguas: eso lo gobierna REC-11, que salio SIN_DIFERENCIA_DETECTABLE",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")
    (OUT / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (OUT / "failures.jsonl").write_text("", encoding="utf-8", newline="\n")
    print(f"[REC-11-CRUCES] n={len(ok)} tabla_A: {tasa_con:.4f} vs {tasa_sin:.4f} "
          f"(x{out['tabla_A_sobre_los_116']['enriquecimiento']}) p={pA:.4f} | "
          f"tabla_B p={pB:.4f} | rescatados sin bloqueante: {rescatados_sin_bloqueante}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
