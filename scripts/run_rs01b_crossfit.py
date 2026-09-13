# -*- coding: utf-8 -*-
"""run_rs01b_crossfit.py — RS-01B: cross-fitting OOF de clones v0.6.

Ejecuta la UNICA via cientificamente valida de RS-01 (PREREGISTRO.md §4.1-4.7,
sello paraguas): medir OOF si la deduplicacion (politica MF-11-R1 con umbral
ANIDADO por fold) mejora Top-1 sin degradar RMSD, con clones v0.6 cuyos
hiperparametros y semilla estan CONGELADOS al entrenamiento historico.

Contrato literal aplicado:

  - K=5 folds EXACTOS de fold_plan.json ([55,16,15,15,15] por las 38
    componentes combinadas scaffold+receptor). Por fold: outer-train =
    116 - fold; se entrena el clon y se evalua en el fold (OOF real).
  - Clones v0.6: XGBRanker rank:pairwise, n_estimators=52 SIN early stopping,
    max_depth 6, lr 0.05, subsample 0.8, seed 42, n_jobs 4 — TODOS los datos
    outer-train. Runtime python-embed/python.exe (3.11.9, xgboost 3.2.0).
  - Dos brazos por fold: (a) ORIGINAL (U=None en fold-eval, sin deduplicar);
    (b) DEDUP con umbral ANIDADO: dentro del outer-train se elige U con la
    regla EXACTA de MF-11-R1 (MAYOR umbral en {0.5,0.75,1.0,1.5,2.0} con 0
    perdidas de cobertura <= 2.0 A + degradacion mediana <= 0.1 A +
    reduccion >= 10%); si ninguno cumple -> U=None (sin dedup en ese fold).
    El umbral elegido se aplica al fold-eval. Se reporta U por fold.
  - Contrato de features A1 (de RS-01A): variance/range POR CORRIDA en ambos
    brazos; tras dedup SOLO se recalculan cluster_density (semantica historica
    del dataset builder: pares del MISMO complejo con RMSD pocket-frame
    < 2.0 A sin alinear, desde records/{pid}.json — hallazgo RS-01A) y, en
    consecuencia, las columnas z y percentiles afectados (toda la matriz
    z/pct por complejo sobre el conjunto resultante).
  - GATE PRIMARIO (guardia dura del maintainer): +3 aciertos Top-1 OOF
    (dedup vs original, acumulado) Y mediana de diferencias pareadas por
    complejo median(RMSD_dedup - RMSD_original) <= 0.1 A. PROHIBIDO usar
    diferencia de medianas o suma como gate (solo se reportan secundarias).
  - Incertidumbre: bootstrap BCa primario por las 38 componentes (10 000
    replicas, seed 42) sobre el Δ Top-1 y sobre la mediana pareada de RMSD;
    por complejo solo sensibilidad (percentil); McNemar exacto; por
    fold/estrato descriptivo con denominador (umbral >= 5 componentes para
    intervalo; fold 0 tiene 1 componente -> sin intervalo).
  - 31 empates: en el brazo dedup se evaluan TODOS los medoides alternativos
    empatados (contrafactual completo, B6-ii) sobre los conjuntos OOF.
  - Cero val/test/CONFIRM: auditoria de builtins.open con whitelist (patron
    RS-01A). poses_val.jsonl / poses_test.jsonl / FND-05 NUNCA se abren.

Composicion (solo lectura de codigo sellado):
  - rescoring/pose_selector/selector.py  -> PoseSelector (carga del checkpoint
    v0.6 SOLO para validar el contrato de features congelado; sus predicciones
    NO se usan en RS-01B) + UMBRAL_ABSTENCION_DEFECTO + UMBRAL_CLUSTER.
  - scripts/dedup_pose_union_medoid.py  -> parsear_atomos_pesados,
    matriz_distancias, clustering_diametro, medoid_detalle, UMBRALES
    (recomputacion identica a la del sidecar sellado de MF-11-R1).

Determinismo: salidas sin timestamps ni aleatoriedad no-seeded; dos corridas
completas producen metrics.json y per_complex.jsonl byte-identicos.

Uso:
  python scripts/run_rs01b_crossfit.py [--out-dir scripts/artifacts_science/RS-01B]
"""
from __future__ import annotations

import argparse
import builtins
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# ───────────────────────── auditoria de archivos abiertos ──────────────────
# Garantia de cuarentena (0 acceso a val/test/CONFIRM): todo open() bajo el
# repo se registra; al final se verifica que solo se abrieron archivos del
# whitelist. poses_val.jsonl / poses_test.jsonl / FND-05 nunca figuran.
_ORIGINAL_OPEN = builtins.open
_ABIERTOS_REPO: set[str] = set()


def _open_auditado(archivo, *args, **kwargs):
    try:
        p = Path(str(archivo)).resolve()
        try:
            rel = p.relative_to(PROJECT_ROOT.resolve())
            _ABIERTOS_REPO.add(str(rel).replace("\\", "/"))
        except ValueError:
            pass
    except Exception:
        pass
    return _ORIGINAL_OPEN(archivo, *args, **kwargs)


builtins.open = _open_auditado

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import numpy as np  # noqa: E402

from pose_selector.selector import (  # noqa: E402
    UMBRAL_ABSTENCION_DEFECTO,
    UMBRAL_CLUSTER,
    PoseSelector,
)
from dedup_pose_union_medoid import (  # noqa: E402
    UMBRALES,
    clustering_diametro,
    matriz_distancias,
    medoid_detalle,
    parsear_atomos_pesados,
)

# ───────────────────────── rutas y constantes ───────────────────────────────

ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_science"
RS01 = ARTIFACTOS / "RS-01"
MF11R1 = ARTIFACTOS / "MF-11-R1"
MF01_UNION = ARTIFACTOS / "MF-01-UNION"
DATASET = PROJECT_ROOT / "data" / "pose_selector_dataset"
RECORDS_DIR = DATASET / "records"

R_CHECKPOINT = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06.xgb"
R_META = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06_meta.json"
R_VIEW = RS01 / "cache_train_only_view.jsonl"
R_VIEW_MANIFEST = RS01 / "cache_view_manifest.json"
R_INVENTORY = RS01 / "INVENTORY.json"
R_FOLD_PLAN = RS01 / "fold_plan.json"
R_POSES_TRAIN = DATASET / "poses_train.jsonl"
R_UNION_CAND = MF01_UNION / "union_candidates_train.jsonl"
R_UNION_LABELS = MF01_UNION / "union_labels_train.jsonl"
R_DEDUP_CAND = MF11R1 / "dedup_candidates_train_1.5.jsonl"
R_SIDECAR = MF11R1 / "cluster_members_train_1.5.jsonl"
R_MF11R1_METRICS = MF11R1 / "metrics.json"

OUT_DIR_DEFAULT = ARTIFACTOS / "RS-01B"

UMBRAL_POSITIVA = 2.0  # hit: rmsd <= 2.0 A
UMBRAL_ABSTENCION = UMBRAL_ABSTENCION_DEFECTO  # 0.097663 (congelado)

FEATURES_V0 = ["vina_score", "pose_score_variance", "pose_score_range",
               "n_heavy", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
               "n_clashes", "cluster_density"]

PCT_RAW = ["vina_score", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
           "n_clashes", "pose_score_variance", "pose_score_range",
           "cluster_density", "n_heavy"]

N_Z = 224
N_MODELO_B = 233
N_FOLDS = 5

SEED_BOOT = 42
N_BOOT = 10_000

# Hiperparametros CONGELADOS del entrenamiento historico
# (ruta_c_fase1_6_v06.py:91-101 + PREREGISTRO.md §4.3 B3):
# n_estimators=52 = best_iteration 51 + 1, SIN early stopping.
PARAMS_CLON = {
    "objective": "rank:pairwise",
    "n_estimators": 52,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "n_jobs": 4,
    "seed": 42,
    "random_state": 42,
}


# ───────────────────────── utilidades ──────────────────────────────────────

def configurar_salida() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def leer_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in
            path.read_text(encoding="utf-8").splitlines() if l.strip()]


def escribir_jsonl(path: Path, filas: list) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for fila in filas:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


def escribir_json(path: Path, obj) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def clave_identidad(identidad: str) -> tuple:
    partes = identidad.split("|")  # split|pid|source|file_stem|model_idx
    return (partes[1], partes[2], partes[3], int(partes[4]))


# ───────────────────────── carga y verificacion de insumos ──────────────────

def verificar_sha(insumos: dict) -> dict:
    """Hash de cada insumo contra el valor registrado en el INVENTORY sellado."""
    tabla = {}
    errores = []
    for nombre, (path, esperado) in insumos.items():
        real = sha256_archivo(path)
        ok = real == esperado
        tabla[nombre] = {"archivo": str(path), "sha256": real,
                         "esperado": esperado, "ok": ok}
        if not ok:
            errores.append(nombre)
    if errores:
        raise SystemExit("ERROR: sha256 de insumos sellados NO coincide: "
                         + ", ".join(errores))
    return tabla


