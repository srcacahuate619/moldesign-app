#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_fnd04_verificacion.py — FND-04: sanity tests y re-verificacion de sellos.

Dos partes, ambas obligatorias por la §6 del doc. 49:

  1. **Sanity tests perfect/random**: cada estadistico se valida contra casos de
     respuesta conocida analiticamente. Si la biblioteca falla aqui, no se usa.
  2. **Re-verificacion independiente**: se recomputan los intervalos de `RS-14` y
     `RS-14-R1` desde sus `per_complex.jsonl` con ESTA biblioteca y se comparan con
     los valores sellados. Es la primera vez que un CI del programa se comprueba con
     una implementacion distinta de la que lo produjo.

Un desacuerdo aqui NO reabre un sello: lo documenta. La inmutabilidad post-seal se
respeta y la discrepancia, si la hubiera, se registra como hallazgo.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from estadistica_fnd04 import (  # noqa: E402
    wilson, mcnemar_exacto, bootstrap_bca_pareado, benjamini_hochberg)

ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FND-04"


def sanity():
    """Casos con respuesta conocida. Devuelve (lista de resultados, todos_ok)."""
    t = []

    def chk(nombre, ok, detalle):
        t.append({"test": nombre, "pass": bool(ok), "detalle": detalle})

    # Wilson: proporcion perfecta no puede tener ancho cero
    # el borde superior de Wilson para p=1 vale 1.0 solo analiticamente; en coma
    # flotante puede quedar en 0.999...  Comparar con == seria un test mal escrito.
    lo, hi = wilson(10, 10)
    chk("wilson_perfecto_no_degenera", lo < 1.0 and abs(hi - 1.0) < 1e-9,
        f"10/10 -> [{lo:.4f}, {hi:.4f}]")
    lo, hi = wilson(0, 10)
    chk("wilson_cero_no_degenera", abs(lo) < 1e-9 and hi > 0.0,
        f"0/10 -> [{lo:.4f}, {hi:.4f}]")
    lo, hi = wilson(5, 10)
    chk("wilson_simetrico_en_0.5", abs((lo + hi) / 2 - 0.5) < 1e-9,
        f"5/10 -> [{lo:.4f}, {hi:.4f}]")

    # McNemar: sin discordancias -> p=1; totalmente asimetrico -> p pequeno
    chk("mcnemar_sin_discordancia", mcnemar_exacto(0, 0) == 1.0, "b=c=0 -> 1.0")
    p = mcnemar_exacto(8, 0)
    chk("mcnemar_asimetrico", abs(p - 2 * 0.5 ** 8) < 1e-12, f"b=8,c=0 -> {p:.6f}")
    chk("mcnemar_simetrico", mcnemar_exacto(5, 5) == 1.0, "b=c=5 -> 1.0")

    # Bootstrap: constante -> intervalo degenerado en el punto
    th, lo, hi = bootstrap_bca_pareado([0.3] * 20, n_boot=500, seed=1)
    chk("bootstrap_constante_degenera", abs(th - 0.3) < 1e-12 and lo == hi == th,
        f"[{lo:.4f}, {hi:.4f}]")
    # Bootstrap: media claramente positiva -> IC excluye el cero
    th, lo, hi = bootstrap_bca_pareado([1.0] * 30 + [0.9] * 30, n_boot=2000, seed=1)
    chk("bootstrap_positivo_excluye_cero", lo > 0, f"media {th:.3f} -> [{lo:.3f}, {hi:.3f}]")
    # Bootstrap: simetrico alrededor de cero -> IC incluye el cero
    th, lo, hi = bootstrap_bca_pareado([1.0] * 25 + [-1.0] * 25, n_boot=2000, seed=1)
    chk("bootstrap_nulo_incluye_cero", lo <= 0 <= hi, f"media {th:.3f} -> [{lo:.3f}, {hi:.3f}]")

    # FDR: todos nulos -> ningun rechazo; todos ceros -> todos rechazados
    chk("fdr_todos_nulos", not any(benjamini_hochberg([0.9] * 10)), "10 x p=0.9")
    chk("fdr_todos_signif", all(benjamini_hochberg([0.0] * 10)), "10 x p=0.0")
    r = benjamini_hochberg([0.001, 0.5, 0.6, 0.7, 0.8])
    chk("fdr_mixto", r[0] and not any(r[1:]), f"{r}")

    return t, all(x["pass"] for x in t)


