#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf33_cruces.py — MF-33-CRUCES: los 7 que el ensemble no convierte, ¿quiénes son?

Sin computo nuevo. Joins sobre artefactos ya sellados. Son las dos preguntas que la 12.2 del
roadmap tenia apuntadas como victorias rapidas, y una tercera que aparecio al correr `REC-09`.

`MF-33` midio que el ensemble flexible convierte 26 de 33 en COLOCACION, y sobre los 48 de
la cohorte su brazo B alcanza <=2 A en 41 y falla en **7**. La pregunta abierta desde su
sello es que tienen esos 7 de particular.

Cruce 1 — la cuenca rugosa (`MF-14`)
------------------------------------
`MF-14` perturbo la pose nativa a radios crecientes y midio si la minimizacion **vuelve**.
Un complejo cuya cuenca no devuelve desde 0.5 A es rugoso: tiene minimos locales pegados al
nativo. Hipotesis registrada en la 12.2: los que no regresan desde 0.5 A son los mismos que
el ensemble no convierte.

Cantidad: fraccion de puntos con `vuelve` a `r_nominal=0.5`, comparada entre el grupo que
`B` convierte y el que no.

Cruce 2 — las aguas del sitio (`REC-08-EXT` y `REC-09`)
-------------------------------------------------------
Hipotesis declarada en el sello de `REC-08-EXT`: los que no convierten tienen mas aguas
retenidas en el sitio. Se mide con dos variables, no una:

  * `aguas_sitio` de `REC-08-EXT` — cuantas aguas hay a 8 A del ligando. Es presencia.
  * `n_aguas_bloqueantes` de `REC-09` — cuantas **chocan** con el ligando cristalografico a
    2.6 A. Es estorbo, que es lo que la hipotesis realmente quiere decir.

Cruce 3 — no estaba en la lista, y sale de `REC-09`
---------------------------------------------------
`REC-09` identifico 6 complejos cuyo cristal puntua absurdamente mal -por encima de -3.0
kcal/mol-, que es la senal de un sistema mal montado y no de un fallo de busqueda. La
pregunta que eso obliga a hacer: **cuantos de esos 6 estan entre los 7 que el ensemble no
convierte**. Si se solapan, buena parte de lo que el programa lleva contando como fallo de
busqueda o de puntuacion es en realidad **preparacion**.

Limites
-------
1. **Sin gates de decision.** Son mediciones de asociacion sobre n pequeno -7 contra 41- y
   no autorizan atribucion causal. Con 7 casos no se hace inferencia: se describe y se
   nombra a los complejos, que es lo util.
2. **No relee `MF-33` ni lo toca.** Que complejos convierte su brazo B es dato sellado. Lo
   que `MF-33-A3` esta midiendo -si la ventaja era diversidad conformacional o conteo de
   poses- afecta al POR QUE convierte, no a CUALES, asi que estos cruces no dependen de A3.
3. `REC-09` quedo `INCONCLUSIVE` con lectura MIXTO. Su lista de absurdos es dato medido y
   G1 paso en 116 de 116; lo que quedo sin decidir es si las aguas los explican.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
R_RUGOSIDAD = 0.5


