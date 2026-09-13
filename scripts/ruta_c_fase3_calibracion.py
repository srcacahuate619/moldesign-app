# -*- coding: utf-8 -*-
"""
ruta_c_fase3_calibracion.py — Ruta C, Fase 3 (docs/42_RUTA_C_PROTOCOLO.md).

Que hace:
  1. Calibracion + abstencion (C5): el artefacto de Fase 1.6 NO guarda
     scores por pose, asi que se reentrena v0.6 con el protocolo exacto
     (seed 42). Por complejo: margen = score(top1) - score(top2) y
     p_top1 = softmax(scores)_top1. Barrido de umbrales de abstencion
     (margin < t -> "no se") sobre VAL unicamente, punto de operacion
     elegido con regla pre-registrada y aplicado a TEST.
  2. R-RC4: en TEST, confusion entre abstenerse/aceptar y
     decidible/indecidible (complejo con >=1 pose <=2 A).
     Bonus: clasificador logistico de decidibilidad con AUC en VAL.
  3. R-RC2: split a nivel de POSE (mismo pid puede aparecer en train y
     test; 70/15/15 por conteo de poses, seed 42) con protocolo v0.6;
     top-1 comparado contra 0.6596 (split por complejo congelado).
  4. R-RC3: en el test congelado, complejos donde v0.6 elige pose >10 A
     existiendo una pose <=2 A (y el mismo conteo para Vina).
  5. Checkpoint de produccion: v06_production_model.xgb +
     v06_production_meta.json + funcion puntuar_complejo() verificada
     contra el test congelado (debe reproducir 0.6596).

Salida: scripts/artifacts_ruta_c_fase3.json (escritura incremental).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import ruta_c_fase1_6_v06 as v06

FEATURES_TOTAL = v06.FEATURES_TOTAL
FEATURES_V0 = v06.FEATURES_V0
FEATURES_RICH = v06.FEATURES_RICH
PCT_RAW = v06.PCT_RAW
PCT_INDICES = v06.PCT_INDICES
PARAMS = v06.PARAMS
N_MODELO_B = v06.N_MODELO_B
UMBRAL_POSITIVA = v06.UMBRAL_POSITIVA

DATASET_DIR = v06.DATASET_DIR
ARTIFACTO = SCRIPTS_DIR / "artifacts_ruta_c_fase3.json"
MODELO_PROD = DATASET_DIR / "v06_production_model.xgb"
META_PROD = DATASET_DIR / "v06_production_meta.json"

V06_TOP1_TEST_REFERENCIA = 0.6596
VINA_TOP1_TEST_REFERENCIA = 0.5319
SEED_POSE_SPLIT = 42
PROP_POSE_SPLIT = (0.70, 0.15, 0.15)
UMBRAL_RC3 = 10.0


# ───────────────────────── utilidades ────────────────────────────────────────

def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_artefacto(art: dict, etapa: str) -> None:
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTO.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ARTIFACTO)


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ───────────────── transformacion portatil (identica a Fase 1.6) ─────────────

def z_por_pid(X: np.ndarray, grupos: list) -> np.ndarray:
    """Z-score por columna dentro del complejo (filas contiguas).
    std == 0 -> z = 0. NaN permanece NaN (se rellena a 0 despues).
    Copia exacta de la transformacion de Fase 1.6 (uso de produccion)."""
    Z = np.full_like(X, np.nan, dtype=np.float64)
    ini = 0
    for g in grupos:
        cols = X[ini:ini + g]
        m = np.nanmean(cols, axis=0)
        s = np.nanstd(cols, axis=0)
        z = np.zeros_like(cols)
        ok = s > 0
        z[:, ok] = (cols[:, ok] - m[ok]) / s[ok]
        z[np.isnan(cols)] = np.nan
        Z[ini:ini + g] = z
        ini += g
    return Z


def pct_por_pid(X: np.ndarray, grupos: list, indices: list) -> np.ndarray:
    """Rango percentil 0-100 por complejo (empates -> rango promedio)
    para las columnas indicadas. Complejo de 1 pose -> 50.0.
    Copia exacta de la transformacion de Fase 1.6 (uso de produccion)."""
    from scipy.stats import rankdata
    P = np.full((X.shape[0], len(indices)), np.nan, dtype=np.float64)
    ini = 0
    for g in grupos:
        for j, col in enumerate(indices):
            x = X[ini:ini + g, col]
            if g == 1:
                P[ini:ini + g, j] = 50.0
                continue
            r = rankdata(x)
            P[ini:ini + g, j] = 100.0 * (r - 1.0) / (g - 1.0)
        ini += g
    return P


# ───────────────── inferencia de produccion (a portar en Fase 4) ─────────────

_BOOSTER = None


def cargar_booster_produccion():
    global _BOOSTER
    if _BOOSTER is None:
        import xgboost
        _BOOSTER = xgboost.Booster()
        _BOOSTER.load_model(str(MODELO_PROD))
    return _BOOSTER


def puntuar_complejo(records: list) -> np.ndarray:
    """Inferencia v0.6 de produccion para UN complejo.

    records: lista de dicts, uno por pose, con las 224 features raw
    (FEATURES_V0 + FEATURES_RICH; ver v06_production_meta.json). Devuelve
    los scores por pose (mayor = mejor) en el MISMO orden de entrada.

    Pipeline: matriz raw (n, 224) -> z-score intra-complejo por columna
    (std == 0 -> 0) -> rango percentil de las 9 features de PCT_RAW
    (1 pose -> 50) -> concatenar (n, 233) -> predict del booster.
    """
    if not records:
        return np.zeros(0, dtype=np.float64)
    X = np.array([[float(r.get(f, 0.0)) for f in FEATURES_TOTAL]
                  for r in records], dtype=np.float64)
    g = [len(records)]
    Z = z_por_pid(X, g)
    Z[np.isnan(Z)] = 0.0
    P = pct_por_pid(X, g, PCT_INDICES)
    P[np.isnan(P)] = 0.0
    X_B = np.hstack([Z, P])
    import xgboost
    return cargar_booster_produccion().predict(xgboost.DMatrix(X_B))


# ───────────────── estructuras por complejo ──────────────────────────────────

def scores_por_pid(registros: list, pids_orden: list, scores: np.ndarray) -> dict:
    """{pid: [(registro, score)]} ordenado descendente por score; los
    empates conservan el orden canonico (equivale al max() de Fase 1.6)."""
    por = defaultdict(list)
    for r, s in zip(registros, scores):
        por[r["pid"]].append((r, float(s)))
    return {pid: sorted(por[pid], key=lambda rs: -rs[1]) for pid in pids_orden}


def metricas_confianza(filas: list) -> dict:
    """margin = score(top1) - score(top2); p_top1 = softmax(scores)_top1.
    Complejo de 1 pose: margin = None (sin segundo), p_top1 = 1.0."""
    from scipy.special import softmax
    scores = np.array([s for _, s in filas], dtype=np.float64)
    p_top1 = float(softmax(scores)[0])
    if len(scores) == 1:
        return {"n_poses": 1, "margin": None, "p_top1": p_top1}
    return {"n_poses": len(scores), "margin": float(scores[0] - scores[1]),
            "p_top1": p_top1}


def datos_por_complejo(por_pid: dict, pids_orden: list) -> list:
    out = []
    for pid in pids_orden:
        filas = por_pid[pid]
        c = metricas_confianza(filas)
        rmsds = [r["rmsd"] for r, _ in filas]
        out.append({
            "pid": pid,
            "n_poses": c["n_poses"],
            "margin": c["margin"],
            "p_top1": round(c["p_top1"], 6),
            "top1_rmsd": float(filas[0][0]["rmsd"]),
            "top1_ok": bool(filas[0][0]["rmsd"] <= UMBRAL_POSITIVA),
            "min_rmsd": float(min(rmsds)),
            "tiene_pose_buena": bool(min(rmsds) <= UMBRAL_POSITIVA),
        })
    return out


def datos_vina_por_complejo(registros: list, pids_orden: list) -> list:
    """Por complejo: pose de MENOR vina_score (empates -> primera canonica),
    misma regla que el baseline de Fase 1. Para R-RC3."""
    por = defaultdict(list)
    for i, r in enumerate(registros):
        por[r["pid"]].append((i, r))
    out = []
    for pid in pids_orden:
        filas = por[pid]
        mejor = min(filas, key=lambda ir: (ir[1]["vina_score"], ir[0]))[1]
        rmsds = [r["rmsd"] for _, r in filas]
        out.append({
            "pid": pid,
            "n_poses": len(filas),
            "top1_rmsd": float(mejor["rmsd"]),
            "top1_ok": bool(mejor["rmsd"] <= UMBRAL_POSITIVA),
            "min_rmsd": float(min(rmsds)),
            "tiene_pose_buena": bool(min(rmsds) <= UMBRAL_POSITIVA),
        })
    return out

# ───────────────── calibracion / abstencion ──────────────────────────────────

def barrido_abstencion(datos: list, umbrales: list) -> list:
    """Abstenerse si margin < t (estricto). Complejos de 1 pose
    (margin None) siempre se aceptan: no hay desacuerdo que detectar."""
    filas = []
    for t in umbrales:
        rech = [d for d in datos if d["margin"] is not None and d["margin"] < t]
        acep = [d for d in datos if d["margin"] is None or d["margin"] >= t]
        top1_a = (sum(1 for d in acep if d["top1_ok"]) / len(acep)
                  if acep else None)
        top1_r = (sum(1 for d in rech if d["top1_ok"]) / len(rech)
                  if rech else None)
        filas.append({
            "umbral": round(float(t), 6),
            "n_abstenciones": len(rech),
            "tasa_abstencion": round(len(rech) / len(datos), 4),
            "n_aceptados": len(acep),
            "top1_aceptados": (round(top1_a, 4) if top1_a is not None else None),
            "top1_rechazados": (round(top1_r, 4) if top1_r is not None else None),
        })
    return filas


def elegir_umbral(filas: list) -> dict:
    """Regla pre-registrada (val unicamente):
    (1) umbrales con top1_aceptados >= 0.75 y abstencion <= 0.40: el de
        MENOR abstencion (menos conservador que cumple la meta);
    (2) si ninguno cumple: rodilla con abstencion <= 0.40 maximizando
        top1_aceptados;
    (3) sin opciones: t = 0 (sin abstencion)."""
    cand = [f for f in filas
            if f["top1_aceptados"] is not None
            and f["top1_aceptados"] >= 0.75
            and f["tasa_abstencion"] <= 0.40]
    if cand:
        return min(cand, key=lambda f: (f["tasa_abstencion"], f["umbral"]))
    cand2 = [f for f in filas
             if f["top1_aceptados"] is not None
             and f["tasa_abstencion"] <= 0.40]
    if cand2:
        return max(cand2, key=lambda f: (f["top1_aceptados"],
                                         -f["tasa_abstencion"]))
    return filas[0]


def confusion_rc4(datos: list, umbral: float) -> dict:
    """R-RC4: sobre los datos, dividir en abstenidos/aceptados y desglosar
    por decidibilidad (tiene_pose_buena) y acierto top-1."""
    abst = [d for d in datos if d["margin"] is not None and d["margin"] < umbral]
    acep = [d for d in datos if d["margin"] is None or d["margin"] >= umbral]

    def desglose(grupo: list) -> dict:
        n = len(grupo)
        con_buena = sum(1 for d in grupo if d["tiene_pose_buena"])
        aciertos = sum(1 for d in grupo if d["top1_ok"])
        aciertos_con_buena = sum(1 for d in grupo
                                 if d["tiene_pose_buena"] and d["top1_ok"])
        return {
            "n": n,
            "sin_pose_buena": n - con_buena,
            "con_pose_buena": con_buena,
            "con_pose_buena_aciertos_top1": aciertos_con_buena,
            "aciertos_top1": aciertos,
            "top1": round(aciertos / n, 4) if n else None,
        }

    return {"abstenidos": desglose(abst), "aceptados": desglose(acep)}


# ───────────────── bonus: clasificador de decidibilidad ──────────────────────

FEATURES_CLF = ["n_poses", "vina_min", "vina_media", "vina_std", "p_top1",
                "margin", "std_scores", "cluster_top1", "n_contactos4_top1",
                "n_clashes_top1"]


def agregados_clasificador(pid: str, filas: list, por_pid_raw: dict) -> dict:
    vinas = np.array([r["vina_score"] for r in por_pid_raw[pid]],
                     dtype=np.float64)
    scores = np.array([s for _, s in filas], dtype=np.float64)
    margen = (float(scores[0] - scores[1]) if len(scores) > 1
              else float("nan"))
    c = metricas_confianza(filas)
    top1 = filas[0][0]
    return {"pid": pid,
            "n_poses": len(scores),
            "vina_min": float(vinas.min()),
            "vina_media": float(vinas.mean()),
            "vina_std": float(vinas.std()),
            "p_top1": c["p_top1"],
            "margin": margen,
            "std_scores": float(scores.std()),
            "cluster_top1": float(top1.get("cluster_density", 0.0)),
            "n_contactos4_top1": float(top1.get("n_contacts_4", 0.0)),
            "n_clashes_top1": float(top1.get("n_clashes", 0.0))}


def clasificador_decidibilidad(datos_train: list, agg_train: list,
                               datos_val: list, agg_val: list) -> dict:
    """Logistica sobre agregados por complejo de TRAIN (label:
    tiene_pose_buena). AUC sobre VAL; el test NO se toca."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler
    Xtr = np.array([[a[n] for n in FEATURES_CLF] for a in agg_train],
                   dtype=np.float64)
    ytr = np.array([1 if d["tiene_pose_buena"] else 0 for d in datos_train])
    sc = StandardScaler().fit(Xtr)
    clf = LogisticRegression(max_iter=2000).fit(sc.transform(Xtr), ytr)
    Xva = np.array([[a[n] for n in FEATURES_CLF] for a in agg_val],
                   dtype=np.float64)
    yva = np.array([1 if d["tiene_pose_buena"] else 0 for d in datos_val])
    finitos = np.all(np.isfinite(Xva), axis=1)
    auc = roc_auc_score(yva[finitos],
                        clf.predict_proba(sc.transform(Xva[finitos]))[:, 1])
    auc_train = roc_auc_score(ytr, clf.predict_proba(sc.transform(Xtr))[:, 1])
    coefs = {n: round(float(c), 4)
             for n, c in zip(FEATURES_CLF, clf.coef_[0])}
    return {
        "features": FEATURES_CLF,
        "coeficientes": coefs,
        "auc_train": round(float(auc_train), 4),
        "auc_val": round(float(auc), 4),
        "n_val_usados": int(finitos.sum()),
        "n_val_total": len(datos_val),
        "nota": ("complejos de 1 pose (margin NaN) excluidos de la "
                 "evaluacion en val; el test congelado no se usa"),
    }