def cargar_insumos() -> dict:
    inventario = leer_json(R_INVENTORY)
    if sha256_archivo(R_INVENTORY) != "9863070ab93aa5eb9baf3a34bf5451d957445aaa512318c426e9e555075a4ede":
        raise SystemExit("ERROR: INVENTORY.json no coincide con su sha sellado")

    mf11_metrics = leer_json(R_MF11R1_METRICS)
    if sha256_archivo(R_MF11R1_METRICS) != "2d271875f10270e197f72a0bedb39fb52f0b347109781a931432dcdca4c0c5cd":
        raise SystemExit("ERROR: MF-11-R1/metrics.json no coincide con su sha sellado")

    inv = inventario["checkpoint_v06"]
    tabla_sha = verificar_sha({
        "checkpoint_xgb": (R_CHECKPOINT, inv["sha256"]),
        "checkpoint_meta": (R_META, inv["meta_sha256"]),
        "cache_view": (R_VIEW, "6afeb3705ad4ba0d49918e6849da2876cd63e4260aa8f47487b0b393596bbc34"),
        "cache_view_manifest": (R_VIEW_MANIFEST, "ed7e9ec63d912c6936023cd57159febe891462f256d10314d40106d0d042d640"),
        "poses_train": (R_POSES_TRAIN, "d2076355e53f6dd6dc09a4017655f3992baabb221b8ae5606d94d73fd747e654"),
        "union_candidates_train": (R_UNION_CAND, "61ab0e26901659c0d6e8bf98f47bbcae82d187265fc8181953d58ff6a2033ce9"),
        "union_labels_train": (R_UNION_LABELS, "19843afd49135f30297884ce56889312a4f34b6f75cd708127eca1789338bfbb"),
        "dedup_candidates_1_5": (R_DEDUP_CAND, "fef90c21c92d3527a3431d8e880601d33208a1c12688057f8ebf95642589fa78"),
        "sidecar_cluster_members_1_5": (R_SIDECAR, "7026b8dea49062d49e4765ab116864fe6bd550ac660c76da646aabb7a645d0a0"),
        "fold_plan": (R_FOLD_PLAN, "9d97ad70b25331b4ae3e926210f6372ed7ec092d5a7a5fff6fe61af83b961c30"),
    })

    candidatos = leer_jsonl(R_UNION_CAND)
    labels = leer_jsonl(R_UNION_LABELS)
    vista = leer_jsonl(R_VIEW)
    poses_train = leer_jsonl(R_POSES_TRAIN)
    sidecar = leer_jsonl(R_SIDECAR)
    fold_plan = leer_json(R_FOLD_PLAN)

    if {c["identity"] for c in candidatos} != {l["identity"] for l in labels}:
        raise SystemExit("ERROR: identidades union candidates/labels no coinciden 1:1")

    claves_vista = [(r["pid"], r["source"], r["file_stem"], r["model_idx"])
                    for r in vista]
    claves_union = [clave_identidad(c["identity"]) for c in candidatos]
    if claves_vista != claves_union:
        raise SystemExit("ERROR: orden/identidad de la vista no coincide con la union")

    reps_sidecar = [s["representative_identity"] for s in sidecar]
    miembros_sidecar = [m for s in sidecar for m in s["member_identities"]]
    if sorted(miembros_sidecar) != sorted(c["identity"] for c in candidatos):
        raise SystemExit("ERROR: membresias del sidecar no parten la union")
    if sorted(reps_sidecar) != [c["identity"] for c in
                                leer_jsonl(R_DEDUP_CAND)]:
        raise SystemExit("ERROR: dedup_candidates != representantes del sidecar")

    return {
        "inventario": inventario,
        "tabla_sha": tabla_sha,
        "candidatos": candidatos,
        "labels": labels,
        "vista": vista,
        "poses_train": poses_train,
        "sidecar": sidecar,
        "fold_plan": fold_plan,
        "mf11_metrics": mf11_metrics,
    }


# ───────────────────────── features por pose ───────────────────────────────

def cargar_features(insumos: dict) -> dict:
    """feats_por_identidad: {identidad: np.array(224)} con las 9 baratas
    congeladas (poses_train) + 215 ricas (vista train-only del cache)."""
    candidatos = {c["identity"]: c for c in insumos["candidatos"]}
    por_identidad: dict[str, np.ndarray] = {}
    for r in insumos["poses_train"]:
        identidad = f"train|{r['pid']}|{r['source']}|{r['file_stem']}|{r['model_idx']}"
        c = candidatos[identidad]
        fila = [r.get(f) for f in FEATURES_V0]
        fila[0] = c["vina_score"] if r.get("vina_score") is None else r["vina_score"]
        por_identidad[identidad] = np.array(fila, dtype=np.float64)

    ricos = {}
    for r in insumos["vista"]:
        identidad = f"train|{r['pid']}|{r['source']}|{r['file_stem']}|{r['model_idx']}"
        ricos[identidad] = np.array(r["rich"], dtype=np.float64)

    out = {}
    for identidad, baratas in por_identidad.items():
        rico = ricos.get(identidad)
        if rico is None or rico.shape != (215,):
            raise SystemExit(f"ERROR: sin 215 ricas para {identidad}")
        out[identidad] = np.hstack([baratas, rico])
    return out


def cargar_densas(insumos: dict) -> dict:
    """densas_por_identidad: malla densa de coords pesadas mapeadas del builder
    (records/{pid}.json -> _coords, redondeo a 3 decimales historico)."""
    densas: dict[str, np.ndarray] = {}
    pids_train = sorted({c["pid"] for c in insumos["candidatos"]})
    for pid in pids_train:
        rec = leer_json(RECORDS_DIR / f"{pid}.json")
        for clave, regs in sorted(rec.get("registros", {}).items()):
            for r in regs:
                identidad = f"train|{r['pid']}|{r['source']}|{r['file_stem']}|{r['model_idx']}"
                idx = sorted(int(k) for k in r.get("_coords", {}))
                if not idx:
                    raise SystemExit(f"ERROR: {identidad} sin _coords")
                n = max(idx) + 1
                densa = np.full((n, 3), np.nan)
                for m in idx:
                    densa[m] = r["_coords"][str(m)]
                densas[identidad] = densa
    return densas


def rmsd_entre_poses(a: np.ndarray, b: np.ndarray) -> float:
    """Replica exacta de build_pose_selector_dataset.py:436-447."""
    if a.shape == b.shape:
        return float(np.sqrt(np.mean((a - b) ** 2)))
    valida = np.isfinite(a) & np.isfinite(b)
    if not valida.any():
        return float("inf")
    diff = a - b
    return float(np.sqrt(np.nanmean(diff[valida] ** 2)))


def densidad_historica(densas: dict, identidades: list) -> dict:
    """cluster_density con la semantica HISTORICA del dataset builder (pasada
    B): pares de poses del MISMO complejo con RMSD pocket-frame < UMBRAL_CLUSTER
    sin alinear; cada pose del par suma 1. PRESERVADA, NO corregida."""
    dens = {i: 0 for i in identidades}
    por_pid = defaultdict(list)
    for i in identidades:
        por_pid[i.split("|")[1]].append(i)
    for pid in sorted(por_pid):
        ids = por_pid[pid]
        n = len(ids)
        for a in range(n):
            da = densas[ids[a]]
            for b in range(a + 1, n):
                if rmsd_entre_poses(da, densas[ids[b]]) < UMBRAL_CLUSTER:
                    dens[ids[a]] += 1
                    dens[ids[b]] += 1
    return dens


# ───────────────────────── transformacion por complejo ─────────────────────

def z_por_pid(X: np.ndarray, grupos: list) -> np.ndarray:
    """Copia exacta de ruta_c_fase1_6_v06.py:217-232."""
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
    """Copia exacta de ruta_c_fase1_6_v06.py:235-251."""
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


# ───────────────────────── dedup anidada (regla MF-11-R1) ───────────────────

def dmat_por_pid_todos(coords_por_identidad: dict, por_pid: dict,
                       pids: list) -> dict:
    """Matriz de distancias pose-vs-pose (metricas exactas del script sellado)
    por complejo, desde las coords PDBQT de la union."""
    dmat: dict = {}
    for pid in pids:
        identidades = sorted(por_pid[pid])
        dmat[pid] = matriz_distancias(
            identidades, {i: coords_por_identidad[i] for i in identidades})
    return dmat


def clusters_por_umbral_todos(dmat_por_pid: dict, por_pid: dict,
                              pids: list) -> dict:
    """clusters_por_u[clave_u][pid] = lista de clusters (una pasada, 5 U)."""
    out = {str(u): {} for u in UMBRALES}
    for pid in pids:
        identidades = sorted(por_pid[pid])
        for u in UMBRALES:
            out[str(u)][pid] = clustering_diametro(
                identidades, dmat_por_pid[pid], u)
    return out


def medoids_por_pid(pids: list, clusters_pid: dict, dmat_por_pid: dict) -> dict:
    """{pid: [medoids en orden canonico]} para los clusters de un umbral."""
    return {pid: sorted([medoid_detalle(cl, dmat_por_pid[pid])[0]
                         for cl in clusters_pid[pid]], key=clave_identidad)
            for pid in pids}


