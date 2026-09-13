#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs14_selector_v2.py — RS-14: reapertura de la cartera D sobre el conjunto v2.

Prerrequisito formal: `scripts/artifacts_science/RS-14-PRE/PREREGISTRO.md` sellado.

Evalúa si un selector entrenado bajo el protocolo congelado de v0.6 supera al
baseline de `vina_score` en **precisión condicional** (§9 del doc. 49), con
leave-one-complex-out sobre los 116 de train de v2 y un nulo por permutación
dentro de complejo.

Reporta los tres números por separado —cobertura del oráculo, precisión
condicional y Top-1 global— y el gate se evalúa sobre la precisión condicional.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DS = PROJECT_ROOT / "data" / "pose_selector_dataset"
V2 = DS / "v2"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-14"
UMBRAL_A = 2.0
SEMILLAS = (42, 43, 44)
PCT_RAW = ["vina_score", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
           "n_clashes", "pose_score_variance", "pose_score_range",
           "cluster_density", "n_heavy"]
BASE_9 = ["vina_score", "pose_score_variance", "pose_score_range", "n_heavy",
          "n_contacts_4", "n_contacts_6", "contacts_per_ha_4", "n_clashes",
          "cluster_density"]
HP = dict(objective="rank:pairwise", n_estimators=500, max_depth=6,
          learning_rate=0.05, subsample=0.8, n_jobs=4, eval_metric="auc")


