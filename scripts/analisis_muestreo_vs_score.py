#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_muestreo_vs_score.py — ¿el generador no la produce, o el score no la elige?

MF-08 y MF-02F agotaron las dos palancas geométricas sobre la misma cohorte —menos
espacio de búsqueda y más reinicios— y ambas convirtieron 3 de 33 moviendo la
mediana ~0.8 Å. Queda separar las dos causas posibles del fallo de colocación:

  (A) **muestreo**: entre todas las poses generadas no existe ninguna a ≤2 Å;
      ningún selector puede arreglarlo.
  (B) **puntuación**: la pose buena existe pero el score de Vina no la rankea
      arriba; ahí sí hay margen para un selector.

Sobre el material de K90 (~250 poses por complejo, ya en disco) se calcula por
complejo: el oráculo (mejor RMSD disponible), el RMSD de la pose que el score
elegiría (top-1), el rango de la mejor pose según score, y la correlación de
Spearman entre score y RMSD.

Cero cómputo nuevo: solo lectura de los `conf*.out.pdbqt` existentes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MATERIAL = Path(os.environ.get("MVS_MATERIAL", str(PROJECT_ROOT / "data" / "molflex_reinicios")))
# El conjunto K90 vive en DOS directorios: el prefijo K30 es el material sellado de
# MF-02D y solo los conformeros posteriores se dockearon en MF-02F. Leer uno solo
# deja fuera la mitad de las poses y sesga el oraculo y el top-1 por score.
MATERIAL_K30 = PROJECT_ROOT / "data" / "molflex_train_v2"
COHORTE = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-09"
UMBRAL_A = 2.0


