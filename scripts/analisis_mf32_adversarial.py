#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf32_adversarial.py — MF-32: auditoría adversarial de la línea MolFlex.

**Tipo: medición.** Reanálisis del material sellado de `MF-08`. Sin cómputo nuevo.

Propósito
---------
Este experimento **no busca confirmar** la lectura de la línea C. Busca refutarla. Se
escribe adoptando la posición de un revisor hostil del futuro paper, cuya tesis sería:

> «Las intervenciones de MolFlex (caja, reinicios, campo de fuerza, presupuesto) mejoran
> el oráculo ~0.8 Å y no convierten; el cuello está en el paisaje de puntuación.»

Los tres ataques que un revisor competente haría:

**Ataque 1 — el umbral de 2.0 Å hace todo el trabajo.** Toda la narrativa depende de un
corte duro. `MF-22` mostró poses cayendo en 2.1–2.8 Å: si el umbral fuera 2.5 Å, «no
convierte» podría volverse «convierte». Si el recuento de conversiones y el orden de los
brazos cambian sustancialmente al mover el umbral, la conclusión es un artefacto de
dónde se dibujó la raya.

**Ataque 2 — regresión a la media.** La cohorte de 33 se **seleccionó** como los
complejos que fallan bajo la configuración base. Re-medir la cola de una distribución
ruidosa produce mejora **por construcción**, sin que ninguna intervención haga nada. La
firma diagnóstica: la mejora debe correlacionar con lo malo que era el valor de partida,
y el grupo seleccionado por el extremo opuesto —los controles— debe **empeorar**.

**Ataque 3 — varianza por semilla (no contrastable aquí).** Todas las comparaciones usan
`seed 42`. Nadie ha medido cuánto varía Vina entre semillas en esta cohorte. `FND-03`
declara esa medición como P0 y **no tiene artefacto**. Requiere ejecutar Vina, así que
se deja registrado como el hueco más grave y se propone como experimento de servidor.

Qué se mide
-----------
1. **Sensibilidad al umbral**: conversiones por brazo a 1.5 / 2.0 / 2.5 / 3.0 Å, y
   cuántos complejos quedan en la banda de casi-acierto.
2. **Regresión a la media (a)**: correlación entre el oráculo de partida y la mejora.
3. **Regresión a la media (b)**: ¿empeoran los controles? Es el test decisivo, porque
   fueron seleccionados por el extremo contrario.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import bootstrap_bca_pareado, wilson  # noqa: E402

ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-32"
UMBRALES = (1.5, 2.0, 2.5, 3.0)


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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    corr = [json.loads(l) for l in
            (ART / "MF-08" / "corridas.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ok = [c for c in corr if c.get("ok") and c.get("oraculo_pocket") is not None]

    # ── Ataque 1: sensibilidad al umbral ──
    a1: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        d: Dict[str, Any] = {}
        for brazo in ("B20", "B30", "B_ADAPT"):
            g = [c for c in ok if c["estrato"] == est and c["brazo"] == brazo]
            if not g:
                continue
            fila = {"n": len(g)}
            for u in UMBRALES:
                k = sum(1 for c in g if c["oraculo_pocket"] <= u)
                lo, hi = wilson(k, len(g))
                fila[f"conv_{u}"] = {"k": k, "tasa": round(k / len(g), 4),
                                    "wilson95": [round(lo, 3), round(hi, 3)]}
            fila["oraculo_mediano"] = round(median(c["oraculo_pocket"] for c in g), 3)
            fila["casi_acierto_2_3A"] = sum(1 for c in g if 2.0 < c["oraculo_pocket"] <= 3.0)
            d[brazo] = fila
        a1[est] = d

    # ── Ataque 2a: la mejora correlaciona con lo malo que era el punto de partida ──
    por = defaultdict(dict)
    for c in ok:
        por[c["pid"]][c["brazo"]] = c
    pares = []
    for pid, d in por.items():
        if "B30" in d and "B_ADAPT" in d:
            pares.append({"pid": pid, "estrato": d["B30"]["estrato"],
                          "base_b30": d["B30"]["oraculo_pocket"],
                          "mejora": round(d["B30"]["oraculo_pocket"] - d["B_ADAPT"]["oraculo_pocket"], 3)})
    a2a = {}
    for est in ("COLOCACION", "CONTROL", "TODOS"):
        g = [p for p in pares if est == "TODOS" or p["estrato"] == est]
        if len(g) < 8:
            continue
        a2a[est] = {"n": len(g),
                    "spearman_base_vs_mejora":
                        _spearman([p["base_b30"] for p in g], [p["mejora"] for p in g]),
                    "mejora_mediana": round(median(p["mejora"] for p in g), 3)}

    # ── Ataque 2b: ¿empeoran los controles? (test decisivo) ──
    a2b = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [p for p in pares if p["estrato"] == est]
        if len(g) < 5:
            continue
        d = [-p["mejora"] for p in g]     # >0 => el oraculo EMPEORA con B_ADAPT
        th, lo, hi = bootstrap_bca_pareado(d, n_boot=10000, seed=42)
        a2b[est] = {"n": len(g), "delta_oraculo_medio": round(th, 3),
                    "ci95": [round(lo, 3), round(hi, 3)],
                    "empeoran": sum(1 for x in d if x > 0),
                    "mejoran": sum(1 for x in d if x < 0)}

    metrics = {
        "experiment_id": "MF-32",
        "tipo": "auditoria adversarial (reanalisis de MF-08, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "postura": "no busca confirmar la lectura de la linea C; busca refutarla",
        "ataque1_sensibilidad_al_umbral": a1,
        "ataque2a_regresion_a_la_media": a2a,
        "ataque2b_degradan_los_controles": a2b,
        "ataque3_no_contrastable_aqui": (
            "varianza por semilla de Vina: todas las comparaciones usan seed 42 y nadie ha "
            "medido la varianza entre semillas en esta cohorte. FND-03 la declara P0 y NO "
            "tiene artefacto. Es el hueco mas grave de la linea y exige ejecutar Vina"),
        "lectura": (
            "ataque 1 prospera si el orden de brazos o el recuento cambian mucho al mover el "
            "umbral. ataque 2 prospera si la mejora correlaciona fuerte con el punto de "
            "partida Y los controles empeoran; si los controles NO empeoran, la regresion a "
            "la media no explica el efecto"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for p in pares:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("=== ATAQUE 1: conversiones por umbral ===")
    for est, d in a1.items():
        print(f"--- {est} ---")
        print("%-9s %4s %s" % ("brazo", "n", "  ".join(f"<={u}A" for u in UMBRALES)))
        for brazo, f in d.items():
            print("%-9s %4d %s   (casi-acierto 2-3A: %d)" % (
                brazo, f["n"], "  ".join("%2d" % f[f"conv_{u}"]["k"] for u in UMBRALES),
                f["casi_acierto_2_3A"]))
    print()
    print("=== ATAQUE 2a: regresion a la media ===")
    for est, v in a2a.items():
        print("  %-11s n=%2d  rho(base, mejora)=%s  mejora mediana=%s" % (
            est, v["n"], v["spearman_base_vs_mejora"], v["mejora_mediana"]))
    print()
    print("=== ATAQUE 2b: degradan los controles? ===")
    for est, v in a2b.items():
        print("  %-11s n=%2d  delta=%+.3f CI95[%+.3f,%+.3f]  empeoran %d / mejoran %d" % (
            est, v["n"], v["delta_oraculo_medio"], v["ci95"][0], v["ci95"][1],
            v["empeoran"], v["mejoran"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
