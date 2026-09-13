#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf31_ocupacion.py — MF-31: ¿gobierna la ocupación de caja? Test sobre una intervención real.

**Tipo: medición.** Reanálisis del material sellado de `MF-08`, sin cómputo nuevo.

La hipótesis y por qué se puede contrastar aquí
----------------------------------------------
`MF-27` (52 complejos de alta flexibilidad) y `MF-12` (203 complejos, split externo)
coinciden en que lo que predice el fallo **no es el número de torsiones** sino el
**volumen efectivo de búsqueda**: la ocupación de caja discrimina con cociente 0.55 y
es el coeficiente dominante del clasificador (−1.009), mientras las torsiones aportan
+0.017, esencialmente cero.

Las dos son correlacionales. Pero el programa **ya ejecutó una intervención sobre esa
variable**: `MF-08` varió el tamaño de caja (20 Å, 30 Å y adaptativa) sobre los mismos
48 complejos, con 144 corridas selladas. Si la ocupación gobierna, esa intervención
debe mostrarlo.

Diseño del contraste
--------------------
Ocupación = volumen de la esfera envolvente del ligando / volumen de caja. Dentro de un
complejo el numerador es fijo, así que la ocupación varía sólo por `box³`.

  * **Test 1 (transversal)**: sobre las 144 corridas, ¿correlaciona la ocupación con el
    oráculo alcanzado? Débil por diseño: mezcla complejos con dificultades distintas.
  * **Test 2 (pareado, el que importa)**: dentro de cada complejo, pasar de `B30` a
    `B_ADAPT` cambia la ocupación en una cantidad **que varía entre complejos** porque
    la caja adaptativa se ajusta al ligando. Si la ocupación gobierna, los complejos con
    mayor reducción de ocupación deben mejorar más el oráculo. Eso es dosis-respuesta
    sobre una intervención, no una correlación transversal.

Lo que falsifica la hipótesis
-----------------------------
Si Δocupación no correlaciona con Δoráculo dentro de complejo, la ocupación es un
**marcador** de dificultad y no una **palanca**: predice el fallo pero moverla no lo
arregla. Sería coherente con que `MF-08` sólo convirtiera 3 de 33 pese a apretar la caja.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import bootstrap_bca_pareado  # noqa: E402

ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-31"


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < 8:
        return None

    def R(v):
        o = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            p = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[o[k]] = p
            i = j + 1
        return r
    ra, rb = R(a), R(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def main() -> int:
    import molflex as mf
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    corridas = [json.loads(l) for l in
                (ART / "MF-08" / "corridas.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]

    # radio envolvente del ligando cristalografico (mecanistico, no predictivo)
    rmax: Dict[str, float] = {}
    for pid in {c["pid"] for c in corridas}:
        cr = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if cr is None:
            continue
        cf = cr.GetConformer(0)
        pes = [i for i, a in enumerate(cr.GetAtoms()) if a.GetAtomicNum() > 1]
        pts = [(cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z)
               for i in pes]
        cen = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
        rmax[pid] = max(math.sqrt(sum((p[k] - cen[k]) ** 2 for k in range(3))) for p in pts)

    filas = []
    for c in corridas:
        if not c.get("ok") or c["pid"] not in rmax or c.get("oraculo_pocket") is None:
            continue
        occ = (4 / 3 * math.pi * rmax[c["pid"]] ** 3) / (c["box"] ** 3)
        filas.append({**c, "ocupacion": round(occ, 5), "rmax": round(rmax[c["pid"]], 3)})

    # ── Test 1: transversal ──
    t1 = {}
    for est in ("COLOCACION", "CONTROL", "TODOS"):
        g = [f for f in filas if est == "TODOS" or f["estrato"] == est]
        if len(g) < 8:
            continue
        t1[est] = {"n_corridas": len(g),
                   "spearman_ocupacion_vs_oraculo":
                       _spearman([f["ocupacion"] for f in g], [f["oraculo_pocket"] for f in g])}

    # ── Test 2: pareado dentro de complejo, B30 -> B_ADAPT ──
    por = defaultdict(dict)
    for f in filas:
        por[f["pid"]][f["brazo"]] = f
    pares = []
    for pid, d in por.items():
        if "B30" in d and "B_ADAPT" in d:
            pares.append({
                "pid": pid, "estrato": d["B30"]["estrato"],
                "box_adapt": d["B_ADAPT"]["box"],
                "d_ocupacion": round(d["B_ADAPT"]["ocupacion"] - d["B30"]["ocupacion"], 5),
                "d_oraculo": round(d["B_ADAPT"]["oraculo_pocket"] - d["B30"]["oraculo_pocket"], 3),
                "exito_b30": bool(d["B30"]["exito"]), "exito_adapt": bool(d["B_ADAPT"]["exito"]),
            })
    t2 = {}
    for est in ("COLOCACION", "CONTROL", "TODOS"):
        g = [p for p in pares if est == "TODOS" or p["estrato"] == est]
        if len(g) < 8:
            continue
        rho = _spearman([p["d_ocupacion"] for p in g], [p["d_oraculo"] for p in g])
        th, lo, hi = bootstrap_bca_pareado([p["d_oraculo"] for p in g], n_boot=10000, seed=42)
        t2[est] = {
            "n_complejos": len(g),
            "spearman_d_ocupacion_vs_d_oraculo": rho,
            "d_ocupacion_mediana": round(median(p["d_ocupacion"] for p in g), 5),
            "d_oraculo_mediano": round(th, 3),
            "d_oraculo_ci95": [round(lo, 3), round(hi, 3)],
            "mejoran": sum(1 for p in g if p["d_oraculo"] < 0),
            "empeoran": sum(1 for p in g if p["d_oraculo"] > 0),
        }

    metrics = {
        "experiment_id": "MF-31",
        "tipo": "medicion (reanalisis de la intervencion sellada de MF-08, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "definicion": "ocupacion = volumen de la esfera envolvente del ligando / volumen de caja",
        "n_corridas": len(filas), "n_pares_B30_vs_BADAPT": len(pares),
        "test1_transversal": t1,
        "test2_pareado_dosis_respuesta": t2,
        "lectura": ("rho negativo y sustancial en el test 2 => reducir la ocupacion MEJORA el "
                    "oraculo y la ocupacion es una PALANCA. rho ~0 => es un MARCADOR de "
                    "dificultad y no una palanca: predice el fallo pero moverla no lo arregla, "
                    "coherente con que MF-08 solo convirtiera 3 de 33"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for p in pares:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(json.dumps({"test1": t1, "test2": t2}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
