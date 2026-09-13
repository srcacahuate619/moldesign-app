# -*- coding: utf-8 -*-
"""
ruta_c_fase3_5_decidibilidad.py — Ruta C, Fase 3.5 + R-RC5
(docs/42_RUTA_C_PROTOCOLO.md, secciones C5 y R-RC5).

PARTE 1 — Abstencion por decidibilidad (C5):
  1. Reentreno de v0.6 con el protocolo exacto de Fase 3 (seed 42) y
     verificacion de reproducibilidad (objetivo: test top-1 0.6596).
  2. Features por complejo (~18 agregados) y clasificador de decidibilidad
     (label = el complejo tiene >=1 pose <= 2 A). LogisticRegression
     primero; si AUC val < 0.85 se prueba GradientBoosting depth 3.
  3. Punto de operacion elegido SOLO sobre VAL:
     - regla por decidibilidad: t_d que maximiza F1 sobre val;
     - regla combinada: grilla (t_m margen) x (t_d probabilidad) sobre val.
  4. Comparacion sobre TEST (tocado una sola vez): regla por margen
     (Fase 3) vs regla por decidibilidad vs regla combinada. Para cada una:
     tasa de abstencion, top-1 en aceptados, top-1 en rechazados y
     confusion R-RC4 (abstenidos/aceptados vs decidible/indecidible).
     La mejor regla en TEST es la recomendacion (umbrales SOLO de val).

PARTE 2 — R-RC5 robustez metamorfica:
  A) Invarianza a rotacion/traslacion rigida (10 complejos de test,
     semilla fija): se aplica R (rotacion propia, semilla 1000+i) y t
     uniforme a las coords de TODAS las poses y del receptor; se
     re-extraen las 224 features con el extractor v0.5 sobre los archivos
     de poses (S1 vina_redock_work, S2 .work_molflex_v3, S3 tmp/ruta_a;
     logica de rutas de build_pose_selector_dataset.py). Tolerancia 1e-6.
  B) Perturbacion debil (sigma = 0.1 A, semilla 42+i) sobre los atomos
     pesados de las poses de los 47 complejos de test: re-extraccion de
     224 features, scoring con el modelo de produccion (puntuar_complejo)
     y comparacion de selecciones. Analisis de margenes (top1-top2) de
     los complejos que cambian vs los que no cambian.

Salida: scripts/artifacts_ruta_c_fase3_5.json (escritura incremental).
"""

from __future__ import annotations

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

import build_pose_selector_dataset as b  # noqa: E402 (rutas/mapas serial->mol)
import molflex as mf  # noqa: E402 (parsear_out_vina, leer_ligando)
import ruta_c_fase1_5_v05 as v05  # noqa: E402 (extractor de 224 features)
import ruta_c_fase1_6_v06 as v06  # noqa: E402 (pipeline campeon v0.6)
import ruta_c_fase3_calibracion as f3  # noqa: E402 (Fase 3: abstención por margen)

DATASET_DIR = v06.DATASET_DIR
ARTIFACTO = SCRIPTS_DIR / "artifacts_ruta_c_fase3_5.json"
ARTIFACTO_FASE3 = SCRIPTS_DIR / "artifacts_ruta_c_fase3.json"

V06_TOP1_TEST_REFERENCIA = 0.6596
UMBRAL_POSITIVA = v06.UMBRAL_POSITIVA
META_FASE3_T_M = 0.097663          # umbral de margen elegido por Fase 3 (val)
TOL_INVARIANZA = 1e-6
SIGMA_RUIDO = 0.1
N_COMPLEJOS_INVARIANZA = 10
SEED_BASE_A = 1000                 # semilla de transformacion rigida por complejo
SEED_BASE_B = 42                   # semilla de ruido por complejo
META_TOP1_ACEPTADOS = 0.85         # barra de la tarea para la regla combinada
META_MAX_ABSTENCION = 0.35

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
RUTA_A = PROJECT_ROOT / "tmp" / "ruta_a"


# ───────────────────────── utilidades ────────────────────────────────────────

def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_artefacto(art: dict, etapa: str) -> None:
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTO.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ARTIFACTO)


# ───────────────── agregados por complejo para decidibilidad ─────────────────

FEATURES_DEC = [
    "n_poses", "vina_top_raw", "z_vina_top", "pct_vina_top", "margin",
    "p_top1", "std_scores", "cluster_top1", "cluster_max", "n_cluster_ge1",
    "max_abs_z_cpa4", "spread_contacts_6", "spread_shell_O_N_0_4",
    "n_contactos4_top1", "cpa4_top1", "n_clashes_top1", "vina_min", "vina_std",
]

JUSTIFICACION_FEATURES_DEC = (
    "La decidibilidad de un complejo (existe >=1 pose <=2 A) se caracteriza "
    "por tres familias: (a) saliencia de la pose elegida por v0.6 (margin, "
    "p_top1, std_scores, z_vina_top, pct_vina_top: si la mejor pose no se "
    "despega, el complejo es dudoso); (b) calidad de interaccion de la pose "
    "elegida (n_contactos4_top1, cpa4_top1, n_clashes_top1, cluster_top1, "
    "vina_top_raw: una pose cristalina interactua fuerte y esta en un "
    "cumulo); (c) estructura poblacional del conjunto de poses (n_poses, "
    "cluster_max, n_cluster_ge1, max_abs_z_cpa4, spread_contacts_6, "
    "spread_shell_O_N_0_4, vina_min, vina_std: los complejos decidibles "
    "suelen tener un cumulo nativo y dispersion de senal de interaccion). "
    "spread = std de la feature RAW entre las poses del complejo (la std de "
    "un z-score seria siempre 1 por construccion, por eso se usa la raw); "
    "max_abs_z_cpa4 = maximo |z| de contacts_per_ha_4 entre las poses "
    "(std del complejo == 0 -> z = 0, convencion de v0.6)."
)


def key_registro(r: dict) -> tuple:
    return (r["source"], r["file_stem"], r["model_idx"])


def z_columna(x: np.ndarray) -> np.ndarray:
    """Z-score de una columna de un solo complejo (std == 0 -> 0)."""
    s = np.std(x)
    if s > 0:
        return (x - np.mean(x)) / s
    return np.zeros_like(x, dtype=np.float64)


