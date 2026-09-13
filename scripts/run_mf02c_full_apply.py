#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02c_full_apply.py — MF-02C: completar la aplicación de MolFlex a los 116 de train.

Prerrequisito formal: `scripts/artifacts_science/MF-02C-PRE/PREREGISTRO.md` sellado.

MF-02B aplicó el pipeline congelado a 50 complejos (38 sin cobertura + 12 de
control) y recuperó 30, subiendo la cobertura del oráculo de 67.2% a 93.1%. Este
experimento completa los **66 restantes** para dejar el conjunto de train con la
salida del generador en los 116, y mide la cobertura total resultante.

Reutiliza sin modificarlo el runner sellado de MF-02B (`_una`), de modo que el
protocolo por complejo es byte-idéntico: `n_conf=30`, caja 25 A,
`exhaustiveness=8`, semillas 42, `top_k=3`, `cpu=1`.

No reconstruye el dataset de features (`poses_train.jsonl`): eso es ingeniería de
datos con su propio contrato y queda declarado como fuera de alcance.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_mf02b_apply_molflex as B  # noqa: E402  (runner sellado de MF-02B)

EXPERIMENT_ID = "MF-02C"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
MF02B_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02B"
UMBRAL_A = B.UMBRAL_A


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02C: aplicar MolFlex a los 66 restantes de train")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    B.WORK = OUT_DIR / "_work"
    B.WORK.mkdir(parents=True, exist_ok=True)

    coh = B.cohorte()
    todos = sorted(coh["mejor_dataset"])
    ya = set(coh["sin_cobertura"]) | set(coh["control"])
    resto = [p for p in todos if p not in ya]
    if args.limite:
        resto = resto[:args.limite]
    print(f"[MF-02C] train={len(todos)} | ya corridos en MF-02B={len(ya)} | "
          f"restantes={len(resto)}", flush=True)

    jobs = [{"pid": p, "brazo": "A8", "estrato": "RESTO"} for p in resto]
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(B._una, jobs, chunksize=1), 1):
            filas.append(f)
            if i % 5 == 0 or i == len(jobs):
                ok = sum(1 for x in filas if x.get("exito"))
                print(f"  [{i}/{len(jobs)}] entregan <=2A: {ok} ({round(time.time() - t0)}s)",
                      flush=True)

    # ── Cobertura total de train: dataset ∪ MolFlex (MF-02B + MF-02C) ──
    mejor_molflex: Dict[str, float] = {}
    for r in (json.loads(l) for l in (MF02B_DIR / "corridas.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()):
        v = r.get("rmsd_entregado")
        if v is not None and (r["pid"] not in mejor_molflex or v < mejor_molflex[r["pid"]]):
            mejor_molflex[r["pid"]] = v
    for r in filas:
        v = r.get("rmsd_entregado")
        if v is not None and (r["pid"] not in mejor_molflex or v < mejor_molflex[r["pid"]]):
            mejor_molflex[r["pid"]] = v

    resumen = []
    for pid in todos:
        base = coh["mejor_dataset"].get(pid)
        nuevo = mejor_molflex.get(pid)
        union = min([x for x in (base, nuevo) if x is not None], default=None)
        resumen.append({
            "pid": pid,
            "corrido_en": "MF-02B" if pid in ya else "MF-02C",
            "mejor_dataset": base,
            "mejor_molflex": nuevo,
            "mejor_union": round(union, 3) if union is not None else None,
            "cubierto_antes": bool(base is not None and base <= UMBRAL_A),
            "cubierto_despues": bool(union is not None and union <= UMBRAL_A),
            "fuentes_dataset": coh["fuentes_dataset"].get(pid),
        })

    antes = sum(1 for r in resumen if r["cubierto_antes"])
    despues = sum(1 for r in resumen if r["cubierto_despues"])
    perdidos = [r["pid"] for r in resumen if r["cubierto_antes"] and not r["cubierto_despues"]]
    sin_molflex = [r["pid"] for r in resumen if r["mejor_molflex"] is None]
    n_ok = sum(1 for f in filas if f.get("ok"))

    from statistics import median
    costes = [f["wall_s"] for f in filas if f.get("ok")]
    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"n_conf": B.N_CONF, "top_k": B.TOP_K, "exhaustiveness": B.BRAZOS["A8"],
                   "umbral_A": UMBRAL_A,
                   "protocolo": "identico a MF-02B (runner sellado, reutilizado sin modificar)"},
        "n_restantes": len(resto), "n_corridas": len(filas), "n_ok": n_ok,
        "cobertura_train_antes": {"n": antes, "de": len(todos), "frac": round(antes / len(todos), 4)},
        "cobertura_train_despues": {"n": despues, "de": len(todos), "frac": round(despues / len(todos), 4)},
        "ganancia_puntos": round((despues - antes) / len(todos) * 100, 1),
        "complejos_sin_pose_molflex": sin_molflex,
        "coste": {"n": len(costes), "mediana_s": round(median(costes), 1) if costes else None,
                  "total_s": round(sum(costes), 1) if costes else None},
        "fuera_de_alcance": ("No reconstruye poses_train.jsonl con features; este experimento "
                             "mide cobertura del oraculo, no produce el dataset del selector."),
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% de corridas completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_no_regresion": {"criterio": "la union no reduce la cobertura de ningun complejo",
                            "perdidos": perdidos, "pass": not perdidos},
        "G3_cobertura": {"criterio": "cobertura de train con la union >= 90%",
                         "cobertura": metrics["cobertura_train_despues"]["frac"],
                         "pass": metrics["cobertura_train_despues"]["frac"] >= 0.90},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in resumen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "corridas.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            if not r.get("ok"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02C] decision {metrics['decision']}")
    print(f"  cobertura del oraculo en train: {antes}/{len(todos)} -> {despues}/{len(todos)} "
          f"({metrics['cobertura_train_antes']['frac']:.1%} -> "
          f"{metrics['cobertura_train_despues']['frac']:.1%}, +{metrics['ganancia_puntos']} puntos)")
    print(f"  coste mediana {metrics['coste']['mediana_s']} s/complejo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