# ───────────────── R-RC2: split a nivel de pose ──────────────────────────────

def split_pose_level(todos: list, X_pool: np.ndarray, seed: int) -> dict:
    """Asigna cada POSE (no cada complejo) a train/val/test 70/15/15 con
    permutacion fija (seed 42). Un mismo pid puede aparecer en las tres
    particiones. Las filas de cada particion conservan el orden canonico
    global, por lo que los bloques por pid siguen siendo contiguos."""
    rng = np.random.default_rng(seed)
    n = len(todos)
    perm = rng.permutation(n)
    n_tr = int(round(PROP_POSE_SPLIT[0] * n))
    n_va = int(round(PROP_POSE_SPLIT[1] * n))
    idx = {"train": perm[:n_tr], "val": perm[n_tr:n_tr + n_va],
           "test": perm[n_tr + n_va:]}
    out = {}
    for nombre, ids in idx.items():
        orden = np.sort(ids)
        regs = [todos[i] for i in orden]
        X = X_pool[orden]
        grupos, pids = v06.grupos_por_pid(regs)
        out[nombre] = {"registros": regs, "X_raw": X, "grupos": grupos,
                       "pids": pids}
    return out


# ───────────────── R-RC3: conteo del modo de fallo R4 ────────────────────────

def contar_rc3(datos: list, umbral_rmsd: float) -> dict:
    """Complejos donde la pose elegida tiene rmsd > umbral_rmsd mientras
    EXISTE otra pose <= 2 A en el mismo complejo."""
    casos = [d for d in datos
             if d["top1_rmsd"] > umbral_rmsd and d["tiene_pose_buena"]]
    detalle = [{"pid": d["pid"], "rmsd_elegida": round(d["top1_rmsd"], 3),
                "min_rmsd": round(d["min_rmsd"], 3)} for d in casos]
    return {"n_casos": len(casos), "n_total": len(datos),
            "tasa": round(len(casos) / len(datos), 4), "detalle": detalle}


