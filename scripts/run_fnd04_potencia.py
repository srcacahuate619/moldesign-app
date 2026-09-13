#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_fnd04_potencia.py — FND-04b: efecto mínimo detectable de los gates del programa.

Aplica `efecto_minimo_detectable` a los gates comparativos que **ya se ejecutaron**,
con su n y su discordancia reales. Responde, para cada uno: *¿qué efecto podría haber
detectado este diseño?* — la pregunta que la §20.9 exige responder **antes** de sellar
y que hasta ahora no se ha respondido nunca.

No reabre ningún sello. Es diagnóstico retrospectivo del programa, y su producto es la
regla operativa para los prerregistros futuros.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import (efecto_minimo_detectable, n_necesario,  # noqa: E402
                               mcnemar_exacto)

ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FND-04"


def _discordancia_selector(exp: str, semillas=("42", "43", "44")):
    """(n_cubiertos, discordancia, dif_observada) de un experimento de seleccion."""
    p = ART / exp / "per_complex.jsonl"
    if not p.exists():
        return None
    difs = []
    for l in p.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if not d.get("cubierto"):
            continue
        s = d.get("selector_acierta", {})
        v = [1.0 if s.get(k) else 0.0 for k in semillas if k in s]
        ms = sum(v) / len(v) if v else 0.0
        mb = 1.0 if d.get("baseline_acierta") else 0.0
        difs.append(ms - mb)
    if not difs:
        return None
    n = len(difs)
    disc = sum(1 for x in difs if abs(x) > 1e-9) / n
    return n, disc, sum(difs) / n


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    casos: List[Dict[str, Any]] = []

    for exp in ("RS-14", "RS-14-R1"):
        r = _discordancia_selector(exp)
        if r:
            n, disc, dif = r
            casos.append({"gate": exp, "descripcion": "selector vs vina_score (precision condicional)",
                          "n": n, "discordancia": round(disc, 4), "diferencia_observada": round(dif, 4)})

    # gates de conteo pareado ya sellados, con sus discordancias documentadas
    casos.append({"gate": "MF-19", "descripcion": "rigido vs flexible (mismo conformero)",
                  "n": 33, "discordancia": round(3 / 33, 4), "diferencia_observada": round(3 / 33, 4)})
    casos.append({"gate": "D-MF-HARD-EXH4", "descripcion": "vina_exh4 vs molflex_k15 (estrato hard)",
                  "n": 17, "discordancia": round(8 / 17, 4), "diferencia_observada": round(8 / 17, 4)})
    casos.append({"gate": "MF-08", "descripcion": "B_ADAPT vs B25 (recuperacion en cohorte dificil)",
                  "n": 33, "discordancia": round(3 / 33, 4), "diferencia_observada": round(3 / 33, 4)})

    for c in casos:
        n, d = c["n"], c["discordancia"]
        if d <= 0:
            c["mde_80"] = None
            continue
        c["mde_80"] = round(efecto_minimo_detectable(n, d, 0.80), 4)
        c["mde_90"] = round(efecto_minimo_detectable(n, d, 0.90), 4)
        c["mde_en_complejos"] = round(c["mde_80"] * n, 1)
        c["detectable"] = bool(abs(c["diferencia_observada"]) >= c["mde_80"])
        for obj in (0.05, 0.10):
            c[f"n_para_{int(obj*100)}pp"] = n_necesario(obj, d, 0.80)

    metrics = {
        "experiment_id": "FND-04b",
        "tipo": "diagnostico retrospectivo de potencia (no reabre ningun sello)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modelo": ("diferencia pareada en {-1,0,+1}; Var = discordancia - delta^2; "
                   "gate = CI95 pareado que excluye el cero; aproximacion normal"),
        "casos": casos,
        "regla_propuesta": ("ningun prerregistro de gate comparativo se sella sin declarar su "
                            "efecto minimo detectable al n disponible (doc. 49 §20.9)"),
    }
    (OUT_DIR / "metrics_potencia.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print("%-16s %5s %7s %10s %9s %10s %12s %12s" % (
        "gate", "n", "disc.", "dif obs.", "MDE 80%", "en cplx", "n p/ 5pp", "n p/ 10pp"))
    for c in casos:
        print("%-16s %5d %7.3f %10.4f %9s %10s %12s %12s%s" % (
            c["gate"], c["n"], c["discordancia"], c["diferencia_observada"],
            c.get("mde_80"), c.get("mde_en_complejos"),
            c.get("n_para_5pp"), c.get("n_para_10pp"),
            "" if c.get("detectable") else "   <- indetectable por diseno"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
