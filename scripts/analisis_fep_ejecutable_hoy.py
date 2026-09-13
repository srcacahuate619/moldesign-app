#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep_ejecutable_hoy.py — FEP-07: ¿cuántos cálculos FEP+ se pueden correr HOY?

La cartera H tiene tres auditorías y ninguna responde la pregunta que decide el trabajo:

  * `FEP-01` cuenta ligandos con tautómero ambiguo — 164 de 203, refinado a **54** por
    `FEP-01-EXT` cuando se mide dónde acaba el protón;
  * `FEP-02` cuenta receptores con huecos — 86 de 203, refinado a **41** por `FEP-02-EXT`
    cuando se mide si el hueco está en el sitio;
  * `FEP-03` cuenta parejas congenéricas — **91 aptas** de 487 evaluadas.

Cada una mira una pieza. Un cálculo de energía libre relativa necesita **las tres a la vez**
y sobre **los dos miembros de la pareja**: si un solo extremo tiene el tautómero sin decidir
o un hueco en el bolsillo, la pareja no se puede correr.

Este experimento hace el cruce. No mide nada nuevo: **une lo ya sellado** y devuelve el
numero que ninguno de los cinco artefactos anteriores contiene.

Las tres cuentas que se producen
--------------------------------
  **EJECUTABLE HOY**       ambos extremos limpios en ligando y receptor;
  **BLOQUEADA POR TAUTOMERO** el unico defecto es una decision de tautomero — barata,
                              es declarar, no reparar;
  **BLOQUEADA POR RECEPTOR**  algun extremo necesita reparacion estructural — cara.

La distincion importa porque las dos barreras cuestan ordenes de magnitud distintos:
declarar un tautomero es una decision quimica documentada; reparar un hueco en el sitio es
modelado estructural.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"


def _cargar(exp: str, fichero: str = "per_complex.jsonl") -> List[Dict[str, Any]]:
    p = ART / exp / fichero
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-07: parejas FEP+ ejecutables hoy")
    ap.add_argument("--salida", default=str(ART / "FEP-07"))
    args = ap.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── lo ya sellado ────────────────────────────────────────────────────────
    parejas = [r for r in _cargar("FEP-03", "parejas.jsonl") if r.get("apta_fep")]
    # ligando: necesita decision de tautomero si el proton se mueve (FEP-01-EXT)
    taut: Set[str] = {r["pid"] for r in _cargar("FEP-01-EXT") if r.get("patron_h_cambia")}
    # receptor: necesita reparacion si tiene hueco EN EL SITIO (FEP-02-EXT)
    hueco: Set[str] = {r["pid"] for r in _cargar("FEP-02-EXT")
                       if r.get("clasificacion") == "EN_EL_SITIO"}
    # y el resto de la documentacion de receptor que FEP-02 exigia
    doc: Dict[str, bool] = {r["pid"]: bool(r.get("documentado_para_fep"))
                            for r in _cargar("FEP-02")}

    filas: List[Dict[str, Any]] = []
    for p in parejas:
        a, b = p["pid_a"], p["pid_b"]
        ta, tb = a in taut, b in taut
        ha, hb = a in hueco, b in hueco
        r = {
            "pid_a": a, "pid_b": b,
            "cobertura_mcs": p.get("cobertura_mcs"), "perturbacion": p.get("perturbacion"),
            "tautomero_pendiente": sorted([x for x, f in ((a, ta), (b, tb)) if f]),
            "hueco_en_sitio": sorted([x for x, f in ((a, ha), (b, hb)) if f]),
            "receptor_documentado": {a: doc.get(a), b: doc.get(b)},
        }
        if ha or hb:
            r["estado"] = "BLOQUEADA_POR_RECEPTOR"
        elif ta or tb:
            r["estado"] = "BLOQUEADA_POR_TAUTOMERO"
        else:
            r["estado"] = "EJECUTABLE_HOY"
        filas.append(r)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    est = Counter(r["estado"] for r in filas)
    # dianas: cuantas quedan representadas entre las ejecutables
    ejec = [r for r in filas if r["estado"] == "EJECUTABLE_HOY"]
    pids_ejec: Set[str] = set()
    for r in ejec:
        pids_ejec.update((r["pid_a"], r["pid_b"]))

    metrics = {
        "experiment_id": "FEP-07",
        "tipo": "cruce de artefactos sellados, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 3),
        "fuentes": {
            "FEP-03/parejas.jsonl": "parejas congenericas aptas",
            "FEP-01-EXT": "ligandos donde el proton se mueve (decision de tautomero pendiente)",
            "FEP-02-EXT": "receptores con hueco EN EL SITIO (reparacion estructural)",
            "FEP-02": "documentado_para_fep, criterio completo de receptor"},
        "n_parejas_aptas": len(parejas),
        "estado": dict(est),
        "EJECUTABLE_HOY": {
            "n": est["EJECUTABLE_HOY"],
            "fraccion_de_aptas": round(est["EJECUTABLE_HOY"] / len(parejas), 4) if parejas else None,
            "n_complejos_implicados": len(pids_ejec)},
        "si_se_declaran_los_tautomeros": {
            "n": est["EJECUTABLE_HOY"] + est["BLOQUEADA_POR_TAUTOMERO"],
            "coste": "declarar tautomero, no reparar estructura"},
        "limitacion_declarada": (
            "Ejecutable HOY significa 'sin los dos bloqueos medidos', no 'lista para "
            "produccion'. FEP-02 exige ademas documentar cadenas, disulfuros, metales, "
            "cofactores y aguas, y ese criterio completo (documentado_para_fep) se reporta "
            "aparte sin usarse para clasificar, porque lo cumplen muy pocos y absorberia "
            "toda la senal. El numero es una COTA SUPERIOR de lo ejecutable."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    print(f"[FEP-07] {len(parejas)} parejas aptas de FEP-03, cruzadas en "
          f"{metrics['duration_seconds']}s")
    for k in ("EJECUTABLE_HOY", "BLOQUEADA_POR_TAUTOMERO", "BLOQUEADA_POR_RECEPTOR"):
        print(f"  {k:26s} {est[k]:3d}")
    print(f"  -> ejecutables hoy: {est['EJECUTABLE_HOY']} parejas sobre "
          f"{len(pids_ejec)} complejos")
    print(f"  -> tras declarar tautomeros: "
          f"{metrics['si_se_declaran_los_tautomeros']['n']}")
    n_doc = sum(1 for r in filas if all(r["receptor_documentado"].values()))
    print(f"  (criterio COMPLETO de FEP-02 en ambos extremos: {n_doc} parejas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
