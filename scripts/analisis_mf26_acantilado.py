#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf26_acantilado.py — MF-26: ¿dónde colapsa la colocación al crecer los grados de libertad?

**Tipo: medición.** Reanálisis de `MF-24` (116 complejos de train) sin cómputo nuevo.

La pregunta
-----------
`MF-24` midió que el coste de colocación correlaciona con el tamaño y la flexibilidad
del ligando (ρ = 0.53 con torsiones; los que convierten tienen 5 torsiones y los que
fallan 12). Pero una correlación monótona no dice lo que un ingeniero necesita saber:
**¿hay un umbral operativo?**

La búsqueda de Vina explora 6 grados rígidos más uno por torsión. Si el presupuesto es
fijo (`exhaustiveness=8`) y el espacio crece de forma multiplicativa con las torsiones,
la tasa de conversión no debería decaer suavemente: debería **colapsar** a partir de
cierto número. Ese número es una especificación de producción — dice qué ligandos se
pueden dockear con el protocolo congelado y cuáles hay que enrutar de otra forma.

Y hay un segundo asunto que `MF-24` dejó abierto. El **enterramiento** fue el único
predictor con signo contrario (ρ = −0.31): los complejos que convierten están *más*
enterrados. Pero el enterramiento por átomo está confundido con el tamaño —los ligandos
grandes sobresalen del bolsillo—, así que no se sabe si aporta algo propio. Aquí se
separa estratificando por torsiones.

Qué se mide
-----------
1. **Curva de conversión** frente a número de torsiones, por bandas, con intervalos de
   Wilson (`FND-04`) — porque con 10-30 complejos por banda el punto estimado solo no
   dice nada.
2. **Coste de colocación** mediano por banda.
3. **Enterramiento estratificado**: dentro de cada banda de torsiones, ¿siguen los que
   convierten estando más enterrados? Si el efecto sobrevive a la estratificación, es
   propio; si desaparece, era tamaño disfrazado.

Limitación declarada
--------------------
n=116 repartidos en bandas, así que los CI son anchos por construcción y ninguna banda
individual soporta un claim fuerte. Lo que se busca es la **forma de la curva**, no el
valor de un punto. Y sigue siendo correlacional: la banda no se asignó, se observó.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import wilson, mcnemar_exacto  # noqa: E402

ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-26"
BANDAS = ((0, 2), (3, 5), (6, 8), (9, 12), (13, 17), (18, 99))


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-26: acantilado de conversion vs torsiones")
    ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in
            (ART / "MF-24" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ok = [r for r in rows if "colocacion" in r and r.get("n_torsiones") is not None]
    print(f"[MF-26] {len(ok)} complejos con torsiones y desenlace")

    curva = {}
    for lo, hi in BANDAS:
        g = [r for r in ok if lo <= r["n_torsiones"] <= hi]
        if not g:
            continue
        c = sum(1 for r in g if r["convierte"])
        w_lo, w_hi = wilson(c, len(g))
        curva[f"{lo}-{'inf' if hi > 90 else hi}"] = {
            "n": len(g), "convierten": c,
            "tasa": round(c / len(g), 4),
            "wilson95": [round(w_lo, 4), round(w_hi, 4)],
            "coloc_mediano": round(median(r["colocacion"] for r in g), 3),
            "rmsd_conf_mediano": round(median(r["rmsd_conf"] for r in g), 3),
            "pesados_mediano": int(median(r["n_pesados"] for r in g)),
        }

    # enterramiento estratificado por banda de torsiones
    estrat = {}
    for lo, hi in BANDAS:
        g = [r for r in ok if lo <= r["n_torsiones"] <= hi]
        conv = [r for r in g if r["convierte"]]
        nc = [r for r in g if not r["convierte"]]
        if len(conv) < 3 or len(nc) < 3:
            continue
        a = median(r["enterramiento"] for r in conv)
        b = median(r["enterramiento"] for r in nc)
        estrat[f"{lo}-{'inf' if hi > 90 else hi}"] = {
            "n_convierten": len(conv), "n_no": len(nc),
            "enterramiento_convierten": round(a, 3),
            "enterramiento_no": round(b, 3),
            "diferencia": round(a - b, 3),
        }
    bandas_utiles = [v for v in estrat.values()]
    favor = sum(1 for v in bandas_utiles if v["diferencia"] > 0)

    metrics = {
        "experiment_id": "MF-26",
        "tipo": "medicion (reanalisis de MF-24, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_complejos": len(ok),
        "curva_conversion_por_torsiones": curva,
        "enterramiento_estratificado": estrat,
        "enterramiento_veredicto": (
            f"el efecto del enterramiento favorece a los que convierten en {favor} de "
            f"{len(bandas_utiles)} bandas con muestra suficiente"),
        "limitacion": ("bandas con 10-30 complejos: los CI de Wilson son anchos y ninguna "
                       "banda individual soporta un claim. Se busca la FORMA de la curva. "
                       "Correlacional: la banda se observo, no se asigno"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print()
    print("%-10s %4s %11s %8s %-18s %12s %10s" % (
        "torsiones", "n", "convierten", "tasa", "Wilson95", "coloc med", "pesados"))
    for k, v in curva.items():
        print("%-10s %4d %11d %8.3f  [%.3f, %.3f]  %12.3f %10d" % (
            k, v["n"], v["convierten"], v["tasa"], v["wilson95"][0], v["wilson95"][1],
            v["coloc_mediano"], v["pesados_mediano"]))
    print()
    print("enterramiento estratificado por torsiones (convierten vs no):")
    for k, v in estrat.items():
        print("  %-10s conv=%.3f (n=%d)  no=%.3f (n=%d)  dif=%+.3f" % (
            k, v["enterramiento_convierten"], v["n_convierten"],
            v["enterramiento_no"], v["n_no"], v["diferencia"]))
    print(" ", metrics["enterramiento_veredicto"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