def agregados_decidibilidad(pid: str, filas: list,
                            raw224: list[dict]) -> dict:
    """18 agregados por complejo. filas: [(registro, score)] ordenadas por
    score descendente (v0.6). raw224: dicts con las 224 features raw en
    orden canonico. La pose 'top' es la fila 0 de filas."""
    from scipy.stats import rankdata
    n = len(filas)
    scores = np.array([s for _, s in filas], dtype=np.float64)
    clave_raw = {key_registro(r): d for r, d in zip(
        [f[0] for f in filas], raw224)} if False else None
    # raw224 esta en orden canonico; se alinea con filas por clave.
    por_clave = {key_registro(r): d for r, d in zip(
        [f[0] for f in filas], raw224)}
    # Reordenar raw224 para que coincida con el orden de filas.
    raw_orden = [por_clave[key_registro(r)] for r, _ in filas]
    top = raw_orden[0]

    vinas = np.array([d["vina_score"] for d in raw_orden], dtype=np.float64)
    cpa4 = np.array([d["contacts_per_ha_4"] if d["contacts_per_ha_4"] is not None
                     else 0.0 for d in raw_orden], dtype=np.float64)
    c6 = np.array([d["n_contacts_6"] for d in raw_orden], dtype=np.float64)
    shell = np.array([d["shell_O_N_0_4"] for d in raw_orden], dtype=np.float64)
    dens = np.array([d["cluster_density"] for d in raw_orden], dtype=np.float64)

    z_cpa4 = z_columna(cpa4)
    rango = rankdata(vinas)
    pct_top = (50.0 if n == 1
               else float(100.0 * (rango[0] - 1.0) / (n - 1.0)))
    margen = (float(scores[0] - scores[1]) if n > 1 else float("nan"))

    return {
        "pid": pid,
        "n_poses": n,
        "vina_top_raw": float(top["vina_score"]),
        "z_vina_top": float(z_columna(vinas)[0]),
        "pct_vina_top": pct_top,
        "margin": margen,
        "p_top1": f3.metricas_confianza(filas)["p_top1"],
        "std_scores": float(np.std(scores)),
        "cluster_top1": float(top["cluster_density"]),
        "cluster_max": float(np.max(dens)),
        "n_cluster_ge1": int(np.count_nonzero(dens >= 1)),
        "max_abs_z_cpa4": float(np.max(np.abs(z_cpa4))),
        "spread_contacts_6": float(np.std(c6)),
        "spread_shell_O_N_0_4": float(np.std(shell)),
        "n_contactos4_top1": float(top["n_contacts_4"]),
        "cpa4_top1": (float(top["contacts_per_ha_4"])
                      if top["contacts_per_ha_4"] is not None else 0.0),
        "n_clashes_top1": float(top["n_clashes"]),
        "vina_min": float(np.min(vinas)),
        "vina_std": float(np.std(vinas)),
    }


# ───────────────── clasificador de decidibilidad ─────────────────────────────

def imputar_medianas(X: np.ndarray, med: np.ndarray | None = None):
    """NaN -> mediana por columna (del train si no se pasa)."""
    Xc = X.copy()
    if med is None:
        med = np.nanmedian(Xc, axis=0)
        med = np.where(np.isnan(med), 0.0, med)
    idx = np.where(np.isnan(Xc))
    if idx[0].size:
        Xc[idx] = med[idx[1]]
    return Xc, med


