#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rs14_bca.py — el IC llamado «BCa» de RS-14 era percentil (SCI-B-025).

`run_rs14_selector_v2.py` calcula `np.percentile(boot, [2.5, 97.5])` y lo guarda como
`ci95_bca`. El preregistro de RS-14 pide BCa. El runner está sellado; aquí se recalcula, desde
las mismas diferencias por complejo (`per_complex.jsonl`), el percentil con el mismo generador y
el BCa de verdad (corrección de sesgo z0 y aceleración por jackknife), y se compara con el gate.

Uso:
    python scripts/analisis_rs14_bca.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analisis_fnd04_potencia_dominio import ART, difs_selector  # noqa: E402

B = 2000


def percentil_como_el_runner(dif: np.ndarray) -> tuple:
    boot = np.array([dif[i].mean() for i in np.random.default_rng(42).integers(0, len(dif), size=(B, len(dif)))])
    return float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)), boot


def bca(dif: np.ndarray, boot: np.ndarray, alpha: float = 0.05) -> tuple:
    theta = dif.mean()
    prop = np.mean(boot < theta) + 0.5 * np.mean(boot == theta)
    z0 = norm.ppf(prop)
    jack = np.array([np.delete(dif, i).mean() for i in range(len(dif))])
    u = jack.mean() - jack
    den = 6.0 * (np.sum(u ** 2) ** 1.5)
    a = float(np.sum(u ** 3) / den) if den > 0 else 0.0
    cortes = []
    for z in (norm.ppf(alpha / 2), norm.ppf(1 - alpha / 2)):
        cortes.append(norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z))))
    return float(np.quantile(boot, cortes[0])), float(np.quantile(boot, cortes[1])), float(z0), a


def analizar() -> dict:
    out = {}
    for exp in ("RS-14", "RS-14-R1"):
        dif = np.array(difs_selector(exp))
        lo, hi, boot = percentil_como_el_runner(dif)
        blo, bhi, z0, a = bca(dif, boot)
        sellado = json.loads((ART / exp / "metrics.json").read_text(encoding="utf-8"))["diferencia_pareada"]
        out[exp] = {"n": len(dif), "media": round(float(dif.mean()), 4),
                    "sellado_ci95_bca": sellado["ci95_bca"],
                    "percentil_recalculado": [round(lo, 4), round(hi, 4)],
                    "bca": [round(blo, 4), round(bhi, 4)], "z0": round(z0, 4), "a": round(a, 5),
                    "bca_excluye_cero": blo > 0 or bhi < 0}
    return out


if __name__ == "__main__":
    print(json.dumps(analizar(), ensure_ascii=False, indent=1))
