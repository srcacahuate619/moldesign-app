#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep04_confianza.py — FEP-04: pose inicial, alternativas top-K y confianza calibrada.

**Tipo: medición.** Lectura del material sellado. Sin docking.

Qué pide FEP-04, y por qué es la pieza central del posicionamiento
------------------------------------------------------------------
La cartera H lo define como «pose seleccionada, alternativas top-K y confianza
incluidas». Con MolDesign posicionado como software de entrada, esto **es** el producto:
FEP+ es brutalmente sensible a la pose de partida, así que el valor no está en acertar
siempre —hoy sabemos que no— sino en **declarar cuándo no fiarse**.

Y una confianza que no calibra es peor que ninguna: induce a confiar donde no se debe.

Qué se mide
-----------
Por complejo, tres señales calculables **sin conocer la respuesta**:

  * `margen` — diferencia de score entre el top-1 y el top-2 de poses
    geométricamente distintas. Un top-1 que gana por mucho es más creíble;
  * `dispersion_topk` — RMSD medio entre las K mejores poses. Si convergen al mismo
    sitio, hay acuerdo; si se dispersan, el buscador no decidió;
  * `n_modos_empatados` — modos distintos a menos de 1 kcal/mol del mejor.

Y el desenlace real: si el top-1 está a ≤2 Å (`acierta`).

La métrica que decide
---------------------
**Curva riesgo–cobertura**: si se abstiene en el X% menos confiable, ¿cuánto sube la
precisión en el resto? Es la métrica de incertidumbre que la §5 del doc. 49 declara
como primaria, y es exactamente la promesa del producto: *«sé cuándo no fiarme»*.

Se reporta también la **calibración** por deciles, porque una señal puede ordenar bien
y aun así estar mal escalada.

Limitación declarada
--------------------
Las tres señales se calculan sobre las poses que el pipeline ya generó, así que heredan
sus sesgos. Y no hay conjunto de calibración independiente: la curva se mide sobre los
mismos datos en que se observan las señales, de modo que es **optimista**. Un uso en
producción exigiría calibrar en train y medir en val/test, que es el paso siguiente.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import wilson  # noqa: E402