def _jsonl(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _frac_vuelve(fila: Dict[str, Any], r: float) -> Optional[float]:
    pts = [p for p in fila.get("puntos", []) if p.get("r_nominal") == r]
    if not pts:
        return None
    return round(sum(1 for p in pts if p.get("vuelve")) / len(pts), 4)


def _resumen(vals: List[float]) -> Dict[str, Any]:
    v = [x for x in vals if x is not None]
    if not v:
        return {"n": 0}
    return {"n": len(v), "mediana": round(median(v), 4),
            "min": round(min(v), 4), "max": round(max(v), 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-CRUCES: quienes son los 7 que no convierten")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-CRUCES"
    out_dir.mkdir(parents=True, exist_ok=True)

    m33 = {r["pid"]: r for r in _jsonl(art / "MF-33" / "per_complex.jsonl")}
    m14 = {r["pid"]: r for r in _jsonl(art / "MF-14" / "per_complex.jsonl")}
    r08 = {r["pid"]: r for r in _jsonl(art / "REC-08-EXT" / "per_complex.jsonl")}
    r09 = {r["pid"]: r for r in _jsonl(art / "REC-09" / "per_complex.jsonl")}

    filas: List[Dict[str, Any]] = []
    for pid, r in sorted(m33.items()):
        b = r.get("brazos", {}).get("B", {})
        f14, f08, f09 = m14.get(pid), r08.get(pid), r09.get(pid)
        filas.append({
            "pid": pid, "estrato": r.get("estrato"),
            "B_alcanza": bool(b.get("alcanza")),
            "B_rmsd_min": b.get("rmsd_min"),
            "frac_vuelve_0.5": _frac_vuelve(f14, R_RUGOSIDAD) if f14 else None,
            "r50": (f14 or {}).get("r50"),
            "aguas_sitio": (f08 or {}).get("aguas_sitio"),
            "aguas_bloqueantes": (f09 or {}).get("n_aguas_bloqueantes"),
            "score_cristal": (f09 or {}).get("score_con_aguas"),
            "absurdo": (f09 or {}).get("absurdo"),
        })

    conv = [f for f in filas if f["B_alcanza"]]
    noconv = [f for f in filas if not f["B_alcanza"]]

    absurdos = sorted(f["pid"] for f in filas if f["absurdo"])
    absurdos_noconv = sorted(f["pid"] for f in noconv if f["absurdo"])

    out = {
        "analisis_id": "MF-33-CRUCES",
        "tipo": "mediciones de asociacion sin gates de decision, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_complejos": len(filas),
        "grupos": {"B_convierte": len(conv), "B_no_convierte": len(noconv),
                   "pids_no_convierte": sorted(f["pid"] for f in noconv)},
        "cruce_1_cuenca_rugosa_MF14": {
            "pregunta": "los que no regresan desde 0.5 A son los mismos que el ensemble no convierte?",
            "cantidad": f"fraccion de puntos con vuelve=True a r_nominal={R_RUGOSIDAD}",
            "convierte": _resumen([f["frac_vuelve_0.5"] for f in conv]),
            "no_convierte": _resumen([f["frac_vuelve_0.5"] for f in noconv]),
        },
        "cruce_2_aguas_REC08EXT_REC09": {
            "pregunta": "los que no convierten tienen mas aguas retenidas en el sitio?",
            "aguas_en_sitio_8A": {"convierte": _resumen([f["aguas_sitio"] for f in conv]),
                                  "no_convierte": _resumen([f["aguas_sitio"] for f in noconv])},
            "aguas_bloqueantes_2.6A": {"convierte": _resumen([f["aguas_bloqueantes"] for f in conv]),
                                       "no_convierte": _resumen([f["aguas_bloqueantes"] for f in noconv])},
        },
        "cruce_3_preparacion_REC09": {
            "pregunta": "cuantos de los cristales que puntuan absurdo estan entre los que el ensemble no convierte?",
            "absurdos_en_la_cohorte_de_48": absurdos,
            "absurdos_que_ademas_no_convierten": absurdos_noconv,
            "n_absurdos": len(absurdos),
            "n_absurdos_no_convierten": len(absurdos_noconv),
            "fraccion_de_los_no_convierten_que_son_absurdos": (
                round(len(absurdos_noconv) / len(noconv), 4) if noconv else None),
            "fraccion_de_absurdos_entre_los_que_convierten": (
                round(sum(1 for f in conv if f["absurdo"]) / len(conv), 4) if conv else None),
        },
        "limites_declarados": [
            "sin gates: son asociaciones sobre n pequeno (7 contra 41) y no autorizan atribucion causal",
            "no relee MF-33 ni lo toca; MF-33-A3 afecta al POR QUE convierte, no a CUALES",
            "REC-09 quedo INCONCLUSIVE: su lista de absurdos es dato medido, lo indeciso es si las aguas los explican",
        ],
        "per_complex": filas,
    }
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    c1 = out["cruce_1_cuenca_rugosa_MF14"]
    c2 = out["cruce_2_aguas_REC08EXT_REC09"]
    c3 = out["cruce_3_preparacion_REC09"]
    print(f"[MF-33-CRUCES] {len(conv)} convierten / {len(noconv)} no")
    print(f"  1. rugosidad (frac vuelve a 0.5 A): convierte={c1['convierte'].get('mediana')} "
          f"no_convierte={c1['no_convierte'].get('mediana')}")
    print(f"  2. aguas en sitio: {c2['aguas_en_sitio_8A']['convierte'].get('mediana')} vs "
          f"{c2['aguas_en_sitio_8A']['no_convierte'].get('mediana')} | "
          f"bloqueantes: {c2['aguas_bloqueantes_2.6A']['convierte'].get('mediana')} vs "
          f"{c2['aguas_bloqueantes_2.6A']['no_convierte'].get('mediana')}")
    print(f"  3. absurdos entre los que NO convierten: {c3['n_absurdos_no_convierten']} de "
          f"{len(noconv)} ({c3['fraccion_de_los_no_convierten_que_son_absurdos']}) -> {absurdos_noconv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