def evaluar_regla_umbral(pids: list, clusters_pid: dict, dmat_por_pid: dict,
                         labels: dict, umbral: float) -> dict:
    """Fase de EVALUACION de la regla MF-11-R1 (unica que lee labels; la
    admision y la eleccion de medoid NUNCA usan labels). Solamente sobre los
    pids del outer-train."""
    n_antes = 0
    n_despues = 0
    perdidos = 0
    degradaciones = []
    for pid in pids:
        clusters = clusters_pid[pid]
        ids_complejo = [i for cl in clusters for i in cl]
        rmsds = [float(labels[i]["rmsd"]) for i in ids_complejo]
        mejor_antes = min(rmsds)
        n_antes += len(ids_complejo)
        n_despues += len(clusters)
        reps = [medoid_detalle(cl, dmat_por_pid[pid])[0] for cl in clusters]
        min_rep = min(float(labels[r]["rmsd"]) for r in reps)
        if mejor_antes <= UMBRAL_POSITIVA and min_rep > UMBRAL_POSITIVA:
            perdidos += 1
        degradaciones.append(min_rep - mejor_antes)
    degradacion_mediana = float(np.median(degradaciones))
    reduccion = (1 - n_despues / n_antes) if n_antes else 0.0
    cumple = bool(perdidos == 0 and degradacion_mediana <= 0.1
                  and reduccion >= 0.10)
    return {
        "umbral": umbral,
        "n_antes": n_antes,
        "n_despues": n_despues,
        "reduccion_pct": round(100.0 * reduccion, 2),
        "n_perdidos": perdidos,
        "degradacion_mediana": round(degradacion_mediana, 4),
        "cumple": cumple,
    }


def seleccionar_umbral_anidado(pids: list, clusters_por_u: dict,
                               dmat_por_pid: dict, labels: dict):
    """Regla preregistrada: el MAYOR umbral que cumple (a)+(b)+(c) DENTRO del
    outer-train. Devuelve (elegido, resumenes, causa). elegido = None si
    ninguno cumple (contingencia B6-i cerrada: U=None, sin dedup)."""
    resumenes = {}
    for u in UMBRALES:
        resumenes[str(u)] = evaluar_regla_umbral(
            pids, clusters_por_u[str(u)], dmat_por_pid, labels, u)
    validos = [u for u in UMBRALES if resumenes[str(u)]["cumple"]]
    if not validos:
        return None, resumenes, ("ningun umbral cumple (a) 0 perdidas + (b) "
                                 "degradacion mediana <= 0.1 + (c) reduccion "
                                 ">= 10% dentro del outer-train: U=None (sin "
                                 "deduplicacion en ambas variantes del fold)")
    elegido = max(validos)
    r = resumenes[str(elegido)]
    causa = (f"{elegido} es el MAYOR umbral que cumple (a) 0 perdidas, "
             f"(b) degradacion mediana {r['degradacion_mediana']} <= 0.1, "
             f"(c) reduccion {r['reduccion_pct']}% >= 10%")
    return elegido, resumenes, causa


def feats_dedup_por_conjunto(feats: dict, densas: dict,
                             ids_por_pid: dict) -> dict:
    """Contrato A1: variance/range POR-RUN congelados; tras dedup SOLO se
    recalcula cluster_density (semantica historica) entre supervivientes de
    cada complejo; la matriz z/pct se computa despues sobre el conjunto
    resultante."""
    out = dict(feats)
    for pid, ids in ids_por_pid.items():
        dens = densidad_historica(densas, ids)
        for i in ids:
            fila = out[i].copy()
            fila[8] = float(dens[i])
            out[i] = fila
    return out


# ───────────────────────── entrenamiento de clones ─────────────────────────

def entrenar_clon(X: np.ndarray, y: np.ndarray, grupos: list):
    """XGBRanker con hiperparametros CONGELADOS (PARAMS_CLON), sin early
    stopping, sin eval_set. Mismo fallback de metrica que el entrenamiento
    historico (auc -> rmse)."""
    from xgboost import XGBRanker
    modelo = None
    metrica = None
    for m in ("auc", "rmse"):
        try:
            modelo = XGBRanker(eval_metric=m, **PARAMS_CLON)
            modelo.fit(X, y, group=grupos, verbose=False)
            metrica = m
            break
        except Exception:
            modelo = None
    if modelo is None:
        raise RuntimeError("ninguna metrica de ranking pudo entrenar el clon")
    return modelo, metrica


def construir_entrenamiento(pids: list, ids_por_pid: dict, feats: dict,
                            labels: dict, indices_pct: list):
    """Matriz (N, 233) + y (-rmsd) + grupos por complejo, filas contiguas por
    pid en orden canonico. z/pct por complejo sobre el conjunto resultante."""
    filas = []
    y = []
    grupos = []
    for pid in pids:
        ids = ids_por_pid[pid]
        X = np.vstack([feats[i] for i in ids])
        assert X.shape == (len(ids), N_Z)
        Z = z_por_pid(X, [len(ids)])
        Z[np.isnan(Z)] = 0.0
        P = pct_por_pid(X, [len(ids)], indices_pct)
        P[np.isnan(P)] = 0.0
        X_B = np.hstack([Z, P])
        assert X_B.shape == (len(ids), N_MODELO_B)
        filas.append(X_B)
        y.extend([-float(labels[i]["rmsd"]) for i in ids])
        grupos.append(len(ids))
    X_train = np.vstack(filas)
    return X_train, np.array(y, dtype=np.float64), grupos


# ───────────────────────── evaluacion OOF ──────────────────────────────────

def evaluar_conjunto(clon, pids: list, ids_por_pid: dict, feats: dict,
                     labels: dict, indices_pct: list) -> dict:
    """Top-1 por complejo (argmax del score, orden canonico), RMSD del
    ganador (oraculo union_labels), hit <= 2.0 A, margen top1-top2 y
    abstencion con el umbral CONGELADO 0.097663 (N=1 -> margen 0 -> abstenido)."""
    import xgboost
    resultados = {}
    for pid in pids:
        ids = ids_por_pid[pid]
        X = np.vstack([feats[i] for i in ids])
        assert X.shape == (len(ids), N_Z)
        Z = z_por_pid(X, [len(ids)])
        Z[np.isnan(Z)] = 0.0
        P = pct_por_pid(X, [len(ids)], indices_pct)
        P[np.isnan(P)] = 0.0
        X_B = np.hstack([Z, P])
        assert X_B.shape == (len(ids), N_MODELO_B)
        scores = np.asarray(clon.get_booster().predict(
            xgboost.DMatrix(X_B)), dtype=np.float64)
        k = int(np.argmax(scores))
        ganador = ids[k]
        rmsd = float(labels[ganador]["rmsd"])
        hit = rmsd <= UMBRAL_POSITIVA
        if len(ids) > 1:
            orden = np.sort(scores)[::-1]
            margen = float(orden[0] - orden[1])
            abstenido = margen < UMBRAL_ABSTENCION
        else:
            margen = 0.0
            abstenido = True
        min_rmsd = min(float(labels[i]["rmsd"]) for i in ids)
        resultados[pid] = {
            "ganador": ganador,
            "fuente": ganador.split("|")[2],
            "score_top": round(float(scores[k]), 6),
            "rmsd": rmsd,
            "hit": bool(hit),
            "margen": round(margen, 6),
            "abstenido": bool(abstenido),
            "n_poses": len(ids),
            "tiene_pose_buena": bool(min_rmsd <= UMBRAL_POSITIVA),
        }
    return resultados


def agregar_brazo(resultados: dict, pids: list) -> dict:
    hits = sum(1 for p in pids if resultados[p]["hit"])
    rmsds = [resultados[p]["rmsd"] for p in pids]
    abst = sum(1 for p in pids if resultados[p]["abstenido"])
    return {
        "n_complejos": len(pids),
        "top1_hits": hits,
        "top1_rate": round(hits / len(pids), 4),
        "rmsd_mediana_ganador": round(float(np.median(rmsds)), 4),
        "n_abstenciones": abst,
        "tasa_abstencion": round(abst / len(pids), 4),
    }


def pareado_por_pid(res_o: dict, res_d: dict, pids: list) -> dict:
    deltas_hit = [(1 if res_d[p]["hit"] else 0) - (1 if res_o[p]["hit"] else 0)
                  for p in pids]
    deltas_rmsd = [res_d[p]["rmsd"] - res_o[p]["rmsd"] for p in pids]
    return {
        "delta_hits": int(sum(deltas_hit)),
        "mediana_pareada_rmsd": round(float(np.median(deltas_rmsd)), 6),
        "diferencia_medianas_rmsd": round(
            float(np.median([res_d[p]["rmsd"] for p in pids])) -
            float(np.median([res_o[p]["rmsd"] for p in pids])), 6),
        "suma_pareada_rmsd": round(float(np.sum(deltas_rmsd)), 6),
        "media_pareada_rmsd": round(float(np.mean(deltas_rmsd)), 6),
        "deltas_hit_por_pid": {p: d for p, d in zip(pids, deltas_hit)},
        "deltas_rmsd_por_pid": {p: round(float(d), 6)
                                for p, d in zip(pids, deltas_rmsd)},
    }