def _spearman(a: List[float], b: List[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None
    def rangos(v):
        orden = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
                j += 1
            promedio = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[orden[k]] = promedio
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def _analizar(job: Dict[str, str]) -> Dict[str, Any]:
    import molflex as mf
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"]}
    dirs = [d / pid / pid for d in (MATERIAL_K30, MATERIAL)]
    dirs = [d for d in dirs if (d / "index_map.json").exists()]
    if not dirs:
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out

    scores: List[float] = []
    rmsds: List[float] = []
    for w in dirs:
        s2m = {int(s): int(m) for s, m in
               json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
        for f in sorted(w.glob("conf*.out.pdbqt")):
            for sc, at in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
                if sc is None:
                    continue
                c = mf.coords_pose_a_por_mol(at, s2m)
                if not c:
                    continue
                rp = mf.rmsd_pose_pocket(crystal, c)
                if rp is None:
                    continue
                scores.append(float(sc))
                rmsds.append(float(rp))
    out["n_directorios"] = len(dirs)
    if not scores:
        out["error"] = "SIN_POSES"
        return out

    n = len(scores)
    orden = sorted(range(n), key=lambda i: scores[i])          # mejor score primero
    i_mejor_rmsd = min(range(n), key=lambda i: rmsds[i])
    out.update({
        "n_poses": n,
        "oraculo_rmsd": round(rmsds[i_mejor_rmsd], 3),
        "top1_rmsd": round(rmsds[orden[0]], 3),
        "top1_score": round(scores[orden[0]], 3),
        "score_de_la_mejor_rmsd": round(scores[i_mejor_rmsd], 3),
        "rango_de_la_mejor_rmsd": orden.index(i_mejor_rmsd) + 1,
        "percentil_de_la_mejor_rmsd": round((orden.index(i_mejor_rmsd) + 1) / n, 4),
        "n_poses_buenas": sum(1 for r in rmsds if r <= UMBRAL_A),
        "spearman_score_rmsd": _spearman(scores, rmsds),
        "existe_pose_buena": bool(min(rmsds) <= UMBRAL_A),
        "top1_acierta": bool(rmsds[orden[0]] <= UMBRAL_A),
    })
    # ¿Alguna de las 9 mejores por score acierta? (lo que veria un top-K corto)
    for k in (1, 5, 9, 20):
        out[f"acierta_top{k}"] = bool(any(rmsds[i] <= UMBRAL_A for i in orden[:k]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Muestreo vs puntuacion sobre material existente")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coh = json.loads(COHORTE.read_text(encoding="utf-8"))
    jobs = ([{"pid": p, "estrato": "COLOCACION"} for p in coh["cohorte_colocacion"]]
            + [{"pid": p, "estrato": "CONTROL"} for p in coh["control_cubiertos"]])
    print(f"[MF-09] {len(jobs)} complejos | material {MATERIAL.name}", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs, chunksize=1), 1):
            filas.append(r)
            if i % 10 == 0 or i == len(jobs):
                print(f"  [{i}/{len(jobs)}] ({round(time.time() - t0)}s)", flush=True)

    ok = [f for f in filas if "error" not in f]

    def resumen(estrato: str) -> Dict[str, Any]:
        g = [f for f in ok if f["estrato"] == estrato]
        if not g:
            return {}
        con = [f for f in g if f["existe_pose_buena"]]
        sp = [f["spearman_score_rmsd"] for f in g if f["spearman_score_rmsd"] is not None]
        return {
            "n": len(g),
            "n_poses_mediana": round(median([f["n_poses"] for f in g]), 1),
            "oraculo_mediana": round(median([f["oraculo_rmsd"] for f in g]), 3),
            "top1_mediana": round(median([f["top1_rmsd"] for f in g]), 3),
            "existe_pose_buena": len(con),
            "top1_acierta": sum(1 for f in g if f["acierta_top1"]),
            "acierta_top5": sum(1 for f in g if f["acierta_top5"]),
            "acierta_top9": sum(1 for f in g if f["acierta_top9"]),
            "acierta_top20": sum(1 for f in g if f["acierta_top20"]),
            "margen_de_seleccion": len(con) - sum(1 for f in g if f["acierta_top1"]),
            "spearman_mediano": round(median(sp), 4) if sp else None,
            "rango_mediano_de_la_mejor_rmsd": round(median([f["rango_de_la_mejor_rmsd"] for f in g]), 1),
            "percentil_mediano_de_la_mejor_rmsd": round(median([f["percentil_de_la_mejor_rmsd"] for f in g]), 4),
        }

    res = {e: resumen(e) for e in ("COLOCACION", "CONTROL")}
    metrics = {
        "experiment_id": "MF-09",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "material": str(MATERIAL.relative_to(PROJECT_ROOT)),
        "umbral_A": UMBRAL_A,
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": res,
        "definiciones": {
            "muestreo": "no existe ninguna pose <=2 A entre todas las generadas: ningun selector puede arreglarlo",
            "puntuacion": "existe pose buena pero el top-1 por score no acierta: margen para un selector",
            "margen_de_seleccion": "complejos con pose buena disponible que el top-1 por score falla",
        },
    }
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    for e, r in res.items():
        if not r:
            continue
        print(f"\n{e} (n={r['n']}, mediana {r['n_poses_mediana']} poses/complejo):")
        print(f"  oraculo mediano {r['oraculo_mediana']} A | top-1 por score {r['top1_mediana']} A")
        print(f"  existe pose <=2 A: {r['existe_pose_buena']}/{r['n']} | top-1 acierta: {r['top1_acierta']}")
        print(f"  acierta en top-5 {r['acierta_top5']} | top-9 {r['acierta_top9']} | top-20 {r['acierta_top20']}")
        print(f"  MARGEN DE SELECCION: {r['margen_de_seleccion']} complejos con pose buena que el score no elige")
        print(f"  spearman(score,rmsd) mediano: {r['spearman_mediano']} | "
              f"la mejor pose queda en el percentil {r['percentil_mediano_de_la_mejor_rmsd']:.1%} por score")
    return 0


if __name__ == "__main__":
    sys.exit(main())
