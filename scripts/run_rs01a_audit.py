# -*- coding: utf-8 -*-
"""run_rs01a_audit.py — RS-01A: auditoria IN-SAMPLE del checkpoint v0.6 congelado.

Ejecuta las tres lecturas del preregistro sellado RS-01 (commit d320bcd,
PREREGISTRO.md §3.3) y el contrafactual de los 31 empates cross-source (B6-ii):

  - A0  reproduccion historica exacta (2739 poses, features de conjunto
       CONGELADAS del dataset: variance/range POR-RUN + cluster_density
       congelada). Referencia: modelo_B.train.top1_rate=0.6724,
       mediana_rmsd=1.425 (scripts/artifacts_ruta_c_fase1_6.json).
  - A1  PRIMARIA: original (2739) vs deduplicado MF-11-R1 (2413 medoids
       1.5 A). En AMBOS brazos variance/range POR-RUN congelados; tras
       dedup SOLO se recalcula cluster_density (semantica HISTORICA del
       dataset builder: pares pose-pose RMSD pocket-frame < 2.0 A sin
       alinear, UMBRAL_CLUSTER=2.0 — PRESERVADA, NO corregida) y, en
       consecuencia, la matriz z/pct por complejo.
  - A2  sensibilidad de produccion (SECUNDARIA): variance/range POR
       REQUEST en ambos brazos (semantica exacta de selector.py:219-225,
       round(...,4)); cluster_density: original = congelada (validada
       identica a la recomputada sobre el conjunto completo), dedup =
       recomputada entre supervivientes.
  - 31 empates cross-source: recomputacion determinista de las sumas de
    medoid (dmat por pid desde las coords PDBQT de la union sellada +
    membresias del sidecar, metricas EXACTAS de dedup_pose_union_medoid.py)
    y contrafactual completo: para CADA medoid alternativo empatado se
    recalcula el conjunto completo de resultados A1 (nunca se escoge uno
    despues de ver resultados).

Declaracion de resultado: SOLO auditoria in-sample de compatibilidad y
perturbacion. NO es claim de mejora (PREREGISTRO.md §3.5).

Restricciones DURAS: no entrena, no modifica el modelo, no pip, no red, no
commits, no seal. Solo abre archivos del whitelist (auditado via parche de
builtins.open y reportado en metrics). poses_val.jsonl / poses_test.jsonl
NUNCA se abren.

Composicion (solo lectura de codigo sellado):
  - rescoring/pose_selector/selector.py  -> PoseSelector (carga del booster
    y contrato de features) + UMBRAL_ABSTENCION_DEFECTO + UMBRAL_CLUSTER.
  - scripts/dedup_pose_union_medoid.py  -> parsear_atomos_pesados,
    rmsd_pocket_pose_vs_pose, matriz_distancias, medoid_detalle (recomputacion
    de medoids identica a la del sidecar sellado).

Fuente de coordenadas para cluster_density post-dedup (desviacion
documentada y validada): la definicion del dataset builder usa la MALLA
DENSA de indices mapeados por fuente (serial -> indice de atomo pesado del
cristal, mapas por fuente); las coords PDBQT de la union comparadas 1:1 por
serial NO reproducen la densidad congelada (2212/2739 discrepancias — los
mapas serial->atomo difieren entre fuentes). Se usan las coords densas
mapeadas de data/pose_selector_dataset/records/{pid}.json (_coords, misma
malla por complejo, redondeo a 3 decimales del builder). Validacion dura:
recomputacion sobre el conjunto ORIGINAL completo = valores congelados
2739/2739 exactos.

Determinismo: salidas sin timestamps ni aleatoriedad no-seeded; dos corridas
producen metrics.json y per_complex.jsonl byte-identicos.

Uso:
  python scripts/run_rs01a_audit.py [--out-dir scripts/artifacts_science/RS-01A]
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
# Garantia de cuarentena (0 acceso a val/test): todo open() bajo el repo se
# registra; al final se verifica que solo se abrieron archivos del whitelist.
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
    medoid_detalle,
    matriz_distancias,
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

OUT_DIR_DEFAULT = ARTIFACTOS / "RS-01A"

UMBRAL_POSITIVA = 2.0  # hit: rmsd <= 2.0 A

FEATURES_V0 = ["vina_score", "pose_score_variance", "pose_score_range",
               "n_heavy", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
               "n_clashes", "cluster_density"]

PCT_RAW = ["vina_score", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
           "n_clashes", "pose_score_variance", "pose_score_range",
           "cluster_density", "n_heavy"]

N_Z = 224
N_MODELO_B = 233

# Valores de referencia (INVENTORY.json sellado + preregistro §3.1)
HISTORICO_TRAIN_TOP1 = 0.6724
HISTORICO_TRAIN_MEDIANA = 1.425
UMBRAL_ABSTENCION = UMBRAL_ABSTENCION_DEFECTO  # 0.097663

SEED_BOOT = 42
N_BOOT = 10_000


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
        tabla[nombre] = {"archivo": str(path), "sha256": real, "esperado": esperado, "ok": ok}
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
    dedup_cand = leer_jsonl(R_DEDUP_CAND)
    sidecar = leer_jsonl(R_SIDECAR)
    fold_plan = leer_json(R_FOLD_PLAN)

    if {c["identity"] for c in candidatos} != {l["identity"] for l in labels}:
        raise SystemExit("ERROR: identidades union candidates/labels no coinciden 1:1")

    # Identidad posicional vista <-> union (B4): mismo orden canonico.
    claves_vista = [(r["pid"], r["source"], r["file_stem"], r["model_idx"])
                    for r in vista]
    claves_union = [clave_identidad(c["identity"]) for c in candidatos]
    if claves_vista != claves_union:
        raise SystemExit("ERROR: orden/identidad de la vista no coincide con la union")

    reps_sidecar = [s["representative_identity"] for s in sidecar]
    ids_dedup = [c["identity"] for c in dedup_cand]
    if sorted(ids_dedup) != sorted(reps_sidecar):
        raise SystemExit("ERROR: dedup_candidates != representantes del sidecar")

    miembros_sidecar = [m for s in sidecar for m in s["member_identities"]]
    if sorted(miembros_sidecar) != sorted(c["identity"] for c in candidatos):
        raise SystemExit("ERROR: membresias del sidecar no parten la union")

    return {
        "inventario": inventario,
        "tabla_sha": tabla_sha,
        "candidatos": candidatos,
        "labels": labels,
        "vista": vista,
        "poses_train": poses_train,
        "dedup_ids": sorted(ids_dedup, key=clave_identidad),
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


# ───────────────────────── evaluacion de un brazo ──────────────────────────

def evaluar_brazo(selector: PoseSelector, indices_pct: list, ids_orden: list,
                  feats_por_identidad: dict, labels: dict) -> dict:
    """Evalua un conjunto de poses (orden canonico por complejo): transforma
    z/pct por complejo, predice con el checkpoint congelado y devuelve
    resultados por complejo + agregados."""
    pids = []
    grupos = []
    n = 0
    for identidad in ids_orden:
        pid = identidad.split("|")[1]
        if not pids or pids[-1] != pid:
            if pids:
                grupos.append(n)
                n = 0
            pids.append(pid)
        n += 1
    if n:
        grupos.append(n)

    X = np.vstack([feats_por_identidad[i] for i in ids_orden])
    assert X.shape == (len(ids_orden), N_Z)
    Z = z_por_pid(X, grupos)
    Z[np.isnan(Z)] = 0.0
    P = pct_por_pid(X, grupos, indices_pct)
    P[np.isnan(P)] = 0.0
    X_B = np.hstack([Z, P])
    assert X_B.shape == (len(ids_orden), N_MODELO_B)

    import xgboost
    scores = np.asarray(selector.booster.predict(xgboost.DMatrix(X_B)),
                        dtype=np.float64)

    por_pid = defaultdict(list)
    for identidad, s in zip(ids_orden, scores):
        pid = identidad.split("|")[1]
        por_pid[pid].append((identidad, float(s)))

    detalle_por_pid = {}
    top1_ok = 0
    rmsds_ganador = []
    margenes = []
    abstenciones = 0
    fuentes_ganador = defaultdict(int)
    fuentes_disponibles = {}
    n_poses_por_pid = {}

    for pid in pids:
        filas = por_pid[pid]  # orden canonico preservado
        ss = np.array([s for _, s in filas])
        k = int(np.argmax(ss))
        ganador, score_top = filas[k]
        rmsd = float(labels[ganador]["rmsd"])
        rmsds_ganador.append(rmsd)
        hit = rmsd <= UMBRAL_POSITIVA
        if hit:
            top1_ok += 1
        if len(filas) > 1:
            margen = float(np.sort(ss)[::-1][0] - np.sort(ss)[::-1][1])
            abstenido = margen < UMBRAL_ABSTENCION
        else:
            margen = 0.0
            abstenido = True
        margenes.append(margen)
        abstenciones += 1 if abstenido else 0
        fuente = ganador.split("|")[2]
        fuentes_ganador[fuente] += 1
        disp = sorted({i.split("|")[2] for i, _ in filas})
        fuentes_disponibles[pid] = disp
        n_poses_por_pid[pid] = len(filas)
        detalle_por_pid[pid] = {
            "ganador": ganador,
            "fuente": fuente,
            "score_top": round(score_top, 6),
            "rmsd": rmsd,
            "hit": bool(hit),
            "margen": round(margen, 6),
            "abstenido": bool(abstenido),
            "n_poses": len(filas),
            "tiene_pose_buena": bool(min(float(labels[i]["rmsd"]) for i, _ in filas)
                                      <= UMBRAL_POSITIVA),
        }

    n_complejos = len(pids)
    return {
        "n_complejos": n_complejos,
        "n_poses": len(ids_orden),
        "top1_hits": top1_ok,
        "top1_rate": round(top1_ok / n_complejos, 4),
        "rmsd_mediana_ganador": round(float(np.median(rmsds_ganador)), 3),
        "rmsd_media_ganador": round(float(np.mean(rmsds_ganador)), 4),
        "margen_mediana": round(float(np.median(margenes)), 6),
        "margen_media": round(float(np.mean(margenes)), 6),
        "n_abstenciones": abstenciones,
        "tasa_abstencion": round(abstenciones / n_complejos, 4),
        "desglose_abstencion": desglose_abstencion(detalle_por_pid),
        "fuente_ganadora": dict(sorted(fuentes_ganador.items())),
        "fuente_ganadora_condicionada": fuente_condicionada(detalle_por_pid,
                                                             fuentes_disponibles),
        "fuentes_disponibles": fuentes_disponibles,
        "n_poses_por_pid": n_poses_por_pid,
        "detalle_por_pid": detalle_por_pid,
        "scores_por_identidad": dict(zip(ids_orden, [round(float(s), 6)
                                                     for s in scores])),
    }


def desglose_abstencion(detalle: dict) -> dict:
    """Esquema confusion_rc4 de Fase 3: abstenidos/aceptados por decidibilidad
    (tiene_pose_buena) y acierto top-1."""
    abst = [d for d in detalle.values() if d["abstenido"]]
    acep = [d for d in detalle.values() if not d["abstenido"]]

    def g(grupo):
        n = len(grupo)
        con_buena = sum(1 for d in grupo if d["tiene_pose_buena"])
        aciertos = sum(1 for d in grupo if d["hit"])
        aciertos_con_buena = sum(1 for d in grupo if d["tiene_pose_buena"] and d["hit"])
        return {"n": n, "sin_pose_buena": n - con_buena, "con_pose_buena": con_buena,
                "con_pose_buena_aciertos_top1": aciertos_con_buena,
                "aciertos_top1": aciertos,
                "top1": round(aciertos / n, 4) if n else None}

    return {"abstenidos": g(abst), "aceptados": g(acep)}


def fuente_condicionada(detalle: dict, disponibilidad: dict) -> dict:
    """Fuente ganadora CONDICIONADA a mascaras de disponibilidad (B6-iii)."""
    por_fuente = {}
    for pid, d in detalle.items():
        for f in disponibilidad[pid]:
            por_fuente.setdefault(f, {"n_disponibles": 0, "n_ganadores": 0})
            por_fuente[f]["n_disponibles"] += 1
        por_fuente[d["fuente"]]["n_ganadores"] += 1
    out = {}
    for f, v in sorted(por_fuente.items()):
        out[f] = {"n_disponibles": v["n_disponibles"], "n_ganadores": v["n_ganadores"],
                  "rate": round(v["n_ganadores"] / v["n_disponibles"], 4)}
    return out


# ───────────────────────── comparacion pareada ─────────────────────────────

FOLD_PLAN_CACHE: dict = {}


def comparar_pareado(orig: dict, dedup: dict, pids: list,
                     con_bootstrap: bool = True) -> dict:
    det_o = orig["detalle_por_pid"]
    det_d = dedup["detalle_por_pid"]
    cambiados = []
    perdidas = []
    recuperaciones = []
    perdidas_cob = []
    recuperaciones_cob = []
    flips_abstencion = []
    deltas_margen = []
    for pid in pids:
        o, d = det_o[pid], det_d[pid]
        if o["ganador"] != d["ganador"]:
            cambiados.append(pid)
        if o["hit"] and not d["hit"]:
            perdidas.append(pid)
        if not o["hit"] and d["hit"]:
            recuperaciones.append(pid)
        if o["tiene_pose_buena"] and not d["tiene_pose_buena"]:
            perdidas_cob.append(pid)
        if not o["tiene_pose_buena"] and d["tiene_pose_buena"]:
            recuperaciones_cob.append(pid)
        if o["abstenido"] != d["abstenido"]:
            flips_abstencion.append(pid)
        deltas_margen.append(d["margen"] - o["margen"])

    # cambios de disponibilidad de fuentes inducidos por la dedup
    dispo_o = orig["fuentes_disponibles"]
    dispo_d = dedup["fuentes_disponibles"]
    cambios_disponibilidad = []
    for pid in pids:
        desaparecen = [f for f in dispo_o[pid] if f not in dispo_d[pid]]
        aparecen = [f for f in dispo_d[pid] if f not in dispo_o[pid]]
        if desaparecen or aparecen:
            cambios_disponibilidad.append({"pid": pid, "desaparecen": desaparecen,
                                           "aparecen": aparecen})

    out = {
        "ganadores_cambiados": {"n": len(cambiados), "pids": cambiados},
        "perdidas_hit": {"n": len(perdidas), "pids": perdidas},
        "recuperaciones_hit": {"n": len(recuperaciones), "pids": recuperaciones},
        "perdidas_cobertura": {"n": len(perdidas_cob), "pids": perdidas_cob},
        "recuperaciones_cobertura": {"n": len(recuperaciones_cob), "pids": recuperaciones_cob},
        "flips_abstencion": {"n": len(flips_abstencion), "pids": flips_abstencion},
        "delta_margen": {"mediana": round(float(np.median(deltas_margen)), 6),
                         "media": round(float(np.mean(deltas_margen)), 6),
                         "n_suben": int(sum(1 for x in deltas_margen if x > 0)),
                         "n_bajan": int(sum(1 for x in deltas_margen if x < 0)),
                         "n_iguales": int(sum(1 for x in deltas_margen if x == 0))},
        "cambios_disponibilidad_fuentes": cambios_disponibilidad,
        "mcnemar": mcnemar_hits(det_o, det_d, pids),
    }
    if con_bootstrap:
        out["bootstrap_bc"] = bootstrap_bc(det_o, det_d, pids)
    return out


def mcnemar_hits(det_o: dict, det_d: dict, pids: list) -> dict:
    """McNemar exacto sobre la tabla 2x2 de aciertos pareados (hit <= 2 A)."""
    from scipy.stats import binomtest
    b = sum(1 for p in pids if det_o[p]["hit"] and not det_d[p]["hit"])
    c = sum(1 for p in pids if not det_o[p]["hit"] and det_d[p]["hit"])
    n_discordantes = b + c
    p_valor = None
    if n_discordantes > 0:
        p_valor = min(1.0, 2.0 * binomtest(min(b, c), n_discordantes, 0.5).pvalue)
    return {"b_orig_hit_dedup_miss": b, "c_orig_miss_dedup_hit": c,
            "n_discordantes": n_discordantes,
            "p_valor_exacto_bilateral": None if p_valor is None
            else round(float(p_valor), 6)}


def bootstrap_bc(det_o: dict, det_d: dict, pids: list) -> dict:
    """Bootstrap b/c de la diferencia pareada (dedup - orig) de aciertos y de
    RMSD del ganador. b = por las 38 componentes combinadas del fold_plan
    (BCa primario con fallback percentil, regla C3); c = por complejo
    (sensibilidad, percentil)."""
    pid2comp = {}
    for comp in FOLD_PLAN_CACHE["por_componente"]:
        for pid in comp["pids"]:
            pid2comp[pid] = comp["componente"]
    comps_orden = [comp["componente"] for comp in FOLD_PLAN_CACHE["por_componente"]]

    d_hit = {p: (1 if det_d[p]["hit"] else 0) - (1 if det_o[p]["hit"] else 0)
             for p in pids}
    d_rmsd = {p: det_d[p]["rmsd"] - det_o[p]["rmsd"] for p in pids}

    suma_comp_hit = {c: sum(v for p, v in d_hit.items() if pid2comp[p] == c)
                     for c in comps_orden}
    suma_comp_rmsd = {c: sum(v for p, v in d_rmsd.items() if pid2comp[p] == c)
                      for c in comps_orden}

    rng = np.random.default_rng(SEED_BOOT)
    idx = rng.integers(0, len(comps_orden), size=(N_BOOT, len(comps_orden)))
    boot_b_hit = np.array([sum(suma_comp_hit[comps_orden[i]] for i in fila)
                           for fila in idx], dtype=np.float64)
    boot_b_rmsd = np.array([sum(suma_comp_rmsd[comps_orden[i]] for i in fila)
                            for fila in idx], dtype=np.float64)

    valores_hit = [d_hit[p] for p in pids]
    valores_rmsd = [d_rmsd[p] for p in pids]
    idx2 = rng.integers(0, len(pids), size=(N_BOOT, len(pids)))
    boot_c_hit = np.array([sum(valores_hit[i] for i in fila) for fila in idx2])
    boot_c_rmsd = np.array([sum(valores_rmsd[i] for i in fila) for fila in idx2])

    obs_hit = float(sum(valores_hit))
    obs_rmsd = float(sum(valores_rmsd))

    salida = {"n_replicas": N_BOOT, "seed": SEED_BOOT,
              "estadistica": "suma de diferencias pareadas (dedup - orig)",
              "diferencia_observada_hits": obs_hit,
              "diferencia_observada_rmsd": obs_rmsd}
    salida["por_componentes_b"] = construir_intervalos(
        boot_b_hit, obs_hit, [suma_comp_hit[c] for c in comps_orden],
        "hits_por_componente")
    salida["por_componentes_b_rmsd"] = construir_intervalos(
        boot_b_rmsd, obs_rmsd, [suma_comp_rmsd[c] for c in comps_orden],
        "rmsd_por_componente", bca=False)
    salida["por_complejos_c"] = construir_intervalos(
        boot_c_hit, obs_hit, None, "hits_por_complejo")
    salida["por_complejos_c_rmsd"] = construir_intervalos(
        boot_c_rmsd, obs_rmsd, None, "rmsd_por_complejo", bca=False)
    salida["discordancia_b_c_hits"] = bool(
        excluye_cero(salida["por_componentes_b"]["intervalo"]) !=
        excluye_cero(salida["por_complejos_c"]["intervalo"]))
    salida["discordancia_b_c_rmsd"] = bool(
        excluye_cero(salida["por_componentes_b_rmsd"]["intervalo"]) !=
        excluye_cero(salida["por_complejos_c_rmsd"]["intervalo"]))
    return salida


def excluye_cero(intervalo: list) -> bool:
    lo, hi = intervalo
    return bool(lo > 0 or hi < 0)


def deltas_semantica(nuevo: dict, base: dict, pids: list) -> dict:
    """Comparacion de dos brazos sobre el MISMO conjunto de poses (efecto de
    la semantica de features), reportada como deltas."""
    d_n = nuevo["detalle_por_pid"]
    d_b = base["detalle_por_pid"]
    cambiados = [p for p in pids if d_n[p]["ganador"] != d_b[p]["ganador"]]
    perdidas = [p for p in pids if d_b[p]["hit"] and not d_n[p]["hit"]]
    recuperaciones = [p for p in pids if not d_b[p]["hit"] and d_n[p]["hit"]]
    flips_abst = [p for p in pids if d_n[p]["abstenido"] != d_b[p]["abstenido"]]
    deltas_rmsd = [d_n[p]["rmsd"] - d_b[p]["rmsd"] for p in pids]
    deltas_margen = [d_n[p]["margen"] - d_b[p]["margen"] for p in pids]
    return {
        "delta_top1_rate": round(nuevo["top1_rate"] - base["top1_rate"], 4),
        "delta_hits": nuevo["top1_hits"] - base["top1_hits"],
        "delta_rmsd_mediana_ganador": round(nuevo["rmsd_mediana_ganador"]
                                             - base["rmsd_mediana_ganador"], 4),
        "ganadores_cambiados": {"n": len(cambiados), "pids": cambiados},
        "perdidas_hit": {"n": len(perdidas), "pids": perdidas},
        "recuperaciones_hit": {"n": len(recuperaciones), "pids": recuperaciones},
        "flips_abstencion": {"n": len(flips_abst), "pids": flips_abst},
        "delta_abstenciones": nuevo["n_abstenciones"] - base["n_abstenciones"],
        "delta_margen": {"mediana": round(float(np.median(deltas_margen)), 6),
                         "media": round(float(np.mean(deltas_margen)), 6)},
    }


def construir_intervalos(boot: np.ndarray, obs: float, jack_vals, etiqueta: str,
                         bca: bool = True) -> dict:
    from scipy.stats import norm
    perc = np.percentile(boot, [2.5, 97.5])
    out = {"tipo": etiqueta, "intervalo_percentil_95": [round(float(perc[0]), 6),
                                                        round(float(perc[1]), 6)]}
    if not bca:
        out["metodo"] = "percentil 2.5-97.5"
        out["intervalo"] = out["intervalo_percentil_95"]
        out["excluye_cero"] = excluye_cero(out["intervalo"])
        return out
    # BCa con jackknife sobre las unidades (regla C3d: fallback si degenera)
    theta = obs
    if jack_vals:
        jack = np.array([theta - v for v in jack_vals], dtype=np.float64)
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
        z0 = float(norm.ppf(np.mean(boot <= theta)))
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
        out["metodo"] = "BCa primario (jackknife sobre las 38 componentes)"
        out["bca_degenerado"] = False
        out["aceleracion"] = round(a, 6)
        out["sesgo_z0"] = round(z0, 6)
        out["intervalo"] = [round(lo, 6), round(hi, 6)]
        out["excluye_cero"] = excluye_cero(out["intervalo"])
        return out
    out["metodo"] = "BCa degenerado -> percentil bootstrap (regla C3d)"
    out["bca_degenerado"] = True
    out["intervalo"] = out["intervalo_percentil_95"]
    out["excluye_cero"] = excluye_cero(out["intervalo"])
    return out


# ───────────────────────── 31 empates cross-source ─────────────────────────

def recomputar_medoids(insumos: dict, candidatos_por_identidad: dict) -> dict:
    """Recomputacion determinista de medoids (metricas exactas del script
    sellado): dmat por pid desde coords PDBQT de la union + membresias del
    sidecar. Verifica representante == medoid y cuantifica empates."""
    coords = {c["identity"]: parsear_atomos_pesados(c.get("pdbqt", ""))[0]
              for c in insumos["candidatos"]}
    dmat_por_pid = {}
    por_pid = defaultdict(list)
    for c in insumos["candidatos"]:
        por_pid[c["pid"]].append(c["identity"])
    for pid in sorted(por_pid):
        identidades = sorted(por_pid[pid])
        dmat_por_pid[pid] = matriz_distancias(identidades,
                                              {i: coords[i] for i in identidades})

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
            fuentes = {candidatos_por_identidad[m]["source"] for m in empatados}
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
            "n_representantes_coinciden_medoid_recomputado": len(insumos["sidecar"]) - no_coinciden,
            "n_no_singleton": n_no_singleton,
            "n_empates_medoid": n_empates,
            "n_empates_cross_source": n_cross,
            "esperado_mf11r1": {"n_clusters_no_singleton": esperados["n_clusters_no_singleton"],
                                "n_empates_medoid": esperados["n_empates_medoid"],
                                "n_empates_cross_source": esperados["n_empates_cross_source"]},
            "coincide_con_sellado": (n_no_singleton == esperados["n_clusters_no_singleton"]
                                     and n_empates == esperados["n_empates_medoid"]
                                     and n_cross == esperados["n_empates_cross_source"]
                                     and no_coinciden == 0),
        },
        "clusters_cross": clusters_cross,
        "dmat_por_pid": dmat_por_pid,
    }


def contrafactual_empates(selector, indices_pct, feats, feats_dedup, densas,
                          labels, dedup_ids: list, detalle_sellado: dict,
                          clusters_cross: list, pids_orden: list) -> dict:
    """Para CADA medoid alternativo empatado de los 31 clusters cross-source:
    swap en el conjunto dedup y recalculo COMPLETO de A1 (nada de escoger
    despues de ver). Reporta cambios de ganador por complejo y direccion de
    fuente."""
    # cache de per-pid para el resto de pids (no afectados por un swap)
    detalle_por_cluster = []
    n_alternativas_total = 0
    n_alternativas_cambian = 0
    n_alternativas_cambian_hit = 0
    n_clusters_con_cambio = 0
    direccion_fuente = defaultdict(int)  # (fuente_ganador_sellado, fuente_ganador_alt)
    direccion_alt_fuente = defaultdict(int)  # fuente del alternativo que cambia

    dedup_por_pid = defaultdict(list)
    for i in dedup_ids:
        dedup_por_pid[i.split("|")[1]].append(i)

    for cluster in clusters_cross:
        pid = cluster["pid"]
        rep = cluster["representante"]
        alternativas = [e for e in cluster["empatados"] if e["identity"] != rep]
        alts_detalle = []
        alguna_cambia = False
        for alt in alternativas:
            n_alternativas_total += 1
            ids_alt = [alt["identity"] if i == rep else i for i in dedup_por_pid[pid]]
            feats_alt = dict(feats_dedup)
            fila_alt = feats[alt["identity"]].copy()
            feats_alt[alt["identity"]] = fila_alt
            dens_alt = densidad_historica(densas, ids_alt)
            for i in ids_alt:
                fila = feats_alt[i].copy()
                fila[8] = float(dens_alt[i])
                feats_alt[i] = fila
            ids_global_alt = sorted(set(dedup_ids) - {rep} | {alt["identity"]},
                                    key=clave_identidad)
            feats_global_alt = dict(feats_dedup)
            for i in ids_alt:
                feats_global_alt[i] = feats_alt[i]
            res_alt = evaluar_brazo(selector, indices_pct, ids_global_alt,
                                    feats_global_alt, labels)
            d_alt = res_alt["detalle_por_pid"][pid]
            d_sel = detalle_sellado[pid]
            cambio = d_alt["ganador"] != d_sel["ganador"]
            cambio_hit = d_alt["hit"] != d_sel["hit"]
            if cambio:
                n_alternativas_cambian += 1
                alguna_cambia = True
                direccion_fuente[(d_sel["fuente"], d_alt["fuente"])] += 1
                direccion_alt_fuente[alt["source"]] += 1
            if cambio_hit:
                n_alternativas_cambian_hit += 1
            alts_detalle.append({
                "alternativo_identity": alt["identity"],
                "alternativo_source": alt["source"],
                "cambia_ganador": bool(cambio),
                "cambia_hit": bool(cambio_hit),
                "ganador_sellado": {"identity": d_sel["ganador"],
                                    "fuente": d_sel["fuente"],
                                    "rmsd": d_sel["rmsd"], "hit": d_sel["hit"]},
                "ganador_alternativo": {"identity": d_alt["ganador"],
                                        "fuente": d_alt["fuente"],
                                        "rmsd": d_alt["rmsd"], "hit": d_alt["hit"]},
                "top1_rate_global_alt": res_alt["top1_rate"],
                "rmsd_mediana_global_alt": res_alt["rmsd_mediana_ganador"],
            })
        if alguna_cambia:
            n_clusters_con_cambio += 1
        detalle_por_cluster.append({
            "cluster_key": cluster["cluster_key"],
            "pid": pid,
            "representante": {"identity": rep,
                              "fuente": cluster["representante_fuente"]},
            "empatados": cluster["empatados"],
            "n_alternativas": len(alternativas),
            "alguna_alternativa_cambia_ganador": bool(alguna_cambia),
            "alternativas": alts_detalle,
        })

    return {
        "resumen": {
            "n_clusters_cross_source": len(clusters_cross),
            "n_alternativas_evaluadas": n_alternativas_total,
            "n_alternativas_cambian_ganador": n_alternativas_cambian,
            "n_alternativas_cambian_hit": n_alternativas_cambian_hit,
            "n_clusters_con_al_menos_un_cambio": n_clusters_con_cambio,
            "direccion_fuente_ganador": {f"{a}->{b}": n for (a, b), n in
                                         sorted(direccion_fuente.items())},
            "fuente_del_alternativo_que_cambia": dict(
                sorted(direccion_alt_fuente.items())),
        },
        "detalle_clusters": detalle_por_cluster,
    }


# ───────────────────────── flujo principal ─────────────────────────────────

def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(description="RS-01A auditoria in-sample v0.6")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    print("== RS-01A: auditoria in-sample del checkpoint v0.6 congelado ==")

    insumos = cargar_insumos()
    global FOLD_PLAN_CACHE
    FOLD_PLAN_CACHE = insumos["fold_plan"]
    print("  insumos sellados verificados (sha256): OK")

    # ── checkpoint congelado via PoseSelector (solo lectura) ──
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
          f"{meta.get('best_iteration')}, umbral abstencion {UMBRAL_ABSTENCION}")

    # ── features y coords ──
    feats = cargar_features(insumos)
    densas = cargar_densas(insumos)
    labels = {l["identity"]: l for l in insumos["labels"]}
    candidatos_por_identidad = {c["identity"]: c for c in insumos["candidatos"]}

    ids_original = sorted(candidatos_por_identidad.keys(), key=clave_identidad)
    ids_dedup = insumos["dedup_ids"]
    pids_orden = sorted({i.split("|")[1] for i in ids_original})
    assert len(pids_orden) == 116

    # validacion: densidad historica recomputada sobre el conjunto ORIGINAL
    dens_recomputada_orig = densidad_historica(densas, ids_original)
    n_coinciden = sum(1 for i in ids_original
                      if float(feats[i][8]) == float(dens_recomputada_orig[i]))
    print(f"  validacion densidad historica: {n_coinciden}/2739 exactas")
    if n_coinciden != 2739:
        raise SystemExit("ERROR: recomputacion de cluster_density no reproduce "
                         "los valores congelados")

    # ── A0: reproduccion historica exacta ──
    res_a0 = evaluar_brazo(selector, indices_pct, ids_original, feats, labels)
    igual_top1 = res_a0["top1_rate"] == HISTORICO_TRAIN_TOP1
    igual_mediana = res_a0["rmsd_mediana_ganador"] == HISTORICO_TRAIN_MEDIANA
    print(f"  A0: top1={res_a0['top1_rate']} (hist {HISTORICO_TRAIN_TOP1}, "
          f"{'OK' if igual_top1 else 'DIFERENTE'}) | mediana="
          f"{res_a0['rmsd_mediana_ganador']} (hist {HISTORICO_TRAIN_MEDIANA}, "
          f"{'OK' if igual_mediana else 'DIFERENTE'})")

    # ── A1: primaria ──
    res_a1_orig = evaluar_brazo(selector, indices_pct, ids_original, feats, labels)
    identico_a0 = res_a1_orig["scores_por_identidad"] == res_a0["scores_por_identidad"]

    feats_dedup = {}
    dens_dedup = densidad_historica(densas, ids_dedup)
    for i in ids_dedup:
        fila = feats[i].copy()
        fila[8] = float(dens_dedup[i])
        feats_dedup[i] = fila
    res_a1_dedup = evaluar_brazo(selector, indices_pct, ids_dedup, feats_dedup,
                                 labels)
    comparacion_a1 = comparar_pareado(res_a1_orig, res_a1_dedup, pids_orden)
    print(f"  A1: orig {res_a1_orig['top1_rate']} ({res_a1_orig['top1_hits']}/116) "
          f"-> dedup {res_a1_dedup['top1_rate']} ({res_a1_dedup['top1_hits']}/116) | "
          f"cambiados {comparacion_a1['ganadores_cambiados']['n']} | "
          f"perdidas {comparacion_a1['perdidas_hit']['n']} | "
          f"recuperaciones {comparacion_a1['recuperaciones_hit']['n']} | "
          f"McNemar p={comparacion_a1['mcnemar']['p_valor_exacto_bilateral']}")

    # ── A2: sensibilidad de produccion (variance/range POR REQUEST) ──
    def aplicar_variance_range_por_request(feats_base: dict, ids: list) -> dict:
        out = {}
        por_pid = defaultdict(list)
        for i in ids:
            por_pid[i.split("|")[1]].append(i)
        for pid, ids_pid in por_pid.items():
            vinas = [float(feats_base[i][0]) for i in ids_pid]
            if len(vinas) > 1:
                var_score = round(float(np.var(vinas)), 4)
                rango_score = round(float(max(vinas) - min(vinas)), 4)
            else:
                var_score, rango_score = 0.0, 0.0
            for i in ids_pid:
                fila = feats_base[i].copy()
                fila[1] = var_score
                fila[2] = rango_score
                out[i] = fila
        return out

    feats_a2_orig = aplicar_variance_range_por_request(feats, ids_original)
    res_a2_orig = evaluar_brazo(selector, indices_pct, ids_original,
                                feats_a2_orig, labels)
    feats_a2_dedup = aplicar_variance_range_por_request(feats_dedup, ids_dedup)
    res_a2_dedup = evaluar_brazo(selector, indices_pct, ids_dedup,
                                 feats_a2_dedup, labels)
    comparacion_a2 = comparar_pareado(res_a2_orig, res_a2_dedup, pids_orden,
                                      con_bootstrap=False)
    print(f"  A2: orig {res_a2_orig['top1_rate']} -> dedup {res_a2_dedup['top1_rate']} | "
          f"cambiados {comparacion_a2['ganadores_cambiados']['n']}")

    # ── 31 empates cross-source ──
    recomputo = recomputar_medoids(insumos, candidatos_por_identidad)
    v = recomputo["verificacion"]
    print(f"  medoids: reps coinciden {v['n_representantes_coinciden_medoid_recomputado']}/"
          f"{v['n_clusters_sidecar']} | no-singleton {v['n_no_singleton']} | "
          f"empates {v['n_empates_medoid']} | cross {v['n_empates_cross_source']} | "
          f"coincide sellado: {v['coincide_con_sellado']}")
    if not v["coincide_con_sellado"]:
        raise SystemExit("ERROR: recomputacion de medoids NO coincide con el "
                         "sidecar sellado de MF-11-R1")

    contrafactual = contrafactual_empates(
        selector, indices_pct, feats, feats_dedup, densas, labels, ids_dedup,
        res_a1_dedup["detalle_por_pid"], recomputo["clusters_cross"], pids_orden)
    c = contrafactual["resumen"]
    print(f"  31 empates: {c['n_alternativas_evaluadas']} alternativas evaluadas | "
          f"{c['n_alternativas_cambian_ganador']} cambian ganador | "
          f"{c['n_clusters_con_al_menos_un_cambio']} clusters con >=1 cambio | "
          f"direccion: {c['direccion_fuente_ganador']}")

    # ── A0 historico ──
    a0_block = {
        "lectura": "A0 — reproduccion historica exacta",
        "contrato": ("2739 poses originales, features de conjunto CONGELADAS del "
                     "dataset (variance/range POR-RUN + cluster_density congelada); "
                     "pipeline actual (selector.py + transformacion Fase 1.6) sobre "
                     "features congeladas; NO re-ejecuta el extractor (alcance C4)"),
        "n_poses": res_a0["n_poses"],
        "n_complejos": res_a0["n_complejos"],
        "top1_hits": res_a0["top1_hits"],
        "top1_rate": res_a0["top1_rate"],
        "rmsd_mediana_ganador": res_a0["rmsd_mediana_ganador"],
        "rmsd_media_ganador": res_a0["rmsd_media_ganador"],
        "margen_mediana": res_a0["margen_mediana"],
        "n_abstenciones": res_a0["n_abstenciones"],
        "tasa_abstencion": res_a0["tasa_abstencion"],
        "desglose_abstencion": res_a0["desglose_abstencion"],
        "fuente_ganadora": res_a0["fuente_ganadora"],
        "fuente_ganadora_condicionada": res_a0["fuente_ganadora_condicionada"],
        "reproduccion_historica": {
            "referencia": ("scripts/artifacts_ruta_c_fase1_6.json "
                           "modelo_B.train (entrenamiento historico)"),
            "historico_top1_rate": HISTORICO_TRAIN_TOP1,
            "historico_mediana_rmsd": HISTORICO_TRAIN_MEDIANA,
            "obtenido_top1_rate": res_a0["top1_rate"],
            "obtenido_mediana_rmsd": res_a0["rmsd_mediana_ganador"],
            "top1_igual": igual_top1,
            "mediana_igual": igual_mediana,
            "reproduce": bool(igual_top1 and igual_mediana),
        },
    }

    def bloque_brazo(res: dict, lectura: str, contrato: str) -> dict:
        return {
            "lectura": lectura,
            "contrato": contrato,
            "n_poses": res["n_poses"],
            "n_complejos": res["n_complejos"],
            "top1_hits": res["top1_hits"],
            "top1_rate": res["top1_rate"],
            "rmsd_mediana_ganador": res["rmsd_mediana_ganador"],
            "rmsd_media_ganador": res["rmsd_media_ganador"],
            "margen_mediana": res["margen_mediana"],
            "margen_media": res["margen_media"],
            "n_abstenciones": res["n_abstenciones"],
            "tasa_abstencion": res["tasa_abstencion"],
            "desglose_abstencion": res["desglose_abstencion"],
            "fuente_ganadora": res["fuente_ganadora"],
            "fuente_ganadora_condicionada": res["fuente_ganadora_condicionada"],
        }

    metrics = {
        "experimento": "RS-01A",
        "declaracion_resultado": ("El resultado es SOLO una auditoria in-sample de "
                                  "compatibilidad y perturbacion del checkpoint "
                                  "congelado v0.6 frente a la union deduplicada "
                                  "MF-11-R1. Cualquier diferencia observada no "
                                  "constituye evidencia de mejora ni de degradacion "
                                  "generalizable; para eso existe RS-01B."),
        "preregistro": "scripts/artifacts_science/RS-01/PREREGISTRO.md (sello paraguas d320bcd, §3.3/§3.4)",
        "runtime": {
            "python": sys.version.split()[0],
            "xgboost": __import__("xgboost").__version__,
            "numpy": np.__version__,
            "checkpoint_sha256": insumos["tabla_sha"]["checkpoint_xgb"]["sha256"],
            "checkpoint_bytes": R_CHECKPOINT.stat().st_size,
            "n_arboles_cargados": n_arboles,
            "best_iteration_meta": meta.get("best_iteration"),
        },
        "integridad_insumos_sha256": insumos["tabla_sha"],
        "validacion_densidad_historica": {
            "metodo": ("recomputacion con la definicion del dataset builder "
                       "(malla densa mapeada de records/{pid}.json, RMSD pocket-frame "
                       "< 2.0 A sin alinear, UMBRAL_CLUSTER=2.0) sobre el conjunto "
                       "ORIGINAL completo"),
            "n_coinciden_con_congelado": n_coinciden,
            "n_total": 2739,
            "exacto": bool(n_coinciden == 2739),
        },
        "a0": a0_block,
        "a1": {
            "nota": ("PRIMARIA. variance/range POR-RUN congelados en AMBOS brazos; "
                     "tras dedup SOLO cluster_density se recalcula (pares entre "
                     "supervivientes, semantica historica) y en consecuencia la "
                     "matriz z/pct por complejo"),
            "original": bloque_brazo(
                res_a1_orig, "A1 original (2739)", "features congeladas (identico a A0)"),
            "deduplicado": bloque_brazo(
                res_a1_dedup, "A1 dedup (2413)",
                "variance/range POR-RUN congelados; cluster_density recalculada "
                "post-dedup; z/pct por complejo sobre el conjunto resultante"),
            "a1_original_identico_a_a0": identico_a0,
            "pareado": comparacion_a1,
        },
        "a2": {
            "nota": ("SECUNDARIA (sensibilidad de produccion). variance/range POR "
                     "REQUEST en ambos brazos (semantica selector.py:219-225, "
                     "round(...,4)); cluster_density: original congelada (validada "
                     "identica a la recomputada), dedup recalculada. Alcance C4: NO "
                     "valida el extractor end-to-end"),
            "original": bloque_brazo(
                res_a2_orig, "A2 original (2739)",
                "variance/range POR REQUEST sobre features congeladas"),
            "deduplicado": bloque_brazo(
                res_a2_dedup, "A2 dedup (2413)",
                "variance/range POR REQUEST; cluster_density recalculada post-dedup"),
            "pareado": comparacion_a2,
            "deltas_semantica_vs_a1": {
                "nota": ("efecto aislado de la semantica por-request (A2) frente a "
                         "la por-run congelada (A1) dentro de CADA brazo"),
                "original": deltas_semantica(res_a2_orig, res_a1_orig, pids_orden),
                "deduplicado": deltas_semantica(res_a2_dedup, res_a1_dedup, pids_orden),
            },
        },
        "empates_contrafactual": contrafactual,
        "empates_contrafactual_verificacion_recomputacion": recomputo["verificacion"],
        "archivos_abiertos_repo": sorted(_ABIERTOS_REPO),
        "garantia_cuarentena": (
            "builtins.open auditado contra whitelist explicita: solo se abrieron "
            "los insumos declarados, los modulos importados por composicion, los "
            "records train y las salidas; poses_val.jsonl y poses_test.jsonl NO "
            "figuran en archivos_abiertos_repo y nunca se abren en ninguna lectura "
            "(los archivos internos del interprete python-embed/ y __pycache__ "
            "quedan fuera del alcance de la auditoria)"),
        "determinismo": ("salidas sin timestamps ni aleatoriedad no-seeded; dos "
                         "corridas producen metrics.json y per_complex.jsonl "
                         "byte-identicos"),
    }

    # ── auditoria de cuarentena: whitelist de archivos abiertos ──
    whitelist = {
        "scripts/run_rs01a_audit.py",
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
    fuera = sorted(p for p in _ABIERTOS_REPO
                   if p not in whitelist and "__pycache__" not in p
                   and not p.endswith(".pyc")
                   and not p.startswith("python-embed/"))
    if fuera:
        raise SystemExit("ERROR: archivos fuera del whitelist abiertos: "
                         + "; ".join(fuera))

    # ── per_complex.jsonl ──
    filas_pc = []
    for pid in pids_orden:
        d0 = res_a0["detalle_por_pid"][pid]
        d1o = res_a1_orig["detalle_por_pid"][pid]
        d1d = res_a1_dedup["detalle_por_pid"][pid]
        d2o = res_a2_orig["detalle_por_pid"][pid]
        d2d = res_a2_dedup["detalle_por_pid"][pid]

        def mini(d):
            return {"ganador": d["ganador"], "fuente": d["fuente"],
                    "rmsd": round(d["rmsd"], 4), "hit": d["hit"],
                    "margen": d["margen"], "abstenido": d["abstenido"]}

        filas_pc.append({
            "pid": pid,
            "n_poses_original": d0["n_poses"],
            "n_poses_dedup": d1d["n_poses"],
            "fuentes_disponibles_original": res_a0["fuentes_disponibles"][pid],
            "fuentes_disponibles_dedup": res_a1_dedup["fuentes_disponibles"][pid],
            "a0": mini(d0),
            "a1_original": mini(d1o),
            "a1_dedup": mini(d1d),
            "a2_original": mini(d2o),
            "a2_dedup": mini(d2d),
            "a1_cambio_ganador": d1o["ganador"] != d1d["ganador"],
            "a1_perdida_hit": d1o["hit"] and not d1d["hit"],
            "a1_recuperacion_hit": not d1o["hit"] and d1d["hit"],
            "a1_cambio_abstencion": d1o["abstenido"] != d1d["abstenido"],
            "a1_delta_margen": round(d1d["margen"] - d1o["margen"], 6),
            "a2_cambio_ganador": d2o["ganador"] != d2d["ganador"],
            "a2_cambio_abstencion": d2o["abstenido"] != d2d["abstenido"],
            "a2_delta_margen": round(d2d["margen"] - d2o["margen"], 6),
        })

    escribir_json(out_dir / "metrics.json", metrics)
    escribir_jsonl(out_dir / "per_complex.jsonl", filas_pc)
    escribir_jsonl(out_dir / "failures.jsonl", [])

    print(f"  salidas escritas en {out_dir}")
    print(f"  sha metrics={sha256_archivo(out_dir / 'metrics.json')[:16]}... "
          f"per_complex={sha256_archivo(out_dir / 'per_complex.jsonl')[:16]}...")
    print(f"  duracion: {time.monotonic() - t0:.1f}s")


if __name__ == "__main__":
    main()