# ───────────────── utilidades de verificacion ────────────────────────────────

def registros_raw_224(registros: list, cache: dict) -> list:
    """Reconstruye los dicts con las 224 features raw por pose."""
    out = []
    for r in registros:
        clave = (r["pid"], r["source"], r["file_stem"], r["model_idx"])
        d = {f: float(r.get(f, 0.0)) for f in FEATURES_V0}
        for f, v in zip(FEATURES_RICH, cache[clave]):
            d[f] = float(v)
        out.append(d)
    return out

# ───────────────── flujo principal ───────────────────────────────────────────

def main() -> None:
    v06.configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 3: calibracion + abstencion + refutaciones + checkpoint ==")

    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": "3 (calibracion C5 + R-RC2/R-RC3/R-RC4 + checkpoint v0.6)",
        "nota_reentreno": ("el artefacto de Fase 1.6 no guarda scores por "
                           "pose; se reentrena v0.6 con el protocolo exacto "
                           "(seed 42) y se re-infieren val/test"),
        "referencias": {
            "v06_top1_test": V06_TOP1_TEST_REFERENCIA,
            "vina_top1_test": VINA_TOP1_TEST_REFERENCIA,
        },
        "config": {
            "umbral_positiva_angstroms": UMBRAL_POSITIVA,
            "umbral_rc3_rmsd": UMBRAL_RC3,
            "seniales_confianza": ("margin = score(top1) - score(top2); "
                                   "p_top1 = softmax(scores)_top1; "
                                   "complejo de 1 pose: margin None "
                                   "(se acepta siempre)"),
            "barrido_val": ("cuantiles 0.05..0.95 (paso 0.05) de los "
                            "margenes finitos de val + t = 0"),
            "r_rc2": {"seed": SEED_POSE_SPLIT,
                      "proporciones_por_pose": list(PROP_POSE_SPLIT)},
            "protocolo_v06": PARAMS,
        },
    }
    guardar_artefacto(art, "config")

    # ── carga de datos + reentreno v0.6 (protocolo exacto) ──
    splits = {n: v06.cargar_split(n) for n in ("train", "val", "test")}
    grupos_split, pids_split, y_split = {}, {}, {}
    for n, regs in splits.items():
        g, pids = v06.grupos_por_pid(regs)
        grupos_split[n] = g
        pids_split[n] = pids
        y_split[n] = -np.array([r["rmsd"] for r in regs], dtype=np.float64)
    X_raw = v06.construir_X_raw(splits)
    modelos = v06.preparar_modelos(X_raw, grupos_split)
    modelo_b, metrica_b = v06.entrenar_ranker(
        modelos["train"]["B"], y_split["train"], grupos_split["train"],
        modelos["val"]["B"], y_split["val"], grupos_split["val"])

    ev_test = v06.evaluar_modelo(modelo_b, modelos["test"]["B"],
                                 splits["test"], pids_split["test"])
    top1_retrain = ev_test["top1_rate"]
    delta_rep = round(top1_retrain - V06_TOP1_TEST_REFERENCIA, 4)
    art["reentreno_v06"] = {
        "eval_metric": metrica_b,
        "best_iteration": int(getattr(modelo_b, "best_iteration", -1)),
        "best_score": (float(modelo_b.best_score) if modelo_b.best_score else None),
        "top1_test_reentrenado": top1_retrain,
        "top1_test_referencia": V06_TOP1_TEST_REFERENCIA,
        "delta": delta_rep,
        "reproducibilidad": "EXACTA" if delta_rep == 0.0
                            else ("CON_DELTA_%+f" % delta_rep),
    }
    print("  reentreno v0.6: best_iteration=%d top1_test=%.4f "
          "(referencia %.4f, %s)"
          % (art["reentreno_v06"]["best_iteration"], top1_retrain,
             V06_TOP1_TEST_REFERENCIA, art["reentreno_v06"]["reproducibilidad"]))
    guardar_artefacto(art, "reentreno_v06")

    # ── scores por complejo (train/val/test) ──
    scores_split = {n: modelo_b.predict(modelos[n]["B"])
                    for n in ("train", "val", "test")}
    por_pid_split = {n: scores_por_pid(splits[n], pids_split[n],
                                       scores_split[n])
                     for n in ("train", "val", "test")}
    datos_split = {n: datos_por_complejo(por_pid_split[n], pids_split[n])
                   for n in ("train", "val", "test")}
    por_pid_raw = {n: {pid: [r for r in splits[n] if r["pid"] == pid]
                       for pid in pids_split[n]}
                   for n in ("train", "val", "test")}

    # ── Parte 1: barrido de abstencion sobre VAL ──
    margenes_val = [d["margin"] for d in datos_split["val"]
                    if d["margin"] is not None]
    cuantiles = np.quantile(margenes_val, np.arange(0.05, 1.0, 0.05))
    umbrales = [0.0] + sorted({round(float(q), 6) for q in cuantiles})
    barrido_val = barrido_abstencion(datos_split["val"], umbrales)
    print("  barrido de abstencion (val, %d complejos):"
          % len(datos_split["val"]))
    for f in barrido_val:
        print("    t=%.6f  abst=%.2f  top1_acept=%s  top1_rech=%s  n_acept=%d"
              % (f["umbral"], f["tasa_abstencion"],
                 str(f["top1_aceptados"]), str(f["top1_rechazados"]),
                 f["n_aceptados"]))

    elegido = elegir_umbral(barrido_val)
    t_elegido = float(elegido["umbral"])
    if (elegido["top1_aceptados"] is not None
            and elegido["top1_aceptados"] >= 0.75
            and elegido["tasa_abstencion"] <= 0.40):
        justificacion = ("cumple la meta (top-1 aceptados >= 0.75, "
                         "abstencion <= 0.40) con la menor abstencion "
                         "del barrido (%.2f)" % elegido["tasa_abstencion"])
    elif elegido["umbral"] == 0.0:
        justificacion = ("ningun umbral alcanza la meta dentro de los "
                         "limites; se conserva sin abstencion (t = 0)")
    else:
        justificacion = ("ningun umbral cumple la meta estricta; rodilla: "
                         "maximo top-1 aceptado dentro del limite de "
                         "abstencion <= 0.40 (%s)"
                         % str(elegido["top1_aceptados"]))
    barrido_test = barrido_abstencion(datos_split["test"], umbrales)
    fila_test_elegida = barrido_abstencion(datos_split["test"], [t_elegido])[0]
    art["calibracion"] = {
        "seniales": art["config"]["seniales_confianza"],
        "n_val_complejos": len(datos_split["val"]),
        "n_val_margenes_finitos": len(margenes_val),
        "barrido_val": barrido_val,
        "umbral_elegido": t_elegido,
        "justificacion": justificacion,
        "test_con_abstencion": fila_test_elegida,
        "test_sin_abstencion_referencia": V06_TOP1_TEST_REFERENCIA,
        "barrido_test_informativo": barrido_test,
    }
    print("  umbral elegido: t=%s -> %s" % (str(t_elegido), justificacion))
    print("  test con t=%s: abst=%.2f top1_acept=%s top1_rech=%s "
          "(sin abstencion: %.4f)"
          % (str(t_elegido), fila_test_elegida["tasa_abstencion"],
             str(fila_test_elegida["top1_aceptados"]),
             str(fila_test_elegida["top1_rechazados"]),
             V06_TOP1_TEST_REFERENCIA))
    guardar_artefacto(art, "calibracion")

    # ── Parte 1b: R-RC4 (test) ──
    conf = confusion_rc4(datos_split["test"], t_elegido)
    art["r_rc4"] = {
        "umbral": t_elegido,
        "confusion": conf,
        "interpretacion": ("abstenidos-sin-pose-buena = abstencion correcta "
                           "(indecidible); abstenidos-con-pose-buena = "
                           "abstencion costosa (podiamos ganar); "
                           "aceptados-sin-pose-buena = fallo garantizado "
                           "(no existia pose buena que elegir)"),
    }
    print("  R-RC4 (test, t=%s): abstenidos %d (sin buena %d, con buena %d) "
          "| aceptados %d (sin buena %d, aciertos %d)"
          % (str(t_elegido), conf["abstenidos"]["n"],
             conf["abstenidos"]["sin_pose_buena"],
             conf["abstenidos"]["con_pose_buena"],
             conf["aceptados"]["n"], conf["aceptados"]["sin_pose_buena"],
             conf["aceptados"]["aciertos_top1"]))
    guardar_artefacto(art, "r_rc4")

    # ── Bonus: clasificador de decidibilidad (AUC val) ──
    agg_train = [agregados_clasificador(d["pid"],
                                        por_pid_split["train"][d["pid"]],
                                        por_pid_raw["train"])
                 for d in datos_split["train"]]
    agg_val = [agregados_clasificador(d["pid"],
                                      por_pid_split["val"][d["pid"]],
                                      por_pid_raw["val"])
               for d in datos_split["val"]]
    clf = clasificador_decidibilidad(datos_split["train"], agg_train,
                                     datos_split["val"], agg_val)
    art["bonus_decidibilidad"] = clf
    print("  bonus decidibilidad: AUC val = %s (n=%d/%d; AUC train %s)"
          % (str(clf["auc_val"]), clf["n_val_usados"], clf["n_val_total"],
             str(clf["auc_train"])))
    guardar_artefacto(art, "bonus_decidibilidad")

    # ── Parte 2a: R-RC2 (split por pose) ──
    pool = sorted(splits["train"] + splits["val"] + splits["test"],
                  key=lambda r: (r["pid"], r["source"], r["file_stem"],
                                 r["model_idx"]))
    X_pool = v06.construir_X_raw({"pool": pool})["pool"]
    sp = split_pose_level(pool, X_pool, SEED_POSE_SPLIT)
    X_split_pl = {n: sp[n]["X_raw"] for n in ("train", "val", "test")}
    grupos_pl = {n: sp[n]["grupos"] for n in ("train", "val", "test")}
    modelos_pl = v06.preparar_modelos(X_split_pl, grupos_pl)
    y_pl = {n: -np.array([r["rmsd"] for r in sp[n]["registros"]],
                         dtype=np.float64)
            for n in ("train", "val", "test")}
    modelo_pl, metrica_pl = v06.entrenar_ranker(
        modelos_pl["train"]["B"], y_pl["train"], grupos_pl["train"],
        modelos_pl["val"]["B"], y_pl["val"], grupos_pl["val"])
    ev_pl_val = v06.evaluar_modelo(modelo_pl, modelos_pl["val"]["B"],
                                   sp["val"]["registros"], sp["val"]["pids"])
    ev_pl_test = v06.evaluar_modelo(modelo_pl, modelos_pl["test"]["B"],
                                    sp["test"]["registros"],
                                    sp["test"]["pids"])
    pids_train_pl = set(sp["train"]["pids"])
    pids_test_pl = set(sp["test"]["pids"])
    traslape = len(pids_test_pl & pids_train_pl)
    delta_rc2 = round(ev_pl_test["top1_rate"] - V06_TOP1_TEST_REFERENCIA, 4)
    veredicto_rc2 = ("LEAKAGE_PROBABLE" if delta_rc2 >= 0.05
                     else "SIN_EVIDENCIA_DE_LEAKAGE")
    art["r_rc2"] = {
        "config": {
            "seed": SEED_POSE_SPLIT,
            "proporciones_por_pose": list(PROP_POSE_SPLIT),
            "n_poses": {"train": len(sp["train"]["registros"]),
                        "val": len(sp["val"]["registros"]),
                        "test": len(sp["test"]["registros"])},
            "n_pids": {"train": len(pids_train_pl),
                       "val": len(set(sp["val"]["pids"])),
                       "test": len(pids_test_pl)},
            "eval_metric": metrica_pl,
            "best_iteration": int(getattr(modelo_pl, "best_iteration", -1)),
        },
        "n_pids_test_con_poses_en_train": traslape,
        "top1_test_pose_level": ev_pl_test["top1_rate"],
        "mediana_rmsd_test": ev_pl_test["mediana_rmsd"],
        "top1_val_pose_level": ev_pl_val["top1_rate"],
        "top1_test_complejo_nivel_referencia": V06_TOP1_TEST_REFERENCIA,
        "delta": delta_rc2,
        "veredicto": veredicto_rc2,
    }
    print("  R-RC2 (split por pose, seed %d): top1_test=%s vs %.4f "
          "(delta %+.4f) -> %s (traslape pids train/test: %d)"
          % (SEED_POSE_SPLIT, str(ev_pl_test["top1_rate"]),
             V06_TOP1_TEST_REFERENCIA, delta_rc2, veredicto_rc2, traslape))
    guardar_artefacto(art, "r_rc2")

    # ── Parte 2b: R-RC3 (test congelado) ──
    datos_vina_test = datos_vina_por_complejo(splits["test"],
                                              pids_split["test"])
    rc3_v06 = contar_rc3(datos_split["test"], UMBRAL_RC3)
    rc3_vina = contar_rc3(datos_vina_test, UMBRAL_RC3)
    art["r_rc3"] = {
        "umbral_rmsd_elegida": UMBRAL_RC3,
        "criterio": "pose elegida > 10 A y existe pose <= 2 A en el complejo",
        "v06": rc3_v06,
        "vina": rc3_vina,
    }
    print("  R-RC3 (test congelado): v0.6 %d/%d | Vina %d/%d"
          % (rc3_v06["n_casos"], rc3_v06["n_total"],
             rc3_vina["n_casos"], rc3_vina["n_total"]))
    guardar_artefacto(art, "r_rc3")

    # ── Parte 3: checkpoint de produccion ──
    best_it = int(getattr(modelo_b, "best_iteration", -1))
    booster = modelo_b.get_booster()[:best_it + 1]
    booster.save_model(str(MODELO_PROD))
    sha_modelo = sha256_archivo(MODELO_PROD)
    n_nan = sum(int(np.isnan(X_raw[n]).sum()) for n in ("train", "val", "test"))
    meta = {
        "modelo": "v0.6 XGBRanker rank:pairwise (selector oficial de Ruta C)",
        "archivo_modelo": str(MODELO_PROD.relative_to(PROJECT_ROOT)),
        "sha256_modelo": sha_modelo,
        "generated_at": ahora_iso(),
        "n_features_modelo": N_MODELO_B,
        "feature_names_233": (["z_" + f for f in FEATURES_TOTAL]
                              + ["pct_" + f for f in PCT_RAW]),
        "feature_names_raw_224": list(FEATURES_TOTAL),
        "orden_pct": list(PCT_RAW),
        "nan_fill_medians": None,
        "nota_nan": ("no se observan NaN en las 224 features raw "
                     "(n_nan_total=%d); la transformacion define "
                     "NaN -> 0 tras z/pct por seguridad" % n_nan),
        "hiperparametros": {**PARAMS, "eval_metric": metrica_b},
        "transformacion": ("z-score por columna dentro de cada complejo "
                           "(std == 0 -> z = 0); rangos percentiles 0-100 "
                           "(empates -> rango promedio) sobre las 9 features "
                           "de PCT_RAW; cada complejo se normaliza de forma "
                           "independiente; NaN -> 0 despues de transformar"),
        "train_pids": pids_split["train"],
        "n_train_complejos": len(pids_split["train"]),
        "n_train_poses": len(splits["train"]),
        "best_iteration": best_it,
        "n_trees_guardadas": best_it + 1,
        "nota_early_stopping": ("se guardan SOLO los arboles hasta "
                                "best_iteration (early stopping); la "
                                "inferencia reproduce exactamente "
                                "XGBRanker.predict"),
        "extractor_raw": ("las 224 features raw provienen del extractor "
                          "v0.5 (scripts/ruta_c_fase1_5_v05.py): shells 96 "
                          "+ ECIF-lite 56 + per-residuo 63 + geometricas 9. "
                          "Produccion DEBE ejecutar ese extractor para "
                          "poses nuevas (trabajo de Fase 4)."),
    }
    META_PROD.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    # ── verificacion de puntuar_complejo contra el test congelado ──
    cache = v06.cargar_cache_v05()
    import xgboost
    s_booster = cargar_booster_produccion().predict(
        xgboost.DMatrix(modelos["test"]["B"]))
    dif_global = float(np.max(np.abs(s_booster - scores_split["test"])))
    por_pid_pred = defaultdict(list)
    for r, s in zip(splits["test"], scores_split["test"]):
        por_pid_pred[r["pid"]].append(float(s))
    n_ok = 0
    max_dif = 0.0
    aciertos_fn = 0
    for pid in pids_split["test"]:
        regs = por_pid_raw["test"][pid]
        recs = registros_raw_224(regs, cache)
        s_fn = puntuar_complejo(recs)
        s_can = np.array(por_pid_pred[pid], dtype=np.float64)
        dif = float(np.max(np.abs(s_fn - s_can)))
        max_dif = max(max_dif, dif)
        idx_fn = int(np.argmax(s_fn))
        idx_can = int(np.argmax(s_can))
        mismo = (regs[idx_fn]["file_stem"], regs[idx_fn]["model_idx"]) == \
                (regs[idx_can]["file_stem"], regs[idx_can]["model_idx"])
        if mismo and dif < 1e-4:
            n_ok += 1
        if regs[idx_fn]["rmsd"] <= UMBRAL_POSITIVA:
            aciertos_fn += 1
    n_test = len(pids_split["test"])
    top1_fn = round(aciertos_fn / n_test, 4)
    verif = {
        "n_complejos_test": n_test,
        "n_concordancias_argmax": n_ok,
        "max_diferencia_scores": round(max_dif, 8),
        "max_diferencia_vs_xgbranker_test": round(dif_global, 8),
        "top1_puntuar_complejo": top1_fn,
        "top1_modelo": top1_retrain,
        "reproduce_top1_test": bool(top1_fn == top1_retrain),
        "reproduce_referencia_06596": bool(top1_fn == V06_TOP1_TEST_REFERENCIA),
    }
    art["checkpoint_produccion"] = {
        "modelo": str(MODELO_PROD.relative_to(PROJECT_ROOT)),
        "meta": str(META_PROD.relative_to(PROJECT_ROOT)),
        "sha256_modelo": sha_modelo,
        "verificacion_puntuar_complejo": verif,
    }
    print("  checkpoint: %s sha256=%s"
          % (str(MODELO_PROD.relative_to(PROJECT_ROOT)), sha_modelo[:16] + "..."))
    print("  puntuar_complejo: %d/%d concordancias argmax, max dif %.2e "
          "(global vs XGBRanker %.2e), top1 %s (modelo %s, referencia %.4f)"
          % (n_ok, n_test, max_dif, dif_global, str(top1_fn), str(top1_retrain),
             V06_TOP1_TEST_REFERENCIA))
    guardar_artefacto(art, "checkpoint")

    # ── detalle por complejo del test (para Fase 4) ──
    art["detalle_test"] = [
        {"pid": d["pid"], "n_poses": d["n_poses"], "margin": d["margin"],
         "p_top1": d["p_top1"], "top1_rmsd": round(d["top1_rmsd"], 3),
         "top1_ok": d["top1_ok"], "min_rmsd": round(d["min_rmsd"], 3),
         "tiene_pose_buena": d["tiene_pose_buena"]}
        for d in datos_split["test"]]

    art["caveats_honestos"] = [
        "El barrido de umbrales usa cuantiles de los margenes de VAL "
        "(40 complejos, ruido estadistico); el punto de operacion elegido "
        "sobre val puede trasladarse con varianza al test congelado.",
        "Complejos de 1 sola pose (1 en val, 2 en test) no tienen margen: "
        "se aceptan siempre (no hay desacuerdo interno que detectar).",
        "El clasificador de decidibilidad usa agregados computados con los "
        "scores v0.6 de TRAIN (in-sample para train; honesto para val). "
        "AUC val con n=39 (se excluye el complejo de 1 pose).",
        "R-RC2: el split por-pose degrada a v0.6 POR DISENO (la comparacion "
        "intra-complejo se rompe al partir los complejos en particiones); "
        "el criterio de refutacion es inflacion, no degradacion: "
        "pose-level < complejo-level -> sin evidencia de leakage.",
        "El umbral de abstencion se elige sobre VAL y se aplica a TEST una "
        "sola vez (sin tunear sobre test).",
        "Reproducibilidad del reentreno v0.6 documentada en 'reentreno_v06' "
        "(misma version de xgboost 3.2.0 y seed 42).",
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print("  artefacto: %s (%.1fs)"
          % (str(ARTIFACTO.relative_to(PROJECT_ROOT)), art["duracion_total_s"]))


if __name__ == "__main__":
    main()