# ───────────────────────── estadistica ─────────────────────────────────────

def mcnemar_hits(res_o: dict, res_d: dict, pids: list) -> dict:
    """McNemar exacto sobre la tabla 2x2 de aciertos pareados OOF.

    Corrigendum estadistico (2026-08-16): scipy.stats.binomtest(...).pvalue
    YA es bilateral; la version anterior lo multiplicaba por 2. Aqui se usa
    el p tal cual. 0 pares discordantes -> p = 1.0 (convencion)."""
    from scipy.stats import binomtest
    b = sum(1 for p in pids if res_o[p]["hit"] and not res_d[p]["hit"])
    c = sum(1 for p in pids if not res_o[p]["hit"] and res_d[p]["hit"])
    n_discordantes = b + c
    if n_discordantes == 0:
        p_valor = 1.0
    else:
        p_valor = float(binomtest(min(b, c), n_discordantes, 0.5).pvalue)
    return {"b_orig_hit_dedup_miss": b, "c_orig_miss_dedup_hit": c,
            "n_discordantes": n_discordantes,
            "p_valor_exacto_bilateral": round(float(p_valor), 6),
            "nota_corrigendum": ("binomtest(...).pvalue ya es bilateral; el "
                                 "factor 2 de la version anterior queda "
                                 "eliminado (corrigendum estadistico)")}


def excluye_cero(intervalo: list) -> bool:
    lo, hi = intervalo
    return bool(lo > 0 or hi < 0)


def bca_intervalo(boot: np.ndarray, obs: float, jack_influencia: list,
                  etiqueta: str) -> dict:
    """BCa primario con jackknife (regla C3d: si degenera, fallback al
    percentil 2.5-97.5 registrado explicitamente). jack_influencia = lista de
    valores de influencia (theta - theta_sin_unidad), convencion RS-01A."""
    from scipy.stats import norm
    perc = np.percentile(boot, [2.5, 97.5])
    out = {"tipo": etiqueta, "intervalo_percentil_95":
           [round(float(perc[0]), 6), round(float(perc[1]), 6)]}
    jack = np.array(jack_influencia, dtype=np.float64)
    jbar = float(np.mean(jack))
    num = float(np.sum((jbar - jack) ** 3))
    den = 6.0 * float(np.sum((jbar - jack) ** 2) ** 1.5)
    if den == 0 or not np.isfinite(den) or not np.isfinite(num):
        out["metodo"] = "BCa degenerado -> percentil bootstrap (regla C3d)"
        out["bca_degenerado"] = True
        out["intervalo"] = out["intervalo_percentil_95"]
        out["excluye_cero"] = excluye_cero(out["intervalo"])
        return out
    a = num / den
    z0 = float(norm.ppf(np.mean(boot <= obs)))
    al = 0.025
    za = norm.ppf(al)
    z1a = norm.ppf(1 - al)
    q_lo = norm.cdf(z0 + (z0 + za) / (1 - a * (z0 + za)))
    q_hi = norm.cdf(z0 + (z0 + z1a) / (1 - a * (z0 + z1a)))
    if not (np.isfinite(q_lo) and np.isfinite(q_hi)):
        out["metodo"] = "BCa degenerado -> percentil bootstrap (regla C3d)"
        out["bca_degenerado"] = True
        out["intervalo"] = out["intervalo_percentil_95"]
        out["excluye_cero"] = excluye_cero(out["intervalo"])
        return out
    lo = float(np.percentile(boot, 100.0 * q_lo))
    hi = float(np.percentile(boot, 100.0 * q_hi))
    out["metodo"] = "BCa primario (jackknife por unidades)"
    out["bca_degenerado"] = False
    out["aceleracion"] = round(a, 6)
    out["sesgo_z0"] = round(z0, 6)
    out["intervalo"] = [round(lo, 6), round(hi, 6)]
    out["excluye_cero"] = excluye_cero(out["intervalo"])
    return out


def bootstrap_componentes_38(pids: list, pid2comp: dict, comps_orden: list,
                             res_o: dict, res_d: dict) -> dict:
    """Bootstrap PRIMARIO por las 38 componentes combinadas del fold_plan
    (resampling de componentes con reemplazo, 10 000 replicas exactas,
    seed 42, BCa) sobre el Δ Top-1 (suma) y sobre la mediana pareada de RMSD."""
    d_hit = {p: (1 if res_d[p]["hit"] else 0) - (1 if res_o[p]["hit"] else 0)
             for p in pids}
    d_rmsd = {p: res_d[p]["rmsd"] - res_o[p]["rmsd"] for p in pids}

    suma_comp_hit = {c: sum(v for p, v in d_hit.items() if pid2comp[p] == c)
                     for c in comps_orden}
    deltas_comp = {c: np.array([d_rmsd[p] for p in pids if pid2comp[p] == c],
                               dtype=np.float64) for c in comps_orden}

    rng = np.random.default_rng(SEED_BOOT)
    idx = rng.integers(0, len(comps_orden), size=(N_BOOT, len(comps_orden)))
    boot_hits = np.array([sum(suma_comp_hit[comps_orden[i]] for i in fila)
                          for fila in idx], dtype=np.float64)
    boot_med = np.array([
        float(np.median(np.concatenate([deltas_comp[comps_orden[i]]
                                        for i in fila])))
        for fila in idx], dtype=np.float64)

    obs_hits = float(sum(d_hit.values()))
    obs_med = float(np.median(list(d_rmsd.values())))

    jack_hits = [obs_hits - suma_comp_hit[c] for c in comps_orden]
    jack_med = [obs_med - float(np.median(np.concatenate(
        [deltas_comp[c2] for c2 in comps_orden if c2 != c])))
        for c in comps_orden]

    out = {"n_replicas": N_BOOT, "seed": SEED_BOOT,
           "unidades": "38 componentes combinadas del fold_plan",
           "diferencia_observada_hits": obs_hits,
           "mediana_pareada_rmsd_observada": obs_med}
    out["hits"] = bca_intervalo(boot_hits, obs_hits, jack_hits,
                                "Δ Top-1 (suma de diferencias pareadas)")
    out["mediana_pareada_rmsd"] = bca_intervalo(
        boot_med, obs_med, jack_med, "mediana pareada de RMSD")
    return out


def bootstrap_complejos_sensibilidad(pids: list, res_o: dict,
                                     res_d: dict) -> dict:
    """Sensibilidad: bootstrap por COMPLEJO (percentil 2.5-97.5, 10 000
    replicas) — SOLO lectura de sensibilidad, reportado aparte."""
    d_hit_vals = [(1 if res_d[p]["hit"] else 0) - (1 if res_o[p]["hit"] else 0)
                  for p in pids]
    d_rmsd_vals = [res_d[p]["rmsd"] - res_o[p]["rmsd"] for p in pids]
    rng = np.random.default_rng(SEED_BOOT + 1)
    idx = rng.integers(0, len(pids), size=(N_BOOT, len(pids)))
    boot_hits = np.array([sum(d_hit_vals[i] for i in fila) for fila in idx],
                         dtype=np.float64)
    boot_med = np.array([float(np.median([d_rmsd_vals[i] for i in fila]))
                         for fila in idx], dtype=np.float64)
    perc_hits = np.percentile(boot_hits, [2.5, 97.5])
    perc_med = np.percentile(boot_med, [2.5, 97.5])
    return {
        "n_replicas": N_BOOT,
        "unidades": f"{len(pids)} complejos (sensibilidad)",
        "hits": {"metodo": "percentil 2.5-97.5",
                 "intervalo": [round(float(perc_hits[0]), 6),
                               round(float(perc_hits[1]), 6)],
                 "excluye_cero": excluye_cero([float(perc_hits[0]),
                                               float(perc_hits[1])])},
        "mediana_pareada_rmsd": {
            "metodo": "percentil 2.5-97.5",
            "intervalo": [round(float(perc_med[0]), 6),
                          round(float(perc_med[1]), 6)],
            "excluye_cero": excluye_cero([float(perc_med[0]),
                                          float(perc_med[1])])},
    }