V2 = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
MATS = {"train": PROJECT_ROOT / "data" / "molflex_train_v2",
        "valtest": PROJECT_ROOT / "data" / "molflex_valtest_v2"}
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FEP-04"
TOP_K = 5
U_MODO = 2.0
DELTA_EMPATE = 1.0
UMBRAL_A = 2.0


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    pid, split = job["pid"], job["split"]
    out: Dict[str, Any] = {"pid": pid, "split": split}
    esperadas = {(k[0], k[1]): (r, s) for k, r, s in job["poses"]}
    w = MATS[split] / pid / pid
    if not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    coords, rms, scores = [], [], []
    for f in sorted(w.glob("conf*.out.pdbqt")):
        stem = f.name[:-len(".pdbqt")]
        for midx, (sc, at) in enumerate(
                mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace"))):
            if (stem, midx) not in esperadas:
                continue
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c or any(i not in c for i in pesados):
                continue
            coords.append([list(c[i]) for i in pesados])
            r, s = esperadas[(stem, midx)]
            rms.append(r)
            scores.append(s)
    n = len(coords)
    out["n_poses"] = n
    if n < 5:
        out["error"] = "POCAS_POSES"
        return out

    X = np.asarray(coords, dtype=float)
    sc = np.asarray(scores)
    rm = np.asarray(rms)
    orden = np.argsort(sc)          # mas negativo = mejor
    top = orden[:TOP_K]

    # RMSD pose-vs-pose del top-K
    def _rmsd(i, j):
        return float(np.sqrt(((X[i] - X[j]) ** 2).sum(axis=1).mean()))

    disp = [_rmsd(int(a), int(b)) for ii, a in enumerate(top) for b in top[ii + 1:]]
    out["dispersion_topk"] = round(float(np.mean(disp)), 3) if disp else 0.0

    # margen: top-1 contra la mejor pose GEOMETRICAMENTE distinta (>U_MODO del top-1)
    i0 = int(orden[0])
    alt = [int(i) for i in orden[1:] if _rmsd(i0, int(i)) > U_MODO]
    out["margen"] = round(float(sc[alt[0]] - sc[i0]), 3) if alt else None

    # modos distintos empatados a <=DELTA_EMPATE del mejor
    umbral = float(sc[i0]) + DELTA_EMPATE
    cand = [int(i) for i in orden if sc[i] <= umbral]
    reps: List[int] = []
    for i in cand:
        if all(_rmsd(i, j) > U_MODO for j in reps):
            reps.append(i)
    out["n_modos_empatados"] = len(reps)

    out["rmsd_top1"] = round(float(rm[i0]), 3)
    out["acierta"] = bool(rm[i0] <= UMBRAL_A)
    out["oraculo"] = round(float(rm.min()), 3)
    out["cubierto"] = bool(rm.min() <= UMBRAL_A)
    out["acierta_top5"] = bool(rm[top].min() <= UMBRAL_A)
    return out


def _riesgo_cobertura(filas: List[Dict[str, Any]], clave: str, mayor_mejor: bool):
    g = [r for r in filas if r.get(clave) is not None]
    if len(g) < 20:
        return None
    g.sort(key=lambda r: r[clave], reverse=mayor_mejor)   # primero los mas confiables
    curva = []
    for frac in (1.0, 0.9, 0.75, 0.5, 0.25):
        k = max(5, int(len(g) * frac))
        sub = g[:k]
        a = sum(1 for r in sub if r["acierta"])
        lo, hi = wilson(a, len(sub))
        curva.append({"cobertura": round(k / len(g), 2), "n": len(sub),
                      "precision": round(a / len(sub), 4),
                      "wilson95": [round(lo, 3), round(hi, 3)]})
    return curva


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-04: confianza de la pose inicial")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = []
    for split, arch in (("train", "poses_train.jsonl"),
                        ("valtest", "poses_val.jsonl"), ("valtest", "poses_test.jsonl")):
        por = defaultdict(list)
        for l in (V2 / arch).read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                if d.get("source") == "molflex":
                    por[d["pid"]].append(((d["file_stem"], d["model_idx"]),
                                          d["rmsd"], d["vina_score"]))
        for pid, v in por.items():
            jobs.append({"pid": pid, "split": split, "poses": v})
    print(f"[FEP-04] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            if i % 40 == 0:
                print(f"  [{i}/{len(jobs)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "acierta" in r]
    curvas = {
        "margen": _riesgo_cobertura(ok, "margen", mayor_mejor=True),
        "dispersion_topk": _riesgo_cobertura(ok, "dispersion_topk", mayor_mejor=False),
        "n_modos_empatados": _riesgo_cobertura(ok, "n_modos_empatados", mayor_mejor=False),
    }
    base_a = sum(1 for r in ok if r["acierta"])
    metrics = {
        "experiment_id": "FEP-04",
        "tipo": "medicion (lectura de material sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"top_k": TOP_K, "umbral_modo_A": U_MODO,
                   "delta_empate_kcal": DELTA_EMPATE, "umbral_acierto_A": UMBRAL_A},
        "n_complejos": len(filas), "n_ok": len(ok),
        "precision_top1_global": round(base_a / len(ok), 4) if ok else None,
        "precision_top5_global": round(sum(1 for r in ok if r["acierta_top5"]) / len(ok), 4)
        if ok else None,
        "cobertura_oraculo": round(sum(1 for r in ok if r["cubierto"]) / len(ok), 4)
        if ok else None,
        "curvas_riesgo_cobertura": curvas,
        "limitacion": ("las senales se observan sobre los mismos datos en que se mide la "
                       "curva: es OPTIMISTA. Un uso en produccion exige calibrar en train y "
                       "medir en val/test"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\nprecision top-1 global: %.3f | top-5: %.3f | cobertura del oraculo: %.3f" % (
        metrics["precision_top1_global"], metrics["precision_top5_global"],
        metrics["cobertura_oraculo"]))
    for k, c in curvas.items():
        if not c:
            continue
        print(f"\ncurva riesgo-cobertura por {k}:")
        for p in c:
            print("  cobertura %.0f%%  n=%3d  precision=%.3f  Wilson95[%.3f, %.3f]" % (
                p["cobertura"] * 100, p["n"], p["precision"],
                p["wilson95"][0], p["wilson95"][1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
