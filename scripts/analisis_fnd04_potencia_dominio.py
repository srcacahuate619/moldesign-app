#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fnd04_potencia_dominio.py — los MDE de FND-04 dentro de su dominio (SCI-B-018, SCI-B-002).

`estadistica_fnd04.efecto_minimo_detectable` modela la diferencia por complejo en {-1, 0, +1}
con P(|X| = 1) = d. Bajo ese modelo |media| <= d: un efecto mayor que la discordancia es
imposible. La función no lo comprueba, y `FND-04/metrics_potencia.json` publica MDE fuera del
dominio (MF-19 y MF-08: d = 3/33 = 0,0909 y MDE = 0,1322).

`estadistica_fnd04.py` y `run_fnd04_potencia.py` están sellados en FND-04 (y el primero en dos
experimentos más), así que no se tocan. Aquí:

1. `mde_en_dominio` devuelve el MDE sólo si cabe en el modelo; si no, `None` (no alcanzable).
2. MF-12 declaró su MDE (0,136) con n = 203 = 116 de entrenamiento + 87 de evaluación; el
   gate pareado se evalúa sobre los 87 (SCI-B-077). Aquí se recalcula con n = 87.
3. Para RS-14 y RS-14-R1, cuya respuesta por complejo es fraccionaria (media de tres semillas
   del selector menos un acierto 0/1), el MDE se recalcula con la varianza empírica de esas
   diferencias en vez de la del modelo ±1 (SCI-B-002). Sigue siendo aproximación normal.

Lee sólo artefactos sellados. Uso:
    python scripts/analisis_fnd04_potencia_dominio.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional

ART = Path(__file__).resolve().parent / "artifacts_science"
Z_975 = 1.959963984540054
Z_POT = {0.80: 0.8416212335729143, 0.90: 1.2815515655446004}


def mde_modelo(n: int, d: float, potencia: float = 0.80) -> float:
    """La fórmula sellada, sin el dominio: sqrt(k d / (n + k))."""
    k = (Z_975 + Z_POT[potencia]) ** 2
    return math.sqrt(k * d / (n + k))


def mde_en_dominio(n: int, d: float, potencia: float = 0.80) -> Optional[float]:
    """MDE bajo el modelo ±1, o None si ningún efecto posible (|delta| <= d) alcanza la potencia."""
    if not 0 < d <= 1 or n < 2:
        raise ValueError("d en (0, 1] y n >= 2")
    m = mde_modelo(n, d, potencia)
    return m if m <= d else None


def mde_empirico(difs: List[float], potencia: float = 0.80) -> float:
    """MDE con la desviación típica observada de las diferencias por complejo."""
    sd = statistics.stdev(difs)
    return (Z_975 + Z_POT[potencia]) * sd / math.sqrt(len(difs))


def difs_selector(exp: str, semillas=("42", "43", "44")) -> List[float]:
    """Las mismas diferencias que `run_fnd04_potencia._discordancia_selector`."""
    difs = []
    for linea in (ART / exp / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        r = json.loads(linea)
        if not r.get("cubierto"):
            continue
        s = r.get("selector_acierta", {})
        v = [1.0 if s.get(k) else 0.0 for k in semillas if k in s]
        difs.append((sum(v) / len(v) if v else 0.0) - (1.0 if r.get("baseline_acierta") else 0.0))
    return difs


def analizar() -> Dict:
    sellado = json.loads((ART / "FND-04" / "metrics_potencia.json").read_text(encoding="utf-8"))
    casos = []
    for c in sellado["casos"]:
        n, d = c["n"], c["discordancia"]
        fila = {"gate": c["gate"], "n": n, "discordancia": d, "mde_80_sellado": c["mde_80"],
                "mde_80_en_dominio": None, "alcanzable": False}
        m = mde_en_dominio(n, d)
        if m is not None:
            fila["mde_80_en_dominio"] = round(m, 4)
            fila["alcanzable"] = True
        if c["gate"] in ("RS-14", "RS-14-R1"):
            difs = difs_selector(c["gate"])
            fila["n_difs"] = len(difs)
            fila["fraccionarias"] = sum(1 for x in difs if abs(x) not in (0.0, 1.0))
            fila["sd_empirica"] = round(statistics.stdev(difs), 4)
            fila["sd_modelo"] = round(math.sqrt(d - statistics.mean(difs) ** 2), 4)
            fila["mde_80_empirico"] = round(mde_empirico(difs), 4)
        casos.append(fila)
    mf12 = json.loads((ART / "MF-12" / "metrics.json").read_text(encoding="utf-8"))
    casos.append({"gate": "MF-12", "n": mf12["n_valtest"], "discordancia": 0.5,
                  "mde_80_sellado": mf12["efecto_minimo_detectable_declarado"],
                  "n_del_sellado": mf12["n_train"] + mf12["n_valtest"],
                  "mde_80_en_dominio": round(mde_en_dominio(mf12["n_valtest"], 0.5), 4), "alcanzable": True})
    return {"fuente": "FND-04/metrics_potencia.json + RS-14*/per_complex.jsonl", "casos": casos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = analizar()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    for c in r["casos"]:
        extra = (f"  empírico {c['mde_80_empirico']} (sd {c['sd_empirica']} vs modelo {c['sd_modelo']}, "
                 f"{c['fraccionarias']}/{c['n_difs']} fraccionarias)") if "mde_80_empirico" in c else ""
        print(f"{c['gate']:16s} n={c['n']:3d} d={c['discordancia']:.4f} sellado={c['mde_80_sellado']} "
              f"dominio={c['mde_80_en_dominio'] if c['alcanzable'] else 'NO ALCANZABLE'}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
