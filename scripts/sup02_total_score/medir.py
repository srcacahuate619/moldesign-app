#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SUP-02-TOTAL-SCORE: ¿ordena el total_score mejor que Vina? Aplica `entrada/REGISTRO_PREVIO.md` sin correr nada.

Lee el top-1 de Vina y el pKi de `per_complex.jsonl` de CAL-D-01-R4-2-VMAT2-8T69 y CAL-8HFI-01, y el `total_score` que el producto
calculó en la misma corrida (`resultado.total_score` del crudo). Escribe `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.

Uso: python scripts/sup02_total_score/medir.py
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

RAIZ = Path(__file__).resolve().parents[2]
ART = RAIZ / "scripts" / "artifacts_science"
EXP = ART / "SUP-02-TOTAL-SCORE"
SEMILLA, REMUESTREOS = 42, 10_000
TECHO, SUELO = 99.5, 0.5


def _filas(experimento: str) -> list[dict]:
    with open(ART / experimento / "per_complex.jsonl", encoding="utf-8") as fh:
        return [f for f in map(json.loads, fh) if f.get("tipo") == "panel"]


def _crudo_r4_2(fila: dict) -> Path:
    for terminal in (ART / "CAL-D-01-R4-2-VMAT2-8T69" / "_work" / "panel").glob(f"shard-*/{fila['id']}.terminal.json"):
        return terminal.parent / json.loads(terminal.read_text(encoding="utf-8"))["crudo"]
    raise FileNotFoundError(fila["id"])


def _crudo_8hfi(fila: dict) -> Path:
    return ART / "CAL-8HFI-01" / "_work" / f"{fila['id']}.json.gz"


SERIES = {
    "8T69": ("CAL-D-01-R4-2-VMAT2-8T69", _crudo_r4_2),
    "8HFI": ("CAL-8HFI-01", _crudo_8hfi),
}


def _total_score(crudo: Path) -> float:
    datos = json.load(gzip.open(crudo, "rt", encoding="utf-8"))
    return float(datos["resultado"]["total_score"])


def _rho(x, y) -> float:
    return float(spearmanr(x, y).statistic)


def _serie(nombre: str, experimento: str, crudo_de) -> tuple[dict, list[dict], list[dict]]:
    filas, fallos = [], []
    for f in _filas(experimento):
        try:
            ts = _total_score(crudo_de(f))
        except (OSError, KeyError, ValueError) as exc:
            fallos.append({"serie": nombre, "id": f["id"], "motivo": f"{type(exc).__name__}: {exc}"})
            continue
        filas.append({"serie": nombre, "id": f["id"], "pki": f["pki"], "vina_kcal": f["E_kcal"], "total_score": ts})
    pki = np.array([f["pki"] for f in filas])
    vina = -np.array([f["vina_kcal"] for f in filas])
    ts = np.array([f["total_score"] for f in filas])
    rho_ts, rho_vina = _rho(ts, pki), _rho(vina, pki)
    rng = np.random.default_rng(SEMILLA)
    deltas = np.empty(REMUESTREOS)
    for i in range(REMUESTREOS):
        idx = rng.integers(0, len(filas), len(filas))
        deltas[i] = _rho(ts[idx], pki[idx]) - _rho(vina[idx], pki[idx])
    lo, hi = (float(v) for v in np.nanpercentile(deltas, [2.5, 97.5]))
    metricas = {
        "n": len(filas),
        "rho_total_score": round(rho_ts, 4),
        "rho_vina": round(rho_vina, 4),
        "delta": round(rho_ts - rho_vina, 4),
        "delta_ic95": [round(lo, 4), round(hi, 4)],
        "remuestreos_no_finitos": int(np.sum(~np.isfinite(deltas))),
        "rho_total_score_frente_a_vina": round(_rho(ts, vina), 4),
        "en_el_techo": int(np.sum(ts >= TECHO)),
        "en_el_suelo": int(np.sum(ts <= SUELO)),
        "total_score_mediana": round(float(np.median(ts)), 2),
        "total_score_rango": [round(float(ts.min()), 2), round(float(ts.max()), 2)],
        "ic_excluye_cero": "por_encima" if lo > 0 else "por_debajo" if hi < 0 else "no",
    }
    return metricas, filas, fallos


def main() -> None:
    metricas, filas, fallos = {}, [], []
    for nombre, (experimento, crudo_de) in SERIES.items():
        m, f, x = _serie(nombre, experimento, crudo_de)
        metricas[nombre], filas, fallos = m, filas + f, fallos + x
    lados = {m["ic_excluye_cero"] for m in metricas.values()}
    decision = ("GO" if lados == {"por_encima"} else "NO_GO")
    salida = {
        "experiment_id": "SUP-02-TOTAL-SCORE",
        "series": metricas,
        "dano": "por_debajo" in lados,
        "decision": decision,
        "bootstrap": {"remuestreos": REMUESTREOS, "semilla": SEMILLA, "tipo": "pareado por compuesto, percentiles 2,5–97,5"},
    }
    (EXP / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(EXP / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in filas)
    with open(EXP / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in fallos)
    print(json.dumps(salida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
