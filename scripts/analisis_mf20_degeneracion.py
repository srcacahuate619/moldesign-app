#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf20_degeneracion.py — MF-20: ¿una sola causa explica los negativos de C y D?

**Hipótesis nueva.** Las carteras C y D han acumulado negativos por vías que parecían
independientes:

  * **C (colocación)**: el buscador no encuentra la pose nativa aunque la función la
    prefiera (`MF-13`) y su cuenca exista (`MF-14`);
  * **D (selección)**: el selector no supera a `vina_score` ni con el denominador
    corregido ni con las etiquetas corregidas (`RS-14`, `RS-14-R1`).

La hipótesis es que **ambos son la misma cosa medida en dos sitios**: si el paisaje de
puntuación es **degenerado** —muchas poses geométricamente distintas empatadas cerca
del óptimo— entonces (a) la búsqueda no tiene a dónde converger y (b) no existe
información que un selector pueda explotar, porque las candidatas son indistinguibles
para la función que las genera.

Es una hipótesis **falsable y correlacional**: si la degeneración no separa nada,
queda descartada y las dos carteras fallan por causas distintas.

Qué se mide
-----------
Por complejo, sobre las poses del conjunto v2:

  1. se agrupan las poses en **modos geométricamente distintos** con el mismo
     clustering de diámetro controlado de `MF-11-R1`/`MF-11-R2` a 2.0 Å;
  2. por modo se toma su **mejor score**;
  3. **degeneración(Δ)** = número de modos distintos cuyo mejor score está a Δ o menos
     del mejor score global, para Δ ∈ {0.5, 1.0, 2.0} kcal/mol.

Luego se contrasta esa degeneración contra los desenlaces ya medidos: cobertura del
oráculo, acierto del top-1, y el embudo de `MF-15-EXT`.

Limitación declarada de antemano
--------------------------------
n=48 y correlacional. No se afirma causalidad ni se deriva umbral operativo. Y la
degeneración se mide con la MISMA función cuyo fallo se investiga, así que no puede
distinguir «el paisaje es degenerado» de «la función no resuelve»: son la misma
afirmación vista de dos lados, y así se reporta.
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
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MAT = [PROJECT_ROOT / "data" / "molflex_train_v2",
       PROJECT_ROOT / "data" / "molflex_valtest_v2"]
V2 = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-20"
U_CLUSTER = 2.0
DELTAS = (0.5, 1.0, 2.0)
UMBRAL_A = 2.0


