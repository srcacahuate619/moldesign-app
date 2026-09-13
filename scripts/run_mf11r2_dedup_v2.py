#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf11r2_dedup_v2.py — MF-11-R2: re-derivar el umbral de deduplicación sobre v2.

Entregable 9 del doc. 49, pendiente desde el 2026-08-17. `RC-F0-V2` lo dejó pedido de
forma explícita:

  «No aplica la deduplicación de `MF-11-R1`. Su umbral de 1.5 Å se eligió sobre la
   unión v1 (2,739 poses de train) con una regla explícita. La v2 es **6.9× más
   densa** (18,812 poses de train): reusar el *código* es reutilización, reusar el
   *umbral* sin re-derivarlo sería extrapolarlo a otro régimen.»

Aquí se re-deriva. **El contrato de `MF-11-R1` se reutiliza sin cambiar ni una regla**;
lo único que cambia es el conjunto sobre el que se aplica.

Contrato heredado de MF-11-R1, literal
--------------------------------------
  * **métrica**: RMSD pocket-frame pose-vs-pose, átomos pesados, correspondencia 1:1
    por índice de átomo, **sin alineamiento**;
  * **regla de admisión**: diámetro controlado — la pose entra al PRIMER clúster (en
    orden de creación) cuya distancia a TODOS sus miembros sea ≤ U, lo que garantiza
    que todo par de miembros queda a ≤ U; greedy por identidad ascendente; si no cabe
    en ninguno, clúster nuevo;
  * **representante**: medoid geométrico (minimiza la suma de RMSDs a los demás,
    empate por identidad ascendente). Es **label-blind**: no mira el RMSD al cristal
    ni el score;
  * **umbrales preregistrados**: 0.5, 0.75, 1.0, 1.5, 2.0 Å;
  * **selección**: el **MAYOR** umbral que cumpla las tres condiciones —(a) 0 pérdidas
    de cobertura, (b) degradación mediana ≤ 0.1 Å, (c) reducción ≥ 10%—. Si ninguno
    las cumple, **NO_GO** con la tabla completa, sin elegir a dedo.

Separación de oráculo: las etiquetas de RMSD al cristal se leen **solo** en la fase de
evaluación, nunca durante el clustering.

Alcance declarado
-----------------
Sólo las poses de fuente `molflex` (17,669 de 18,812 en train) tienen coordenadas
trazables al material. Las 1,143 de `flexible_redock` y `ruta_a` **pasan sin agrupar**,
como singletons. Es la opción conservadora: no aportan reducción y no pueden causar
pérdida de cobertura.

Métrica de las etiquetas: se usa el `rmsd` **ingenuo**, el mismo del contrato de
`MF-11-R1`, para que la comparación sea homogénea. `RC-F0-SYM` verificó que la
cobertura por complejo es idéntica bajo ambas métricas, así que la elección no afecta
a la condición (a).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MAT = [PROJECT_ROOT / "data" / "molflex_train_v2",
       PROJECT_ROOT / "data" / "molflex_valtest_v2"]
V2 = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-11-R2"
UMBRALES = (0.5, 0.75, 1.0, 1.5, 2.0)
UMBRAL_COBERTURA = 2.0


def _clusterizar(D: np.ndarray, U: float) -> List[List[int]]:
    """Diámetro controlado, greedy por identidad ascendente (contrato MF-11-R1)."""
    clusters: List[List[int]] = []
    for i in range(D.shape[0]):
        colocado = False
        for c in clusters:
            if D[i, c].max() <= U:      # distancia a TODOS los miembros
                c.append(i)
                colocado = True
                break
        if not colocado:
            clusters.append([i])
    return clusters