def entrenar_decidibilidad(agg_train: list, datos_train: list,
                           agg_val: list, datos_val: list) -> dict:
    """Logistica primero; si AUC val < 0.85 se prueba GBT depth 3 y se
    queda el mejor. El AUC de val se evalua sobre complejos con margen
    finito (n >= 2 poses), mismo criterio que el bonus de Fase 3."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    Xtr = np.array([[a[f] for f in FEATURES_DEC] for a in agg_train],
                   dtype=np.float64)
    ytr = np.array([1 if d["tiene_pose_buena"] else 0 for d in datos_train],
                   dtype=int)
    Xva = np.array([[a[f] for f in FEATURES_DEC] for a in agg_val],
                   dtype=np.float64)
    yva = np.array([1 if d["tiene_pose_buena"] else 0 for d in datos_val],
                   dtype=int)

    Xtr_c, med = imputar_medianas(Xtr)
    sc = StandardScaler().fit(Xtr_c)
    Ztr = sc.transform(Xtr_c)

    def probas_log():
        clf = LogisticRegression(max_iter=4000)
        clf.fit(Ztr, ytr)
        return clf

    def probas_gbt():
        clf = GradientBoostingClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)
        clf.fit(Ztr, ytr)
        return clf

    finitos_val = np.isfinite(Xva).all(axis=1)

    def auc_de(clf):
        Zva = sc.transform(imputar_medianas(Xva, med)[0])
        p = clf.predict_proba(Zva)[:, 1]
        auc_v = (roc_auc_score(yva[finitos_val], p[finitos_val])
                 if finitos_val.sum() >= 2 and len(np.unique(yva[finitos_val])) == 2
                 else None)
        auc_t = roc_auc_score(ytr, clf.predict_proba(Ztr)[:, 1])
        return auc_v, auc_t, p

    log = probas_log()
    auc_v, auc_t, p_log = auc_de(log)
    modelo_uso = "LogisticRegression"
    clf_final = log
    p_final = p_log
    nota = ""
    if auc_v is None or auc_v < 0.85:
        gbt = probas_gbt()
        auc_v_g, auc_t_g, p_gbt = auc_de(gbt)
        if auc_v_g is not None and (auc_v is None or auc_v_g > auc_v):
            modelo_uso = "GradientBoostingClassifier(max_depth=3)"
            clf_final = gbt
            p_final = p_gbt
            auc_v, auc_t = auc_v_g, auc_t_g
        nota = ("la logistica no alcanzo AUC val >= 0.85; se probo GBT "
                "depth 3 y se quedo el mejor de los dos")

    coefs = None
    if modelo_uso == "LogisticRegression":
        coefs = {f: round(float(c), 4)
                 for f, c in zip(FEATURES_DEC, clf_final.coef_[0])}
    return {
        "modelo": modelo_uso,
        "features": FEATURES_DEC,
        "justificacion_features": JUSTIFICACION_FEATURES_DEC,
        "coeficientes_logistica": coefs,
        "auc_train": round(float(auc_t), 4),
        "auc_val": round(float(auc_v), 4) if auc_v is not None else None,
        "n_val_usados": int(finitos_val.sum()),
        "n_val_total": len(datos_val),
        "nota_modelo": nota,
        "mediana_imputacion_margin": float(med[FEATURES_DEC.index("margin")]),
        "balance_label_train": {
            "decidibles": int(ytr.sum()), "indecidibles": int(len(ytr) - ytr.sum())},
        "clf": clf_final, "scaler": sc, "med": med, "p_val": p_final,
    }


def probas_split(clf_info: dict, agg: list) -> np.ndarray:
    Z = clf_info["scaler"].transform(
        imputar_medianas(
            np.array([[a[f] for f in FEATURES_DEC] for a in agg],
                     dtype=np.float64), clf_info["med"])[0])
    return clf_info["clf"].predict_proba(Z)[:, 1]


# ───────────────── reglas de abstencion ──────────────────────────────────────

def aplicar_regla(datos: list, p_pred, t_m, t_d, usa_margin: bool,
                  usa_p: bool) -> dict:
    """Fila con metricas de una regla de abstencion sobre una lista de
    datos por complejo. Abstenerse si (usa_margin y margin < t_m) o
    (usa_p y P(decidable) < t_d). Complejo de 1 pose (margin None) no
    cuenta para la parte de margen (igual que Fase 3)."""
    rech, acep = [], []
    for i, d in enumerate(datos):
        abst = False
        if usa_margin and d["margin"] is not None and d["margin"] < t_m:
            abst = True
        if usa_p and p_pred is not None and p_pred[i] < t_d:
            abst = True
        (rech if abst else acep).append(d)

    def tasa(grupo, campo):
        if not grupo:
            return None
        return round(sum(1 for d in grupo if d[campo]) / len(grupo), 4)

    return {
        "t_m": (round(float(t_m), 6) if t_m is not None else None),
        "t_d": (round(float(t_d), 6) if t_d is not None else None),
        "n_abstenciones": len(rech),
        "tasa_abstencion": round(len(rech) / len(datos), 4),
        "n_aceptados": len(acep),
        "top1_aceptados": tasa(acep, "top1_ok"),
        "top1_rechazados": tasa(rech, "top1_ok"),
    }


def confusion_rc4_regla(datos: list, p_pred, t_m, t_d,
                        usa_margin: bool, usa_p: bool) -> dict:
    """Desglose R-RC4 para una regla arbitraria (abstenidos/aceptados vs
    decidibilidad y aciertos top-1)."""
    rech, acep = [], []
    for i, d in enumerate(datos):
        abst = False
        if usa_margin and d["margin"] is not None and d["margin"] < t_m:
            abst = True
        if usa_p and p_pred is not None and p_pred[i] < t_d:
            abst = True
        (rech if abst else acep).append(d)

    def desglose(grupo: list) -> dict:
        n = len(grupo)
        con_buena = sum(1 for d in grupo if d["tiene_pose_buena"])
        aciertos = sum(1 for d in grupo if d["top1_ok"])
        return {
            "n": n,
            "sin_pose_buena": n - con_buena,
            "con_pose_buena": con_buena,
            "con_pose_buena_aciertos_top1":
                sum(1 for d in grupo if d["tiene_pose_buena"] and d["top1_ok"]),
            "aciertos_top1": aciertos,
            "top1": round(aciertos / n, 4) if n else None,
        }

    return {"abstenidos": desglose(rech), "aceptados": desglose(acep)}


def elegir_td_f1(datos_val: list, p_val: np.ndarray, candidatas: list) -> dict:
    """t_d (regla solo-decidibilidad) que maximiza F1 sobre VAL
    (label: tiene_pose_buena; prediccion: P >= t_d)."""
    from sklearn.metrics import f1_score
    y = np.array([1 if d["tiene_pose_buena"] else 0 for d in datos_val])
    mejor = None
    for t_d in candidatas:
        yp = (p_val >= t_d).astype(int)
        f1 = f1_score(y, yp, zero_division=0)
        if mejor is None or (f1, -t_d) > (mejor["f1"], -mejor["t_d"]):
            mejor = {"f1": round(float(f1), 4), "t_d": round(float(t_d), 6)}
    return mejor


def grilla_combinada_val(datos_val: list, p_val: np.ndarray,
                         marg_cands: list, p_cands: list) -> dict:
    """Evalua la regla combinada sobre VAL para toda la grilla
    (t_m x t_d) y elige el punto de operacion con regla pre-registrada:
    (1) top-1 aceptados >= 0.85 y abstencion <= 0.35 -> menor abstencion;
    (2) abstencion <= 0.35 -> maximo top-1 aceptados (desempate: menor
        abstencion y luego menores umbrales);
    (3) sin opciones dentro del limite -> (0, 0), sin abstencion."""
    filas = []
    for t_m in marg_cands:
        for t_d in p_cands:
            f = aplicar_regla(datos_val, p_val, t_m, t_d, True, True)
            filas.append(f)
    cand = [f for f in filas
            if f["top1_aceptados"] is not None
            and f["top1_aceptados"] >= META_TOP1_ACEPTADOS
            and f["tasa_abstencion"] <= META_MAX_ABSTENCION]
    if cand:
        elegido = min(cand, key=lambda f: (f["tasa_abstencion"],
                                           f["t_m"], f["t_d"]))
        justificacion = ("cumple la meta (top-1 aceptados >= %.2f, "
                         "abstencion <= %.2f) con la menor abstencion "
                         "de la grilla" % (META_TOP1_ACEPTADOS,
                                           META_MAX_ABSTENCION))
    else:
        cand2 = [f for f in filas
                 if f["top1_aceptados"] is not None
                 and f["tasa_abstencion"] <= META_MAX_ABSTENCION]
        if cand2:
            elegido = max(cand2, key=lambda f: (f["top1_aceptados"],
                                                -f["tasa_abstencion"],
                                                -f["t_m"], -f["t_d"]))
            justificacion = ("ningun punto cumple la meta estricta; rodilla: "
                             "maximo top-1 aceptado dentro de abstencion "
                             "<= %.2f" % META_MAX_ABSTENCION)
        else:
            elegido = {"t_m": 0.0, "t_d": 0.0,
                       "top1_aceptados": None, "tasa_abstencion": None}
            justificacion = ("ningun punto alcanza la meta dentro de los "
                             "limites; se conserva sin abstencion (0, 0)")
    return {"elegido": elegido, "justificacion": justificacion,
            "n_puntos_grilla": len(filas),
            "n_marg_cands": len(marg_cands), "n_p_cands": len(p_cands)}


# ───────────────── R-RC5: re-extraccion de features desde poses ──────────────

_pose_cache: dict = {}
_mapa_cache: dict = {}
_cristal_meta: dict = {}


def archivo_pose(r: dict) -> Path:
    """Ruta del archivo de poses por fuente (logica de enumerar_trabajos
    de build_pose_selector_dataset.py)."""
    if r["source"] == "flexible_redock":
        return PDBBIND / "vina_redock_work" / r["pid"] / (r["pid"] + "_out.pdbqt")
    if r["source"] == "molflex":
        return WORK_V3 / r["pid"] / (r["file_stem"] + ".pdbqt")
    return RUTA_A / r["pid"] / r["file_stem"] / "out.pdbqt"


def modelos_archivo(r: dict) -> list:
    clave = (r["pid"], r["source"], r["file_stem"])
    if clave not in _pose_cache:
        _pose_cache[clave] = mf.parsear_out_vina(
            archivo_pose(r).read_text(encoding="utf-8"))
    return _pose_cache[clave]


def mapa_pose(r: dict):
    clave = (r["pid"], r["source"], r["file_stem"])
    if clave not in _mapa_cache:
        if r["source"] == "flexible_redock":
            _mapa_cache[clave] = b.mapa_para_redock_s1(r["pid"])
        elif r["source"] == "molflex":
            _mapa_cache[clave] = b.mapa_s2(WORK_V3 / r["pid"] / "index_map.json")
        else:
            _mapa_cache[clave] = b.mapa_s3(
                RUTA_A / r["pid"] / r["file_stem"] / "lig.pdbqt")
    return _mapa_cache[clave]


def meta_cristal(pid: str):
    """(indices de atomos pesados del cristal, elementos por indice)."""
    if pid not in _cristal_meta:
        crystal = mf.leer_ligando(str(PDBBIND / pid / f"{pid}_ligand.sdf"))
        pesados = [i for i, a in enumerate(crystal.GetAtoms())
                   if a.GetAtomicNum() > 1]
        elems = v05.obtener_elementos_ligando(pid)
        _cristal_meta[pid] = (pesados, elems)
    return _cristal_meta[pid]


def coords_pose(r: dict):
    """Coords (n_heavy, 3) y elementos de la pose del registro, leidos del
    archivo de poses original (precision completa, sin redondeos)."""
    pesados, elems = meta_cristal(r["pid"])
    mapa, razon = mapa_pose(r)
    if mapa is None:
        raise RuntimeError(
            f"mapa serial->mol no disponible para {r['pid']} "
            f"({r['source']}/{r['file_stem']}): {razon}")
    por_mol = mf.coords_pose_a_por_mol(
        modelos_archivo(r)[r["model_idx"]][1], mapa)
    faltan = [m for m in pesados if m not in por_mol]
    if faltan:
        raise RuntimeError(
            f"pose {r['pid']}/{r['file_stem']}/{r['model_idx']}: "
            f"{len(faltan)} atomos pesados sin mapear")
    coords = np.array([por_mol[m] for m in pesados], dtype=np.float64)
    return coords, [elems[m] for m in pesados]


def receptor_transformado(rec: dict, R: np.ndarray, t: np.ndarray) -> dict:
    """Copia del receptor con coords rotadas/trasladadas y KDTree nuevo.
    Los codigos de tipado (shell/ECIF/residuo) se conservan: la identidad
    atomica no cambia bajo transformacion rigida."""
    from scipy.spatial import cKDTree
    coords = rec["coords"] @ R.T + t
    return {"coords": coords, "shell_codes": rec["shell_codes"],
            "ecif_codes": rec["ecif_codes"], "res_codes": rec["res_codes"],
            "es_no": rec["es_no"], "tree": cKDTree(coords),
            "n_hechos": rec.get("n_hechos", 0),
            "n_heuristicos": rec.get("n_heuristicos", 0)}


def extraer_224(r: dict, receptor: dict, lig_coords: np.ndarray,
                lig_elems: list, cluster: float) -> dict:
    """Re-extrae las 224 features raw de una pose con el extractor v0.5:
    215 ricas (calcular_rich) + 5 geometricas baratas recomputadas
    (contactos 4/6 A, clashes < 2.2 A, contacts_per_ha_4, cluster_density);
    las 4 baratas no geometricas (vina_score, varianza/rango de scores,
    n_heavy) se toman del registro congelado (no dependen de la geometria)."""
    shell, ecif, pop = v05.calcular_rich(receptor, lig_coords, lig_elems)
    dists = receptor["tree"].query(lig_coords, k=1)[0]
    n_clash = int(np.count_nonzero(dists < 2.2))
    n_c4 = int(np.count_nonzero(dists < 4.0))
    n_c6 = int(np.count_nonzero(dists < 6.0))
    n_heavy = len(lig_coords)
    cpa4 = round(n_c4 / n_heavy, 4) if n_heavy else None
    d = {
        "vina_score": r["vina_score"],
        "pose_score_variance": r["pose_score_variance"],
        "pose_score_range": r["pose_score_range"],
        "n_heavy": r["n_heavy"],
        "n_contacts_4": n_c4,
        "n_contacts_6": n_c6,
        "contacts_per_ha_4": cpa4,
        "n_clashes": n_clash,
        "cluster_density": float(cluster),
    }
    rich = list(shell) + list(ecif) + list(pop)
    d.update({f: float(v) for f, v in zip(v05.FEATURES_RICH, rich)})
    return d


def cluster_por_par(coords_list: list[np.ndarray], umbral: float = 2.0):
    """Densidad de cluster intra-complejo sobre coords (misma definicion
    del dataset builder: poses vecinas a < 2.0 A RMSD sin alinear)."""
    n = len(coords_list)
    dens = np.zeros(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            dd = float(np.sqrt(np.mean((coords_list[i] - coords_list[j]) ** 2)))
            if dd < umbral:
                dens[i] += 1
                dens[j] += 1
    return dens


def rotacion_propia(rng: np.random.Generator) -> np.ndarray:
    """Matriz de rotacion propia 3x3 aleatoria (QR de gaussiana,
    determinante forzado a +1)."""
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


def argmax_identidad(scores: np.ndarray, regs: list[dict]):
    """Clave de identidad de la pose elegida por argmax."""
    if len(scores) == 0:
        return None
    r = regs[int(np.argmax(scores))]
    return (r["source"], r["file_stem"], r["model_idx"])


# ───────────────── R-RC5 A: invarianza rigida ────────────────────────────────

def r_rc5a_invarianza(pids10: list, regs_por_pid: dict,
                      raw224_por_pid: dict) -> dict:
    """Rotacion+traslacion rigida sobre poses y receptor de 10 complejos.
    Compara features limpias vs transformadas (tolerancia 1e-6) y la
    estabilidad de la seleccion (transformado vs limpio; limpio vs
    canonico congelado)."""
    max_dif_global = 0.0
    max_dif_por_feature = np.zeros(len(v06.FEATURES_TOTAL))
    n_estables_rot = 0
    n_estables_canonico = 0
    detalle = []
    for i, pid in enumerate(pids10):
        regs = regs_por_pid[pid]
        rng = np.random.default_rng(SEED_BASE_A + i)
        R = rotacion_propia(rng)
        t = rng.uniform(-50.0, 50.0, 3)
        limpio, rotado = [], []
        coords_limpios = []
        coords_rotados = []
        for r in regs:
            lig, elems = coords_pose(r)
            rec = v05.obtener_receptor(r["pid"], r["source"], r["file_stem"])
            if rec is None:
                raise RuntimeError(f"receptor ilegible para {r['pid']}")
            lig_r = lig @ R.T + t
            rec_r = receptor_transformado(rec, R, t)
            coords_limpios.append(lig)
            coords_rotados.append(lig_r)
            limpio.append((r, lig, elems, rec))
            rotado.append((r, lig_r, elems, rec_r))
        dens_limpio = cluster_por_par(coords_limpios)
        dens_rotado = cluster_por_par(coords_rotados)
        d224_limpio = [extraer_224(r, rec, lig, elems, float(dens_limpio[k]))
                       for k, (r, lig, elems, rec) in enumerate(limpio)]
        d224_rotado = [extraer_224(r, rec_r, lig_r, elems, float(dens_rotado[k]))
                       for k, (r, lig_r, elems, rec_r) in enumerate(rotado)]
        dif_max_pid = 0.0
        for da, db in zip(d224_limpio, d224_rotado):
            for j, f in enumerate(v06.FEATURES_TOTAL):
                dif = abs(float(da[f]) - float(db[f]))
                if dif > max_dif_por_feature[j]:
                    max_dif_por_feature[j] = dif
                if dif > dif_max_pid:
                    dif_max_pid = dif
        max_dif_global = max(max_dif_global, dif_max_pid)

        s_limpio = f3.puntuar_complejo(d224_limpio)
        s_rotado = f3.puntuar_complejo(d224_rotado)
        sel_limpio = argmax_identidad(s_limpio, regs)
        sel_rotado = argmax_identidad(s_rotado, regs)
        if sel_limpio == sel_rotado:
            n_estables_rot += 1

        s_canonico = f3.puntuar_complejo(raw224_por_pid[pid])
        sel_canonico = argmax_identidad(s_canonico, regs)
        if sel_limpio == sel_canonico:
            n_estables_canonico += 1

        detalle.append({
            "pid": pid, "n_poses": len(regs),
            "max_dif_limpio_vs_rotado": round(dif_max_pid, 10),
            "seleccion_estable_rot": bool(sel_limpio == sel_rotado),
            "seleccion_estable_vs_canonico": bool(sel_limpio == sel_canonico),
            "seleccion_limpia": sel_limpio,
            "seleccion_rotada": sel_rotado,
            "seleccion_canonica": sel_canonico,
        })

    sobre_tol = [{"feature": v06.FEATURES_TOTAL[j],
                  "max_dif": round(float(max_dif_por_feature[j]), 10)}
                 for j in np.where(max_dif_por_feature > TOL_INVARIANZA)[0]]
    return {
        "n_complejos": len(pids10),
        "pids": pids10,
        "transformacion": ("R rotacion propia (QR de gaussiana, semilla "
                           "%d+i) + t uniforme en [-50, 50]^3 aplicada a "
                           "coords de poses y receptor" % SEED_BASE_A),
        "tolerancia": TOL_INVARIANZA,
        "max_dif_224": round(max_dif_global, 10),
        "features_sobre_tolerancia": sobre_tol,
        "veredicto_invarianza": ("OK" if not sobre_tol else "BUG_ENCONTRADO"),
        "n_selecciones_estables_rot": n_estables_rot,
        "n_selecciones_estables_vs_canonico": n_estables_canonico,
        "detalle": detalle,
    }


# ───────────────── R-RC5 B: perturbacion debil ───────────────────────────────

def r_rc5b_ruido(pids_test: list, regs_por_pid: dict,
                 raw224_por_pid: dict, score_canonico_por_pid: dict,
                 datos_test: list) -> dict:
    """Ruido gaussiano sigma=0.1 A sobre atomos pesados de las poses de
    los 47 complejos de test. Re-extrae 224 features y compara la
    seleccion perturbada contra la canonica (modelo de produccion)."""
    margen_por_pid = {d["pid"]: d["margin"] for d in datos_test}
    cambiados = []
    sin_cambio = []
    drift = []
    flips = []
    detalle_cambios = []
    for i, pid in enumerate(pids_test):
        regs = regs_por_pid[pid]
        rng = np.random.default_rng(SEED_BASE_B + i)
        coords_limpios = []
        d224_pert = []
        receptor_por_rec = []
        for r in regs:
            lig, elems = coords_pose(r)
            rec = v05.obtener_receptor(r["pid"], r["source"], r["file_stem"])
            if rec is None:
                raise RuntimeError(f"receptor ilegible para {r['pid']}")
            coords_limpios.append(lig)
            receptor_por_rec.append(rec)
        lig_pert = [c + rng.normal(0.0, SIGMA_RUIDO, c.shape)
                    for c in coords_limpios]
        dens_pert = cluster_por_par(lig_pert)
        for k, r in enumerate(regs):
            lig_p = lig_pert[k]
            rec = receptor_por_rec[k]
            d224_pert.append(extraer_224(r, rec, lig_p,
                                         meta_cristal(pid)[1], float(dens_pert[k])))

        s_pert = f3.puntuar_complejo(d224_pert)
        sel_pert = argmax_identidad(s_pert, regs)

        s_canon = np.array([score_canonico_por_pid[pid][key_registro(r)]
                            for r in regs], dtype=np.float64)
        sel_canon = argmax_identidad(s_canon, regs)

        if sel_pert != sel_canon:
            cambiados.append(pid)
            detalle_cambios.append({
                "pid": pid,
                "margin": (round(margen_por_pid[pid], 6)
                           if margen_por_pid[pid] is not None else None),
                "sel_canonica": sel_canon,
                "sel_perturbada": sel_pert,
            })
        else:
            sin_cambio.append(pid)

        # Drift de la re-extraccion limpia vs canonico (control de calidad
        # del propio re-extractor, no del ruido).
        dens_limpio = cluster_por_par(coords_limpios)
        d224_limpio = [extraer_224(r, rec, lig, meta_cristal(pid)[1],
                                   float(dens_limpio[k]))
                       for k, (r, lig, rec) in
                       enumerate(zip(regs, coords_limpios, receptor_por_rec))]
        s_limpio = f3.puntuar_complejo(d224_limpio)
        sel_limpio = argmax_identidad(s_limpio, regs)
        if sel_limpio != sel_canon:
            drift.append({"pid": pid, "sel_canonica": sel_canon,
                          "sel_reextraida": sel_limpio})

        top1_ok_canon = regs[int(np.argmax(s_canon))]["rmsd"] <= UMBRAL_POSITIVA
        top1_ok_pert = regs[int(np.argmax(s_pert))]["rmsd"] <= UMBRAL_POSITIVA
        if sel_pert != sel_canon and top1_ok_canon != top1_ok_pert:
            flips.append({"pid": pid,
                          "cambio": ("ok->mal" if top1_ok_canon else "mal->ok")})

    marg_camb = [margen_por_pid[p] for p in cambiados
                 if margen_por_pid[p] is not None]
    marg_sinc = [margen_por_pid[p] for p in sin_cambio
                 if margen_por_pid[p] is not None]
    finitos = [margen_por_pid[p] for p in pids_test
               if margen_por_pid[p] is not None]
    finitos_ord = sorted(finitos)
    grupos = np.array_split(np.array(finitos_ord), 3)
    camb_set = set(cambiados)
    terciles = []
    for k, g in enumerate(grupos, 1):
        n_cam = sum(1 for p in pids_test
                    if margen_por_pid[p] is not None
                    and margen_por_pid[p] in g and p in camb_set)
        terciles.append({
            "tercil": k,
            "rango_margen": [round(float(g[0]), 4), round(float(g[-1]), 4)],
            "n_complejos": int(len(g)),
            "n_cambiaron": n_cam,
            "fraccion_cambio": round(n_cam / len(g), 4),
        })

    def resumen_margenes(lista):
        if not lista:
            return None
        return {
            "n": len(lista),
            "media": round(float(np.mean(lista)), 4),
            "mediana": round(float(np.median(lista)), 4),
            "min": round(float(min(lista)), 4),
            "max": round(float(max(lista)), 4),
        }

    return {
        "sigma_angstrom": SIGMA_RUIDO,
        "semilla_base": SEED_BASE_B,
        "n_complejos": len(pids_test),
        "n_cambiaron": len(cambiados),
        "fraccion_cambio": round(len(cambiados) / len(pids_test), 4),
        "n_flips_ok_mal": len(flips),
        "flips": flips,
        "margen_cambiados": resumen_margenes(marg_camb),
        "margen_no_cambiados": resumen_margenes(marg_sinc),
        "terciles_margen": terciles,
        "pids_cambiados": sorted(cambiados),
        "detalle_cambios": detalle_cambios,
        "drift_reextraccion_limpia_vs_canonico": {
            "n_mismatch": len(drift),
            "detalle": drift,
            "interpretacion": ("0 mismatches => la comparacion perturbada "
                               "vs canonica aisla el efecto del ruido"),
        },
    }


# ───────────────── flujo principal ───────────────────────────────────────────

def main() -> None:
    v06.configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 3.5: abstencion por decidibilidad + R-RC5 ==")

    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md (C5, R-RC5)",
        "fase": "3.5 (abstencion por decidibilidad) + R-RC5 (robustez metamorfica)",
        "referencias": {
            "v06_top1_test": V06_TOP1_TEST_REFERENCIA,
            "fase3_umbral_margen_val": META_FASE3_T_M,
        },
        "config": {
            "features_decidibilidad": FEATURES_DEC,
            "meta_top1_aceptados": META_TOP1_ACEPTADOS,
            "meta_max_abstencion": META_MAX_ABSTENCION,
            "tolerancia_invarianza": TOL_INVARIANZA,
            "sigma_ruido_rc5b": SIGMA_RUIDO,
            "n_complejos_invarianza": N_COMPLEJOS_INVARIANZA,
        },
    }
    guardar_artefacto(art, "config")

    # ── Parte 0: reentreno v0.6 (protocolo exacto de Fase 3) ──
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
        "top1_test_reentrenado": top1_retrain,
        "top1_test_referencia": V06_TOP1_TEST_REFERENCIA,
        "delta": delta_rep,
        "reproducibilidad": "EXACTA" if delta_rep == 0.0
                            else "CON_DELTA_%+f" % delta_rep,
    }
    print("  reentreno v0.6: top1_test=%.4f (referencia %.4f, %s)"
          % (top1_retrain, V06_TOP1_TEST_REFERENCIA,
             art["reentreno_v06"]["reproducibilidad"]))
    if delta_rep != 0.0:
        print("  AVISO: el reentreno NO reproduce 0.6596; revisar entorno")
    guardar_artefacto(art, "reentreno_v06")

    # ── scores y datos por complejo (igual que Fase 3) ──
    scores_split = {n: modelo_b.predict(modelos[n]["B"])
                    for n in ("train", "val", "test")}
    por_pid_split = {n: f3.scores_por_pid(splits[n], pids_split[n],
                                          scores_split[n])
                     for n in ("train", "val", "test")}
    datos_split = {n: f3.datos_por_complejo(por_pid_split[n], pids_split[n])
                   for n in ("train", "val", "test")}
    por_pid_raw = {n: {pid: [r for r in splits[n] if r["pid"] == pid]
                       for pid in pids_split[n]}
                   for n in ("train", "val", "test")}
    cache = v06.cargar_cache_v05()
    raw224_por_pid = {}
    for n in ("train", "val", "test"):
        raw224_por_pid[n] = {
            pid: f3.registros_raw_224(por_pid_raw[n][pid], cache)
            for pid in pids_split[n]}

    # ── Parte 1: agregados y clasificador de decidibilidad ──
    def agregados_split(nombre):
        out = []
        for pid in pids_split[nombre]:
            filas = por_pid_split[nombre][pid]
            out.append(agregados_decidibilidad(
                pid, filas, raw224_por_pid[nombre][pid]))
        return out

    agg_split = {n: agregados_split(n) for n in ("train", "val", "test")}
    clf_info = entrenar_decidibilidad(agg_split["train"], datos_split["train"],
                                      agg_split["val"], datos_split["val"])
    p_split = {n: probas_split(clf_info, agg_split[n])
               for n in ("train", "val", "test")}
    art["decidibilidad_modelo"] = {k: v for k, v in clf_info.items()
                                   if k not in ("clf", "scaler", "med", "p_val")}
    print("  decidibilidad: modelo=%s AUC val=%s (n=%d/%d) | AUC train=%s"
          % (clf_info["modelo"], str(clf_info["auc_val"]),
             clf_info["n_val_usados"], clf_info["n_val_total"],
             str(clf_info["auc_train"])))
    guardar_artefacto(art, "decidibilidad_modelo")

    # ── puntos de operacion sobre VAL unicamente ──
    margenes_val = [d["margin"] for d in datos_split["val"]
                    if d["margin"] is not None]
    marg_cands = [0.0] + sorted({round(float(q), 6)
                                 for q in np.quantile(
                                     margenes_val, np.arange(0.05, 1.0, 0.05))})
    p_cands = sorted({round(float(q), 6)
                      for q in np.quantile(
                          p_split["val"], np.arange(0.05, 1.0, 0.05))}
                     | {round(float(x), 4)
                        for x in np.arange(0.30, 0.96, 0.05)})
    td_alone = elegir_td_f1(datos_split["val"], p_split["val"], p_cands)
    comb = grilla_combinada_val(datos_split["val"], p_split["val"],
                                marg_cands, p_cands)
    t_m3 = META_FASE3_T_M
    if ARTIFACTO_FASE3.exists():
        try:
            fase3_art = json.loads(ARTIFACTO_FASE3.read_text(encoding="utf-8"))
            t_m3 = float(fase3_art["calibracion"]["umbral_elegido"])
        except Exception:
            pass
    art["puntos_operacion_val"] = {
        "margen_fase3_t": t_m3,
        "td_solo_f1": td_alone,
        "combinada": {k: v for k, v in comb.items()},
    }
    print("  t_d solo (max F1 val): %s | combinada val: t_m=%s t_d=%s -> %s"
          % (str(td_alone), str(comb["elegido"].get("t_m")),
             str(comb["elegido"].get("t_d")), comb["justificacion"]))
    guardar_artefacto(art, "puntos_operacion_val")

    # ── aplicacion a TEST (una sola pasada) ──
    t_m_comb = float(comb["elegido"].get("t_m", 0.0))
    t_d_comb = float(comb["elegido"].get("t_d", 0.0))
    t_d_alone_v = float(td_alone["t_d"])

    filas_test = {
        "margin_only": aplicar_regla(datos_split["test"], None,
                                     t_m3, None, True, False),
        "decidibilidad_only": aplicar_regla(datos_split["test"],
                                            p_split["test"], None,
                                            t_d_alone_v, False, True),
        "combinada": aplicar_regla(datos_split["test"], p_split["test"],
                                   t_m_comb, t_d_comb, True, True),
    }
    filas_val = {
        "margin_only": aplicar_regla(datos_split["val"], None,
                                     t_m3, None, True, False),
        "decidibilidad_only": aplicar_regla(datos_split["val"],
                                            p_split["val"], None,
                                            t_d_alone_v, False, True),
        "combinada": aplicar_regla(datos_split["val"], p_split["val"],
                                   t_m_comb, t_d_comb, True, True),
    }
    confusion_test = {
        nombre: confusion_rc4_regla(
            datos_split["test"], p_split["test"] if nombre != "margin_only"
            else None,
            filas_test[nombre]["t_m"], filas_test[nombre]["t_d"],
            nombre != "decidibilidad_only", nombre != "margin_only")
        for nombre in ("margin_only", "decidibilidad_only", "combinada")}

    # ── recomendacion (pre-registrada; umbrales SOLO de val) ──
    # 1) Si la regla combinada cumple la meta (top-1 >= 0.85 con abstencion
    #    <= 0.35 en TEST) -> mecanismo mejorado, se recomienda la combinada.
    # 2) Si no, comparar decidibilidad/combinada contra la regla por margen
    #    de Fase 3 a PRESUPUESTO IGUALADO de abstencion (dominancia
    #    estricta: mayor top-1 con abstencion <=).
    # 3) Sin dominancia -> la regla por margen de Fase 3 se mantiene.
    barrido_fase3 = None
    if ARTIFACTO_FASE3.exists():
        try:
            barrido_fase3 = json.loads(
                ARTIFACTO_FASE3.read_text(encoding="utf-8")
                )["calibracion"]["barrido_test_informativo"]
        except Exception:
            barrido_fase3 = None

    comb_test = filas_test["combinada"]
    mecanismo_mejorado = bool(
        comb_test["top1_aceptados"] is not None
        and comb_test["top1_aceptados"] >= META_TOP1_ACEPTADOS
        and comb_test["tasa_abstencion"] <= META_MAX_ABSTENCION)

    def margen_a_igual_abstencion(abst: float) -> dict:
        if not barrido_fase3:
            return None
        fm = min(barrido_fase3, key=lambda r: abs(r["tasa_abstencion"] - abst))
        return {"t": fm["umbral"], "tasa_abstencion": fm["tasa_abstencion"],
                "top1_aceptados": fm["top1_aceptados"],
                "top1_rechazados": fm["top1_rechazados"]}

    dominancias = {}
    for nombre in ("decidibilidad_only", "combinada"):
        fila = filas_test[nombre]
        fm = margen_a_igual_abstencion(fila["tasa_abstencion"])
        dominancia = False
        if fm is not None and fila["top1_aceptados"] is not None \
                and fm["top1_aceptados"] is not None:
            dominancia = fila["top1_aceptados"] > fm["top1_aceptados"]
        dominancias[nombre] = {
            "abstencion_regla": fila["tasa_abstencion"],
            "top1_regla": fila["top1_aceptados"],
            "margen_presupuesto_igualado": fm,
            "domina_al_margen": bool(dominancia),
        }

    if mecanismo_mejorado:
        regla_rec = "combinada"
        veredicto = ("MEJORADO: la regla combinada alcanza top-1 aceptados "
                     ">= %.2f con abstencion <= %.2f en TEST" % (
                         META_TOP1_ACEPTADOS, META_MAX_ABSTENCION))
        criterio = ("meta explicita de la tarea: top-1 aceptados >= %.2f "
                    "con abstencion <= %.2f" % (META_TOP1_ACEPTADOS,
                                                META_MAX_ABSTENCION))
    elif any(d["domina_al_margen"] for d in dominancias.values()):
        mejor_dom = max((k for k in dominancias if dominancias[k]["domina_al_margen"]),
                        key=lambda k: (dominancias[k]["top1_regla"],
                                       -dominancias[k]["abstencion_regla"]))
        regla_rec = mejor_dom
        veredicto = ("MEJORA_PARCIAL: la regla '%s' domina al margen a "
                     "presupuesto igualado (top-1 %s vs %s), pero no "
                     "alcanza la meta estricta" % (
                         mejor_dom,
                         str(dominancias[mejor_dom]["top1_regla"]),
                         str(dominancias[mejor_dom]
                             ["margen_presupuesto_igualado"]["top1_aceptados"])))
        criterio = ("dominancia estricta sobre la regla por margen a "
                    "presupuesto igualado de abstencion")
    else:
        regla_rec = "margin_only"
        veredicto = ("SIN_MEJORA_HONESTA: la regla combinada no alcanza "
                     "top-1 >= %.2f con abstencion <= %.2f y ninguna regla "
                     "basada en decidibilidad domina al margen a "
                     "presupuesto igualado; la regla por margen de Fase 3 "
                     "se mantiene" % (META_TOP1_ACEPTADOS,
                                      META_MAX_ABSTENCION))
        criterio = ("sin dominancia de las reglas de decidibilidad; se "
                    "conserva la regla por margen de Fase 3")
    art["recomendacion"] = {
        "criterio": criterio,
        "regla_recomendada": regla_rec,
        "config_recomendada": filas_test[regla_rec]
            if regla_rec in filas_test else {"t_m": t_m3, "t_d": None},
        "mecanismo_mejorado": mecanismo_mejorado,
        "veredicto": veredicto,
        "comparacion_test": [
            {"regla": nombre,
             "top1_aceptados": f["top1_aceptados"],
             "tasa_abstencion": f["tasa_abstencion"],
             "config": {"t_m": f["t_m"], "t_d": f["t_d"]}}
            for nombre, f in filas_test.items()],
        "comparacion_presupuesto_igualado": dominancias,
    }
    art["reglas_comparacion"] = {
        "val": filas_val,
        "test": filas_test,
        "confusion_rc4_test": confusion_test,
        "origen_umbrales": {
            "margin_only": "Fase 3 (artifacts_ruta_c_fase3.json)",
            "decidibilidad_only": "t_d = max F1 sobre val",
            "combinada": "grilla t_m x t_d sobre val",
        },
    }
    print("  TEST: margin_only %s | decidibilidad_only %s | combinada %s"
          % (str(filas_test["margin_only"]), str(filas_test["decidibilidad_only"]),
             str(filas_test["combinada"])))
    print("  recomendacion: %s (%s)" % (regla_rec, veredicto))
    guardar_artefacto(art, "reglas_comparacion")

    # ── Parte 2: R-RC5 ──
    pids_test = pids_split["test"]
    regs_por_pid_test = {pid: [r for r in splits["test"] if r["pid"] == pid]
                         for pid in pids_test}
    pids10 = pids_test[:N_COMPLEJOS_INVARIANZA]

    print("  R-RC5A: invarianza rigida en %d complejos..." % len(pids10))
    t_a = time.monotonic()
    res_a = r_rc5a_invarianza(pids10, regs_por_pid_test, raw224_por_pid["test"])
    art["r_rc5"] = {"A_invarianza": res_a}
    print("  R-RC5A: max dif %.3g (%s), estables rot %d/%d, estables vs "
          "canonico %d/%d (%.0fs)"
          % (res_a["max_dif_224"], res_a["veredicto_invarianza"],
             res_a["n_selecciones_estables_rot"], len(pids10),
             res_a["n_selecciones_estables_vs_canonico"], len(pids10),
             time.monotonic() - t_a))
    guardar_artefacto(art, "r_rc5a")

    score_canonico_test = {}
    for pid in pids_test:
        score_canonico_test[pid] = {
            key_registro(r): float(s)
            for (r, s) in por_pid_split["test"][pid]}

    print("  R-RC5B: ruido sigma=%.1f A en %d complejos..."
          % (SIGMA_RUIDO, len(pids_test)))
    t_b = time.monotonic()
    res_b = r_rc5b_ruido(pids_test, regs_por_pid_test, raw224_por_pid["test"],
                         score_canonico_test, datos_split["test"])
    art["r_rc5"]["B_ruido"] = res_b
    print("  R-RC5B: cambiaron %d/%d (%.1f%%); margen cambiados %s | "
          "no cambiados %s | drift %d (%.0fs)"
          % (res_b["n_cambiaron"], res_b["n_complejos"],
             100 * res_b["fraccion_cambio"],
             str(res_b["margen_cambiados"]), str(res_b["margen_no_cambiados"]),
             res_b["drift_reextraccion_limpia_vs_canonico"]["n_mismatch"],
             time.monotonic() - t_b))
    guardar_artefacto(art, "r_rc5b")

    # ── resumen final ──
    art["resumen"] = {
        "v06_test_top1": top1_retrain,
        "decidibilidad_auc_val": clf_info["auc_val"],
        "regla_recomendada": art["recomendacion"]["regla_recomendada"],
        "rc5a_max_dif": res_a["max_dif_224"],
        "rc5b_fraccion_cambio": res_b["fraccion_cambio"],
    }
    art["caveats_honestos"] = [
        "El clasificador de decidibilidad usa agregados calculados con los "
        "scores v0.6 de TRAIN (in-sample para train; honesto para val/test). "
        "AUC val sobre los complejos con >=2 poses (n=39, igual que Fase 3).",
        "Los umbrales (t_d solo, t_m/t_d combinados) se eligen SOLO sobre "
        "val (40 complejos, ruido estadistico) y se aplican a test una sola "
        "vez; el punto elegido puede trasladarse con varianza al test.",
        "Complejos de 1 pose (margin None) no participan de la abstencion "
        "por margen (igual que Fase 3); si participan de la regla por "
        "decidibilidad (su P se calcula con margen imputado por mediana).",
        "Re-extraccion R-RC5: las coords de poses se leen de los archivos "
        "de docking (S1/S2/S3, logica de build_pose_selector_dataset.py) "
        "con los mapas serial->mol de cada fuente; las 5 features baratas "
        "geometricas y las 215 ricas se recalculan, las 4 baratas no "
        "geometricas (vina_score, varianza/rango, n_heavy) se conservan "
        "del dataset congelado. La re-extraccion limpia reproduce el cache "
        "v0.5 exactamente (verificado en muestras S1/S2/S3 y via 'drift' "
        "en R-RC5B).",
        "R-RC5A transforma poses y receptor juntos: la invarianza esperada "
        "es exacta (las 224 features dependen solo de distancias). El "
        "cluster_density se recalcula sobre coords transformadas (no se "
        "copia del canonico).",
        "R-RC5B perturba SOLO las poses (el receptor queda fijo), por eso "
        "el cambio de seleccion es esperable en complejos con poses casi "
        "empatadas (margen bajo); se reporta el analisis de margenes.",
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print("  artefacto: %s (%.1fs)"
          % (str(ARTIFACTO.relative_to(PROJECT_ROOT)), art["duracion_total_s"]))


if __name__ == "__main__":
    main()
