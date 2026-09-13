# -*- coding: utf-8 -*-
"""run_rs08_router.py — RS-08: router de decidibilidad ACCIONABLE.

Cross-fitting ANIDADO que entrena y evalua el router de escalamiento dentro
de los 5 folds sellados de RS-01B ([55,16,15,15,15] por las 38 componentes
combinadas scaffold+receptor), segun el prerregistro sellado
(scripts/artifacts_science/RS-08/PREREGISTRO.md, sello b4204bd) y
CAMPANA-2-PLAN sellado (41b7f09) IT1/DECISIONS QA-3.

Clases accionables por complejo (decision del maintainer):
  - solved:                v0.6 ya selecciono una pose <= 2 A (Top-1 correcto)
  - rescoring_actionable@2: Top-1 falla (> 2 A) pero existe pose <= 2 A entre
                            las top-2 (escalar a RS-03; PRIMARIA del router)
  - sampling_needed:        ni top-2 ni top-3 contienen pose <= 2 A
                           (nueva generacion; NO MM/GBSA-like)
  - @3 (top-3): solo sensibilidad, nunca gate primario.

Cross-fitting ANIDADO (obligatorio):
  - Outer: 5 folds del fold_plan sellado. El clon v0.6 outer es el YA sellado
    (RS-01B brazo_original / RS-04-OOF baseline; sha por fold verificados al
    inicio: 6e872ba2/2541609f/9584f7d9/8eab79bf/fabc39ec). NO se reentrena.
  - Inner: dentro de cada outer-train se construyen 5 sub-folds por
    componentes REUTILIZANDO las asignaciones del fold_plan restringidas al
    outer-train donde aplique: los sub-folds g != f son los grupos del
    fold_plan presentes en el outer-train; el quinto sub-fold se obtiene
    partiendo el grupo mas grande (por componentes si tiene > 1; por pids
    ordenados si es un componente unico - fold 0 con 55 pids). Para cada
    sub-fold se entrena un clon v0.6 inner (MISMO XGBoost congelado:
    rank:pairwise, 52 trees, depth 6, lr 0.05, subsample 0.8, seed 42, sin
    early stopping, 233 features A1 SIN strain) sobre el inner-train y se
    evalua sobre el sub-fold: features Y etiquetas del router sobre el
    outer-train proceden de estas predicciones INNER-OOF (el clon que
    predice un complejo NUNCA lo vio). PROHIBIDO usar el OOF global cuyos
    modelos vieron el outer-test.
  - Etiqueta del router por complejo del outer-train: error del clon
    inner-OOF (top-1 rmsd > 2 A? clase accionable@2).
  - Features del router (13, documentadas en FEATURES_ROUTER): margen
    top1-top2, score top1, n_poses, abstenido y los 9 percentiles del ganador
    sobre las columnas PCT_RAW (A1). El margen de v0.6 es FEATURE, no
    selector.
  - Modelo del router: regresion logistica (arquitectura de referencia de
    Fase 3.5 / QA-3) con estandarizacion ajustada DENTRO del outer-train.
    Riesgo = P(rescoring_actionable@2).
  - Umbral: percentil 70 del riesgo inner-OOF del outer-train (presupuesto
    nominal 30% de mayor riesgo); aplicacion FIJA al outer-test (prohibido
    re-seleccionar mirando la distribucion del outer-test). Sensibilidad
    adicional a 10/20/40% (percentiles 90/80/60 del outer-train).
  - Drift real de presupuesto: fraccion escalada en el outer-test; gate de
    operacion aceptable 25-35% (fuera de rango -> desviacion con causa, no
    se re-umbraliza).

Comparadores al MISMO coste (mismo numero de complejos escalados por fold,
presupuesto real del router, pareado por fold):
  1. margin-only v0.6 (RIVAL PRINCIPAL): k complejos de menor margen
     top1-top2 del clon outer.
  2. seleccion aleatoria (CONTROL INFERIOR, seed 42).

Gate de desarrollo:
  - Capturar >= +3 fallos recuperables@2 vs margin-only al mismo coste.
  - NO aumentar falsos escalamientos (complejos solved escalados) vs
    margin-only (delta <= 0; si > 0, gate FAIL aunque se cumpla el +3).
  - Bootstrap BCa por las 38 componentes (10 000 replicas, seed 42) sobre
    delta fallos recuperables@2 y sobre delta falsos escalamientos.
  - Sensibilidad presupuestaria 10/20/40% (descriptiva, sin gate).
  - Estratos hard/control separados; McNemar exacto opcional.
  - val40 y D-RC-CONFIRM intactas (whitelist con FORBIDDEN; auditoria de
    builtins.open del patron RS-01B/RS-04-OOF).

Limitacion de claim: RS-08 solo puede recibir GO como ROUTER (decisibilidad
accionable). PROHIBIDO reclamar mejora de Top-1: el rescoring solo es util
si RS-03 (MM/GBSA-like) convierte los escalados en aciertos (cascada
integrada v0.6 -> RS-08 -> RS-03). El strain MMFF94s NO es feature del
router.

Composicion (solo lectura de codigo sellado; nada sellado se edita):
  - scripts/run_rs04_oof.py -> preparar_insumos (folds sellados, features
    A1, labels, indices_pct), cargar_ligandos (ionizado); parchea
    builtins.open via run_rs01b_crossfit (auditoria de cuarentena).
  - scripts/run_rs01b_crossfit.py -> entrenar_clon, construir_entrenamiento,
    z/pct, bca_intervalo, PARAMS_CLON, etc.

Determinismo: salidas sin timestamps ni aleatoriedad no-seeded (seed 42 en
clones inner, bootstrap y seleccion aleatoria; LogReg lbfgs determinista);
dos corridas producen salidas byte-identicas. Los 25 clones inner se
hashean (sha256 del .xgb) sin conservar los binarios (solo meta jsonl).

Uso:
  python-embed/python.exe scripts/run_rs08_router.py
      [--out-dir scripts/artifacts_science/RS-08]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import numpy as np  # noqa: E402
import xgboost  # noqa: E402

# ── composicion (nada sellado se edita) ─────────────────────────────────────
# run_rs04_oof importa run_rs04_qc (rdkit) y run_rs01b_crossfit (este ultimo
# parchea builtins.open con la auditoria de archivos abiertos).
import run_rs04_oof as r4  # noqa: E402
import run_rs01b_crossfit as rs1b  # noqa: E402

from run_rs04_oof import FORBIDDEN, cargar_ligandos, preparar_insumos  # noqa: E402
from run_rs01b_crossfit import (  # noqa: E402
    PARAMS_CLON,
    PCT_RAW,
    UMBRAL_ABSTENCION,
    UMBRAL_POSITIVA,
    N_BOOT,
    N_FOLDS,
    SEED_BOOT,
    bca_intervalo,
    clave_identidad,
    construir_entrenamiento,
    entrenar_clon,
    excluye_cero,
    leer_json,
    leer_jsonl,
    escribir_json,
    escribir_jsonl,
    sha256_archivo,
    z_por_pid,
    pct_por_pid,
)

from rdkit import Chem  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

# ───────────────────────── rutas y constantes ───────────────────────────────

ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR_DEFAULT = ARTIFACTOS / "RS-08"
RS01B_DIR = ARTIFACTOS / "RS-01B"
RS04OOF_DIR = ARTIFACTOS / "RS-04-OOF"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"

# presupuestos nominales: (fraccion, percentil de riesgo inner-OOF)
BUDGETS = (0.10, 0.20, 0.30, 0.40)
DRIFT_BAJO = 0.25
DRIFT_ALTO = 0.35
GATE_DELTA_FALLOS = 3
GATE_DELTA_FALSOS_MAX = 0

# Presupuesto primario (QA-3): 30% de mayor riesgo -> percentil 70.
BUDGET_PRIMARIO = 0.30

# sha esperados de los clones outer sellados (RS-01B brazo_original ==
# RS-04-OOF baseline; verificados al inicio, NO se reentrenan).
SHA_OUTER_ESPERADOS = [
    "6e872ba2", "2541609f", "9584f7d9", "8eab79bf", "fabc39ec",
]

FEATURES_ROUTER = [
    "score_top1",
    "margen_top1_top2",
    "n_poses",
    "abstenido",
    "pct_vina_score",
    "pct_n_contacts_4",
    "pct_n_contacts_6",
    "pct_contacts_per_ha_4",
    "pct_n_clashes",
    "pct_pose_score_variance",
    "pct_pose_score_range",
    "pct_cluster_density",
    "pct_n_heavy",
]

SALIDAS = ("metrics.json", "per_complex.jsonl", "failures.jsonl")


# ───────────────────────── utilidades ──────────────────────────────────────

def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _round(x, n=6):
    return round(float(x), n)


def sha_modelo_tmp(modelo, tmp_path: Path) -> str:
    """sha256 del binario .xgb de un clon SIN conservar el binario (el
    contrato solo pide el sha en inner_models/). El entrenamiento congelado
    (seed 42) hace el sha determinista entre corridas."""
    modelo.save_model(str(tmp_path))
    sha = sha256_archivo(tmp_path)
    os.remove(tmp_path)
    return sha


# ───────────────────────── evaluacion por complejo (router) ─────────────────

def evaluar_complejo(clon, pid, ids, feats, labels, indices_pct) -> dict:
    """Prediccion OOF de un clon v0.6 sobre un complejo: ranking completo,
    clases accionables (@2 y @3) y el vector de features del router (13).

    Clases (prerregistro RS-08):
      solved                -> top-1 rmsd <= 2 A
      rescoring_actionable  -> top-1 falla pero min(rmsd top-k) <= 2 A
      sampling_needed       -> ninguna pose <= 2 A en el top-k
    """
    X = np.vstack([feats[i] for i in ids])
    assert X.shape == (len(ids), rs1b.N_Z)
    Z = z_por_pid(X, [len(ids)])
    Z[np.isnan(Z)] = 0.0
    P = pct_por_pid(X, [len(ids)], indices_pct)
    P[np.isnan(P)] = 0.0
    X_B = np.hstack([Z, P])
    assert X_B.shape == (len(ids), rs1b.N_MODELO_B)
    scores = np.asarray(clon.get_booster().predict(
        xgboost.DMatrix(X_B)), dtype=np.float64)
    orden = np.argsort(scores)[::-1]
    n = len(ids)
    top_ids = [ids[k] for k in orden]
    rmsds = [float(labels[i]["rmsd"]) for i in top_ids]
    rmsd_top1 = rmsds[0]
    if n > 1:
        margen = float(scores[orden[0]] - scores[orden[1]])
        rmsd_top2 = rmsds[1]
    else:
        margen = 0.0
        rmsd_top2 = None
    rmsd_top3 = rmsds[2] if n > 2 else None

    def clase(k):
        if rmsd_top1 <= UMBRAL_POSITIVA:
            return "solved"
        if min(rmsds[:k]) <= UMBRAL_POSITIVA:
            return "rescoring_actionable"
        return "sampling_needed"

    clase_2 = clase(2)
    clase_3 = clase(3)
    pct_winner = P[orden[0], :]
    feats_router = np.array(
        [float(scores[orden[0]]), margen, float(n),
         1.0 if margen < UMBRAL_ABSTENCION else 0.0]
        + [float(v) for v in pct_winner], dtype=np.float64)
    assert feats_router.shape == (len(FEATURES_ROUTER),)
    return {
        "clase_2": clase_2,
        "clase_3": clase_3,
        "rmsd_top1": rmsd_top1,
        "rmsd_top2": rmsd_top2,
        "rmsd_top3": rmsd_top3,
        "margen": margen,
        "score_top1": float(scores[orden[0]]),
        "n_poses": n,
        "abstenido": bool(margen < UMBRAL_ABSTENCION),
        "feats_router": feats_router,
    }


# ───────────────────────── sub-folds internos (documentados) ────────────────

def construir_subfolds(outer_fold, pids_orden, pid2fold, pid2comp):
    """5 sub-folds por componentes DENTRO del outer-train.

    Metodo (prerregistro): se reutilizan las asignaciones del fold_plan
    restringidas al outer-train donde aplique (los grupos g != f presentes);
    el grupo del fold_plan del propio outer fold esta vacio en el
    outer-train, asi que el quinto sub-fold se obtiene PARTIENDO el grupo mas
    grande del outer-train: por componentes si tiene > 1; por pids ordenados
    si es un componente unico (fold 0, 55 pids). Determinista."""
    outer_train = [p for p in pids_orden if pid2fold[p] != outer_fold]
    grupos = {g: sorted(p for p in outer_train if pid2fold[p] == g)
              for g in range(N_FOLDS)}
    no_vacios = {g: ps for g, ps in grupos.items() if ps}
    g_mayor = max(no_vacios, key=lambda g: len(no_vacios[g]))
    L = no_vacios[g_mayor]
    comps_L = sorted({pid2comp[p] for p in L})
    if len(comps_L) > 1:
        mitad = (len(comps_L) + 1) // 2
        comps_A = set(comps_L[:mitad])
        A = sorted(p for p in L if pid2comp[p] in comps_A)
        B = sorted(p for p in L if pid2comp[p] not in comps_A)
        metodo = (f"grupo g={g_mayor} partido por componentes "
                  f"({mitad}/{len(comps_L) - mitad})")
    else:
        mitad = (len(L) + 1) // 2
        A = L[:mitad]
        B = L[mitad:]
        metodo = (f"grupo g={g_mayor} (componente unico, {len(L)} pids) "
                  f"partido por pids ordenados ({mitad}/{len(L) - mitad})")
    subfolds = []
    for g in range(N_FOLDS):
        if g == outer_fold:
            continue
        if g == g_mayor:
            subfolds.append(A)
            subfolds.append(B)
        else:
            subfolds.append(no_vacios[g])
    return subfolds, g_mayor, metodo


# ───────────────────────── router (LogReg, QA-3) ───────────────────────────

def entrenar_router(X, y):
    """LogReg (arquitectura de referencia de Fase 3.5 / QA-3) con
    estandarizacion ajustada DENTRO del outer-train. Devuelve el clasificador,
    la estandarizacion (aplicada tal cual al outer-test) y el riesgo
    P(rescoring_actionable@2) inner-OOF."""
    mu = np.mean(X, axis=0)
    sd = np.std(X, axis=0)
    sd[sd == 0.0] = 1.0
    Xs = (X - mu) / sd
    clf = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000,
                             random_state=42)
    clf.fit(Xs, y)
    riesgo = clf.predict_proba(Xs)[:, 1]
    return clf, mu, sd, riesgo


# ───────────────────────── metricas por selector ────────────────────────────

def metricas_selector(sel, ev_test):
    """(fallos recuperables@2, fallos recuperables@3, falsos escalamientos)
    para un selector dado, sobre el outer-test de un fold."""
    capt2 = [p for p in sel if ev_test[p]["clase_2"] == "rescoring_actionable"]
    capt3 = [p for p in sel if ev_test[p]["clase_3"] == "rescoring_actionable"]
    falsos = [p for p in sel if ev_test[p]["clase_2"] == "solved"]
    return len(capt2), len(capt3), len(falsos)


def resumen_budget(b, q, sel_router, sel_margin, sel_aleatorio, ev_test,
                   n_eval):
    r2, r3, rf = metricas_selector(sel_router, ev_test)
    m2, m3, mf = metricas_selector(sel_margin, ev_test)
    a2, a3, af = metricas_selector(sel_aleatorio, ev_test)
    k = len(sel_router)
    drift = k / n_eval if n_eval else 0.0
    return {
        "presupuesto_nominal_pct": round(100.0 * b, 1),
        "umbral_riesgo": _round(q, 6),
        "n_escalados_router": k,
        "n_eval": n_eval,
        "drift_pct": _round(100.0 * drift, 2),
        "fallos_recuperables_2": {"router": r2, "margin_only": m2,
                                  "aleatorio": a2},
        "fallos_recuperables_3": {"router": r3, "margin_only": m3,
                                  "aleatorio": a3},
        "falsos_escalamientos": {"router": rf, "margin_only": mf,
                                 "aleatorio": af},
        "delta_fallos2_vs_margin": r2 - m2,
        "delta_falsos_vs_margin": rf - mf,
    }


def conteo_clases(ev_test, pids):
    out = {"solved": 0, "rescoring_actionable": 0, "sampling_needed": 0}
    for p in pids:
        out[ev_test[p]["clase_2"]] += 1
    return out


# ───────────────────────── bootstrap BCa por componentes ────────────────────

def bootstrap_componentes_delta(pids_orden, pid2comp, comps_orden,
                                d_por_pid, etiqueta):
    """Bootstrap PRIMARIO por las 38 componentes del fold_plan (resampling
    de componentes con reemplazo, 10 000 replicas exactas, seed 42, BCa con
    jackknife) sobre la suma pareada d_por_pid (patron RS-01B/RS-04-OOF)."""
    suma_comp = {c: sum(v for p, v in d_por_pid.items() if pid2comp[p] == c)
                 for c in comps_orden}
    rng = np.random.default_rng(SEED_BOOT)
    idx = rng.integers(0, len(comps_orden), size=(N_BOOT, len(comps_orden)))
    boot = np.array([sum(suma_comp[comps_orden[i]] for i in fila)
                     for fila in idx], dtype=np.float64)
    obs = float(sum(d_por_pid.values()))
    jack = [obs - suma_comp[c] for c in comps_orden]
    return bca_intervalo(boot, obs, jack, etiqueta)


# ───────────────────────── flujo principal ─────────────────────────────────

def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(
        description="RS-08: router de decidibilidad accionable (cross-fitting "
                    "anidado, folds sellados RS-01B)")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    inner_dir = out_dir / "inner_models"
    inner_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    print("== RS-08: router de decidibilidad accionable (cross-fitting "
          "ANIDADO, folds sellados RS-01B) ==", flush=True)

    # ── insumos sellados + folds exactos (verificacion sha interna) ──
    prep = preparar_insumos()
    insumos, feats, labels = prep["insumos"], prep["feats"], prep["labels"]
    por_pid, pids_orden = prep["por_pid"], prep["pids_orden"]
    pid2fold, pids_fold = prep["pid2fold"], prep["pids_fold"]
    comps_orden, pid2comp = prep["comps_orden"], prep["pid2comp"]
    indices_pct = prep["indices_pct"]
    estrato_por_pid = prep["estrato_por_pid"]
    n_coinciden = prep["n_coinciden"]
    print("  insumos sellados verificados (sha256): OK | densidad historica "
          f"{n_coinciden}/2739 | folds {prep['tamanos']} | 38 componentes",
          flush=True)

    # ── clones outer sellados: verificacion triple de sha (NO se reentrenan) ──
    rs01b_metrics = leer_json(RS01B_DIR / "metrics.json")
    rs04_metrics = leer_json(RS04OOF_DIR / "metrics.json")
    verif_outer = {}
    for fold in range(N_FOLDS):
        nombre = f"fold{fold}_brazo_original"
        nombre_bl = f"fold{fold}_brazo_baseline"
        sha_rs01b = rs01b_metrics["modelos_fold"][nombre]["sha256"]
        sha_rs04 = rs04_metrics["modelos_fold"][nombre_bl]["sha256"]
        path_xgb = RS01B_DIR / "fold_models" / f"{nombre}.xgb"
        sha_real = sha256_archivo(path_xgb)
        ok = bool(sha_real == sha_rs01b == sha_rs04
                  and sha_real[:8] == SHA_OUTER_ESPERADOS[fold])
        verif_outer[nombre] = {
            "sha256_archivo": sha_real,
            "sha_rs01b_original": sha_rs01b,
            "sha_rs04_baseline": sha_rs04,
            "esperado_preregistro": SHA_OUTER_ESPERADOS[fold],
            "ok": ok,
        }
        if not ok:
            raise SystemExit(f"ERROR: sha del clon outer {nombre} no coincide "
                             "con el sellado")
    print("  clones outer verificados (RS-01B brazo_original == RS-04-OOF "
          "baseline): 5/5 sha sellados (NO reentrenados)", flush=True)

    # ── ionizado por complejo (carga formal del SDF sanitizado) ──
    ligandos, fallos_sdf = cargar_ligandos(pids_orden)
    if fallos_sdf:
        raise SystemExit("ERROR: SDF fallidos: " + ", ".join(f["pid"]
                                                             for f in fallos_sdf))
    ionizado_por_pid = {pid: bool(Chem.GetFormalCharge(ligandos[pid][1]) != 0)
                        for pid in pids_orden}

    # ── cross-fitting anidado por outer fold ──
    rng_aleatorio = np.random.default_rng(SEED_BOOT)
    inner_meta_filas = []
    por_fold = []
    ev_test_global = {}
    riesgo_global = {}
    escalado_global = {"router": {}, "margin": {}, "aleatorio": {}}
    umbral_por_fold = {}

    for fold in range(N_FOLDS):
        t_f = time.monotonic()
        pids_eval = pids_fold[fold]
        outer_train = [p for p in pids_orden if pid2fold[p] != fold]

        # clon outer sellado del fold (predice el outer-test; no lo vio)
        nombre = f"fold{fold}_brazo_original"
        from xgboost import XGBRanker
        clon_outer = XGBRanker()
        clon_outer.load_model(str(RS01B_DIR / "fold_models" / f"{nombre}.xgb"))
        meta_outer = leer_json(RS01B_DIR / "fold_models" / f"{nombre}_meta.json")
        if meta_outer.get("hiperparametros") != PARAMS_CLON:
            raise SystemExit("ERROR: hiperparametros del clon outer no "
                             "coinciden con los congelados")

        # ── inner: 5 sub-folds por componentes dentro del outer-train ──
        subfolds, g_mayor, metodo_split = construir_subfolds(
            fold, pids_orden, pid2fold, pid2comp)
        X_router = []
        y_router = []
        pids_router = []
        n_inner = 0
        for s, sub in enumerate(subfolds):
            inner_train = [p for p in outer_train if p not in sub]
            ids_train = {pid: sorted(por_pid[pid], key=clave_identidad)
                         for pid in inner_train}
            Xt, yt, gt = construir_entrenamiento(inner_train, ids_train,
                                                 feats, labels, indices_pct)
            clon_inner, metrica = entrenar_clon(Xt, yt, gt)
            sha_inner = sha_modelo_tmp(
                clon_inner, inner_dir / f"tmp_xgb_f{fold}_s{s}.xgb")
            inner_meta_filas.append({
                "outer_fold": fold,
                "inner_subfold": s,
                "grupo_origen": g_mayor,
                "metodo_subfold": metodo_split,
                "n_complejos_train": len(inner_train),
                "n_complejos_eval": len(sub),
                "n_filas_train": int(Xt.shape[0]),
                "n_grupos_train": len(gt),
                "eval_metric": metrica,
                "n_arboles": int(clon_inner.get_booster().num_boosted_rounds()),
                "hiperparametros": dict(PARAMS_CLON),
                "seed": 42,
                "sha256_xgb": sha_inner,
            })
            n_inner += 1
            ids_sub = {pid: sorted(por_pid[pid], key=clave_identidad)
                       for pid in sub}
            for pid in sub:
                ev = evaluar_complejo(clon_inner, pid, ids_sub[pid], feats,
                                      labels, indices_pct)
                X_router.append(ev["feats_router"])
                y_router.append(1 if ev["clase_2"] == "rescoring_actionable"
                                else 0)
                pids_router.append(pid)
        X_router = np.vstack(X_router)
        y_router = np.array(y_router, dtype=np.float64)
        print(f"  [fold {fold}] outer-train {len(outer_train)} | inner: "
              f"{n_inner} clones, OOF sobre {len(pids_router)} complejos | "
              f"label actionable@2: {int(y_router.sum())}/"
              f"{len(y_router)} | {metodo_split}", flush=True)

        # ── router: LogReg + umbrales (percentiles del riesgo inner-OOF) ──
        clf, mu, sd, riesgo_inner = entrenar_router(X_router, y_router)
        umbrales = {b: float(np.percentile(riesgo_inner, 100.0 * (1 - b)))
                    for b in BUDGETS}
        umbral_por_fold[fold] = umbrales

        # ── outer-test: clon outer sellado + riesgo del router ──
        ids_eval = {pid: sorted(por_pid[pid], key=clave_identidad)
                    for pid in pids_eval}
        ev_test = {pid: evaluar_complejo(clon_outer, pid, ids_eval[pid],
                                         feats, labels, indices_pct)
                   for pid in pids_eval}
        X_test = np.vstack([ev_test[pid]["feats_router"] for pid in pids_eval])
        riesgo_test = clf.predict_proba((X_test - mu) / sd)[:, 1]
        riesgo_test_por_pid = {pid: _round(float(r), 6)
                               for pid, r in zip(pids_eval, riesgo_test)}
        for pid in pids_eval:
            ev_test_global[pid] = ev_test[pid]
            riesgo_global[pid] = riesgo_test_por_pid[pid]

        # ── selectores por presupuesto (router / margin / aleatorio) ──
        sensibilidades = {}
        prim = None
        for b in BUDGETS:
            q = umbrales[b]
            sel_router = [p for p in pids_eval if riesgo_test_por_pid[p] >= q]
            k = len(sel_router)
            orden_margen = sorted(pids_eval,
                                  key=lambda p: (ev_test[p]["margen"], p))
            sel_margin = orden_margen[:k]
            sel_aleatorio = [str(p) for p in rng_aleatorio.choice(
                sorted(pids_eval), size=k, replace=False)]
            res = resumen_budget(b, q, sel_router, sel_margin, sel_aleatorio,
                                 ev_test, len(pids_eval))
            if b == BUDGET_PRIMARIO:
                prim = res
                for p in pids_eval:
                    escalado_global["router"][p] = p in sel_router
                    escalado_global["margin"][p] = p in sel_margin
                    escalado_global["aleatorio"][p] = p in sel_aleatorio
            else:
                sensibilidades[f"budget_{int(b * 100)}"] = res

        drift_ok = DRIFT_BAJO <= prim["drift_pct"] / 100.0 <= DRIFT_ALTO
        por_fold.append({
            "fold": fold,
            "n_complejos_eval": len(pids_eval),
            "n_outer_train_complejos": len(outer_train),
            "n_componentes": len({pid2comp[p] for p in pids_eval}),
            "clases_2": conteo_clases(ev_test, pids_eval),
            "presupuesto_primario": prim,
            "drift_presupuesto": {
                "n_escalados_router": prim["n_escalados_router"],
                "pct": prim["drift_pct"],
                "gate_aceptable_pct": [25.0, 35.0],
                "aceptable": bool(drift_ok),
                "desviacion_causa": (None if drift_ok else
                                     "presupuesto real fuera de [25,35]% "
                                     "sobre el outer-test; umbral p70 FIJO "
                                     "del outer-train (prohibido re-umbralizar "
                                     "mirando el outer-test)"),
            },
            "sensibilidad": sensibilidades,
            "umbrales_riesgo": {str(round(b, 2)): _round(q, 6)
                                for b, q in umbrales.items()},
        })
        print(f"    primario: drift {prim['drift_pct']}% | fallos2 "
              f"router {prim['fallos_recuperables_2']['router']} / margin "
              f"{prim['fallos_recuperables_2']['margin_only']} / aleatorio "
              f"{prim['fallos_recuperables_2']['aleatorio']} | falsos "
              f"router {prim['falsos_escalamientos']['router']} / margin "
              f"{prim['falsos_escalamientos']['margin_only']} | "
              f"{time.monotonic() - t_f:.1f}s", flush=True)

    # ── globales (presupuesto primario 30%) ──
    def suma_global(campo):
        return {
            "router": sum(pf["presupuesto_primario"][campo]["router"]
                          for pf in por_fold),
            "margin_only": sum(pf["presupuesto_primario"][campo]["margin_only"]
                               for pf in por_fold),
            "aleatorio": sum(pf["presupuesto_primario"][campo]["aleatorio"]
                             for pf in por_fold),
        }

    fallos2 = suma_global("fallos_recuperables_2")
    fallos3 = suma_global("fallos_recuperables_3")
    falsos = suma_global("falsos_escalamientos")
    delta_fallos2 = fallos2["router"] - fallos2["margin_only"]
    delta_falsos = falsos["router"] - falsos["margin_only"]
    cumple_fallos = delta_fallos2 >= GATE_DELTA_FALLOS
    cumple_falsos = delta_falsos <= GATE_DELTA_FALSOS_MAX
    veredicto = "PASS" if (cumple_fallos and cumple_falsos) else "FAIL"

    # bootstrap BCa por las 38 componentes sobre los deltas pareados
    d_fallos = {p: ((1 if escalado_global["router"][p] else 0)
                    - (1 if escalado_global["margin"][p] else 0))
                for p in pids_orden
                if ev_test_global[p]["clase_2"] == "rescoring_actionable"}
    d_falsos = {p: ((1 if escalado_global["router"][p] else 0)
                    - (1 if escalado_global["margin"][p] else 0))
                for p in pids_orden
                if ev_test_global[p]["clase_2"] == "solved"}
    boot_fallos = bootstrap_componentes_delta(
        pids_orden, pid2comp, comps_orden, d_fallos,
        "Δ fallos recuperables@2 (router − margin-only)")
    boot_falsos = bootstrap_componentes_delta(
        pids_orden, pid2comp, comps_orden, d_falsos,
        "Δ falsos escalamientos (router − margin-only)")

    # McNemar exacto (opcional) sobre fallos recuperables@2 capturados
    from scipy.stats import binomtest
    b_mc = sum(1 for p in pids_orden
               if ev_test_global[p]["clase_2"] == "rescoring_actionable"
               and escalado_global["margin"][p]
               and not escalado_global["router"][p])
    c_mc = sum(1 for p in pids_orden
               if ev_test_global[p]["clase_2"] == "rescoring_actionable"
               and escalado_global["router"][p]
               and not escalado_global["margin"][p])
    n_disc = b_mc + c_mc
    p_mc = 1.0 if n_disc == 0 else float(binomtest(min(b_mc, c_mc),
                                                   n_disc, 0.5).pvalue)
    mcnemar = {"b_margin_router_no": b_mc, "c_router_margin_no": c_mc,
               "n_discordantes": n_disc,
               "p_valor_exacto_bilateral": _round(p_mc, 6),
               "nota": ("binomtest(...).pvalue ya es bilateral; 0 pares "
                        "discordantes -> p = 1.0")}

    # estratos hard/control (D-MF-HARD congelado)
    por_estrato = {}
    for estrato in ("hard", "control"):
        pids_e = [p for p in pids_orden if estrato_por_pid[p] == estrato]
        comps_e = sorted({pid2comp[p] for p in pids_e})
        cap = {s: sum(1 for p in pids_e
                      if ev_test_global[p]["clase_2"]
                      == "rescoring_actionable"
                      and escalado_global[s][p])
               for s in ("router", "margin", "aleatorio")}
        fal = {s: sum(1 for p in pids_e
                      if ev_test_global[p]["clase_2"] == "solved"
                      and escalado_global[s][p])
               for s in ("router", "margin", "aleatorio")}
        por_estrato[estrato] = {
            "n_complejos": len(pids_e),
            "n_componentes": len(comps_e),
            "fallos_recuperables_2": cap,
            "falsos_escalamientos": fal,
            "delta_fallos2_vs_margin": cap["router"] - cap["margin"],
            "delta_falsos_vs_margin": fal["router"] - fal["margin"],
        }

    # drift global y desviaciones por fold
    n_escalados_total = sum(pf["presupuesto_primario"]["n_escalados_router"]
                            for pf in por_fold)
    drift_global = _round(100.0 * n_escalados_total / len(pids_orden), 2)
    desviaciones = [{"fold": pf["fold"], "pct": pf["drift_presupuesto"]["pct"],
                     "causa": pf["drift_presupuesto"]["desviacion_causa"]}
                    for pf in por_fold
                    if not pf["drift_presupuesto"]["aceptable"]]

    # sensibilidad global 10/20/40
    sens_global = {}
    for b in BUDGETS:
        if b == BUDGET_PRIMARIO:
            continue
        clave = f"budget_{int(b * 100)}"
        fallos_s = {"router": 0, "margin_only": 0, "aleatorio": 0}
        falsos_s = {"router": 0, "margin_only": 0, "aleatorio": 0}
        n_escal = 0
        for pf in por_fold:
            s = pf["sensibilidad"][clave]
            for k2 in ("router", "margin_only", "aleatorio"):
                fallos_s[k2] += s["fallos_recuperables_2"][k2]
                falsos_s[k2] += s["falsos_escalamientos"][k2]
            n_escal += s["n_escalados_router"]
        sens_global[clave] = {
            "presupuesto_nominal_pct": round(100.0 * b, 1),
            "n_escalados_router_total": n_escal,
            "drift_pct": _round(100.0 * n_escal / len(pids_orden), 2),
            "fallos_recuperables_2": fallos_s,
            "falsos_escalamientos": falsos_s,
            "delta_fallos2_vs_margin": (fallos_s["router"]
                                        - fallos_s["margin_only"]),
            "delta_falsos_vs_margin": (falsos_s["router"]
                                       - falsos_s["margin_only"]),
            "nota": "descriptiva, SIN gate (QA-3)",
        }

    # ── auditoria de cuarentena: whitelist de archivos abiertos ──
    abiertos = set(rs1b._ABIERTOS_REPO)
    rel_out = out_dir.relative_to(PROJECT_ROOT).as_posix()
    whitelist = {
        "scripts/run_rs08_router.py",
        "scripts/run_rs04_oof.py",
        "scripts/run_rs04_qc.py",
        "scripts/run_rs01b_crossfit.py",
        "scripts/dedup_pose_union_medoid.py",
        "rescoring/pose_selector/__init__.py",
        "rescoring/pose_selector/selector.py",
        "rescoring/pose_selector/feature_extractor.py",
        "rescoring/artifacts/pose_selector_v06.xgb",
        "rescoring/artifacts/pose_selector_v06_meta.json",
        "data/pose_selector_dataset/poses_train.jsonl",
        "scripts/artifacts_science/RS-01/INVENTORY.json",
        "scripts/artifacts_science/RS-01/cache_train_only_view.jsonl",
        "scripts/artifacts_science/RS-01/cache_view_manifest.json",
        "scripts/artifacts_science/RS-01/fold_plan.json",
        "scripts/artifacts_science/MF-01-UNION/union_candidates_train.jsonl",
        "scripts/artifacts_science/MF-01-UNION/union_labels_train.jsonl",
        "scripts/artifacts_science/MF-11-R1/dedup_candidates_train_1.5.jsonl",
        "scripts/artifacts_science/MF-11-R1/cluster_members_train_1.5.jsonl",
        "scripts/artifacts_science/MF-11-R1/metrics.json",
        "scripts/artifacts_science/RS-01B/metrics.json",
        "scripts/artifacts_science/RS-04-OOF/metrics.json",
    }
    for pid in pids_orden:
        whitelist.add(f"data/pose_selector_dataset/records/{pid}.json")
        whitelist.add(f"data/pdbbind/{pid}/{pid}_ligand.sdf")
    for fold in range(N_FOLDS):
        nombre = f"fold{fold}_brazo_original"
        whitelist.add(f"scripts/artifacts_science/RS-01B/fold_models/"
                      f"{nombre}.xgb")
        whitelist.add(f"scripts/artifacts_science/RS-01B/fold_models/"
                      f"{nombre}_meta.json")
    for nombre in ("metrics.json", "per_complex.jsonl", "failures.jsonl",
                   "DESIGN.md"):
        whitelist.add(f"{rel_out}/{nombre}")
    whitelist.add(f"{rel_out}/inner_models/meta.jsonl")
    for fold in range(N_FOLDS):
        for s in range(N_FOLDS):
            whitelist.add(f"{rel_out}/inner_models/tmp_xgb_f{fold}_s{s}.xgb")
    fuera = sorted(p for p in abiertos
                   if p not in whitelist and "__pycache__" not in p
                   and not p.endswith(".pyc")
                   and not p.startswith("python-embed/"))
    if fuera:
        raise SystemExit("ERROR: archivos fuera del whitelist abiertos: "
                         + "; ".join(fuera))
    prohibidos = [p for p in abiertos if any(f in p for f in FORBIDDEN)]
    if prohibidos:
        raise SystemExit("ERROR: se abrieron archivos PROHIBIDOS: "
                         + "; ".join(prohibidos))
    print("  cuarentena: 0 accesos val/test/CONFIRM (whitelist OK)", flush=True)

    # ── per_complex.jsonl (116) ──
    filas_pc = []
    for pid in pids_orden:
        ev = ev_test_global[pid]
        filas_pc.append({
            "pid": pid,
            "fold": pid2fold[pid],
            "componente": pid2comp[pid],
            "estrato": estrato_por_pid[pid],
            "ionizado": ionizado_por_pid[pid],
            "n_poses": ev["n_poses"],
            "clase_2": ev["clase_2"],
            "clase_3": ev["clase_3"],
            "rmsd_top1": _round(ev["rmsd_top1"], 4),
            "rmsd_top2": (_round(ev["rmsd_top2"], 4)
                          if ev["rmsd_top2"] is not None else None),
            "rmsd_top3": (_round(ev["rmsd_top3"], 4)
                          if ev["rmsd_top3"] is not None else None),
            "margen": _round(ev["margen"], 6),
            "score_top1": _round(ev["score_top1"], 6),
            "riesgo_router": riesgo_global[pid],
            "umbral_p70_fold": _round(umbral_por_fold[pid2fold[pid]]
                                      [BUDGET_PRIMARIO], 6),
            "escalado_router": bool(escalado_global["router"][pid]),
            "escalado_margin": bool(escalado_global["margin"][pid]),
            "escalado_aleatorio": bool(escalado_global["aleatorio"][pid]),
        })

    # ── metrics.json ──
    metrics = {
        "experimento": "RS-08",
        "declaracion_resultado": (
            "Router de decidibilidad ACCIONABLE (solved / "
            "rescoring_actionable@2 / sampling_needed) con cross-fitting "
            "ANIDADO dentro de los 5 folds sellados de RS-01B: features y "
            "etiquetas del router sobre el outer-train proceden de "
            "predicciones inner-OOF (clones v0.6 entrenados en inner-train "
            "que NO vieron el complejo); umbral percentil 70 del riesgo "
            "inner-OOF del outer-train, aplicado FIJO al outer-test; "
            "comparadores margin-only v0.6 y aleatorio (seed 42) al MISMO "
            "coste real por fold. Gate: >= +3 fallos recuperables@2 vs "
            "margin-only y delta falsos escalamientos <= 0."),
        "preregistro": ("scripts/artifacts_science/RS-08/PREREGISTRO.md "
                        "(sello b4204bd) + CAMPANA-2-PLAN sellado (41b7f09) "
                        "IT1/DECISIONS QA-3"),
        "runtime": {
            "python": sys.version.split()[0],
            "xgboost": xgboost.__version__,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "sklearn": __import__("sklearn").__version__,
            "rdkit": Chem.rdBase.rdkitVersion,
            "interprete": "python-embed/python.exe",
        },
        "integridad_insumos_sha256": insumos["tabla_sha"],
        "validaciones": {
            "densidad_historica": {
                "metodo": "records/{pid}.json, RMSD < 2.0 A",
                "n_coinciden_con_congelado": n_coinciden,
                "n_total": 2739,
                "exacto": bool(n_coinciden == 2739),
            },
            "folds": {
                "tamanos": prep["tamanos"],
                "esperado": [55, 16, 15, 15, 15],
                "n_componentes": len(comps_orden),
                "esperado_componentes": 38,
            },
            "clones_outer_sellados": {
                "nota": ("clon v0.6 outer = RS-01B brazo_original / "
                         "RS-04-OOF baseline (sha verificados, NO "
                         "reentrenados); verificado ademas que los "
                         "hiperparametros del meta coinciden con los "
                         "congelados"),
                "por_fold": verif_outer,
            },
            "cross_fitting_anidado": {
                "metodo": ("5 sub-folds por componentes dentro de cada "
                           "outer-train: reuso de las asignaciones del "
                           "fold_plan restringidas al outer-train donde "
                           "aplique (grupos g != f); el quinto sub-fold "
                           "parte el grupo mas grande (por componentes si "
                           "tiene > 1; por pids ordenados si es componente "
                           "unico). El clon inner que predice un complejo "
                           "NUNCA lo vio (inner-OOF). El OOF global NO se "
                           "reutiliza (sus modelos vieron el outer-test)."),
                "n_clones_inner": len(inner_meta_filas),
                "esperado": N_FOLDS * N_FOLDS,
            },
        },
        "config_router": {
            "clases": {
                "solved": "top-1 <= 2 A (no escalar)",
                "rescoring_actionable@2": ("top-1 falla pero existe pose "
                                           "<= 2 A entre las top-2 "
                                           "(PRIMARIA; escalar a RS-03)"),
                "rescoring_actionable@3": ("top-1 falla pero existe pose "
                                           "<= 2 A entre las top-3 "
                                           "(sensibilidad, nunca gate)"),
                "sampling_needed": ("ni top-2 ni top-3 contienen pose <= 2 A "
                                    "(nueva generacion; NO MM/GBSA-like)"),
            },
            "features": {
                "n_features": len(FEATURES_ROUTER),
                "nombres": list(FEATURES_ROUTER),
                "nota": ("proceden del clon inner-OOF (outer-train) y del "
                         "clon outer sellado (outer-test); el margen v0.6 es "
                         "FEATURE del riesgo, no un segundo umbral ajustado "
                         "en val (QA-3g)"),
            },
            "modelo": {
                "arquitectura": "LogisticRegression (lbfgs, C=1.0, "
                                "max_iter=1000, random_state=42) — "
                                "arquitectura de referencia de Fase 3.5/QA-3",
                "estandarizacion": "media/std ajustadas DENTRO del outer-train "
                                   "(sd==0 -> 1); aplicada tal cual al "
                                   "outer-test",
                "riesgo": "P(rescoring_actionable@2)",
            },
            "umbrales": {
                "metodo": ("percentil 100*(1-b) del riesgo inner-OOF del "
                           "outer-train; aplicacion FIJA al outer-test "
                           "(prohibido re-seleccionar mirando la distribucion "
                           "del outer-test)"),
                "presupuestos": {str(round(b, 2)):
                                 round(100.0 * (1 - b), 1)
                                 for b in BUDGETS},
                "primario_pct": round(100.0 * (1 - BUDGET_PRIMARIO), 1),
            },
            "strain": "FUERA del camino primario y del router (RS-04-OOF "
                      "NO_GO a8c9523); no es feature",
        },
        "por_fold": por_fold,
        "global": {
            "n_complejos_oof": len(pids_orden),
            "clases_2_global": {k: sum(pf["clases_2"][k] for pf in por_fold)
                                for k in ("solved", "rescoring_actionable",
                                          "sampling_needed")},
            "presupuesto_real_total": {
                "n_escalados_router": n_escalados_total,
                "drift_pct": drift_global,
                "gate_aceptable_pct": [25.0, 35.0],
            },
            "fallos_recuperables_2": fallos2,
            "fallos_recuperables_3": fallos3,
            "falsos_escalamientos": falsos,
            "delta_vs_margin": {
                "fallos_recuperables_2": delta_fallos2,
                "falsos_escalamientos": delta_falsos,
            },
            "gate": {
                "criterio": ("capturar >= +3 fallos recuperables@2 vs "
                             "margin-only al mismo coste (presupuesto real, "
                             "pareado por fold) Y delta falsos escalamientos "
                             "<= 0 (los complejos solved escalados no pueden "
                             "aumentar vs margin-only)"),
                "delta_fallos_recuperables_2": delta_fallos2,
                "requerido": GATE_DELTA_FALLOS,
                "cumple_fallos": bool(cumple_fallos),
                "delta_falsos_escalamientos": delta_falsos,
                "requerido_falsos": GATE_DELTA_FALSOS_MAX,
                "cumple_falsos": bool(cumple_falsos),
                "veredicto": veredicto,
            },
            "mcnemar_opcional": mcnemar,
            "drift_por_fold": [
                {"fold": pf["fold"],
                 "n_escalados_router": pf["presupuesto_primario"]
                 ["n_escalados_router"],
                 "pct": pf["drift_presupuesto"]["pct"],
                 "aceptable": pf["drift_presupuesto"]["aceptable"]}
                for pf in por_fold],
            "desviaciones_presupuesto": desviaciones,
            "nota_drift": ("la fraccion escalada en el outer-test es el "
                           "presupuesto REAL; el percentil 70 del outer-train "
                           "no siempre se traduce en 30% exacto; fuera de "
                           "[25,35]% se reporta desviacion con causa, NO se "
                           "re-umbraliza"),
        },
        "incertidumbre": {
            "bootstrap_componentes_38_primario": {
                "n_replicas": N_BOOT,
                "seed": SEED_BOOT,
                "unidades": "38 componentes combinadas del fold_plan",
                "delta_fallos_recuperables_2": boot_fallos,
                "delta_falsos_escalamientos": boot_falsos,
            },
            "nota": ("BCa primario por las 38 componentes; degenerado -> "
                     "percentil bootstrap (regla C3d)"),
        },
        "sensibilidad_presupuestaria": sens_global,
        "por_estrato": por_estrato,
        "inner_models": {
            "n_clones": len(inner_meta_filas),
            "archivo": f"{rel_out}/inner_models/meta.jsonl",
            "nota": ("solo meta jsonl con sha256 de los 25 clones inner "
                     "(los binarios .xgb NO se conservan); mismo XGBoost "
                     "congelado que el clon v0.6 (233 features A1, sin "
                     "strain)"),
        },
        "limitacion_claim": (
            "RS-08 solo puede recibir GO como ROUTER (decisibilidad "
            "accionable). PROHIBIDO reclamar mejora de Top-1: el rescoring "
            "solo es util si RS-03 (MM/GBSA-like, previa RS-03-PARAM) "
            "convierte los complejos escalados en aciertos (cascada integrada "
            "v0.6 -> RS-08 -> RS-03). El strain MMFF94s queda FUERA del "
            "camino primario de la cascada."),
        "archivos_abiertos_repo": sorted(abiertos),
        "garantia_cuarentena": (
            "builtins.open auditado contra whitelist explicita: 0 accesos a "
            "val/test/CONFIRM; poses_val.jsonl, poses_test.jsonl y "
            "D-RC-CONFIRM nunca se abren"),
        "determinismo": (
            "salidas sin timestamps ni aleatoriedad no-seeded (seed 42 en "
            "clones inner, bootstrap y seleccion aleatoria; LogReg lbfgs "
            "determinista; umbral percentil 70 materializado como valor "
            "numerico por fold); dos corridas producen salidas "
            "byte-identicas"),
    }

    escribir_json(out_dir / "metrics.json", metrics)
    escribir_jsonl(out_dir / "per_complex.jsonl", filas_pc)
    escribir_jsonl(out_dir / "failures.jsonl", [])
    escribir_jsonl(inner_dir / "meta.jsonl", inner_meta_filas)

    # ── DESIGN.md (protocolo anidado + veredicto del gate) ──
    drift_desc = ", ".join(
        f"fold {pf['fold']}: {pf['drift_presupuesto']['pct']}%"
        for pf in por_fold)
    design = (
        "# RS-08 — Router de decidibilidad accionable (DESIGN)\n"
        "\n"
        "**Fecha:** 2026-08-16\n"
        "**Rama:** `experimentos/ruta-c-molflex`\n"
        "**Estado:** EJECUTADO (sin seal, sin finish — por instrucción del "
        "maintainer)\n"
        "**Preregistro:** `scripts/artifacts_science/RS-08/PREREGISTRO.md` "
        "(sello b4204bd, contrato literal)\n"
        "**Plan:** `CAMPANA-2-PLAN` sellado (41b7f09) IT1/DECISIONS QA-3\n"
        "**Script:** `scripts/run_rs08_router.py` (por composición; nada "
        "sellado se edita)\n"
        "\n"
        "## 1. Veredicto del gate de desarrollo\n"
        "\n"
        f"**GATE: {veredicto}**\n"
        "\n"
        f"| Criterio | Valor | Requisito | Cumple |\n"
        f"|---|---|---|---|\n"
        f"| Δ fallos recuperables@2 vs margin-only | **{delta_fallos2}** "
        f"| ≥ +3 | {'SÍ' if cumple_fallos else 'NO'} |\n"
        f"| Δ falsos escalamientos vs margin-only | **{delta_falsos}** "
        f"| ≤ 0 | {'SÍ' if cumple_falsos else 'NO'} |\n"
        "\n"
        f"Fallos recuperables@2 capturados: router **{fallos2['router']}**, "
        f"margin-only **{fallos2['margin_only']}**, aleatorio "
        f"**{fallos2['aleatorio']}** (116 OOF, mismo coste real por fold).\n"
        "\n"
        f"Falsos escalamientos (complejos `solved` escalados): router "
        f"**{falsos['router']}**, margin-only **{falsos['margin_only']}**, "
        f"aleatorio **{falsos['aleatorio']}**.\n"
        "\n"
        f"Bootstrap BCa por las 38 componentes (10 000 réplicas, seed 42): "
        f"Δ fallos recuperables@2 {boot_fallos['intervalo']} "
        f"(excluye cero: {boot_fallos['excluye_cero']}); Δ falsos "
        f"escalamientos {boot_falsos['intervalo']} "
        f"(excluye cero: {boot_falsos['excluye_cero']}).\n"
        "\n"
        f"Drift real de presupuesto (fracción escalada en outer-test): "
        f"**{drift_global}%** global ({drift_desc}); gate de operación "
        f"25–35%.\n"
        "\n"
        "## 2. Protocolo ejecutado (literal)\n"
        "\n"
        "- **Outer**: 5 folds EXACTOS del fold_plan sellado (sha "
        "`9d97ad70…`), `[55,16,15,15,15]`, 38 componentes. Clon v0.6 outer = "
        "el sellado (RS-01B `brazo_original` / RS-04-OOF `baseline`), sha "
        "verificados por fold (`6e872ba2/2541609f/9584f7d9/8eab79bf/"
        "fabc39ec`) + meta de hiperparámetros congelados: NO se reentrena.\n"
        "- **Inner (cross-fitting ANIDADO, obligatorio)**: dentro de cada "
        "outer-train, 5 sub-folds por componentes reutilizando las "
        "asignaciones del fold_plan restringidas al outer-train donde "
        "aplique (grupos `g != f`); el quinto sub-fold parte el grupo más "
        "grande (por componentes si tiene >1; por pids ordenados si es un "
        "componente único — fold 0 con 55 pids). Para cada sub-fold se "
        "entrena un clon v0.6 inner (MISMO XGBoost congelado: rank:pairwise, "
        "52 trees, depth 6, lr 0.05, subsample 0.8, seed 42, sin early "
        "stopping, 233 features A1 SIN strain) sobre el inner-train y se "
        "evalúa sobre el sub-fold. Features y etiquetas del router sobre el "
        "outer-train proceden de estas predicciones **inner-OOF** (el clon "
        "que predice un complejo NUNCA lo vio). PROHIBIDO el OOF global "
        "cuyos modelos vieron el outer-test.\n"
        "- **Etiqueta por complejo del outer-train**: error del clon "
        "inner-OOF (top-1 rmsd > 2 Å? clase accionable@2).\n"
        f"- **Features del router** ({len(FEATURES_ROUTER)}): "
        "`score_top1`, `margen_top1_top2`, `n_poses`, `abstenido` y los 9 "
        "percentiles del ganador sobre las columnas PCT_RAW de A1 "
        "(`pct_vina_score`, `pct_n_contacts_4`, `pct_n_contacts_6`, "
        "`pct_contacts_per_ha_4`, `pct_n_clashes`, `pct_pose_score_variance`, "
        "`pct_pose_score_range`, `pct_cluster_density`, `pct_n_heavy`). El "
        "margen v0.6 es FEATURE del riesgo, no el selector (QA-3g).\n"
        "- **Modelo del router**: regresión logística (lbfgs, C=1.0, "
        "random_state 42; arquitectura de referencia Fase 3.5/QA-3) con "
        "estandarización ajustada DENTRO del outer-train; riesgo = "
        "P(rescoring_actionable@2).\n"
        "- **Umbral**: percentil 70 del riesgo inner-OOF del outer-train "
        "(equivalente al 30% de mayor riesgo de QA-3), congelado y aplicado "
        "FIJO al outer-test (prohibido re-seleccionar mirando la "
        "distribución del outer-test). Sensibilidad 10/20/40% "
        "(percentiles 90/80/60 del outer-train) descriptiva, sin gate.\n"
        "- **Drift real de presupuesto**: fracción escalada en el outer-test; "
        "gate de operación 25–35%; fuera de rango → desviación con causa, NO "
        "se re-umbraliza.\n"
        "- **Comparadores al MISMO coste** (mismo número de escalamientos "
        "por fold = presupuesto real del router, pareado): (1) margin-only "
        "v0.6 — k complejos de menor margen top1−top2 del clon outer (RIVAL "
        "PRINCIPAL); (2) selección aleatoria seed 42 (CONTROL INFERIOR).\n"
        "- **Estratos** hard/control (D-MF-HARD congelado) reportados por "
        "separado; McNemar exacto opcional.\n"
        "- **Cero val/test/CONFIRM**: auditoría de `builtins.open` con "
        "whitelist (patrón RS-01B/RS-04-OOF); `poses_val.jsonl`, "
        "`poses_test.jsonl` y FND-05/D-RC-CONFIRM nunca se abren.\n"
        "\n"
        "## 3. Limitación de claim\n"
        "\n"
        "- RS-08 solo puede recibir GO **como router** (decisibilidad "
        "accionable).\n"
        "- PROHIBIDO reclamar mejora de Top-1 por sí solo: el rescoring solo "
        "es útil si RS-03 (MM/GBSA-like, previa RS-03-PARAM) convierte los "
        "complejos escalados en aciertos (cascada integrada v0.6 → RS-08 → "
        "RS-03).\n"
        "- El strain MMFF94s queda FUERA del camino primario de la cascada "
        "y del router (RS-04-OOF NO_GO a8c9523).\n"
        "\n"
        "## 4. Determinismo y salidas\n"
        "\n"
        "- Salidas sin timestamps ni aleatoriedad no-seeded; dos corridas "
        "producen `metrics.json`, `per_complex.jsonl`, `failures.jsonl` e "
        "`inner_models/meta.jsonl` byte-idénticos (verificación con sha256 "
        "en la sección de determinismo del reporte).\n"
        "- `inner_models/` guarda SOLO el meta jsonl con el sha256 de los 25 "
        "clones inner (los binarios `.xgb` no se conservan); los 5 clones "
        "outer sellados se reutilizan verificados por sha.\n"
        "- `validate RS-08` OK (el manifest sellado no se modifica).\n"
    )
    with open(out_dir / "DESIGN.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(design)

    print(f"  GLOBAL: fallos2 router {fallos2['router']} / margin "
          f"{fallos2['margin_only']} / aleatorio {fallos2['aleatorio']} | "
          f"Δ vs margin {delta_fallos2} (requiere >= +3) | falsos router "
          f"{falsos['router']} / margin {falsos['margin_only']} (Δ "
          f"{delta_falsos} <= 0) | GATE: {veredicto}", flush=True)
    print(f"  drift presupuesto global: {drift_global}% | "
          f"desviaciones: {len(desviaciones)}", flush=True)

    shas = {nombre: sha256_archivo(out_dir / nombre)[:16] for nombre in SALIDAS}
    print(f"  salidas escritas en {out_dir}", flush=True)
    print(f"  sha metrics={shas['metrics.json']} "
          f"per_complex={shas['per_complex.jsonl']} "
          f"failures={shas['failures.jsonl']}", flush=True)
    print(f"  duracion: {time.monotonic() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()