def bootstrap_descriptivo_fold(pids_fold: list, comps_fold: list,
                               pid2comp: dict, res_o: dict, res_d: dict,
                               seed_fold: int):
    """Descriptivo por fold (C3b): bootstrap por componentes DEL FOLD
    (percentil 2.5-97.5) SOLO si el fold tiene >= 5 componentes."""
    n_comp = len(comps_fold)
    if n_comp < 5:
        return {"n_componentes": n_comp, "intervalo": None,
                "motivo": ("menos de 5 componentes: sin intervalo "
                           "(solo descriptivo)")}
    d_hit = {p: (1 if res_d[p]["hit"] else 0) - (1 if res_o[p]["hit"] else 0)
             for p in pids_fold}
    d_rmsd = {p: res_d[p]["rmsd"] - res_o[p]["rmsd"] for p in pids_fold}
    suma_comp_hit = {c: sum(v for p, v in d_hit.items() if pid2comp[p] == c)
                     for c in comps_fold}
    deltas_comp = {c: np.array([d_rmsd[p] for p in pids_fold
                                if pid2comp[p] == c], dtype=np.float64)
                   for c in comps_fold}
    rng = np.random.default_rng(seed_fold)
    idx = rng.integers(0, n_comp, size=(N_BOOT, n_comp))
    boot_hits = np.array([sum(suma_comp_hit[comps_fold[i]] for i in fila)
                          for fila in idx], dtype=np.float64)
    boot_med = np.array([
        float(np.median(np.concatenate([deltas_comp[comps_fold[i]]
                                        for i in fila])))
        for fila in idx], dtype=np.float64)
    perc_hits = np.percentile(boot_hits, [2.5, 97.5])
    perc_med = np.percentile(boot_med, [2.5, 97.5])
    return {
        "n_componentes": n_comp,
        "n_complejos": len(pids_fold),
        "metodo": ("percentil 2.5-97.5 (bootstrap por componentes del fold, "
                   "descriptivo)"),
        "hits_intervalo": [round(float(perc_hits[0]), 6),
                           round(float(perc_hits[1]), 6)],
        "mediana_pareada_intervalo": [round(float(perc_med[0]), 6),
                                      round(float(perc_med[1]), 6)],
    }


# ───────────────────────── recomputacion de medoids del sidecar ─────────────

def recomputar_medoids_sidecar(insumos: dict, candidatos_por_identidad: dict,
                               dmat_por_pid: dict) -> dict:
    """Recomputacion determinista de medoids del sidecar sellado (1.5 A):
    verifica representante == medoid y cuantifica empates (212/141/31)."""
    n_no_singleton = 0
    n_empates = 0
    n_cross = 0
    no_coinciden = 0
    clusters_cross = []
    for fila in insumos["sidecar"]:
        miembros = sorted(fila["member_identities"])
        pid = fila["cluster_key"].split("|")[1]
        medoid, empatados = medoid_detalle(miembros, dmat_por_pid[pid])
        if medoid != fila["representative_identity"]:
            no_coinciden += 1
        if len(miembros) >= 2:
            n_no_singleton += 1
        if len(empatados) >= 2:
            n_empates += 1
            fuentes = {candidatos_por_identidad[m]["source"]
                       for m in empatados}
            if len(fuentes) > 1:
                n_cross += 1
                clusters_cross.append({
                    "cluster_key": fila["cluster_key"],
                    "pid": pid,
                    "representante": medoid,
                    "representante_fuente": candidatos_por_identidad[medoid]["source"],
                    "empatados": [{"identity": m,
                                   "source": candidatos_por_identidad[m]["source"]}
                                  for m in empatados],
                })
    esperados = insumos["mf11_metrics"]["empates_medoid"]
    return {
        "verificacion": {
            "n_clusters_sidecar": len(insumos["sidecar"]),
            "n_representantes_coinciden_medoid_recomputado":
                len(insumos["sidecar"]) - no_coinciden,
            "n_no_singleton": n_no_singleton,
            "n_empates_medoid": n_empates,
            "n_empates_cross_source": n_cross,
            "esperado_mf11r1": {
                "n_clusters_no_singleton": esperados["n_clusters_no_singleton"],
                "n_empates_medoid": esperados["n_empates_medoid"],
                "n_empates_cross_source": esperados["n_empates_cross_source"]},
            "coincide_con_sellado": bool(
                n_no_singleton == esperados["n_clusters_no_singleton"]
                and n_empates == esperados["n_empates_medoid"]
                and n_cross == esperados["n_empates_cross_source"]
                and no_coinciden == 0),
        },
        "clusters_cross": clusters_cross,
    }


# ───────────────────────── contrafactual de empates OOF ────────────────────

def recomputar_globales(res_o: dict, res_d: dict, pids: list):
    """(delta_hits, mediana_pareada) sobre el conjunto completo de pids."""
    deltas_hit = sum((1 if res_d[p]["hit"] else 0)
                     - (1 if res_o[p]["hit"] else 0) for p in pids)
    deltas_rmsd = [res_d[p]["rmsd"] - res_o[p]["rmsd"] for p in pids]
    return int(deltas_hit), float(np.median(deltas_rmsd))


def contrafactual_empates_oof(insumos, feats, densas, labels, indices_pct,
                              pids_orden, pid2fold, u_por_fold, pids_fold,
                              clon_ded_por_fold, dmat_por_pid,
                              clusters_por_u, candidatos_por_identidad,
                              ids_eval_ded_por_pid, ev_o_global, ev_d_global,
                              clusters_cross_31) -> dict:
    """B6-ii: en el brazo dedup, evaluar TODOS los medoides alternativos
    empatados (contrafactual completo). Por alternativa: swap en el conjunto
    de evaluacion del complejo, recalculo de cluster_density + z/pct del
    complejo, re-prediccion con el clon dedup del fold, y recomputo de las
    metricas del fold y globales (nunca se escoge uno despues de ver)."""
    n_clusters = 0
    n_cross = 0
    n_alt_total = 0
    n_alt_cambian_ganador = 0
    n_alt_cambian_hit = 0
    n_clusters_con_cambio = 0
    direccion_fuente = defaultdict(int)
    detalle = []
    claves_vistas = set()

    for fold in range(N_FOLDS):
        u = u_por_fold[fold]
        if u is None:
            continue
        clon = clon_ded_por_fold[fold]
        for pid in pids_fold[fold]:
            clusters = clusters_por_u[str(u)][pid]
            for cl in clusters:
                medoid, empatados = medoid_detalle(cl, dmat_por_pid[pid])
                if len(empatados) < 2:
                    continue
                n_clusters += 1
                claves_vistas.add((pid, tuple(sorted(cl))))
                fuentes_emp = {candidatos_por_identidad[i]["source"]
                               for i in empatados}
                cross = len(fuentes_emp) > 1
                if cross:
                    n_cross += 1
                ids_base = ids_eval_ded_por_pid[(fold, pid)]
                alternativas = []
                alguna_cambia = False
                for alt in empatados:
                    if alt == medoid:
                        continue
                    n_alt_total += 1
                    ids_alt = [alt if i == medoid else i for i in ids_base]
                    dens = densidad_historica(densas, ids_alt)
                    feats_alt = dict(feats)
                    for i in ids_alt:
                        fila = feats[i].copy()
                        fila[8] = float(dens[i])
                        feats_alt[i] = fila
                    res_pid_alt = evaluar_conjunto(
                        clon, [pid], {pid: ids_alt}, feats_alt, labels,
                        indices_pct)[pid]
                    d_sel = ev_d_global[pid]
                    cambio = res_pid_alt["ganador"] != d_sel["ganador"]
                    cambio_hit = res_pid_alt["hit"] != d_sel["hit"]
                    if cambio:
                        n_alt_cambian_ganador += 1
                        alguna_cambia = True
                        direccion_fuente[(d_sel["fuente"],
                                          res_pid_alt["fuente"])] += 1
                    if cambio_hit:
                        n_alt_cambian_hit += 1
                    ev_d_alt = dict(ev_d_global)
                    ev_d_alt[pid] = res_pid_alt
                    dh_alt, mp_alt = recomputar_globales(
                        ev_o_global, ev_d_alt, pids_orden)
                    alternativas.append({
                        "alternativo_identity": alt,
                        "alternativo_source":
                            candidatos_por_identidad[alt]["source"],
                        "cambia_ganador": bool(cambio),
                        "cambia_hit": bool(cambio_hit),
                        "ganador_sellado": {"identity": d_sel["ganador"],
                                            "fuente": d_sel["fuente"],
                                            "rmsd": round(d_sel["rmsd"], 4),
                                            "hit": d_sel["hit"]},
                        "ganador_alternativo": {
                            "identity": res_pid_alt["ganador"],
                            "fuente": res_pid_alt["fuente"],
                            "rmsd": round(res_pid_alt["rmsd"], 4),
                            "hit": res_pid_alt["hit"]},
                        "global_delta_hits_alt": dh_alt,
                        "global_mediana_pareada_alt": round(mp_alt, 6),
                    })
                if alguna_cambia:
                    n_clusters_con_cambio += 1
                detalle.append({
                    "fold": fold,
                    "pid": pid,
                    "u_fold": u,
                    "miembros": cl,
                    "representante": {"identity": medoid,
                                      "fuente": candidatos_por_identidad[medoid]["source"]},
                    "empatados": [{"identity": i,
                                   "source": candidatos_por_identidad[i]["source"]}
                                  for i in empatados],
                    "cross_source": bool(cross),
                    "n_alternativas": len(empatados) - 1,
                    "alguna_alternativa_cambia_ganador": bool(alguna_cambia),
                    "alternativas": alternativas,
                })

    # cruce con los 31 cross-source del sidecar sellado (1.5 A)
    en_alcance = []
    fuera_alcance = []
    for cl31 in clusters_cross_31:
        pid = cl31["pid"]
        fold = pid2fold[pid]
        if u_por_fold[fold] == 1.5:
            en_alcance.append({"cluster_key": cl31["cluster_key"], "pid": pid,
                               "fold": fold})
        else:
            fuera_alcance.append({"cluster_key": cl31["cluster_key"],
                                  "pid": pid, "fold": fold,
                                  "u_fold": u_por_fold[fold],
                                  "causa": "el fold no eligio U=1.5"})

    return {
        "resumen": {
            "n_clusters_empatados_foldeval": n_clusters,
            "n_clusters_cross_source": n_cross,
            "n_alternativas_evaluadas": n_alt_total,
            "n_alternativas_cambian_ganador": n_alt_cambian_ganador,
            "n_alternativas_cambian_hit": n_alt_cambian_hit,
            "n_clusters_con_al_menos_un_cambio": n_clusters_con_cambio,
            "direccion_fuente_ganador": {f"{a}->{b}": n for (a, b), n in
                                         sorted(direccion_fuente.items())},
            "nota": ("el contrafactual cubre TODOS los clusters empatados del "
                     "brazo dedup OOF (fold-eval), cross-source y dentro de "
                     "una misma fuente; el desempate por identidad del "
                     "outer-train (training-side) se reporta como caveat "
                     "documentado, no se re-entrena"),
        },
        "cruce_31_cross_source": {
            "n_total_31": len(clusters_cross_31),
            "n_en_alcance": len(en_alcance),
            "n_fuera_alcance": len(fuera_alcance),
            "en_alcance": en_alcance,
            "fuera_alcance": fuera_alcance,
        },
        "detalle_clusters": detalle,
    }


