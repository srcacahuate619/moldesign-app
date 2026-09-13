# -*- coding: utf-8 -*-
"""
ruta_c_fase1_baseline.py — Ruta C, Fase 1 (docs/42_RUTA_C_PROTOCOLO.md).

1) Carga los tres JSONL del dataset pose-selector.
2) Baseline honesto de Vina: por complejo, la pose con MENOR vina_score
   (empates → primera en orden canónico). Reporta top-1 crystal-like rate
   (RMSD ≤ 2.0 A), RMSD mediano de la pose seleccionada y cobertura
   (% complejos con al menos una pose ≤ 2.0 A) en train/val/test.
3) v0 = XGBRanker (rank:pairwise, grupos por complejo) con features baratas:
   vina_score como CONTEXTO (C1: nunca objetivo) + features poblacionales
   (C4). Relevancia = -rmsd. NaN → mediana del train.
4) Evalúa v0 en val y test: top-1, RMSD mediano, Spearman por complejo.
5) Gate G1 (C6): v0 top-1 en TEST > Vina top-1 en TEST.
6) Escribe scripts/artifacts_ruta_c_fase1.json (incremental: el archivo se
   actualiza tras cada etapa para no perder trabajo si algo cae).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1.json"
UMBRAL_POSITIVA = 2.0

FEATURES = ["vina_score", "pose_score_variance", "pose_score_range", "n_heavy",
            "n_contacts_4", "n_contacts_6", "contacts_per_ha_4", "n_clashes",
            "cluster_density"]

PARAMS_V0 = {
    "objective": "rank:pairwise",
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "early_stopping_rounds": 50,
    "n_jobs": 4,
    "random_state": 42,
}


def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_artefacto(art: dict, etapa: str) -> None:
    """Escritura incremental: el artefacto se pisa tras cada etapa."""
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    import os
    os.replace(tmp, ARTIFACTS)


def cargar_split(nombre: str) -> list[dict]:
    registros: list[dict] = []
    path = DATASET_DIR / f"poses_{nombre}.jsonl"
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registros.append(json.loads(linea))
    # Orden canónico determinista: pid, fuente, stem, model_idx.
    registros.sort(key=lambda r: (r["pid"], r["source"], r["file_stem"],
                                  r["model_idx"]))
    return registros


def baseline_vina(registros: list[dict]) -> dict:
    """Por complejo: pose de menor vina_score (empates → primera en orden).
    Complejos sin ningún score → excluidos del baseline (contados)."""
    por_pid: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_pid[r["pid"]].append(r)
    seleccionados: list[float] = []
    cobertura_pos = 0
    n_con_score = 0
    for pid in sorted(por_pid):
        poses = por_pid[pid]
        con_score = [(i, r) for i, r in enumerate(poses)
                     if r.get("vina_score") is not None]
        if not con_score:
            continue
        n_con_score += 1
        mejor = min(con_score, key=lambda ir: (ir[1]["vina_score"], ir[0]))[1]
        seleccionados.append(mejor["rmsd"])
        if any(r["rmsd"] <= UMBRAL_POSITIVA for r in poses):
            cobertura_pos += 1
    if not seleccionados:
        return {"top1_rate": None, "mediana_rmsd": None, "cobertura_pct": None,
                "n_complejos": len(por_pid), "n_con_score": 0}
    return {
        "top1_rate": round(float(np.mean([s <= UMBRAL_POSITIVA for s in seleccionados])), 4),
        "mediana_rmsd": round(float(np.median(seleccionados)), 3),
        "cobertura_pct": round(100.0 * cobertura_pos / n_con_score, 2),
        "n_complejos": len(por_pid),
        "n_con_score": n_con_score,
    }


def preparar_matrices(registros: list[dict], mediana_train: dict | None):
    """X (n, F) e y = -rmsd, con grupos por complejo en el MISMO orden de
    filas. NaN → mediana del train (o mediana local si no hay train)."""
    X = np.array([[r.get(f) for f in FEATURES] for r in registros],
                 dtype=np.float64)
    if mediana_train is not None:
        med = mediana_train
    else:
        med = {f: float(np.nanmedian(X[:, i])) if np.any(~np.isnan(X[:, i])) else 0.0
               for i, f in enumerate(FEATURES)}
    for i in range(X.shape[1]):
        col = X[:, i]
        if np.isnan(med[FEATURES[i]]):
            med[FEATURES[i]] = 0.0
        col[np.isnan(col)] = med[FEATURES[i]]
    y = -np.array([r["rmsd"] for r in registros], dtype=np.float64)
    grupos: list[int] = []
    pids_orden = []
    n = 0
    for r in registros:
        if not pids_orden or r["pid"] != pids_orden[-1]:
            if pids_orden:
                grupos.append(n)
                n = 0
            pids_orden.append(r["pid"])
        n += 1
    if n:
        grupos.append(n)
    return X, y, grupos, pids_orden, med


def evaluar_v0(modelo, X: np.ndarray, registros: list[dict],
               pids_orden: list[str]) -> dict:
    """Top-1 por complejo con argmax del score predicho, RMSD mediano y
    Spearman promedio por complejo (≥ 2 poses, arreglos no constantes)."""
    pred = modelo.predict(X)
    por_pid: dict[str, list[tuple]] = defaultdict(list)
    for r, p in zip(registros, pred):
        por_pid[r["pid"]].append((r, float(p)))
    from scipy.stats import spearmanr
    top1_ok = 0
    rmsds_sel: list[float] = []
    spearmans_neg: list[float] = []
    spearmans_rel: list[float] = []
    n_spearman = 0
    for pid in pids_orden:
        filas = por_pid[pid]
        mejor = max(filas, key=lambda rp: rp[1])[0]
        rmsds_sel.append(mejor["rmsd"])
        if mejor["rmsd"] <= UMBRAL_POSITIVA:
            top1_ok += 1
        if len(filas) >= 2:
            ps = np.array([p for _, p in filas])
            rs = np.array([r["rmsd"] for r, _ in filas])
            if np.std(ps) > 1e-12 and np.std(rs) > 1e-12:
                sp_neg = spearmanr(ps, rs).correlation
                spearmans_neg.append(float(sp_neg) if sp_neg is not None and not np.isnan(sp_neg) else 0.0)
                spearmans_rel.append(-float(spearmans_neg[-1]))
                n_spearman += 1
    n_pids = len(pids_orden)
    return {
        "top1_rate": round(top1_ok / n_pids, 4),
        "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
        "spearman_pred_vs_rmsd_media": (round(float(np.mean(spearmans_neg)), 4)
                                        if spearmans_neg else None),
        "spearman_pred_vs_relevancia_media": (round(float(np.mean(spearmans_rel)), 4)
                                              if spearmans_rel else None),
        "n_complejos": n_pids,
        "n_complejos_spearman": n_spearman,
    }


def main() -> None:
    configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 1: baseline Vina + v0 XGBoost (docs/42) ==")

    art: dict = {"generated_at": ahora_iso(),
                 "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
                 "umbral_pose_positiva_angstrom": UMBRAL_POSITIVA,
                 "gate_G1_criterio": "v0_top1_test > vina_top1_test"}
    manifest = DATASET_DIR / "manifest.json"
    if manifest.exists():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        art["dataset"] = {
            "split_method": m.get("split_method"),
            "test_pids_sha256": m.get("test_pids_sha256"),
            "sha256": m.get("sha256", {}),
            "conteos": m.get("conteos", {}),
        }

    splits = {nombre: cargar_split(nombre)
              for nombre in ("train", "val", "test")}
    for nombre, regs in splits.items():
        print(f"  {nombre}: {len(regs)} registros, "
              f"{len({r['pid'] for r in regs})} complejos")

    # ── 2) Baseline Vina ──
    art["vina_baseline"] = {}
    for nombre in ("train", "val", "test"):
        art["vina_baseline"][nombre] = baseline_vina(splits[nombre])
    guardar_artefacto(art, "baseline_vina")
    print("  Vina baseline:",
          {k: v["top1_rate"] for k, v in art["vina_baseline"].items()})

    # ── 3) v0 XGBRanker ──
    X_train, y_train, g_train, pids_train, med = preparar_matrices(
        splits["train"], None)
    X_val, y_val, g_val, pids_val, _ = preparar_matrices(
        splits["val"], med)
    X_test, y_test, g_test, pids_test, _ = preparar_matrices(
        splits["test"], med)
    art["v0"] = {
        "hiperparametros": PARAMS_V0,
        "features": FEATURES,
        "relevancia": "-rmsd",
        "imputacion_nan": "mediana_train",
    }
    guardar_artefacto(art, "matrices_listas")

    from xgboost import XGBRanker
    # La métrica de early-stopping debe aceptar labels flotantes continuos
    # (-rmsd). ndcg/map exigen labels enteros (relevancia por grados) y
    # revientan; se intenta 'auc' (rank-AUC por grupo) y se degrada a 'rmse'.
    metricas = ["auc", "rmse"]
    modelo = None
    for metrica in metricas:
        try:
            modelo = XGBRanker(eval_metric=metrica, **PARAMS_V0)
            modelo.fit(X_train, y_train, group=g_train,
                       eval_set=[(X_val, y_val)], eval_group=[g_val],
                       verbose=False)
            break
        except Exception as e:
            print(f"  metric '{metrica}' fallo: {type(e).__name__}; probando siguiente")
            modelo = None
    if modelo is None:
        raise RuntimeError("ninguna metrica de early-stopping funciono")
    art["v0"]["eval_metric"] = metrica
    art["v0"]["best_iteration"] = int(getattr(modelo, "best_iteration", -1))
    art["v0"]["best_score"] = (float(modelo.best_score) if modelo.best_score else None)
    print(f"  v0 entrenado (best_iteration={art['v0']['best_iteration']})")
    guardar_artefacto(art, "v0_entrenado")

    # ── 4) Evaluación ──
    art["v0"]["val"] = evaluar_v0(modelo, X_val, splits["val"], pids_val)
    art["v0"]["test"] = evaluar_v0(modelo, X_test, splits["test"], pids_test)
    print(f"  v0 val:  top1={art['v0']['val']['top1_rate']} "
          f"mediana={art['v0']['val']['mediana_rmsd']}")
    print(f"  v0 test: top1={art['v0']['test']['top1_rate']} "
          f"mediana={art['v0']['test']['mediana_rmsd']}")

    # ── 5) Gate G1 ──
    vina_test = art["vina_baseline"]["test"]["top1_rate"]
    v0_test = art["v0"]["test"]["top1_rate"]
    pasa = v0_test > vina_test
    art["gate_G1"] = {
        "vina_top1_test": vina_test,
        "v0_top1_test": v0_test,
        "delta": round(v0_test - vina_test, 4),
        "resultado": "PASS" if pasa else "FAIL",
        "delta_val": round(art["v0"]["val"]["top1_rate"]
                           - art["vina_baseline"]["val"]["top1_rate"], 4),
    }
    if not pasa:
        art["gate_G1"]["remediacion_protocolo"] = (
            "docs/42 seccion 5 Fase 2: revisar features/labels antes de "
            "invertir en el GNN (C6); riesgo pre-registrado: score de Vina "
            "dominante en features (seccion 10, R-RC1)")
    print(f"  Gate G1: {art['gate_G1']['resultado']} "
          f"(v0 {v0_test} vs Vina {vina_test}, delta {art['gate_G1']['delta']})")

    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print(f"  artefacto: {ARTIFACTS}")


if __name__ == "__main__":
    main()