def _clusterizar(D: np.ndarray, U: float) -> List[List[int]]:
    clusters: List[List[int]] = []
    for i in range(D.shape[0]):
        colocado = False
        for c in clusters:
            if D[i, c].max() <= U:
                c.append(i)
                colocado = True
                break
        if not colocado:
            clusters.append([i])
    return clusters


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"]}
    esperadas = {(k[0], k[1]): (r, s) for k, r, s in job["poses"]}
    dirs = [d / pid / pid for d in MAT if (d / pid / pid / "index_map.json").exists()]
    if not dirs:
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    coords, rms, scores = [], [], []
    for w in dirs:
        s2m = {int(s): int(m) for s, m in
               json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
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
    if n < 10:
        out["error"] = "POCAS_POSES"
        return out

    X = np.asarray(coords, dtype=np.float64)
    acc = np.zeros((n, n))
    for k in range(X.shape[1]):
        d = X[:, k, :]
        acc += ((d[:, None, :] - d[None, :, :]) ** 2).sum(axis=2)
    D = np.sqrt(acc / X.shape[1])

    cl = _clusterizar(D, U_CLUSTER)
    sc = np.asarray(scores)
    rm = np.asarray(rms)
    mejor_por_modo = [float(sc[c].min()) for c in cl]
    rmsd_por_modo = [float(rm[c][int(np.argmin(sc[c]))]) for c in cl]
    global_best = min(mejor_por_modo)
    out["n_modos"] = len(cl)
    out["mejor_score"] = round(global_best, 3)
    for dl in DELTAS:
        k = sum(1 for m in mejor_por_modo if m <= global_best + dl)
        out[f"degeneracion_{dl}"] = k
        # de esos modos empatados, cuantos son realmente buenos (<=2 A)
        buenos = sum(1 for m, r in zip(mejor_por_modo, rmsd_por_modo)
                     if m <= global_best + dl and r <= UMBRAL_A)
        out[f"modos_buenos_entre_empatados_{dl}"] = buenos
    out["cubierto"] = bool(rm.min() <= UMBRAL_A)
    out["top1_acierta"] = bool(rm[int(np.argmin(sc))] <= UMBRAL_A)
    out["oraculo"] = round(float(rm.min()), 3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-20: degeneracion del paisaje de puntuacion")
    ap.add_argument("--split", default="train")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    coh = json.loads((ART / "MF-02F" / "cohorte.json").read_text(encoding="utf-8"))
    est = {p: "COLOCACION" for p in coh["cohorte_colocacion"]}
    est.update({p: "CONTROL" for p in coh["control_cubiertos"]})

    por = defaultdict(list)
    for l in (V2 / f"poses_{args.split}.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            if d.get("source") == "molflex":
                por[d["pid"]].append(((d["file_stem"], d["model_idx"]), d["rmsd"], d["vina_score"]))
    jobs = [{"pid": p, "estrato": est.get(p, "RESTO"), "poses": v} for p, v in sorted(por.items())]
    print(f"[MF-20] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            if i % 20 == 0:
                print(f"  [{i}/{len(jobs)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / f"per_complex_{args.split}.jsonl", "w", encoding="utf-8",
              newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    # contraste principal: degeneracion segun desenlace
    grupos: Dict[str, Any] = {}
    for etiq, cond in (("CUBIERTO", True), ("NO_CUBIERTO", False)):
        g = [r for r in ok if r["cubierto"] is cond]
        if not g:
            continue
        grupos[etiq] = {"n": len(g), "n_modos_mediano": int(median(r["n_modos"] for r in g))}
        for dl in DELTAS:
            grupos[etiq][f"degeneracion_{dl}_mediana"] = int(median(r[f"degeneracion_{dl}"] for r in g))
    for etiq, cond in (("TOP1_ACIERTA", True), ("TOP1_FALLA", False)):
        g = [r for r in ok if r["cubierto"] and r["top1_acierta"] is cond]
        if not g:
            continue
        grupos[etiq] = {"n": len(g), "n_modos_mediano": int(median(r["n_modos"] for r in g))}
        for dl in DELTAS:
            grupos[etiq][f"degeneracion_{dl}_mediana"] = int(median(r[f"degeneracion_{dl}"] for r in g))
    por_est = {}
    for e in ("COLOCACION", "CONTROL", "RESTO"):
        g = [r for r in ok if r["estrato"] == e]
        if g:
            por_est[e] = {"n": len(g),
                          "n_modos_mediano": int(median(r["n_modos"] for r in g)),
                          "degeneracion_1.0_mediana": int(median(r["degeneracion_1.0"] for r in g)),
                          "modos_buenos_entre_empatados_1.0_mediana":
                              int(median(r["modos_buenos_entre_empatados_1.0"] for r in g))}
    metrics = {
        "experiment_id": "MF-20",
        "tipo": "medicion correlacional (hipotesis nueva)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "split": args.split,
        "definicion": (f"modos = clusters de diametro <= {U_CLUSTER} A (contrato MF-11-R1); "
                       "degeneracion(D) = numero de modos cuyo mejor score esta a D o menos "
                       "del mejor score global"),
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_desenlace": grupos,
        "por_estrato": por_est,
        "limitacion": ("n=48/116 y correlacional. La degeneracion se mide con la MISMA funcion "
                       "cuyo fallo se investiga, asi que no distingue 'el paisaje es degenerado' "
                       "de 'la funcion no resuelve': son la misma afirmacion vista de dos lados."),
    }
    (OUT_DIR / f"metrics_{args.split}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"por_desenlace": grupos, "por_estrato": por_est},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
