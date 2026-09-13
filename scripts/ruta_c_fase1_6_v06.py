# -*- coding: utf-8 -*-
"""
ruta_c_fase1_6_v06.py — Ruta C, Fase 1.6 (v0.6 relativo), docs/42_RUTA_C_PROTOCOLO.md.

Hipotesis: XGBoost no supero a Vina en v0/v0.5 porque los arboles usan
umbrales GLOBALES mientras la seleccion es INTRA-complejo (por complejo).
Remedio: hacer explicita la relatividad intra-complejo con normalizacion
z-score por complejo y features de rango percentil.

Dos modelos:
  - Modelo A (sanity): SOLO z_vina_score (1 feature). Debe reproducir el
    top-1 test de Vina (0.5319): la transformacion z es monotona dentro de
    cada complejo y preserva el argmin.
  - Modelo B (prueba real): 224 z-scores + 9 percentiles = 233 features.

Features: se REUSA el cache de v0.5 (data/pose_selector_dataset/
features_v05_progress.jsonl, vector rico de 215 por registro, clave por
(pid, source, file_stem, model_idx)) y las 9 features baratas de los jsonl.
NO se recalculan features.

Evaluacion identica a Fase 1/v0.5 (argmax del score por complejo, top-1
crystal-like RMSD <= 2.0 A, RMSD mediano, Spearman promedio por complejo).
Gate: PASS si v0.6-B test top-1 > 0.5319.
Artefacto: scripts/artifacts_ruta_c_fase1_6.json (escritura incremental).
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
DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
ARTIFACTS_V06 = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1_6.json"
ARTIFACTS_V05 = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1_5.json"
ARTIFACTS_V01 = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1.json"
PROGRESS_FEATURES = DATASET_DIR / "features_v05_progress.jsonl"
UMBRAL_POSITIVA = 2.0

# ─── 9 features baratas de Fase 1 (mismas del dataset) ────────────────────
FEATURES_V0 = ["vina_score", "pose_score_variance", "pose_score_range", "n_heavy",
               "n_contacts_4", "n_contacts_6", "contacts_per_ha_4", "n_clashes",
               "cluster_density"]

# ─── Definiciones de features ricas (identicas a v0.5) ──────────────────────
PROTEIN_ELEMENTS: tuple = ("C", "N", "O", "S")
LIGAND_ELEMENTS: tuple = ("C", "N", "O", "S", "F", "P", "Cl", "Br")
SHELL_BINS: tuple = ((0, 4), (4, 8), (8, 12))
SHELL_FEATURES = [f"shell_{pe}_{le}_{lo}_{hi}"
                  for pe in PROTEIN_ELEMENTS
                  for le in LIGAND_ELEMENTS
                  for lo, hi in SHELL_BINS]  # 96

PROT_ECIF_TYPES: tuple = ("C_ali", "C_aro", "N_don", "N_acc",
                          "O_don", "O_acc", "S", "other")
LIG_ECIF_TYPES: tuple = ("C", "N", "O", "S", "F", "Hal", "other")
ECIF_FEATURES = [f"ecif_{pt}_{lt}"
                 for pt in PROT_ECIF_TYPES
                 for lt in LIG_ECIF_TYPES]  # 56

RESIDUOS_21: tuple = ("ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY",
                      "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER",
                      "THR", "TRP", "TYR", "VAL", "OTHER")
POP_FEATURES = ([f"pop_{aa}_4" for aa in RESIDUOS_21]
                + [f"pop_{aa}_6" for aa in RESIDUOS_21]
                + [f"pop_{aa}_hb" for aa in RESIDUOS_21])  # 63

FEATURES_RICH = SHELL_FEATURES + ECIF_FEATURES + POP_FEATURES  # 215
FEATURES_TOTAL = FEATURES_V0 + FEATURES_RICH                     # 224
assert len(SHELL_FEATURES) == 96 and len(ECIF_FEATURES) == 56
assert len(POP_FEATURES) == 63 and len(FEATURES_TOTAL) == 224

# Features con rango percentil (raw, 0-100, empates -> rango promedio).
PCT_RAW = ["vina_score", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
           "n_clashes", "pose_score_variance", "pose_score_range",
           "cluster_density", "n_heavy"]
PCT_INDICES = [FEATURES_V0.index(f) for f in PCT_RAW]

N_Z = len(FEATURES_TOTAL)          # 224
N_PCT = len(PCT_RAW)               # 9
N_MODELO_A = 1                     # solo z_vina_score
N_MODELO_B = N_Z + N_PCT           # 233

PARAMS = {
    "objective": "rank:pairwise",
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "early_stopping_rounds": 50,
    "n_jobs": 4,
    "seed": 42,
    "random_state": 42,
}

VINA_TOP1_TEST_REFERENCIA = 0.5319
TOL_SANITY = 0.001


# ───────────────────────── utilidades de consola/artefacto ─────────────────

def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def guardar_artefacto(art: dict, etapa: str) -> None:
    """Escritura incremental (temp + os.replace), patron de Fase 1."""
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTS_V06.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ARTIFACTS_V06)


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ───────────────────────── carga de datos ───────────────────────────────────

def cargar_split(nombre: str) -> list[dict]:
    registros: list[dict] = []
    path = DATASET_DIR / f"poses_{nombre}.jsonl"
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registros.append(json.loads(linea))
    # Orden canonico deterministico: pid, fuente, stem, model_idx.
    registros.sort(key=lambda r: (r["pid"], r["source"], r["file_stem"],
                                  r["model_idx"]))
    return registros


def cargar_cache_v05() -> dict:
    """{ (pid, source, file_stem, model_idx): vector_rich(215) }.
    La cabecera se valida contra el sha256 actual de los splits
    (dataset congelado). Falla fuerte si el cache es invalido."""
    cache: dict = {}
    with open(PROGRESS_FEATURES, encoding="utf-8") as fh:
        cabecera = json.loads(fh.readline())
        sha_actual = {n: sha256_archivo(DATASET_DIR / f"poses_{n}.jsonl")
                      for n in ("train", "val", "test")}
        if cabecera.get("sha256_splits") != sha_actual:
            raise RuntimeError("cache v0.5 invalido: sha256 de splits distinto")
        for linea in fh:
            if not linea.strip():
                continue
            reg = json.loads(linea)
            clave = (reg["pid"], reg["source"], reg["file_stem"],
                     reg["model_idx"])
            cache[clave] = reg["rich"]
    return cache


def construir_X_raw(splits: dict) -> dict:
    """Matrices raw (n, 224) por split: 9 baratas + 215 ricas del cache.
    La union se hace por clave (pid, source, file_stem, model_idx)."""
    cache = cargar_cache_v05()
    out = {}
    for nombre, regs in splits.items():
        ricos = []
        faltantes = 0
        for r in regs:
            clave = (r["pid"], r["source"], r["file_stem"], r["model_idx"])
            rico = cache.get(clave)
            if rico is None:
                faltantes += 1
                rico = [0.0] * len(FEATURES_RICH)
            ricos.append(rico)
        if faltantes:
            raise RuntimeError(f"{nombre}: {faltantes} registros sin cache")
        X_b = np.array([[r.get(f) for f in FEATURES_V0] for r in regs],
                       dtype=np.float64)
        X = np.hstack([X_b, np.array(ricos, dtype=np.float64)])
        assert X.shape == (len(regs), 224)
        out[nombre] = X
    return out


# ───────────────────────── transformacion por complejo ──────────────────────

def grupos_por_pid(registros: list[dict]) -> tuple[list[int], list[str]]:
    """Conteos por complejo en orden de filas + lista de pids en orden."""
    grupos: list[int] = []
    pids_orden: list[str] = []
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
    return grupos, pids_orden


def z_por_pid(X: np.ndarray, grupos: list[int]) -> np.ndarray:
    """Z-score por columna DENTRO de cada complejo (filas contiguas).
    std_pid == 0 -> z = 0. NaN permanece NaN (se rellena a 0 despues)."""
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


def pct_por_pid(X: np.ndarray, grupos: list[int], indices: list[int]) -> np.ndarray:
    """Rango percentil 0-100 (empates -> rango promedio) por complejo
    para las columnas raw indicadas. Complejo de 1 pose -> 50.0.
    NaN permanece NaN."""
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


def preparar_modelos(X_split: dict, grupos_split: dict) -> dict:
    """Por split: X_A (n,1) y X_B (n,233). NaN -> 0 despues de transformar."""
    out = {}
    for nombre, X in X_split.items():
        grupos = grupos_split[nombre]
        Z = z_por_pid(X, grupos)
        Z[np.isnan(Z)] = 0.0
        P = pct_por_pid(X, grupos, PCT_INDICES)
        P[np.isnan(P)] = 0.0
        X_A = Z[:, 0:1]
        X_B = np.hstack([Z, P])
        assert X_A.shape == (X.shape[0], 1)
        assert X_B.shape == (X.shape[0], N_MODELO_B)
        out[nombre] = {"A": X_A, "B": X_B, "Z": Z, "P": P}
    return out


# ───────────────────────── evaluacion (Fase 1) ──────────────────────────────

def baseline_vina(registros: list[dict]) -> dict:
    """Por complejo: pose de MENOR vina_score (empates -> primera en orden
    canonico). Replica exacta del baseline de Fase 1."""
    por_pid: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_pid[r["pid"]].append(r)
    seleccionados: list[float] = []
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
    if not seleccionados:
        return {"top1_rate": None, "mediana_rmsd": None, "n_con_score": 0}
    return {
        "top1_rate": round(float(np.mean([s <= UMBRAL_POSITIVA
                                          for s in seleccionados])), 4),
        "mediana_rmsd": round(float(np.median(seleccionados)), 3),
        "n_con_score": n_con_score,
    }


def evaluar_modelo(modelo, X: np.ndarray, registros: list[dict],
                   pids_orden: list[str]) -> dict:
    """Top-1 por complejo (argmax del score), RMSD mediano y Spearman
    promedio por complejo (>= 2 poses no constantes). Copia de Fase 1."""
    pred = modelo.predict(X)
    por_pid: dict = defaultdict(list)
    for r, p in zip(registros, pred):
        por_pid[r["pid"]].append((r, float(p)))
    from scipy.stats import spearmanr
    top1_ok = 0
    rmsds_sel: list = []
    spearmans_neg: list = []
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
                sp = spearmanr(ps, rs).correlation
                spearmans_neg.append(
                    float(sp) if sp is not None and not np.isnan(sp) else 0.0)
                n_spearman += 1
    n_pids = len(pids_orden)
    return {
        "top1_rate": round(top1_ok / n_pids, 4),
        "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
        "spearman_pred_vs_rmsd_media": (round(float(np.mean(spearmans_neg)), 4)
                                        if spearmans_neg else None),
        "spearman_pred_vs_relevancia_media": (round(float(-np.mean(spearmans_neg)), 4)
                                              if spearmans_neg else None),
        "n_complejos": n_pids,
        "n_complejos_spearman": n_spearman,
    }


def evaluar_determinista_argmin_z(X_A: np.ndarray, registros: list[dict],
                                  pids_orden: list[str]) -> dict:
    """Seleccion determinista: argmin de z_vina_score por complejo
    (empates -> primera en orden canonico). Equivalente matematico del
    baseline de Vina; sirve para aislar el marco de evaluacion del
    modelo aprendido."""
    z = X_A[:, 0]
    por_pid: dict = defaultdict(list)
    for r, v in zip(registros, z):
        por_pid[r["pid"]].append((r, float(v)))
    top1_ok = 0
    rmsds_sel: list = []
    for pid in pids_orden:
        filas = por_pid[pid]
        mejor = min(enumerate(filas), key=lambda ip: (ip[1][1], ip[0]))[1][0]
        rmsds_sel.append(mejor["rmsd"])
        if mejor["rmsd"] <= UMBRAL_POSITIVA:
            top1_ok += 1
    n_pids = len(pids_orden)
    return {"top1_rate": round(top1_ok / n_pids, 4),
            "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
            "n_complejos": n_pids}


# ───────────────────────── entrenamiento ────────────────────────────────────

def entrenar_ranker(X_train, y_train, g_train, X_val, y_val, g_val) -> tuple:
    from xgboost import XGBRanker
    metricas = ["auc", "rmse"]
    modelo = None
    for metrica in metricas:
        try:
            modelo = XGBRanker(eval_metric=metrica, **PARAMS)
            modelo.fit(X_train, y_train, group=g_train,
                       eval_set=[(X_val, y_val)], eval_group=[g_val],
                       verbose=False)
            break
        except Exception as e:
            print(f"  metric '{metrica}' fallo: {type(e).__name__}; probando siguiente")
            modelo = None
    if modelo is None:
        raise RuntimeError("ninguna metrica de early-stopping funciono")
    return modelo, metrica


# ───────────────────────── diagnostico de techo ─────────────────────────────

def pca1_proyeccion(X: np.ndarray) -> np.ndarray:
    """Primer componente principal sobre columnas estandarizadas.
    Signo fijado por convencion: el loading de mayor magnitud es positivo."""
    Z = X - X.mean(axis=0)
    std = Z.std(axis=0)
    std[std < 1e-12] = 1.0
    Z = Z / std
    u, s, vt = np.linalg.svd(Z, full_matrices=False)
    v1 = vt[0]
    k = int(np.argmax(np.abs(v1)))
    if v1[k] < 0:
        v1 = -v1
    return Z @ v1


def spearman_por_pid_media(proyeccion: np.ndarray, registros: list[dict],
                           pids_orden: list[str]) -> dict:
    """Spearman(proyeccion, rmsd) por complejo (>= 2 poses), media y
    media del valor absoluto (independiente del signo)."""
    from scipy.stats import spearmanr
    por_pid: dict = defaultdict(list)
    for r, p in zip(registros, proyeccion):
        por_pid[r["pid"]].append((float(r["rmsd"]), float(p)))
    vals: list = []
    for pid in pids_orden:
        filas = por_pid[pid]
        if len(filas) < 2:
            continue
        rs = np.array([a for a, _ in filas])
        ps = np.array([b for _, b in filas])
        if np.std(rs) < 1e-12 or np.std(ps) < 1e-12:
            continue
        sp = spearmanr(ps, rs).correlation
        if sp is not None and not np.isnan(sp):
            vals.append(float(sp))
    if not vals:
        return {"media": None, "media_abs": None, "n_complejos": 0}
    return {"media": round(float(np.mean(vals)), 4),
            "media_abs": round(float(np.mean(np.abs(vals))), 4),
            "n_complejos": len(vals)}


def diagnostico_monotonia_A(modelo, X_A: np.ndarray, registros: list[dict],
                            pids_orden: list[str], nombre_split: str) -> dict:
    """Investiga POR QUE el Modelo A aprendido puede desviarse del argmin de
    Vina: (1) monotonia local pred vs z_vina (Spearman por complejo),
    (2) conteo de complejos donde argmax(pred) != argmin(z), con detalles
    de los vina implicados, (3) granularidad de la funcion escalonada."""
    from scipy.stats import spearmanr
    pred = modelo.predict(X_A)
    z = X_A[:, 0]
    por_pid: dict = defaultdict(list)
    for r, p, v in zip(registros, pred, z):
        por_pid[r["pid"]].append((r, float(p), float(v)))
    spears: list = []
    flips: list = []
    n_distintos: list = []
    for pid in pids_orden:
        filas = por_pid[pid]
        ps = np.array([p for _, p, _ in filas])
        vs = np.array([v for _, _, v in filas])
        n_distintos.append(len(np.unique(ps)))
        if len(filas) >= 2 and np.std(ps) > 1e-12 and np.std(vs) > 1e-12:
            sp = spearmanr(ps, vs).correlation
            if sp is not None and not np.isnan(sp):
                spears.append(float(sp))
        idx_argmax = int(np.argmax(ps))
        idx_argmin_z = int(np.argmin(vs))
        if idx_argmax != idx_argmin_z:
            flips.append({
                "pid": pid,
                "vina_pose_vina": round(float(filas[idx_argmin_z][0]["vina_score"]), 3),
                "vina_pose_rmsd": round(float(filas[idx_argmin_z][0]["rmsd"]), 3),
                "vina_pose_z": round(float(vs[idx_argmin_z]), 3),
                "pred_pose_vina": round(float(filas[idx_argmax][0]["vina_score"]), 3),
                "pred_pose_rmsd": round(float(filas[idx_argmax][0]["rmsd"]), 3),
                "pred_pose_z": round(float(vs[idx_argmax]), 3),
                "n_poses": len(filas),
            })
    return {
        "split": nombre_split,
        "spearman_pred_vs_z_media": (round(float(np.mean(spears)), 4)
                                     if spears else None),
        "spearman_pred_vs_z_min": (round(float(np.min(spears)), 4)
                                   if spears else None),
        "n_complejos_spearman": len(spears),
        "n_complejos_flip_vs_argmin_z": len(flips),
        "n_valores_pred_distintos_mediana": (int(np.median(n_distintos))
                                             if n_distintos else None),
        "flips": flips,
    }


def diagnostico_familias_z(Z_train: np.ndarray, registros_train: list[dict],
                           pids_train: list[str]) -> dict:
    """Spearman por-familia vs rmsd en TRAIN usando las columnas YA
    normalizadas z (mismo metodo que v0.5: vina directo, familias
    multidimensionales via PCA-1)."""
    cols = {"z_vina_score": (0, 1), "z_shells": (9, 105),
            "z_ecif": (105, 161), "z_per_residuo": (161, 224)}
    out = {}
    for nombre, rango in cols.items():
        a, b = rango[0], rango[1]
        if b - a == 1:
            proy = Z_train[:, a]
            metodo = "valor_directo"
        else:
            proy = pca1_proyeccion(Z_train[:, a:b])
            metodo = "pca1"
        res = spearman_por_pid_media(proy, registros_train, pids_train)
        res["metodo"] = metodo
        out[nombre] = res
    return out


# ───────────────────────── flujo principal ──────────────────────────────────

def main() -> None:
    configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 1.6 (v0.6 relativo): z-score + percentil por complejo ==")

    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": "1.6 (v0.6 relativo)",
        "hipotesis": ("los arboles de XGBoost usan umbrales globales mientras "
                      "la seleccion es intra-complejo; hacer la relatividad "
                      "explicita con z-score y rango percentil por complejo"),
        "gate_criterio": f"v06B_top1_test > vina_top1_test ({VINA_TOP1_TEST_REFERENCIA})",
        "config": {
            "n_features_raw": len(FEATURES_TOTAL),
            "n_z": N_Z,
            "n_pct": N_PCT,
            "n_modelo_A": N_MODELO_A,
            "n_modelo_B": N_MODELO_B,
            "transformacion": ("z-score por columna dentro de cada complejo "
                               "(std_pid == 0 -> z = 0); rangos percentiles 0-100 "
                               "(empates -> rango promedio) sobre las 9 features raw "
                               "de PCT_RAW; cada split se normaliza de forma "
                               "independiente; NaN -> 0 despues de transformar"),
            "pct_raw": PCT_RAW,
            "hiperparametros": PARAMS,
            "relevancia": "-rmsd",
            "cache_v05": str(PROGRESS_FEATURES.relative_to(PROJECT_ROOT)),
        },
    }
    guardar_artefacto(art, "config")

    # ── Carga de datos y matrices raw ──
    splits = {n: cargar_split(n) for n in ("train", "val", "test")}
    grupos_split = {}
    pids_split = {}
    y_split = {}
    for n, regs in splits.items():
        g, pids = grupos_por_pid(regs)
        grupos_split[n] = g
        pids_split[n] = pids
        y_split[n] = -np.array([r["rmsd"] for r in regs], dtype=np.float64)
    X_raw = construir_X_raw(splits)
    print(f"  matrices raw: train {X_raw['train'].shape} | "
          f"val {X_raw['val'].shape} | test {X_raw['test'].shape}")

    # ── Transformacion por complejo ──
    modelos = preparar_modelos(X_raw, grupos_split)
    print(f"  modelo A: 1 feature | modelo B: {N_MODELO_B} features")

    # ── Baseline Vina recomputado sobre este mismo marco ──
    art["vina_baseline_recomputado"] = {
        n: baseline_vina(splits[n]) for n in ("train", "val", "test")}
    print("  vina recomputado:", {
        n: art["vina_baseline_recomputado"][n]["top1_rate"]
        for n in ("train", "val", "test")})
    guardar_artefacto(art, "vina_recomputado")

    # ── Modelo A (sanity) ──
    modelo_a, metrica_a = entrenar_ranker(
        modelos["train"]["A"], y_split["train"], grupos_split["train"],
        modelos["val"]["A"], y_split["val"], grupos_split["val"])
    art["modelo_A"] = {
        "descripcion": ("XGBRanker con SOLO z_vina_score (1 feature). "
                        "Sanity: la z es monotona intra-complejo y debe "
                        "preservar el argmin de Vina."),
        "features": ["z_vina_score"],
        "eval_metric": metrica_a,
        "best_iteration": int(getattr(modelo_a, "best_iteration", -1)),
        "best_score": (float(modelo_a.best_score) if modelo_a.best_score else None),
    }
    for n in ("train", "val", "test"):
        art["modelo_A"][n] = evaluar_modelo(
            modelo_a, modelos[n]["A"], splits[n], pids_split[n])
    print(f"  A val:  top1={art['modelo_A']['val']['top1_rate']} "
          f"mediana={art['modelo_A']['val']['mediana_rmsd']}")
    print(f"  A test: top1={art['modelo_A']['test']['top1_rate']} "
          f"mediana={art['modelo_A']['test']['mediana_rmsd']}")
    guardar_artefacto(art, "modelo_A_entrenado")

    # ── Sanity: verificacion determinista + monotonia aprendida ──
    det_test = evaluar_determinista_argmin_z(
        modelos["test"]["A"], splits["test"], pids_split["test"])
    det_val = evaluar_determinista_argmin_z(
        modelos["val"]["A"], splits["val"], pids_split["val"])
    diag_test = diagnostico_monotonia_A(
        modelo_a, modelos["test"]["A"], splits["test"], pids_split["test"],
        "test")
    diag_val = diagnostico_monotonia_A(
        modelo_a, modelos["val"]["A"], splits["val"], pids_split["val"],
        "val")
    a_test = art["modelo_A"]["test"]["top1_rate"]
    delta_sanity = round(a_test - VINA_TOP1_TEST_REFERENCIA, 4)
    art["sanity_modelo_A"] = {
        "objetivo": ("reproducir el top-1 test de Vina (0.5319) con la "
                     "feature z_vina_score sola"),
        "tolerancia": TOL_SANITY,
        "A_test_top1": a_test,
        "vina_test_top1_referencia": VINA_TOP1_TEST_REFERENCIA,
        "delta": delta_sanity,
        "resultado": "OK" if abs(delta_sanity) <= TOL_SANITY else "NO_OK",
        "verificacion_determinista_argmin_z": {
            "test": det_test,
            "val": det_val,
            "igual_al_vina_recomputado_test": det_test["top1_rate"]
                == art["vina_baseline_recomputado"]["test"]["top1_rate"],
            "igual_a_referencia_05319_test": det_test["top1_rate"]
                == VINA_TOP1_TEST_REFERENCIA,
        },
        "investigacion_no_ok": {
            "diagnostico_monotonia_test": diag_test,
            "diagnostico_monotonia_val": diag_val,
        },
    }
    print(f"  sanity A: {art['sanity_modelo_A']['resultado']} "
          f"(A {a_test} vs Vina {VINA_TOP1_TEST_REFERENCIA}, "
          f"delta {delta_sanity}; argmin_z determinista {det_test['top1_rate']})")
    print(f"  investigacion A: spearman(pred,z) test {diag_test['spearman_pred_vs_z_media']} "
          f"| flips test {diag_test['n_complejos_flip_vs_argmin_z']} "
          f"val {diag_val['n_complejos_flip_vs_argmin_z']}")
    guardar_artefacto(art, "sanity_A")

    # ── Modelo B (prueba real) ──
    modelo_b, metrica_b = entrenar_ranker(
        modelos["train"]["B"], y_split["train"], grupos_split["train"],
        modelos["val"]["B"], y_split["val"], grupos_split["val"])
    art["modelo_B"] = {
        "descripcion": ("XGBRanker con 224 z-scores + 9 rangos percentiles "
                        "(= 233 features), todo normalizado por complejo."),
        "n_features": N_MODELO_B,
        "eval_metric": metrica_b,
        "best_iteration": int(getattr(modelo_b, "best_iteration", -1)),
        "best_score": (float(modelo_b.best_score) if modelo_b.best_score else None),
    }
    for n in ("train", "val", "test"):
        art["modelo_B"][n] = evaluar_modelo(
            modelo_b, modelos[n]["B"], splits[n], pids_split[n])
    print(f"  B val:  top1={art['modelo_B']['val']['top1_rate']} "
          f"mediana={art['modelo_B']['val']['mediana_rmsd']}")
    print(f"  B test: top1={art['modelo_B']['test']['top1_rate']} "
          f"mediana={art['modelo_B']['test']['mediana_rmsd']}")
    guardar_artefacto(art, "modelo_B_entrenado")

    # ── Importancias (gain) ──
    nombres_b = ([f"z_{f}" for f in FEATURES_TOTAL]
                 + [f"pct_{f}" for f in PCT_RAW])
    booster = modelo_b.get_booster()
    scores = booster.get_score(importance_type="gain")
    por_idx = sorted(((int(k[1:]), float(v)) for k, v in scores.items()),
                     key=lambda kv: -kv[1])
    art["modelo_B"]["importancias_top15"] = [
        {"feature": nombres_b[i], "gain": round(g, 2)}
        for i, g in por_idx[:15]]
    art["modelo_B"]["n_features_con_gain"] = len(por_idx)

    # ── Diagnostico de techo: familias z vs raw (train) ──
    diag_z = diagnostico_familias_z(
        modelos["train"]["Z"], splits["train"], pids_split["train"])
    diag_raw_v05 = {}
    if ARTIFACTS_V05.exists():
        v05 = json.loads(ARTIFACTS_V05.read_text(encoding="utf-8"))
        diag_raw_v05 = v05.get("diagnostico_familias_train", {})
    tabla_familias = []
    mapeo = [("z_vina_score", "vina_score"), ("z_shells", "shells"),
             ("z_ecif", "ecif"), ("z_per_residuo", "per_residuo")]
    for z_key, raw_key in mapeo:
        raw = diag_raw_v05.get(raw_key, {})
        z = diag_z.get(z_key, {})
        tabla_familias.append({
            "familia": raw_key,
            "raw_media_abs_v05": raw.get("media_abs"),
            "raw_media_v05": raw.get("media"),
            "z_media_abs": z.get("media_abs"),
            "z_media": z.get("media"),
            "n_complejos_z": z.get("n_complejos"),
            "metodo": z.get("metodo"),
        })
    art["diagnostico_familias_train"] = {
        "nota": ("z-vina es afin a vina dentro de cada complejo, por lo que "
                 "su Spearman debe coincidir con el raw (chequeo interno); "
                 "las familias multidimensionales se proyectan con PCA-1 "
                 "sobre sus columnas z, mismo metodo que v0.5."),
        "tabla": tabla_familias,
    }
    print("  diagnostico familias z (train):")
    for fila in tabla_familias:
        print(f"    {fila['familia']}: raw_abs {fila['raw_media_abs_v05']} "
              f"-> z_abs {fila['z_media_abs']}")
    guardar_artefacto(art, "diagnostico_familias")

    # ── Tabla comparativa Vina / v0 / v0.5 / A / B ──
    fase1 = {}
    if ARTIFACTS_V01.exists():
        fase1 = json.loads(ARTIFACTS_V01.read_text(encoding="utf-8"))
    fase15 = {}
    if ARTIFACTS_V05.exists():
        fase15 = json.loads(ARTIFACTS_V05.read_text(encoding="utf-8"))
    tabla = {}
    for split in ("val", "test"):
        vina_art = fase1.get("vina_baseline", {}).get(split, {})
        vina_re = art["vina_baseline_recomputado"][split]
        v0_art = fase1.get("v0", {}).get(split, {})
        v05_art = fase15.get("v05", {}).get(split, {})
        tabla[split] = {
            "vina_top1": vina_art.get("top1_rate"),
            "vina_mediana": vina_art.get("mediana_rmsd"),
            "vina_top1_recomputado": vina_re["top1_rate"],
            "v0_top1": v0_art.get("top1_rate"),
            "v0_mediana": v0_art.get("mediana_rmsd"),
            "v05_top1": v05_art.get("top1_rate"),
            "v05_mediana": v05_art.get("mediana_rmsd"),
            "v06A_top1": art["modelo_A"][split]["top1_rate"],
            "v06A_mediana": art["modelo_A"][split]["mediana_rmsd"],
            "v06A_spearman": art["modelo_A"][split]["spearman_pred_vs_rmsd_media"],
            "v06B_top1": art["modelo_B"][split]["top1_rate"],
            "v06B_mediana": art["modelo_B"][split]["mediana_rmsd"],
            "v06B_spearman": art["modelo_B"][split]["spearman_pred_vs_rmsd_media"],
        }
    art["comparacion"] = tabla

    # ── Gate ──
    b_test = art["modelo_B"]["test"]["top1_rate"]
    pasa = b_test > VINA_TOP1_TEST_REFERENCIA
    art["gate_v06B"] = {
        "vina_top1_test": VINA_TOP1_TEST_REFERENCIA,
        "v06B_top1_test": b_test,
        "delta": round(b_test - VINA_TOP1_TEST_REFERENCIA, 4),
        "resultado": "PASS" if pasa else "FAIL",
    }
    print(f"  Gate v0.6-B: {art['gate_v06B']['resultado']} "
          f"(B {b_test} vs Vina {VINA_TOP1_TEST_REFERENCIA}, "
          f"delta {art['gate_v06B']['delta']})")

    art["caveats_honestos"] = [
        "Modelo A: XGBoost aprende una funcion escalonada de z_vina_score; "
        "pequenas no-monotonicidades o empates de hoja pueden romper el "
        "empate canonico de Vina. Por eso se reporta ademas la verificacion "
        "determinista argmin_z (equivalente exacto del baseline de Vina).",
        "Percentiles: (rango - 1) / (n - 1) * 100; complejos con 1 sola pose "
        "reciben 50.0 (sin informacion de orden).",
        "z-score: std_pid == 0 -> z = 0 (feature constante dentro del "
        "complejo); NaN -> 0 despues de transformar (no hay NaN de "
        "vina_score en el dataset).",
        "Se reusan las 215 features ricas del cache v0.5 (dataset congelado, "
        "sha256 validado); las 9 baratas vienen de los jsonl congelados.",
        "Val tiene 40 complejos (ruido estadistico, mismo caveat de v0.5); "
        "la comparacion del gate es sobre el test congelado.",
        "La z por complejo es afin en vina_score dentro de cada complejo: el "
        "Spearman de z-vina debe coincidir con el raw de v0.5 (chequeo "
        "interno de la implementacion).",
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print(f"  artefacto: {ARTIFACTS_V06} ({art['duracion_total_s']}s)")


if __name__ == "__main__":
    main()
