#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf15_embudo.py — MF-15: ¿existe un embudo que lleve al mínimo nativo?

**Tipo: medición.** Sin cómputo nuevo: lee `rmsd` y `vina_score` del conjunto v2
sellado (`RC-F0-V2`). Ninguna coordenada, ningún docking.

La pregunta, y por qué ahora
---------------------------
`MF-13` midió que en ~70% de los complejos difíciles la función de Vina **prefiere**
la pose nativa. `MF-14` mide **cuán ancha** es la cuenca de ese mínimo. Falta la
tercera pieza, que es la que decide si una búsqueda global puede llegar:

  **¿hay un gradiente que lleve hacia la cuenca, o el paisaje es plano fuera de ella?**

Una cuenca ancha con un embudo alrededor es fácil de encontrar. Una cuenca ancha
**sin** embudo es un pozo en una meseta: sólo se cae dentro por azar, y con ~751
poses el azar no basta si la meseta es grande.

Qué se mide
-----------
Para cada complejo, la correlación de Spearman entre `rmsd` y `vina_score`
**restringida a las poses con rmsd ≤ R**, para R creciente:

  * si la correlación es fuerte con R pequeño y se desvanece al crecer R, hay
    **embudo local pero no gradiente global**: desde lejos la puntuación no informa
    hacia dónde ir;
  * si se mantiene a todos los R, hay **embudo global** y el fallo del buscador no
    tiene excusa en el paisaje;
  * si es débil a todos los R, la puntuación **nunca** guía y el muestreo es a ciegas.

Se reporta además la mediana del score por banda de RMSD, que es la misma información
sin depender de un coeficiente.

Convención de signo: `vina_score` es más negativo = mejor. Un embudo produce
correlación **positiva** entre rmsd y score (más lejos, peor score).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V2 = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
COHORTE = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-15"

RADIOS = (2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 1e9)
BANDAS = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 8), (8, 12), (12, 1e9))
MIN_POSES = 8


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < MIN_POSES:
        return None

    def rangos(v):
        orden = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
                j += 1
            prom = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[orden[k]] = prom
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-15: el embudo de puntuacion")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    coh = json.loads(COHORTE.read_text(encoding="utf-8"))
    estrato = {p: "COLOCACION" for p in coh["cohorte_colocacion"]}
    estrato.update({p: "CONTROL" for p in coh["control_cubiertos"]})

    por = defaultdict(list)
    for l in (V2 / f"poses_{args.split}.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            por[d["pid"]].append((d["rmsd"], d["vina_score"]))

    filas: List[Dict[str, Any]] = []
    for pid, v in sorted(por.items()):
        est = estrato.get(pid, "RESTO")
        fila: Dict[str, Any] = {"pid": pid, "estrato": est, "n_poses": len(v),
                                "oraculo": round(min(x[0] for x in v), 3)}
        fila["spearman_por_radio"] = {}
        for R in RADIOS:
            sub = [x for x in v if x[0] <= R]
            k = "global" if R > 1e8 else str(R)
            fila["spearman_por_radio"][k] = {
                "n": len(sub), "rho": _spearman([x[0] for x in sub], [x[1] for x in sub])}
        fila["score_por_banda"] = {}
        for lo, hi in BANDAS:
            sub = [x[1] for x in v if lo <= x[0] < hi]
            k = f"{lo}-{'inf' if hi > 1e8 else hi}"
            fila["score_por_banda"][k] = {
                "n": len(sub), "score_mediano": round(median(sub), 3) if sub else None}
        filas.append(fila)

    with open(OUT_DIR / f"per_complex_{args.split}.jsonl", "w", encoding="utf-8",
              newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL", "RESTO"):
        g = [r for r in filas if r["estrato"] == est]
        if not g:
            continue
        por_radio = {}
        for R in RADIOS:
            k = "global" if R > 1e8 else str(R)
            vals = [r["spearman_por_radio"][k]["rho"] for r in g
                    if r["spearman_por_radio"][k]["rho"] is not None]
            por_radio[k] = {"n_complejos": len(vals),
                            "rho_mediano": round(median(vals), 4) if vals else None}
        bandas = {}
        for lo, hi in BANDAS:
            k = f"{lo}-{'inf' if hi > 1e8 else hi}"
            vals = [r["score_por_banda"][k]["score_mediano"] for r in g
                    if r["score_por_banda"][k]["score_mediano"] is not None]
            bandas[k] = {"n_complejos": len(vals),
                         "score_mediano": round(median(vals), 3) if vals else None}
        resumen[est] = {"n": len(g), "spearman_por_radio": por_radio,
                        "score_mediano_por_banda": bandas}

    metrics = {
        "experiment_id": "MF-15",
        "tipo": "medicion (lectura del conjunto v2 sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": args.split,
        "convencion": "vina_score mas negativo = mejor; un EMBUDO da rho POSITIVO entre rmsd y score",
        "n_complejos": len(filas),
        "resumen": resumen,
        "lectura": ("rho alto a R pequeno y decreciente al crecer R => embudo LOCAL sin "
                    "gradiente global: desde lejos la puntuacion no orienta. rho estable a "
                    "todo R => embudo GLOBAL y el buscador no tiene excusa en el paisaje. "
                    "rho bajo a todo R => la puntuacion nunca guia."),
    }
    (OUT_DIR / f"metrics_{args.split}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
