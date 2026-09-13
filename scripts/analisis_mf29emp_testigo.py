#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf29emp_testigo.py — MF-29-EMP: el tercer testigo, sin recomputo.

El prerregistro de `MF-29-EMP` (docstring de `run_mf29emp_optimo_global.py`, seccion
«Tercer testigo, reusado sin recomputo») declaro ANTES de correr que el cristal relajado
localmente por `MF-13` es una **cota superior independiente** del minimo global, y que

    «si el cristal puntua mejor que lo que encuentra el brazo masivo, la busqueda fallo y
     no hace falta ningun certificado para afirmarlo».

La cantidad primaria de `MF-29-EMP` compara el brazo masivo contra el de produccion: mide
si **mas busqueda del mismo tipo** rinde. El testigo compara el brazo masivo contra un
valor que la funcion alcanza de hecho: mide si la busqueda **llego al fondo**. Son dos
preguntas distintas y este script solo calcula la segunda, que quedo fuera de
`metrics.json` porque el script del experimento no lee `MF-13`.

Que se mide
-----------
Para cada complejo con lectura en `MF-29-EMP` (n=48) y pareja en `MF-13`:

  * `deficit = score_min(masivo) - score_cristal_local(MF-13)`. Es **> 0** cuando el
    cristal relajado puntua mejor -mas negativo- que todo lo que encontro el brazo masivo.
  * el `rmsd_min` del brazo masivo, para separar «no llego a la cuenca» de «llego a la
    cuenca y no bajo al fondo». El umbral de 2.0 A es el mismo de toda la cartera.

Se usa `score_cristal_local` y no `score_cristal` porque el crudo no esta relajado y su
comparacion contra un optimo de busqueda seria injusta con la funcion; `MF-13` midio que
la deriva de esa relajacion es de 0.32 A medianos, es decir, sigue siendo el cristal.

Limites declarados
------------------
1. **Esto no reabre la cantidad primaria.** El gate de `MF-29-EMP` es la fraccion masivo
   vs produccion y se lee como se preregistro. El testigo es contexto declarado, y su
   lectura -si la hay- es sobre `MF-29`, que sigue ABIERTO.
2. **Confusor no descartado: el confórmero de entrada.** `MF-29-EMP` docka
   `conf0.flex.pdbqt`, cuya geometria interna -anillos, longitudes y angulos de enlace-
   esta fija y puede no coincidir con la del ligando cristalografico que puntuo `MF-13`.
   Parte del deficit podria ser del confórmero y no del buscador. Se comprueba barato
   puntuando conf0 superpuesto al cristal, sin re-correr nada; hasta entonces el deficit
   es una **cota superior** de lo que le falta a la busqueda.
3. `MF-13` puntuo con el mismo receptor, la misma caja y la misma funcion, asi que la
   comparacion no cruza pipelines. Lo unico que cambia es el ligando de entrada (1) y (2).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UMBRAL_RMSD = 2.0
DELTA_RUIDO = 0.10   # el mismo de MF-29-EMP, kcal/mol


def _leer_jsonl(ruta: Path) -> List[Dict[str, Any]]:
    with open(ruta, "r", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-29-EMP: cruce con el testigo de MF-13")
    ap.add_argument("--artifacts", default=str(PROJECT_ROOT / "scripts" / "artifacts_science"))
    args = ap.parse_args()
    art = Path(args.artifacts)

    emp = _leer_jsonl(art / "MF-29-EMP" / "per_complex.jsonl")
    m13 = {r["pid"]: r for r in _leer_jsonl(art / "MF-13" / "per_complex.jsonl")}

    filas: List[Dict[str, Any]] = []
    sin_pareja: List[str] = []
    for r in emp:
        if "masivo_mejora" not in r:          # sin lectura: los dos que expiraron
            continue
        c = m13.get(r["pid"])
        if c is None or c.get("score_cristal_local") is None:
            sin_pareja.append(r["pid"])
            continue
        masivo = r["brazos"]["masivo"]
        deficit = round(masivo["score_min"] - c["score_cristal_local"], 3)
        filas.append({
            "pid": r["pid"], "estrato": r["estrato"], "torsdof": r.get("torsdof"),
            "score_masivo": masivo["score_min"],
            "score_cristal_local": c["score_cristal_local"],
            "deficit": deficit,
            "cristal_gana": bool(deficit > DELTA_RUIDO),
            "rmsd_min_masivo": masivo.get("rmsd_min"),
            "en_cuenca": (masivo.get("rmsd_min") is not None
                          and masivo["rmsd_min"] < UMBRAL_RMSD),
        })

    gana = [f for f in filas if f["cristal_gana"]]
    en_cuenca = [f for f in gana if f["en_cuenca"]]
    resumen: Dict[str, Any] = {}
    for est in sorted({f["estrato"] for f in filas}):
        g = [f for f in filas if f["estrato"] == est]
        resumen[est] = {
            "n": len(g),
            "n_cristal_gana": sum(1 for f in g if f["cristal_gana"]),
            "deficit_mediano": round(median([f["deficit"] for f in g]), 3),
            "deficit_max": round(max(f["deficit"] for f in g), 3),
        }

    out = {
        "analisis_id": "MF-29-EMP/testigo-MF-13",
        "tipo": "cruce declarado en el prerregistro, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "definicion_deficit": "score_min(masivo, exh=512) - score_cristal_local(MF-13); >0 => el cristal puntua mejor",
        "umbral_rmsd_cuenca_A": UMBRAL_RMSD,
        "delta_ruido_kcal": DELTA_RUIDO,
        "n_con_testigo": len(filas),
        "sin_pareja_en_mf13": sin_pareja,
        "cantidad": {
            "n_cristal_gana": len(gana),
            "de": len(filas),
            "fraccion": round(len(gana) / len(filas), 4) if filas else None,
            "deficit_mediano_global": round(median([f["deficit"] for f in filas]), 3) if filas else None,
            "n_gana_y_masivo_en_cuenca": len(en_cuenca),
            "n_gana_y_masivo_fuera_de_cuenca": len(gana) - len(en_cuenca),
            "deficit_mediano_en_cuenca": (round(median([f["deficit"] for f in en_cuenca]), 3)
                                          if en_cuenca else None),
        },
        "por_estrato": resumen,
        "peores": sorted(gana, key=lambda f: -f["deficit"])[:10],
        "limites_declarados": [
            "no reabre la cantidad primaria de MF-29-EMP; su gate se lee como se preregistro",
            "confusor no descartado: la geometria interna fija de conf0.flex.pdbqt puede explicar parte del deficit; hasta comprobarlo el deficit es cota superior",
            "MF-13 uso el mismo receptor, caja y funcion; lo unico que cambia es el ligando de entrada",
        ],
        "per_complex": filas,
    }
    destino = art / "MF-29-EMP" / "testigo_mf13.json"
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    q = out["cantidad"]
    print(f"[MF-29-EMP/testigo] n={len(filas)} cristal_gana={q['n_cristal_gana']} "
          f"({q['fraccion']}) deficit_mediano={q['deficit_mediano_global']} "
          f"en_cuenca={q['n_gana_y_masivo_en_cuenca']} fuera={q['n_gana_y_masivo_fuera_de_cuenca']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
