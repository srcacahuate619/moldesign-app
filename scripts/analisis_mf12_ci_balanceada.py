#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf12_ci_balanceada.py — el intervalo que el gate G2 de MF-12 pedía.

El prerregistro de MF-12 fija como métrica primaria la **precisión balanceada** del nivel L
y pide que su IC 95 % bootstrap excluya cero frente al baseline mayoritario. El runner
sellado (`run_mf12_triage.py:179-181`) calcula ese punto, pero pasa al bootstrap la
diferencia pareada de **aciertos** por complejo: el intervalo que decide el GO es el de una
diferencia de exactitud. Lo encontró la auditoría científica (SCI-B-076).

Este script recupera las predicciones de valtest reajustando el mismo modelo
(StandardScaler + LogisticRegression(C=1, max_iter=2000), entrenado en train) sobre los
rasgos y desenlaces que el propio MF-12 selló en `per_complex.jsonl`; comprueba que
reproduce lo sellado (coeficientes, precisiones, exactitudes y el IC de exactitud); y sólo
entonces calcula el IC BCa de la diferencia de **precisión balanceada** pareada por
complejo, con el mismo bootstrap (`estadistica_fnd04.bootstrap_bca_pareado`, 10 000
réplicas, semilla 42).

No toca los artefactos sellados.

Uso:
    python scripts/analisis_mf12_ci_balanceada.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from estadistica_fnd04 import bootstrap_bca_pareado  # noqa: E402

MF12 = Path("scripts/artifacts_science/MF-12")
NIVEL_L = ["n_torsiones", "n_pesados", "n_conformeros", "rg_conformero", "ocupacion_conformero"]
NIVEL_S = ["prot_5A_centro", "prot_8A_centro"]
NIVELES = (("L", NIVEL_L), ("L+S", NIVEL_L + NIVEL_S))


def precision_balanceada(y: Sequence[bool], p: Sequence[bool]) -> float:
    pos = sum(1 for a in y if a)
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    tp = sum(1 for a, b in zip(y, p) if a and b)
    tn = sum(1 for a, b in zip(y, p) if not a and not b)
    return 0.5 * (tp / pos + tn / neg)


def diferencia_balanceada(trios: Sequence[Tuple[bool, bool, bool]]) -> float:
    """Precisión balanceada del modelo menos la del baseline, sobre los mismos complejos.

    Una réplica bootstrap sin las dos clases no define la métrica: devuelve NaN, y se
    cuenta aparte en vez de convertirla en cero.
    """
    y = [t[0] for t in trios]
    return precision_balanceada(y, [t[1] for t in trios]) - precision_balanceada(y, [t[2] for t in trios])


def predicciones(filas: List[Dict[str, Any]], cols: List[str]):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    tr = [r for r in filas if r["split"] == "train"]
    te = [r for r in filas if r["split"] == "valtest"]
    xtr = np.array([[r[c] for c in cols] for r in tr], dtype=float)
    ytr = np.array([r["convierte"] for r in tr])
    xte = np.array([[r[c] for c in cols] for r in te], dtype=float)
    yte = np.array([r["convierte"] for r in te])
    sc = StandardScaler().fit(xtr)
    mod = LogisticRegression(max_iter=2000, C=1.0).fit(sc.transform(xtr), ytr)
    pte = mod.predict(sc.transform(xte))
    pbase = np.full(len(yte), bool(ytr.mean() >= 0.5))
    coef = {c: round(float(v), 4) for c, v in zip(cols, mod.coef_[0])}
    return [bool(v) for v in yte], [bool(v) for v in pte], [bool(v) for v in pbase], coef


def analizar(raiz: Path) -> Dict[str, Any]:
    filas = [json.loads(l) for l in (raiz / MF12 / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    sellado = json.loads((raiz / MF12 / "metrics.json").read_text(encoding="utf-8"))["niveles"]
    salida: Dict[str, Any] = {}
    for nivel, cols in NIVELES:
        y, p, b, coef = predicciones(filas, cols)
        dif_exactitud = [(1.0 if a == m else 0.0) - (1.0 if a == c else 0.0) for a, m, c in zip(y, p, b)]
        th_e, lo_e, hi_e = bootstrap_bca_pareado(dif_exactitud, n_boot=10000, seed=42)
        reproduce = {
            "coeficientes": coef == sellado[nivel]["coeficientes"],
            "precision_balanceada_modelo":
                round(precision_balanceada(y, p), 4) == sellado[nivel]["precision_balanceada_modelo"],
            "exactitud_modelo":
                round(sum(a == m for a, m in zip(y, p)) / len(y), 4) == sellado[nivel]["exactitud_modelo"],
            "ci95_exactitud": [round(lo_e, 4), round(hi_e, 4)] == sellado[nivel]["ci95_bca"],
        }
        trios = list(zip(y, p, b))
        th, lo, hi = bootstrap_bca_pareado(trios, n_boot=10000, seed=42, estadistico=diferencia_balanceada)
        salida[nivel] = {
            "n_valtest": len(y),
            "reproduce_lo_sellado": reproduce,
            "dif_precision_balanceada": round(th, 4),
            "ci95_bca_precision_balanceada": [round(lo, 4), round(hi, 4)],
            "excluye_cero": bool(lo > 0) if not math.isnan(lo) else None,
            "ci95_bca_exactitud_sellado": sellado[nivel]["ci95_bca"],
        }
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-12: IC de la precisión balanceada que pedía G2")
    ap.add_argument("--raiz", type=Path, default=PROJECT_ROOT)
    args = ap.parse_args()
    salida = analizar(args.raiz)
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    return 0 if all(all(v["reproduce_lo_sellado"].values()) for v in salida.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