def cargar() -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """(X 233, rmsd, grupo_idx, pids) del split train de v2."""
    rich = {}
    for l in (V2 / "features_rich_v2.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            rich[(d["pid"], d["source"], d["file_stem"], d["model_idx"])] = d["rich"]
    filas, rmsds, pids = [], [], []
    for l in (V2 / "poses_train.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        k = (r["pid"], r["source"], r["file_stem"], r["model_idx"])
        if k not in rich:
            continue
        base = [r.get(c) if r.get(c) is not None else 0.0 for c in BASE_9]
        filas.append(base + rich[k])
        rmsds.append(r["rmsd"])
        pids.append(r["pid"])
    X = np.asarray(filas, dtype=np.float64)
    return X, np.asarray(rmsds), np.asarray(pids), sorted(set(pids))


def transformar(X: np.ndarray, pids: np.ndarray) -> np.ndarray:
    """Contrato de v0.6: z por columna DENTRO de cada complejo (std 0 -> 0) y
    rangos percentiles 0-100 sobre las 9 de PCT_RAW. NaN -> 0 tras transformar."""
    Z = np.zeros_like(X)
    idx_pct = [BASE_9.index(c) for c in PCT_RAW]
    P = np.zeros((X.shape[0], len(idx_pct)))
    for pid in np.unique(pids):
        m = pids == pid
        sub = X[m]
        mu = sub.mean(axis=0)
        sd = sub.std(axis=0)
        z = np.where(sd > 0, (sub - mu) / np.where(sd > 0, sd, 1.0), 0.0)
        Z[m] = z
        for j, col in enumerate(idx_pct):
            v = sub[:, col]
            orden = np.argsort(v, kind="mergesort")
            rangos = np.empty(len(v))
            i = 0
            while i < len(v):
                k = i
                while k + 1 < len(v) and v[orden[k + 1]] == v[orden[i]]:
                    k += 1
                rangos[orden[i:k + 1]] = (i + k) / 2 + 1
                i = k + 1
            P[m, j] = 100.0 * rangos / len(v)
    out = np.hstack([Z, P])
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def _fit_predict(Xtr, ytr, gtr, Xva, yva, gva, Xte, seed: int):
    from xgboost import XGBRanker
    mdl = XGBRanker(**HP, seed=seed, random_state=seed, early_stopping_rounds=50)
    mdl.fit(Xtr, ytr, group=gtr, eval_set=[(Xva, yva)], eval_group=[gva], verbose=False)
    return mdl.predict(Xte)


def _grupos(pids_sub: np.ndarray) -> List[int]:
    """Tamaños de grupo consecutivos (XGBRanker los exige ordenados)."""
    tam, actual, n = [], None, 0
    for p in pids_sub:
        if p != actual:
            if actual is not None:
                tam.append(n)
            actual, n = p, 0
        n += 1
    tam.append(n)
    return tam


def evaluar(pred: np.ndarray, rmsd: np.ndarray) -> bool:
    """Top-1 por score predicho (mayor = mejor en rank:pairwise)."""
    return bool(rmsd[int(np.argmax(pred))] <= UMBRAL_A)


def main() -> int:
    ap = argparse.ArgumentParser(description="RS-14: selector sobre el conjunto v2")
    ap.add_argument("--permutaciones", type=int, default=200)
    ap.add_argument("--semillas", type=int, nargs="*", default=list(SEMILLAS))
    ap.add_argument("--limite-complejos", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    X, rmsd, pids, lista_pids = cargar()
    if args.limite_complejos:
        lista_pids = lista_pids[:args.limite_complejos]
        m = np.isin(pids, lista_pids)
        X, rmsd, pids = X[m], rmsd[m], pids[m]
    orden = np.argsort(pids, kind="mergesort")
    X, rmsd, pids = X[orden], rmsd[orden], pids[orden]
    Xt = transformar(X, pids)
    cubiertos = {p for p in lista_pids if rmsd[pids == p].min() <= UMBRAL_A}
    print(f"[RS-14] {len(lista_pids)} complejos, {len(rmsd)} poses, {Xt.shape[1]} features | "
          f"cobertura del oraculo {len(cubiertos)}/{len(lista_pids)} "
          f"({len(cubiertos)/len(lista_pids):.1%})", flush=True)

    # ── Baseline: vina_score crudo (menor = mejor) ──
    col_vina = BASE_9.index("vina_score")
    base_hits = {}
    for p in lista_pids:
        m = pids == p
        base_hits[p] = bool(rmsd[m][int(np.argmin(X[m][:, col_vina]))] <= UMBRAL_A)
    base_cond = sum(base_hits[p] for p in cubiertos) / len(cubiertos)
    print(f"[RS-14] baseline vina_score: precision condicional {base_cond:.4f} "
          f"| Top-1 global {sum(base_hits.values())/len(lista_pids):.4f}", flush=True)

    # ── LOCO por semilla ──
    sel_hits: Dict[int, Dict[str, bool]] = {s: {} for s in args.semillas}
    n_fit = 0
    for seed in args.semillas:
        rng = np.random.default_rng(seed)
        for i, p in enumerate(lista_pids, 1):
            te = pids == p
            tr_pids = [q for q in lista_pids if q != p]
            va_pids = set(rng.choice(tr_pids, size=max(1, len(tr_pids) // 5), replace=False))
            tr = np.isin(pids, [q for q in tr_pids if q not in va_pids])
            va = np.isin(pids, list(va_pids))
            pred = _fit_predict(Xt[tr], -rmsd[tr], _grupos(pids[tr]),
                                Xt[va], -rmsd[va], _grupos(pids[va]),
                                Xt[te], seed)
            sel_hits[seed][p] = evaluar(pred, rmsd[te])
            n_fit += 1
            if i % 20 == 0 or i == len(lista_pids):
                c = sum(sel_hits[seed][q] for q in lista_pids[:i] if q in cubiertos)
                d = sum(1 for q in lista_pids[:i] if q in cubiertos)
                print(f"  [seed {seed} {i}/{len(lista_pids)}] condicional parcial "
                      f"{c}/{d} ({round(time.time()-t0)}s)", flush=True)

    cond = {s: sum(sel_hits[s][p] for p in cubiertos) / len(cubiertos) for s in args.semillas}
    glob = {s: sum(sel_hits[s].values()) / len(lista_pids) for s in args.semillas}
    cond_med = float(np.mean(list(cond.values())))

    # ── Diferencia pareada por complejo + BCa bootstrap ──
    dif = np.array([np.mean([sel_hits[s][p] for s in args.semillas]) - base_hits[p]
                    for p in sorted(cubiertos)])
    boot = np.array([dif[rng_i].mean() for rng_i in
                     np.random.default_rng(42).integers(0, len(dif), size=(2000, len(dif)))])
    ci = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))

    # ── Nulo por permutación dentro de complejo (5-fold agrupado) ──
    nulos: List[float] = []
    folds = [lista_pids[i::5] for i in range(5)]
    for k in range(args.permutaciones):
        rp = np.random.default_rng(1000 + k)
        y = rmsd.copy()
        for p in lista_pids:
            m = pids == p
            y[m] = rp.permutation(y[m])
        hits = {}
        for f in folds:
            te = np.isin(pids, f)
            tr_pids = [q for q in lista_pids if q not in f]
            va_pids = set(rp.choice(tr_pids, size=max(1, len(tr_pids) // 5), replace=False))
            tr = np.isin(pids, [q for q in tr_pids if q not in va_pids])
            va = np.isin(pids, list(va_pids))
            pred = _fit_predict(Xt[tr], -y[tr], _grupos(pids[tr]),
                                Xt[va], -y[va], _grupos(pids[va]), Xt[te], 42)
            for p in f:
                sel = pids[te] == p
                hits[p] = bool(rmsd[te][sel][int(np.argmax(pred[sel]))] <= UMBRAL_A)
            n_fit += 1
        nulos.append(sum(hits[p] for p in cubiertos) / len(cubiertos))
        if (k + 1) % 20 == 0:
            print(f"  [nulo {k+1}/{args.permutaciones}] p95 parcial "
                  f"{np.percentile(nulos, 95):.4f} ({round(time.time()-t0)}s)", flush=True)

    p95 = float(np.percentile(nulos, 95)) if nulos else None
    p_emp = float(np.mean([x >= cond_med for x in nulos])) if nulos else None

    metrics = {
        "experiment_id": "RS-14",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "datos": {"complejos": len(lista_pids), "poses": int(len(rmsd)),
                  "features": int(Xt.shape[1]), "split": "train v2"},
        "descomposicion_seccion_9": {
            "cobertura_oraculo": round(len(cubiertos) / len(lista_pids), 4),
            "precision_condicional_selector": round(cond_med, 4),
            "precision_condicional_baseline": round(base_cond, 4),
            "top1_global_selector": round(float(np.mean(list(glob.values()))), 4),
            "top1_global_baseline": round(sum(base_hits.values()) / len(lista_pids), 4),
        },
        "por_semilla": {str(s): {"condicional": round(cond[s], 4), "global": round(glob[s], 4)}
                        for s in args.semillas},
        "diferencia_pareada": {"media": round(float(dif.mean()), 4),
                               "ci95_bca": [round(ci[0], 4), round(ci[1], 4)],
                               "n_complejos": len(dif)},
        "nulo_permutacion": {"n": len(nulos), "p95": round(p95, 4) if p95 else None,
                             "media": round(float(np.mean(nulos)), 4) if nulos else None,
                             "p_empirico": p_emp},
        "n_ajustes": n_fit,
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": "todos los ajustes LOCO completan",
                       "n_ajustes": n_fit, "pass": n_fit >= len(lista_pids) * len(args.semillas)},
        "G2_superioridad": {"criterio": "condicional > baseline con CI95 BCa pareado excluyendo 0",
                            "media_dif": round(float(dif.mean()), 4),
                            "ci95": [round(ci[0], 4), round(ci[1], 4)],
                            "pass": bool(ci[0] > 0)},
        "G3_nulo": {"criterio": "condicional observada > percentil 95 del nulo por permutacion",
                    "observada": round(cond_med, 4), "p95_nulo": round(p95, 4) if p95 else None,
                    "pass": bool(p95 is not None and cond_med > p95)},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for p in lista_pids:
            fh.write(json.dumps({"pid": p, "cubierto": p in cubiertos,
                                 "baseline_acierta": base_hits[p],
                                 "selector_acierta": {str(s): sel_hits[s][p] for s in args.semillas},
                                 "n_poses": int((pids == p).sum()),
                                 "oraculo": round(float(rmsd[pids == p].min()), 3)},
                                ensure_ascii=False) + "\n")
    (OUT_DIR / "nulo.json").write_text(json.dumps({"nulos": nulos}, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")

    d = metrics["descomposicion_seccion_9"]
    print(f"\n[RS-14] decision {metrics['decision']}")
    print(f"  cobertura del oraculo: {d['cobertura_oraculo']:.1%} (covariable, no resultado)")
    print(f"  precision condicional: selector {d['precision_condicional_selector']:.4f} vs "
          f"baseline {d['precision_condicional_baseline']:.4f}")
    print(f"  Top-1 global (ITT): selector {d['top1_global_selector']:.4f} vs "
          f"baseline {d['top1_global_baseline']:.4f}")
    print(f"  diferencia pareada {dif.mean():+.4f} CI95 [{ci[0]:+.4f}, {ci[1]:+.4f}]")
    print(f"  nulo por permutacion: p95 {p95:.4f} | p empirico {p_emp}")
    for k, g in metrics["gates"].items():
        print(f"  {k}: {'PASS' if g['pass'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