def _medoid(D: np.ndarray, c: List[int]) -> int:
    """Medoid geométrico; empate por identidad ascendente. Label-blind."""
    if len(c) == 1:
        return c[0]
    sub = D[np.ix_(c, c)]
    s = sub.sum(axis=1)
    return c[int(np.argmin(s))]


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "n_dataset": job["n_dataset"],
                           "n_otras_fuentes": job["n_otras"]}
    esperadas = {(k[0], k[1]): (v, s) for k, v, s in job["molflex"]}
    dirs = [d / pid / pid for d in MAT if (d / pid / pid / "index_map.json").exists()]
    if not dirs:
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    coords: List[List[List[float]]] = []
    etiquetas: List[float] = []      # rmsd al cristal: SOLO para evaluar
    for w in dirs:
        s2m = {int(s): int(m) for s, m in
               json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
        for f in sorted(w.glob("conf*.out.pdbqt")):
            stem = f.name[:-len(".pdbqt")]
            for midx, (sc, at) in enumerate(
                    mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace"))):
                clave = (stem, midx)
                if clave not in esperadas:
                    continue
                c = mf.coords_pose_a_por_mol(at, s2m)
                if not c or any(i not in c for i in pesados):
                    continue
                coords.append([list(c[i]) for i in pesados])
                etiquetas.append(esperadas[clave][0])
    n = len(coords)
    out["n_agrupables"] = n
    if n == 0:
        out["error"] = "SIN_EMPAREJAR"
        return out

    X = np.asarray(coords, dtype=np.float64)           # (n, atomos, 3)
    # RMSD pose-vs-pose sin alinear, acumulando ATOMO A ATOMO: el intermedio
    # (n, n, atomos, 3) llegaria a cientos de MB por complejo y con varios procesos
    # agotaria la memoria. Asi el pico es una sola matriz (n, n).
    acc = np.zeros((X.shape[0], X.shape[0]), dtype=np.float64)
    for k in range(X.shape[1]):
        d = X[:, k, :]
        acc += ((d[:, None, :] - d[None, :, :]) ** 2).sum(axis=2)
    D = np.sqrt(acc / X.shape[1])
    lab = np.asarray(etiquetas)

    # oraculo ANTES: incluye las poses de otras fuentes, que pasan sin agrupar
    mejor_antes = float(min([lab.min()] + ([job["mejor_otras"]] if job["mejor_otras"] is not None else [])))
    out["oraculo_antes"] = round(mejor_antes, 3)
    out["por_umbral"] = {}
    for U in UMBRALES:
        cl = _clusterizar(D, U)
        reps = [_medoid(D, c) for c in cl]
        mejor_desp = float(min([lab[reps].min()] +
                               ([job["mejor_otras"]] if job["mejor_otras"] is not None else [])))
        n_total_antes = n + job["n_otras"]
        n_total_desp = len(reps) + job["n_otras"]
        out["por_umbral"][str(U)] = {
            "n_clusters": len(cl),
            "n_poses_antes": n_total_antes,
            "n_poses_despues": n_total_desp,
            "reduccion": round(1 - n_total_desp / n_total_antes, 4),
            "oraculo_despues": round(mejor_desp, 3),
            "degradacion": round(mejor_desp - mejor_antes, 3),
            "cubierto_antes": bool(mejor_antes <= UMBRAL_COBERTURA),
            "cubierto_despues": bool(mejor_desp <= UMBRAL_COBERTURA),
        }
    return out


def _cargar(split: str):
    porpid = defaultdict(list)
    otras = defaultdict(list)
    for l in (V2 / f"poses_{split}.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if d.get("source") == "molflex":
            porpid[d["pid"]].append(((d["file_stem"], d["model_idx"]), d["rmsd"], d["vina_score"]))
        else:
            otras[d["pid"]].append(d["rmsd"])
    jobs = []
    for pid in sorted(set(porpid) | set(otras)):
        o = otras.get(pid, [])
        m = porpid.get(pid, [])
        jobs.append({"pid": pid, "molflex": m, "n_otras": len(o),
                     "mejor_otras": min(o) if o else None,
                     "n_dataset": len(m) + len(o)})
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-11-R2: re-derivar el umbral de dedup sobre v2")
    ap.add_argument("--split", default="train")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = _cargar(args.split)
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-11-R2] split={args.split} {len(jobs)} complejos, {args.workers} procesos",
          flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            u15 = r.get("por_umbral", {}).get("1.5", {})
            print(f"  [{i}/{len(jobs)}] {r['pid']} n={r.get('n_agrupables')} "
                  f"U1.5: red={u15.get('reduccion')} deg={u15.get('degradacion')} "
                  f"({round(time.time()-t0)}s)", flush=True)
            with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in filas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    tabla = {}
    for U in UMBRALES:
        u = str(U)
        g = [r["por_umbral"][u] for r in ok]
        antes = sum(x["n_poses_antes"] for x in g)
        desp = sum(x["n_poses_despues"] for x in g)
        perdidas = sum(1 for x in g if x["cubierto_antes"] and not x["cubierto_despues"])
        degs = [x["degradacion"] for x in g]
        tabla[u] = {
            "n_poses_antes": antes, "n_poses_despues": desp,
            "reduccion_global": round(1 - desp / antes, 4),
            "perdidas_de_cobertura": perdidas,
            "degradacion_mediana": round(median(degs), 4),
            "degradacion_p90": round(sorted(degs)[int(0.9 * (len(degs) - 1))], 4),
            "cumple_a_sin_perdidas": perdidas == 0,
            "cumple_b_degradacion": median(degs) <= 0.1,
            "cumple_c_reduccion": (1 - desp / antes) >= 0.10,
        }
        tabla[u]["cumple_las_tres"] = all(
            tabla[u][k] for k in ("cumple_a_sin_perdidas", "cumple_b_degradacion",
                                  "cumple_c_reduccion"))

    elegido = None
    for U in UMBRALES:            # el MAYOR que cumpla las tres
        if tabla[str(U)]["cumple_las_tres"]:
            elegido = U
    metrics = {
        "experiment_id": "MF-11-R2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "split": args.split,
        "contrato": "heredado literal de MF-11-R1; solo cambia el conjunto (v1 -> v2)",
        "alcance": ("solo poses molflex son agrupables; las de flexible_redock y ruta_a "
                    "pasan como singletons (opcion conservadora)"),
        "umbral_v1_mf11r1": 1.5,
        "n_complejos": len(filas), "n_ok": len(ok),
        "tabla_por_umbral": tabla,
        "umbral_elegido": elegido,
        "gates": {
            "G1_validez": {"criterio": ">=95% de complejos procesados",
                           "tasa": round(len(ok) / max(1, len(filas)), 4),
                           "pass": len(ok) >= 0.95 * len(filas)},
            "G2_seleccion": {"criterio": "existe un umbral que cumple (a) 0 perdidas, "
                                         "(b) degradacion mediana <=0.1 A, (c) reduccion >=10%",
                             "elegido": elegido, "pass": elegido is not None},
        },
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-11-R2] tabla:\n" + json.dumps(tabla, ensure_ascii=False, indent=1))
    print(f"[MF-11-R2] umbral elegido: {elegido} (v1 fue 1.5) | decision {metrics['decision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