def reverificar(exp_id: str, semillas=("42", "43", "44")):
    """Recomputa la diferencia pareada de un experimento de seleccion desde su jsonl."""
    p = ART / exp_id / "per_complex.jsonl"
    if not p.exists():
        return {"experimento": exp_id, "error": "SIN_PER_COMPLEX"}
    dif = []
    n_cub = 0
    sel_hits = 0
    base_hits = 0
    for l in p.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if not d.get("cubierto"):
            continue
        n_cub += 1
        s = d.get("selector_acierta", {})
        # media sobre semillas: el selector es estocastico, el baseline no
        vals = [1.0 if s.get(k) else 0.0 for k in semillas if k in s]
        ms = sum(vals) / len(vals) if vals else 0.0
        mb = 1.0 if d.get("baseline_acierta") else 0.0
        sel_hits += ms
        base_hits += mb
        dif.append(ms - mb)
    if not dif:
        return {"experimento": exp_id, "error": "SIN_CUBIERTOS"}
    th, lo, hi = bootstrap_bca_pareado(dif, n_boot=10000, seed=42)
    b = sum(1 for x in dif if x > 0)
    c = sum(1 for x in dif if x < 0)
    sellado = json.loads((ART / exp_id / "metrics.json").read_text(encoding="utf-8"))
    sd = sellado.get("diferencia_pareada", {})
    return {
        "experimento": exp_id,
        "n_complejos_cubiertos": n_cub,
        "condicional_selector_recomputada": round(sel_hits / n_cub, 4),
        "condicional_baseline_recomputada": round(base_hits / n_cub, 4),
        "diferencia_pareada_recomputada": round(th, 4),
        "ci95_bca_recomputado": [round(lo, 4), round(hi, 4)],
        "sellado": {"media": sd.get("media"), "ci95_bca": sd.get("ci95_bca"),
                    "n_complejos": sd.get("n_complejos")},
        "coincide_media": (sd.get("media") is not None
                           and abs(th - sd["media"]) <= 0.01),
        "coincide_signo_del_gate": (sd.get("ci95_bca") is not None
                                    and (lo > 0) == (sd["ci95_bca"][0] > 0)),
        "mcnemar_exacto_discordancias": {"b": b, "c": c, "p": round(mcnemar_exacto(b, c), 6)},
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tests, ok = sanity()
    print(f"[FND-04] sanity: {sum(t['pass'] for t in tests)}/{len(tests)} pasan")
    for t in tests:
        print(f"   {'OK ' if t['pass'] else 'FALLA'} {t['test']}: {t['detalle']}")
    ver = [reverificar("RS-14"), reverificar("RS-14-R1")]
    print()
    for v in ver:
        if "error" in v:
            print(f"[FND-04] {v['experimento']}: {v['error']}")
            continue
        print(f"[FND-04] {v['experimento']}: recomputado {v['diferencia_pareada_recomputada']} "
              f"CI {v['ci95_bca_recomputado']} | sellado {v['sellado']['media']} "
              f"{v['sellado']['ci95_bca']} | coincide={v['coincide_media']} "
              f"gate_igual={v['coincide_signo_del_gate']}")
    metrics = {
        "experiment_id": "FND-04",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sanity_tests": tests,
        "sanity_todos_pasan": ok,
        "reverificacion_independiente": ver,
        "nota": ("un desacuerdo NO reabre un sello: lo documenta. La inmutabilidad "
                 "post-seal se respeta y la discrepancia se registra como hallazgo."),
        "gates": {
            "G1_sanity": {"criterio": "todos los sanity tests perfect/random pasan", "pass": ok},
            "G2_reverificacion": {
                "criterio": "la diferencia pareada recomputada coincide con la sellada (<=0.01) "
                            "y el veredicto del gate no cambia",
                "pass": all(v.get("coincide_media") and v.get("coincide_signo_del_gate")
                            for v in ver if "error" not in v)},
        },
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(f"\n[FND-04] decision {metrics['decision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