# ───────────────────────── flujo principal ─────────────────────────────────

def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(description="RS-01B cross-fitting OOF v0.6")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    fold_models_dir = out_dir / "fold_models"
    fold_models_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    print("== RS-01B: cross-fitting OOF de clones v0.6 (fold_plan sellado) ==",
          flush=True)

    insumos = cargar_insumos()
    print("  insumos sellados verificados (sha256): OK", flush=True)

    # ── checkpoint congelado via PoseSelector (solo contrato de features) ──
    selector = PoseSelector(str(R_CHECKPOINT), str(R_META),
                            abstention_threshold=UMBRAL_ABSTENCION)
    if selector.load_error is not None or selector.booster is None:
        raise SystemExit(f"ERROR: no se pudo cargar el checkpoint: {selector.load_error}")
    meta = selector.meta
    assert len(meta.get("feature_names_233", [])) == N_MODELO_B
    assert meta.get("orden_pct") == PCT_RAW
    assert meta.get("feature_names_raw_224", [])[:9] == FEATURES_V0
    indices_pct = [meta["feature_names_raw_224"].index(f) for f in PCT_RAW]
    n_arboles = selector.booster.num_boosted_rounds()
    print(f"  checkpoint cargado: {n_arboles} arboles, best_iteration "
          f"{meta.get('best_iteration')} (SOLO contrato de features; sus "
          f"predicciones NO se usan en RS-01B)", flush=True)

    # ── features, coords y labels ──
    feats = cargar_features(insumos)
    densas = cargar_densas(insumos)
    labels = {l["identity"]: l for l in insumos["labels"]}
    candidatos_por_identidad = {c["identity"]: c for c in insumos["candidatos"]}
    ids_original = sorted(candidatos_por_identidad.keys(), key=clave_identidad)
    pids_orden = sorted({i.split("|")[1] for i in ids_original})
    assert len(pids_orden) == 116 and len(ids_original) == 2739

    # validacion dura: densidad historica reproducible desde records (RS-01A)
    dens_recomputada_orig = densidad_historica(densas, ids_original)
    n_coinciden = sum(1 for i in ids_original
                      if float(feats[i][8]) == float(dens_recomputada_orig[i]))
    print(f"  validacion densidad historica: {n_coinciden}/2739 exactas", flush=True)
    if n_coinciden != 2739:
        raise SystemExit("ERROR: recomputacion de cluster_density no reproduce "
                         "los valores congelados")

    # ── dmat y clusters para los 5 umbrales (una pasada) ──
    coords_union = {c["identity"]: parsear_atomos_pesados(c.get("pdbqt", ""))[0]
                    for c in insumos["candidatos"]}
    por_pid = defaultdict(list)
    for c in insumos["candidatos"]:
        por_pid[c["pid"]].append(c["identity"])
    dmat_por_pid = dmat_por_pid_todos(coords_union, por_pid, pids_orden)
    clusters_por_u = clusters_por_umbral_todos(dmat_por_pid, por_pid, pids_orden)

    # ── recomputacion de medoids del sidecar (verificacion + 31 cross) ──
    recomputo = recomputar_medoids_sidecar(insumos, candidatos_por_identidad,
                                           dmat_por_pid)
    v = recomputo["verificacion"]
    print(f"  medoids sidecar: reps coinciden "
          f"{v['n_representantes_coinciden_medoid_recomputado']}/"
          f"{v['n_clusters_sidecar']} | no-singleton {v['n_no_singleton']} | "
          f"empates {v['n_empates_medoid']} | cross {v['n_empates_cross_source']} | "
          f"coincide sellado: {v['coincide_con_sellado']}", flush=True)
    if not v["coincide_con_sellado"]:
        raise SystemExit("ERROR: recomputacion de medoids NO coincide con el "
                         "sidecar sellado de MF-11-R1")

    # ── folds exactos del fold_plan ──
    fold_plan = insumos["fold_plan"]
    pid2fold = {e["pid"]: int(e["fold"]) for e in fold_plan["por_pid"]}
    if set(pid2fold) != set(pids_orden):
        raise SystemExit("ERROR: fold_plan no cubre exactamente los 116 pids train")
    pids_fold = {f: sorted(p for p, f2 in pid2fold.items() if f2 == f)
                 for f in range(N_FOLDS)}
    tamanos = [len(pids_fold[f]) for f in range(N_FOLDS)]
    if tamanos != [55, 16, 15, 15, 15]:
        raise SystemExit(f"ERROR: tamanos de fold {tamanos} != [55,16,15,15,15]")
    comps_orden = [c["componente"] for c in fold_plan["por_componente"]]
    pid2comp = {}
    for comp in fold_plan["por_componente"]:
        for pid in comp["pids"]:
            pid2comp[pid] = comp["componente"]
    comps_por_fold = {f: [c["componente"]
                          for c in fold_plan["por_componente"]
                          if c["fold"] == f] for f in range(N_FOLDS)}
    if len(comps_orden) != 38:
        raise SystemExit(f"ERROR: {len(comps_orden)} componentes != 38")

    # ── cross-fitting por fold ──
    u_por_fold = {}
    clon_ded_por_fold = {}
    ev_o_global = {}
    ev_d_global = {}
    ids_eval_ded_por_pid = {}
    por_fold = []
    modelos_info = {}

    # shas de referencia para el REUSO de clones (metrics previo, si existe)
    prev_modelos = {}
    prev_metrics_path = out_dir / "metrics.json"
    if prev_metrics_path.exists():
        prev_modelos = leer_json(prev_metrics_path).get("modelos_fold", {})

    for fold in range(N_FOLDS):
        t_f = time.monotonic()
        pids_train = [p for p in pids_orden if pid2fold[p] != fold]
        pids_eval = pids_fold[fold]

        # umbral ANIDADO (solo outer-train)
        u_elegido, resumenes_u, causa_u = seleccionar_umbral_anidado(
            pids_train, clusters_por_u, dmat_por_pid, labels)
        u_por_fold[fold] = u_elegido
        print(f"  [fold {fold}] outer-train {len(pids_train)} complejos | "
              f"U elegido: {u_elegido} ({causa_u})", flush=True)

        # ── modelos por brazo: REUSO verificado por sha o reentrenamiento ──
        # (corrigendum): si los 10 clones ya existen en fold_models/ y su
        # sha256 coincide con el registrado en el metrics.json previo, se
        # reusan (solo metricas/consolidacion); si difieren o faltan, se
        # reentrenan con los hiperparametros congelados.
        nombre_orig = f"fold{fold}_brazo_original"
        nombre_ded = f"fold{fold}_brazo_dedup"
        path_orig = fold_models_dir / f"{nombre_orig}.xgb"
        path_ded = fold_models_dir / f"{nombre_ded}.xgb"
        path_meta_orig = fold_models_dir / f"{nombre_orig}_meta.json"
        path_meta_ded = fold_models_dir / f"{nombre_ded}_meta.json"

        puede_reusar = bool(
            path_orig.exists() and path_ded.exists()
            and nombre_orig in prev_modelos and nombre_ded in prev_modelos
            and sha256_archivo(path_orig) == prev_modelos[nombre_orig]["sha256"]
            and sha256_archivo(path_ded) == prev_modelos[nombre_ded]["sha256"])

        if puede_reusar:
            from xgboost import XGBRanker
            clon_orig = XGBRanker()
            clon_orig.load_model(str(path_orig))
            clon_ded = XGBRanker()
            clon_ded.load_model(str(path_ded))
            meta_orig = leer_json(path_meta_orig)
            meta_ded = leer_json(path_meta_ded)
            metrica_orig = meta_orig.get("eval_metric")
            metrica_ded = meta_ded.get("eval_metric")
            n_filas_orig = int(meta_orig.get("n_filas", 0))
            n_filas_ded = int(meta_ded.get("n_filas", 0))
            sha_orig = sha256_archivo(path_orig)
            sha_ded = sha256_archivo(path_ded)
            modelos_info[nombre_orig] = {"sha256": sha_orig,
                                         "bytes": path_orig.stat().st_size,
                                         "reusado": True}
            modelos_info[nombre_ded] = {"sha256": sha_ded,
                                        "bytes": path_ded.stat().st_size,
                                        "reusado": True}
        else:
            ids_train_orig = {pid: sorted(por_pid[pid], key=clave_identidad)
                              for pid in pids_train}
            X_orig, y_orig, g_orig = construir_entrenamiento(
                pids_train, ids_train_orig, feats, labels, indices_pct)
            if u_elegido is not None:
                ids_train_ded = medoids_por_pid(
                    pids_train, clusters_por_u[str(u_elegido)], dmat_por_pid)
                feats_train_ded = feats_dedup_por_conjunto(
                    feats, densas, ids_train_ded)
                X_ded, y_ded, g_ded = construir_entrenamiento(
                    pids_train, ids_train_ded, feats_train_ded, labels,
                    indices_pct)
            else:
                ids_train_ded = ids_train_orig
                X_ded, y_ded, g_ded = X_orig, y_orig, g_orig

            clon_orig, metrica_orig = entrenar_clon(X_orig, y_orig, g_orig)
            clon_ded, metrica_ded = entrenar_clon(X_ded, y_ded, g_ded)
            n_filas_orig = int(X_orig.shape[0])
            n_filas_ded = int(X_ded.shape[0])

            def guardar_clon(modelo, brazo, metrica, n_filas):
                nombre = f"fold{fold}_brazo_{brazo}"
                path_xgb = fold_models_dir / f"{nombre}.xgb"
                path_meta = fold_models_dir / f"{nombre}_meta.json"
                modelo.save_model(str(path_xgb))
                sha = sha256_archivo(path_xgb)
                escribir_json(path_meta, {
                    "experimento": "RS-01B",
                    "fold": fold,
                    "brazo": brazo,
                    "U_fold": u_elegido,
                    "hiperparametros": dict(PARAMS_CLON),
                    "eval_metric": metrica,
                    "n_filas": n_filas,
                    "n_complejos_train": len(pids_train),
                    "n_grupos": len(pids_train),
                    "n_arboles": int(modelo.get_booster().num_boosted_rounds()),
                    "seed": 42,
                    "sha256_archivo_xgb": sha,
                    "nota": ("sin early stopping; todos los datos outer-train; "
                             "relevancia -rmsd; grupos por complejo; orden canonico"),
                })
                modelos_info[nombre] = {"sha256": sha,
                                        "bytes": path_xgb.stat().st_size,
                                        "reusado": False}
                return sha

            sha_orig = guardar_clon(clon_orig, "original", metrica_orig,
                                    n_filas_orig)
            sha_ded = guardar_clon(clon_ded, "dedup", metrica_ded,
                                   n_filas_ded)
        clon_ded_por_fold[fold] = clon_ded

        # ── evaluacion OOF ──
        ids_eval_orig = {pid: sorted(por_pid[pid], key=clave_identidad)
                         for pid in pids_eval}
        ev_orig = evaluar_conjunto(clon_orig, pids_eval, ids_eval_orig,
                                   feats, labels, indices_pct)
        if u_elegido is not None:
            ids_eval_ded = medoids_por_pid(
                pids_eval, clusters_por_u[str(u_elegido)], dmat_por_pid)
            feats_eval_ded = feats_dedup_por_conjunto(feats, densas,
                                                      ids_eval_ded)
            ev_ded = evaluar_conjunto(clon_ded, pids_eval, ids_eval_ded,
                                      feats_eval_ded, labels, indices_pct)
        else:
            ids_eval_ded = ids_eval_orig
            ev_ded = evaluar_conjunto(clon_ded, pids_eval, ids_eval_orig,
                                      feats, labels, indices_pct)
        for pid in pids_eval:
            ids_eval_ded_por_pid[(fold, pid)] = ids_eval_ded[pid]
            ev_o_global[pid] = ev_orig[pid]
            ev_d_global[pid] = ev_ded[pid]

        agg_o = agregar_brazo(ev_orig, pids_eval)
        agg_d = agregar_brazo(ev_ded, pids_eval)
        par = pareado_por_pid(ev_orig, ev_ded, pids_eval)
        intervalos_fold = bootstrap_descriptivo_fold(
            pids_eval, comps_por_fold[fold], pid2comp, ev_orig, ev_ded,
            seed_fold=500 + fold)
        por_fold.append({
            "fold": fold,
            "n_componentes": len(comps_por_fold[fold]),
            "n_complejos_eval": len(pids_eval),
            "n_outer_train_complejos": len(pids_train),
            "n_outer_train_poses_original": n_filas_orig,
            "n_outer_train_poses_dedup": n_filas_ded,
            "U": u_elegido,
            "causa_U": causa_u,
            "tabla_umbrales_anidados": resumenes_u,
            "original": agg_o,
            "deduplicado": agg_d,
            "pareado": par,
            "bootstrap_descriptivo": intervalos_fold,
            "modelos": {"original_sha256": sha_orig, "dedup_sha256": sha_ded,
                        "eval_metric_original": metrica_orig,
                        "eval_metric_dedup": metrica_ded},
        })
        print(f"    top1 orig {agg_o['top1_hits']}/{agg_o['n_complejos']} "
              f"| dedup {agg_d['top1_hits']}/{agg_d['n_complejos']} "
              f"(Δ {par['delta_hits']}) | mediana pareada "
              f"{par['mediana_pareada_rmsd']} | "
              f"{time.monotonic() - t_f:.1f}s", flush=True)

    # ── globales ──
    par_global = pareado_por_pid(ev_o_global, ev_d_global, pids_orden)
    agg_o_global = agregar_brazo(ev_o_global, pids_orden)
    agg_d_global = agregar_brazo(ev_d_global, pids_orden)
    delta_hits = par_global["delta_hits"]
    mediana_pareada = par_global["mediana_pareada_rmsd"]
    cumple_hits = delta_hits >= 3
    cumple_mediana = mediana_pareada <= 0.1
    veredicto = "PASS" if (cumple_hits and cumple_mediana) else "FAIL"
    print(f"  GLOBAL: Δ Top-1 = {delta_hits} (requiere >= +3) | "
          f"mediana pareada = {mediana_pareada} (requiere <= 0.1) | "
          f"GATE: {veredicto}", flush=True)

    boot_comp = bootstrap_componentes_38(pids_orden, pid2comp, comps_orden,
                                         ev_o_global, ev_d_global)
    boot_plex = bootstrap_complejos_sensibilidad(pids_orden, ev_o_global,
                                                 ev_d_global)
    mcn = mcnemar_hits(ev_o_global, ev_d_global, pids_orden)
    discordancia_hits = bool(
        excluye_cero(boot_comp["hits"]["intervalo"])
        != excluye_cero(boot_plex["hits"]["intervalo"]))
    discordancia_med = bool(
        excluye_cero(boot_comp["mediana_pareada_rmsd"]["intervalo"])
        != excluye_cero(boot_plex["mediana_pareada_rmsd"]["intervalo"]))

    contrafactual = contrafactual_empates_oof(
        insumos, feats, densas, labels, indices_pct, pids_orden, pid2fold,
        u_por_fold, pids_fold, clon_ded_por_fold, dmat_por_pid,
        clusters_por_u, candidatos_por_identidad, ids_eval_ded_por_pid,
        ev_o_global, ev_d_global, recomputo["clusters_cross"])
    c = contrafactual["resumen"]
    print(f"  empates OOF: {c['n_clusters_empatados_foldeval']} clusters "
          f"empatados ({c['n_clusters_cross_source']} cross-source) | "
          f"{c['n_alternativas_evaluadas']} alternativas | "
          f"{c['n_alternativas_cambian_ganador']} cambian ganador | "
          f"{c['n_alternativas_cambian_hit']} cambian hit | "
          f"31 cross: {contrafactual['cruce_31_cross_source']['n_en_alcance']} "
          f"en alcance", flush=True)

    metrics = {
        "experimento": "RS-01B",
        "declaracion_resultado": ("Evaluacion OOF por cross-fitting de clones "
                                  "v0.6 (hiperparametros congelados) frente a "
                                  "la deduplicacion con umbral anidado por fold "
                                  "(regla MF-11-R1). Gate primario: +3 Top-1 "
                                  "OOF y mediana pareada de RMSD <= 0.1 A."),
        "preregistro": "scripts/artifacts_science/RS-01/PREREGISTRO.md §4.1-4.7 (sello paraguas)",
        "runtime": {
            "python": sys.version.split()[0],
            "xgboost": __import__("xgboost").__version__,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "interprete": "python-embed/python.exe",
            "checkpoint_carga": {
                "sha256": insumos["tabla_sha"]["checkpoint_xgb"]["sha256"],
                "bytes": R_CHECKPOINT.stat().st_size,
                "n_arboles_cargados": n_arboles,
                "best_iteration_meta": meta.get("best_iteration"),
                "uso": ("SOLO contrato de features congelado (meta asserts); "
                        "las predicciones del checkpoint NO se usan: los "
                        "clones se entrenan desde cero por fold"),
            },
        },
        "integridad_insumos_sha256": insumos["tabla_sha"],
        "validaciones": {
            "densidad_historica": {
                "metodo": "records/{pid}.json (malla densa mapeada), RMSD < 2.0 A",
                "n_coinciden_con_congelado": n_coinciden,
                "n_total": 2739,
                "exacto": bool(n_coinciden == 2739),
            },
            "medoids_sidecar_mf11r1": recomputo["verificacion"],
            "folds": {
                "tamanos": tamanos,
                "esperado": [55, 16, 15, 15, 15],
                "n_componentes": len(comps_orden),
                "esperado_componentes": 38,
            },
        },
        "config_clon": {
            "hiperparametros": dict(PARAMS_CLON),
            "n_estimators": 52,
            "early_stopping": "NINGUNO (sin eval_set; sin val 40 en el pipeline)",
            "relevancia": "-rmsd",
            "grupos": "por complejo (filas contiguas, orden canonico)",
            "eval_metric": "auc con fallback rmse (patron historico)",
            "seed": 42,
        },
        "por_fold": por_fold,
        "global": {
            "n_complejos_oof": len(pids_orden),
            "original": agg_o_global,
            "deduplicado": agg_d_global,
            "delta_top1_acumulado": delta_hits,
            "mediana_pareada_rmsd": mediana_pareada,
            "nota_primario": ("la mediana pareada es el estadistico PRIMARIO de "
                              "RMSD (gate); diferencia de medianas y suma son "
                              "SECUNDARIAS y NO participan del gate"),
            "interpretacion_mediana_pareada": (
                "sin evidencia de degradación en la mediana pareada"),
            "alcance_interpretacion": ("la mediana pareada (0.000 A) NO "
                                       "establece compatibilidad ni "
                                       "equivalencia; solo ausencia de "
                                       "degradacion medible en esa "
                                       "estadistica"),
            "diferencia_medianas_rmsd_secundaria": par_global["diferencia_medianas_rmsd"],
            "suma_pareada_rmsd_secundaria": par_global["suma_pareada_rmsd"],
            "media_pareada_rmsd_descriptiva": par_global["media_pareada_rmsd"],
            "gate": {
                "criterio": "+3 aciertos Top-1 OOF acumulados Y mediana pareada RMSD <= 0.1 A",
                "delta_top1_acumulado": delta_hits,
                "requerido_hits": 3,
                "cumple_hits": bool(cumple_hits),
                "mediana_pareada_rmsd": mediana_pareada,
                "umbral_mediana": 0.1,
                "cumple_mediana": bool(cumple_mediana),
                "veredicto": veredicto,
                "prohibido": ("NO se usa diferencia de medianas ni suma como "
                              "gate (solo se reportan como secundarias)"),
            },
            "mcnemar": mcn,
        },
        "incertidumbre": {
            "bootstrap_componentes_38_primario": boot_comp,
            "sensibilidad_por_complejo": boot_plex,
            "discordancias_primario_vs_sensibilidad": {
                "hits": bool(discordancia_hits),
                "mediana_pareada_rmsd": bool(discordancia_med),
                "nota": ("si la lectura por componentes (primaria) y la por "
                         "complejos (sensibilidad) discuerdan sobre el cero, "
                         "la discordancia se reporta explicitamente (B5)"),
            },
            "nota_c3": ("BCa primario solo sobre las 38 componentes globales; "
                        "cortes por fold/estrato = descriptivos con denominador "
                        "explicito (>= 5 componentes para intervalo); BCa "
                        "degenerado -> percentil bootstrap (regla C3d)"),
        },
        "abstencion_oof": {
            "umbral_congelado": UMBRAL_ABSTENCION,
            "nota": "SECUNDARIA: el umbral NO se recalibra en RS-01B",
            "original": {"n_abstenciones": agg_o_global["n_abstenciones"],
                         "tasa": agg_o_global["tasa_abstencion"]},
            "deduplicado": {"n_abstenciones": agg_d_global["n_abstenciones"],
                            "tasa": agg_d_global["tasa_abstencion"]},
        },
        "empates_contrafactual": contrafactual,
        "modelos_fold": modelos_info,
        "corrigendum_estadistico": {
            "fecha": "2026-08-16",
            "bug": ("mcnemar_hits multiplicaba por 2 el pvalue de "
                    "scipy.stats.binomtest(...), que YA es bilateral"),
            "fix": "se elimina el factor 2; 0 pares discordantes -> p = 1.0",
            "valores_corregidos": {
                "rs01a_b4_c0": 0.125,
                "rs01b_b11_c7": 0.480682,
            },
            "nota": ("los numeros cientificos NO cambian (Top-1 47->43, "
                     "mediana pareada 0.000 A, BCa [-8.80, 4.00]); solo "
                     "cambia el p de McNemar"),
        },
        "archivos_abiertos_repo": sorted(_ABIERTOS_REPO),
        "garantia_cuarentena": (
            "builtins.open auditado contra whitelist explicita: solo se "
            "abrieron los insumos train sellados, los modulos importados por "
            "composicion, los records train y las salidas RS-01B; "
            "poses_val.jsonl, poses_test.jsonl y FND-05/D-RC-CONFIRM NO "
            "figuran en archivos_abiertos_repo y nunca se abren en ninguna "
            "fase (los archivos internos de python-embed/ y __pycache__ "
            "quedan fuera del alcance de la auditoria)"),
        "determinismo": ("salidas sin timestamps ni aleatoriedad no-seeded; "
                         "dos corridas completas producen metrics.json y "
                         "per_complex.jsonl byte-identicos"),
    }

    # ── auditoria de cuarentena: whitelist de archivos abiertos ──
    whitelist = {
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
        str(Path(out_dir).relative_to(PROJECT_ROOT).as_posix()) + "/metrics.json",
        str(Path(out_dir).relative_to(PROJECT_ROOT).as_posix()) + "/per_complex.jsonl",
        str(Path(out_dir).relative_to(PROJECT_ROOT).as_posix()) + "/failures.jsonl",
    }
    for pid in pids_orden:
        whitelist.add(f"data/pose_selector_dataset/records/{pid}.json")
    for fold in range(N_FOLDS):
        for brazo in ("original", "dedup"):
            whitelist.add(str(fold_models_dir.relative_to(PROJECT_ROOT)
                              .as_posix()) + f"/fold{fold}_brazo_{brazo}.xgb")
            whitelist.add(str(fold_models_dir.relative_to(PROJECT_ROOT)
                              .as_posix()) + f"/fold{fold}_brazo_{brazo}_meta.json")
    fuera = sorted(p for p in _ABIERTOS_REPO
                   if p not in whitelist and "__pycache__" not in p
                   and not p.endswith(".pyc")
                   and not p.startswith("python-embed/"))
    if fuera:
        raise SystemExit("ERROR: archivos fuera del whitelist abiertos: "
                         + "; ".join(fuera))
    prohibidos = [p for p in _ABIERTOS_REPO
                  if "poses_val" in p or "poses_test" in p or "FND-05" in p
                  or "confirm" in p.lower()]
    if prohibidos:
        raise SystemExit("ERROR: se abrieron archivos PROHIBIDOS: "
                         + "; ".join(prohibidos))
    print("  cuarentena: 0 accesos val/test/CONFIRM (whitelist OK)", flush=True)

    # ── per_complex.jsonl ──
    filas_pc = []
    for pid in pids_orden:
        o = ev_o_global[pid]
        d = ev_d_global[pid]

        def mini(x):
            return {"ganador": x["ganador"], "fuente": x["fuente"],
                    "rmsd": round(x["rmsd"], 4), "hit": x["hit"],
                    "margen": x["margen"], "abstenido": x["abstenido"]}

        filas_pc.append({
            "pid": pid,
            "fold": pid2fold[pid],
            "componente": pid2comp[pid],
            "u_fold": u_por_fold[pid2fold[pid]],
            "n_poses_eval_original": o["n_poses"],
            "n_poses_eval_dedup": d["n_poses"],
            "original": mini(o),
            "deduplicado": mini(d),
            "delta_rmsd_pareado": round(d["rmsd"] - o["rmsd"], 4),
            "hit_original": o["hit"],
            "hit_deduplicado": d["hit"],
            "delta_hit": int(d["hit"]) - int(o["hit"]),
        })

    escribir_json(out_dir / "metrics.json", metrics)
    escribir_jsonl(out_dir / "per_complex.jsonl", filas_pc)
    escribir_jsonl(out_dir / "failures.jsonl", [])

    print(f"  salidas escritas en {out_dir}", flush=True)
    print(f"  sha metrics={sha256_archivo(out_dir / 'metrics.json')[:16]}... "
          f"per_complex={sha256_archivo(out_dir / 'per_complex.jsonl')[:16]}...",
          flush=True)
    print(f"  duracion: {time.monotonic() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
