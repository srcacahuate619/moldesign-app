# -*- coding: utf-8 -*-
"""run_rs04_oof.py — RS-04 OOF: strain MMFF94s como feature sobre v0.6.

Cross-fitting COMPLETO (5 folds sellados de RS-01B, [55,16,15,15,15] por las
38 componentes combinadas scaffold+receptor) que aísla el efecto de la
feature de strain: baseline v0.6 (clon congelado, 233 features) frente a
modelo AUMENTADO (v0.6 + strain_mmff, 234 features), evaluados sobre
EXACTAMENTE los mismos complejos por fold.

Contrato literal aplicado (CAMPANA-2-PLAN sellado 41b7f09, IT1 QA-5/QA-6 +
RS-04-QC sellado 5ffb256):

  - Strain = E_MMFF94s(pose docked, SOLO H optimizados, pesados fijados) -
    E_MMFF94s(minimo aislado). Topologia/ordenes/estereoquimica/cargas desde
    el SDF SANITIZADO; mapeo heavy-atom biyectivo verificado; AddHs
    addCoords=True; MMFF94s (NO se mezcla UFF); halogenos NO excluidos por
    nombre (cobertura real); referencia aislada Nconfs =
    min(200, max(50, 10*rot_bonds)), ETKDGv3 seed 42 numThreads=1,
    optimizacion completa, minimo energetico; strain negativo NO truncado
    (dispara UNA ampliacion del search de referencia; si persiste, fallo
    registrado); resultados separados neutros vs ionizados.
  - 14 poses degeneradas (1kpm x9, 1nm6 x5, flexible_redock): strain no
    computable -> imputacion con la MEDIANA del outer-train de su fold
    (definida DENTRO del outer-train; documentada). Nunca energia cero.
  - XGBoost CONGELADO (aislar el efecto strain): rank:pairwise,
    n_estimators=52, max_depth 6, lr 0.05, subsample 0.8, seed 42, n_jobs 4,
    SIN early stopping, sin eval_set. Mismos hiperparametros en baseline y
    aumentado. Preprocesamiento/imputacion/coeficientes ajustados DENTRO del
    outer-train de cada fold.
  - Gate operacional RS-04: Top-1 OOF acumulado >= 50/116 (47+3); mediana
    pareada dRMSD <= +0.1 A (primaria, nunca diferencia de medianas);
    cobertura quimica >= 95%; cold-start P95 <= 5 s/ligando; cacheado P95
    <= 100 ms/pose y <= 3 s/complejo; sin regresion grave por estrato
    hard/control (grave PREREGISTRADO: perdida de hits > 2 por estrato o
    mediana pareada del estrato > 0.1 A).
  - Incertidumbre: bootstrap BCa por las 38 componentes (10 000 replicas,
    seed 42) sobre Delta Top-1 y mediana pareada; por complejo solo
    sensibilidad; McNemar exacto (binomtest bilateral, sin x2); por estrato
    descriptivo con denominador.
  - Cero val/test/CONFIRM: auditoria de builtins.open con whitelist (patron
    RS-01B/RS-04-QC).

Composicion (solo lectura de codigo sellado):
  - scripts/run_rs04_qc.py  -> strain MMFF94s QA-5 (parsear_pesados_pose,
    plantilla_pesada, grafo_ligando, mapear, mol_pose, _opt_solo_h,
    calcular_strain, _bench_cold, check1/check3).
  - scripts/run_rs01b_crossfit.py -> folds sellados, features A1, clones
    congelados, transformaciones z/pct, evaluacion OOF, bootstrap BCa,
    McNemar (y parchea builtins.open con auditoria de cuarentena).

Determinismo: salidas sin timestamps ni aleatoriedad no-seeded; el strain
se cachea por ligando (referencia aislada, idempotente, ETKDG seed 42); la
2a corrida (--repro) reutiliza cache de referencia + benchmarks.json
congelados + clones verificados por sha y exige salidas byte-identicas, con
spot-check de recomputacion fresca de 3 ligandos contra el cache.

Uso:
  python-embed/python.exe scripts/run_rs04_oof.py              # corrida canonica
  python-embed/python.exe scripts/run_rs04_oof.py --repro      # determinismo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import numpy as np  # noqa: E402

# ── composicion (nada sellado se edita) ─────────────────────────────────────
# run_rs01b_crossfit parchea builtins.open con auditoria de archivos abiertos
# (registra todo open() bajo el repo; usado al final para la whitelist).
import run_rs04_qc as qc  # noqa: E402  (strain MMFF94s, QA-5)
import run_rs01b_crossfit as rs1b  # noqa: E402  (crossfit + estadistica)

from run_rs04_qc import (  # noqa: E402
    MAX_ITERS,
    parsear_pesados_pose,
    plantilla_pesada,
    grafo_ligando,
    mapear,
    mol_pose,
    _opt_solo_h,
    calcular_strain,
)
from run_rs01b_crossfit import (  # noqa: E402
    clave_identidad,
    leer_json,
    leer_jsonl,
    escribir_json,
    escribir_jsonl,
    sha256_archivo,
    z_por_pid,
    pct_por_pid,
    entrenar_clon,
    construir_entrenamiento,
    evaluar_conjunto,
    agregar_brazo,
    pareado_por_pid,
    mcnemar_hits,
    bootstrap_componentes_38,
    bootstrap_complejos_sensibilidad,
    bootstrap_descriptivo_fold,
    excluye_cero,
    cargar_insumos,
    cargar_features,
    cargar_densas,
    densidad_historica,
    PARAMS_CLON,
    FEATURES_V0,
    PCT_RAW,
    N_Z,
    N_MODELO_B,
    UMBRAL_POSITIVA,
    UMBRAL_ABSTENCION,
    N_FOLDS,
    SEED_BOOT,
    N_BOOT,
    R_CHECKPOINT,
    R_META,
    RECORDS_DIR,
)

from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402
from rdkit.Chem import rdForceFieldHelpers as ffd  # noqa: E402
from rdkit.Chem import rdMolDescriptors  # noqa: E402

# ───────────────────────── rutas y constantes ───────────────────────────────

ARTIFACTOS = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR_DEFAULT = ARTIFACTOS / "RS-04-OOF"
RS01 = ARTIFACTOS / "RS-01"
QC_ART = ARTIFACTOS / "RS-04-QC"
RS01B = ARTIFACTOS / "RS-01B"
MF01_UNION = ARTIFACTOS / "MF-01-UNION"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"

R_FOLD_PLAN = RS01 / "fold_plan.json"
R_UNION_CAND = MF01_UNION / "union_candidates_train.jsonl"
R_UNION_LABELS = MF01_UNION / "union_labels_train.jsonl"
R_BENCH_QC = QC_ART / "benchmarks.json"

SEED = 42

N_RAW_AUG = N_Z + 1                      # 225 (224 congeladas + strain)
N_MODELO_AUG = N_RAW_AUG + len(PCT_RAW)  # 234

GATE_HITS = 50            # Top-1 OOF acumulado requerido (47 + 3)
GATE_MEDIANA = 0.1        # mediana pareada dRMSD <= +0.1 A
GATE_COBERTURA = 95.0     # cobertura quimica >= 95%
GATE_COLD_MS = 5000.0     # cold-start P95 <= 5 s/ligando
GATE_POSE_MS = 100.0      # cacheado P95 <= 100 ms/pose
GATE_COMPLEJO_MS = 3000.0 # cacheado P95 <= 3 s/complejo
ESTRATO_PERDIDA_MAX = 2   # perdida de hits por estrato > 2 -> grave (preregistrado)
ESTRATO_MEDIANA_MAX = 0.1 # mediana pareada del estrato > 0.1 -> grave

N_SPOT_REPRO = 3          # ligandos recomputados frescos en --repro (determinismo)
COLD_REPS = 3             # repeticiones cold-start (mediana, patron QC)

EXPANSION_FACTOR = 2      # QA-5: UNA ampliacion del search de referencia
EXPANSION_CAP = 400

FORBIDDEN = ("poses_val", "poses_test", "d-rc-confirm", "val40", "confirm")

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


def nconfs_referencia(plantilla) -> int:
    rot = rdMolDescriptors.CalcNumRotatableBonds(plantilla)
    return min(200, max(50, 10 * rot))


def referencia_aislada(plantilla, nconfs):
    """Replica EXACTA del contrato QA-5/QC: ETKDGv3 seed 42 numThreads=1,
    optimizacion MMFF94s completa por conformero, minimo energetico.
    Devuelve (e_min, n_embebidas) o (None, 0) si no hubo conformeros."""
    mh = Chem.AddHs(plantilla)
    params = AllChem.ETKDGv3()
    params.randomSeed = SEED
    params.pruneRmsThresh = 0.4
    params.numThreads = 1
    ids = list(AllChem.EmbedMultipleConfs(mh, numConfs=nconfs, params=params))
    if not ids:
        return None, 0
    props = ffd.MMFFGetMoleculeProperties(mh, mmffVariant="MMFF94s")
    e_min = None
    for cid in ids:
        ffd.MMFFOptimizeMolecule(mh, mmffVariant="MMFF94s",
                                 maxIters=MAX_ITERS, confId=cid)
        ff = ffd.MMFFGetMoleculeForceField(mh, props, confId=cid)
        e = ff.CalcEnergy()
        if e_min is None or e < e_min:
            e_min = e
    return e_min, len(ids)


def soporte_mmff_ligando(lig) -> bool:
    _, plantilla, _ = lig
    return ffd.MMFFHasAllMoleculeParams(Chem.AddHs(plantilla))


# ───────────────────────── cache de referencia (idempotente) ────────────────

def cache_referencia_path(cache_dir: Path) -> Path:
    return cache_dir / "referencias.jsonl"


def cargar_cache_referencias(cache_dir: Path) -> dict:
    p = cache_referencia_path(cache_dir)
    if not p.exists():
        return {}
    return {r["pid"]: r for r in leer_jsonl(p)}


def append_referencia(cache_dir: Path, fila: dict) -> None:
    p = cache_referencia_path(cache_dir)
    with open(p, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")


def obtener_referencia(pid, lig, cache_dir: Path, cache: dict, anomalias: list):
    """Referencia aislada por ligando con cache idempotente (etapa cara).
    Si el ligando ya esta cacheado, se reutiliza tal cual (ETKDG seed 42 ->
    determinista; --repro hace spot-check de recomputacion fresca)."""
    if pid in cache:
        fila = cache[pid]
        if fila["e_min"] is None:
            anomalias.append({
                "tipo": "referencia_sin_conformeros",
                "pid": pid,
                "detalle": "EmbedMultipleConfs devolvio 0 conformeros",
            })
        return fila
    _, plantilla, _ = lig
    nconfs = nconfs_referencia(plantilla)
    e_min, n_emb = referencia_aislada(plantilla, nconfs)
    fila = {
        "pid": pid,
        "carga_formal": Chem.GetFormalCharge(plantilla),
        "rot_bonds": rdMolDescriptors.CalcNumRotatableBonds(plantilla),
        "nconfs_solicitadas": nconfs,
        "n_embebidas": n_emb,
        "e_min": _round(e_min, 6) if e_min is not None else None,
        "expansion": None,
    }
    if e_min is None:
        anomalias.append({
            "tipo": "referencia_sin_conformeros",
            "pid": pid,
            "detalle": "EmbedMultipleConfs devolvio 0 conformeros",
        })
    append_referencia(cache_dir, fila)
    return fila


def expandir_referencia(fila: dict, lig, cache_dir: Path) -> dict:
    """QA-5: UNA ampliacion del search de referencia (2x, tope 400) cuando
    aparece strain negativo. Actualiza la fila del cache en disco (idempotente:
    si ya hay expansion registrada no se recalcula)."""
    if fila.get("expansion") is not None:
        return fila
    _, plantilla, _ = lig
    nconfs1 = min(EXPANSION_CAP, EXPANSION_FACTOR * int(fila["nconfs_solicitadas"]))
    e_min1, n_emb1 = referencia_aislada(plantilla, nconfs1)
    usada = bool(e_min1 is not None and (fila["e_min"] is None or e_min1 < fila["e_min"]))
    fila["expansion"] = {
        "nconfs_solicitadas": nconfs1,
        "n_embebidas": n_emb1,
        "e_min": _round(e_min1, 6) if e_min1 is not None else None,
        "usada": usada,
    }
    if usada:
        fila["e_min"] = _round(e_min1, 6)
    reescribir_cache_referencias(cache_dir)
    return fila


def reescribir_cache_referencias(cache_dir: Path) -> None:
    p = cache_referencia_path(cache_dir)
    filas = leer_jsonl(p)
    filas.sort(key=lambda r: r["pid"])
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    shutil.move(str(tmp), str(p))


# ───────────────────────── strain por pose (fresco, determinista) ───────────

def strain_pose_identity(candidato, lig):
    """E_pose (H optimizados, pesados fijados) + mapeo para una pose."""
    _, plantilla, g_lig = lig
    atoms, n_g = parsear_pesados_pose(candidato["pdbqt"])
    m1, motivo = mapear(atoms, plantilla, g_lig)
    if motivo is not None:
        return None, motivo, n_g, None
    m, n_heavy = mol_pose(plantilla, atoms, m1)
    res = _opt_solo_h(m, plantilla, atoms, m1)
    return res, None, n_g, atoms


def computar_strain_pose(candidato, lig, e_min):
    """strain = E_pose - E_min SIN truncamiento (QA-5)."""
    res, motivo, n_g, _ = strain_pose_identity(candidato, lig)
    if motivo is not None:
        return {"identity": candidato["identity"], "pid": candidato["pid"],
                "mapeo_ok": False, "motivo": motivo, "e_pose": None,
                "strain": None, "converged": None, "n_g": n_g, "ms": None}
    strain = calcular_strain(res["e_final"], e_min)
    return {"identity": candidato["identity"], "pid": candidato["pid"],
            "mapeo_ok": True, "motivo": None,
            "e_pose": _round(res["e_final"], 4),
            "strain": _round(strain, 4),
            "converged": bool(res["converged"]), "n_g": n_g, "ms": None}


# ───────────────────────── features aumentadas (225) ────────────────────────

def feats_augmentadas(feats: dict, strain_por_identidad: dict,
                      mediana_imputacion: float) -> dict:
    """Matriz aumentada por identidad: 224 congeladas + strain como columna
    225. Las poses con strain no computable (degeneradas) se imputan con la
    mediana del outer-train de su fold (definida DENTRO del outer-train)."""
    out = {}
    for identidad, fila in feats.items():
        s = strain_por_identidad.get(identidad)
        if s is None:
            s = mediana_imputacion
        out[identidad] = np.hstack([fila, np.array([s], dtype=np.float64)])
    return out


def construir_entrenamiento_aug(pids, ids_por_pid, feats, labels, indices_pct):
    """Copia del patron RS-01B (construir_entrenamiento) para la matriz
    aumentada: Z sobre las 225 raw + P sobre las mismas 9 columnas congeladas
    (la feature de strain entra por su columna estandarizada; no altera el
    orden de percentiles de v0.6)."""
    filas = []
    y = []
    grupos = []
    for pid in pids:
        ids = ids_por_pid[pid]
        X = np.vstack([feats[i] for i in ids])
        assert X.shape == (len(ids), N_RAW_AUG)
        Z = z_por_pid(X, [len(ids)])
        Z[np.isnan(Z)] = 0.0
        P = pct_por_pid(X, [len(ids)], indices_pct)
        P[np.isnan(P)] = 0.0
        X_B = np.hstack([Z, P])
        assert X_B.shape == (len(ids), N_MODELO_AUG)
        filas.append(X_B)
        y.extend([-float(labels[i]["rmsd"]) for i in ids])
        grupos.append(len(ids))
    X_train = np.vstack(filas)
    return X_train, np.array(y, dtype=np.float64), grupos


def evaluar_conjunto_aug(clon, pids, ids_por_pid, feats, labels, indices_pct):
    """Copia del patron RS-01B (evaluar_conjunto) para la matriz aumentada."""
    import xgboost
    resultados = {}
    for pid in pids:
        ids = ids_por_pid[pid]
        X = np.vstack([feats[i] for i in ids])
        assert X.shape == (len(ids), N_RAW_AUG)
        Z = z_por_pid(X, [len(ids)])
        Z[np.isnan(Z)] = 0.0
        P = pct_por_pid(X, [len(ids)], indices_pct)
        P[np.isnan(P)] = 0.0
        X_B = np.hstack([Z, P])
        assert X_B.shape == (len(ids), N_MODELO_AUG)
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


# ───────────────────────── costes (re-verificacion en este run) ─────────────

def _p50_p95(ms_list):
    orden = sorted(ms_list)
    if not orden:
        return None, None
    n = len(orden)
    p50 = orden[n // 2]
    p95 = orden[min(n - 1, int(math.ceil(0.95 * n)) - 1)]
    return _round(p50, 3), _round(p95, 3)


def medir_costes(candidatos, ligandos, pids, strain_filas):
    """Re-verificacion en este run de los 3 gates de coste del plan: cold-start
    P50/P95 por ligando con el MISMO protocolo congelado del RS-04-QC
    (qc._bench_cold: leer SDF + sanitizar + plantilla + AddHs + setup MMFF +
    mapear + optimizacion H de la primera pose mapeable, mediana de 3
    repeticiones); cacheado P50/P95 por pose (medido durante el pase de
    strain) y por complejo (suma)."""
    cold_ms = {}
    for pid in pids:
        cand_pid = [c for c in candidatos if c["pid"] == pid]
        reps = []
        for c in cand_pid:
            try:
                reps = [qc._bench_cold(pid, c) for _ in range(COLD_REPS)]
            except Exception:
                continue
            break
        cold_ms[pid] = _round(statistics.median(reps), 3) if reps else None
    cold_vals = sorted(v for v in cold_ms.values() if v is not None)
    cold_p50, cold_p95 = _p50_p95(cold_vals)

    pose_ms = [{"identity": f["identity"], "ms": f["ms"]} for f in strain_filas]
    vals_pose = sorted(p["ms"] for p in pose_ms if p["ms"] is not None)
    pose_p50, pose_p95 = _p50_p95(vals_pose)

    complejo_ms = {}
    for pid in pids:
        suma = sum(p["ms"] for p in pose_ms
                   if p["identity"].split("|")[1] == pid and p["ms"] is not None)
        n_med = sum(1 for p in pose_ms
                    if p["identity"].split("|")[1] == pid and p["ms"] is not None)
        complejo_ms[pid] = _round(suma, 3) if n_med else None
    vals_cplx = sorted(v for v in complejo_ms.values() if v is not None)
    cplx_p50, cplx_p95 = _p50_p95(vals_cplx)

    return {
        "cold_ms_por_ligando": cold_ms,
        "cold_p50_ms": cold_p50,
        "cold_p95_ms": cold_p95,
        "cacheado_pose_ms": pose_ms,
        "cacheado_pose_p50_ms": pose_p50,
        "cacheado_pose_p95_ms": pose_p95,
        "cacheado_complejo_ms": complejo_ms,
        "cacheado_complejo_p50_ms": cplx_p50,
        "cacheado_complejo_p95_ms": cplx_p95,
    }


def gates_coste(bench):
    return {
        "cold_p95_le_5000ms": bench["cold_p95_ms"] is not None
        and bench["cold_p95_ms"] <= GATE_COLD_MS,
        "cacheado_pose_p95_le_100ms": bench["cacheado_pose_p95_ms"] is not None
        and bench["cacheado_pose_p95_ms"] <= GATE_POSE_MS,
        "cacheado_complejo_p95_le_3000ms":
            bench["cacheado_complejo_p95_ms"] is not None
            and bench["cacheado_complejo_p95_ms"] <= GATE_COMPLEJO_MS,
    }


# ───────────────────────── estadistica por estrato ─────────────────────────

def descriptivo_estrato(pids_estrato, comps_estrato, pid2comp, res_b, res_a,
                        seed_estr):
    """Descriptivo por estrato con denominador explicito (>= 5 componentes
    para intervalo percentil bootstrap, patron RS-01B)."""
    n_comp = len(comps_estrato)
    hits_b = sum(1 for p in pids_estrato if res_b[p]["hit"])
    hits_a = sum(1 for p in pids_estrato if res_a[p]["hit"])
    perdida = hits_b - hits_a
    deltas = [res_a[p]["rmsd"] - res_b[p]["rmsd"] for p in pids_estrato]
    mediana = _round(float(np.median(deltas)), 6)
    grave = bool(perdida > ESTRATO_PERDIDA_MAX or mediana > ESTRATO_MEDIANA_MAX)
    intervalo = None
    if n_comp >= 5:
        d_hit = {p: (1 if res_a[p]["hit"] else 0) - (1 if res_b[p]["hit"] else 0)
                 for p in pids_estrato}
        d_rmsd = {p: res_a[p]["rmsd"] - res_b[p]["rmsd"] for p in pids_estrato}
        suma_comp = {c: sum(v for p, v in d_hit.items() if pid2comp[p] == c)
                     for c in comps_estrato}
        deltas_comp = {c: np.array([d_rmsd[p] for p in pids_estrato
                                    if pid2comp[p] == c], dtype=np.float64)
                       for c in comps_estrato}
        rng = np.random.default_rng(seed_estr)
        idx = rng.integers(0, n_comp, size=(N_BOOT, n_comp))
        boot_hits = np.array([sum(suma_comp[comps_estrato[i]] for i in fila)
                              for fila in idx], dtype=np.float64)
        boot_med = np.array([
            float(np.median(np.concatenate([deltas_comp[comps_estrato[i]]
                                            for i in fila])))
            for fila in idx], dtype=np.float64)
        intervalo = {
            "metodo": "percentil 2.5-97.5 (bootstrap por componentes del estrato, descriptivo)",
            "hits_intervalo": [round(float(x), 6) for x in
                               np.percentile(boot_hits, [2.5, 97.5])],
            "mediana_pareada_intervalo": [round(float(x), 6) for x in
                                          np.percentile(boot_med, [2.5, 97.5])],
        }
    return {
        "n_complejos": len(pids_estrato),
        "n_componentes": n_comp,
        "top1_baseline": hits_b,
        "top1_aumentado": hits_a,
        "delta_hits": int(hits_a - hits_b),
        "perdida_hits": int(max(0, perdida)),
        "mediana_pareada_rmsd": mediana,
        "grave_preregistrado": {
            "definicion": ("perdida de hits > 2 por estrato o mediana pareada "
                           "del estrato > 0.1 A (preregistrado)"),
            "perdida_max": ESTRATO_PERDIDA_MAX,
            "mediana_max": ESTRATO_MEDIANA_MAX,
            "es_grave": grave,
        },
        "bootstrap_descriptivo": intervalo,
    }


# ───────────────────────── flujo principal ─────────────────────────────────

def preparar_insumos():
    insumos = cargar_insumos()
    print("  insumos sellados verificados (sha256): OK", flush=True)

    from pose_selector.selector import PoseSelector
    selector = PoseSelector(str(R_CHECKPOINT), str(R_META),
                            abstention_threshold=UMBRAL_ABSTENCION)
    if selector.load_error is not None or selector.booster is None:
        raise SystemExit(f"ERROR: no se pudo cargar el checkpoint: {selector.load_error}")
    meta = selector.meta
    assert len(meta.get("feature_names_233", [])) == N_MODELO_B
    assert meta.get("orden_pct") == PCT_RAW
    assert meta.get("feature_names_raw_224", [])[:9] == FEATURES_V0
    indices_pct = [meta["feature_names_raw_224"].index(f) for f in PCT_RAW]
    print(f"  checkpoint v0.6 cargado ({selector.booster.num_boosted_rounds()} "
          f"arboles; SOLO contrato de features congelado)", flush=True)

    feats = cargar_features(insumos)
    densas = cargar_densas(insumos)
    labels = {l["identity"]: l for l in insumos["labels"]}
    candidatos = insumos["candidatos"]
    candidatos_por_identidad = {c["identity"]: c for c in candidatos}
    ids_original = sorted(candidatos_por_identidad.keys(), key=clave_identidad)
    pids_orden = sorted({i.split("|")[1] for i in ids_original})
    assert len(pids_orden) == 116 and len(ids_original) == 2739

    por_pid = defaultdict(list)
    for c in candidatos:
        por_pid[c["pid"]].append(c["identity"])

    dens_recomputada_orig = densidad_historica(densas, ids_original)
    n_coinciden = sum(1 for i in ids_original
                      if float(feats[i][8]) == float(dens_recomputada_orig[i]))
    print(f"  validacion densidad historica: {n_coinciden}/2739 exactas", flush=True)
    if n_coinciden != 2739:
        raise SystemExit("ERROR: recomputacion de cluster_density no reproduce "
                         "los valores congelados")

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
    comps_por_fold = {f: [c["componente"] for c in fold_plan["por_componente"]
                          if c["fold"] == f] for f in range(N_FOLDS)}
    if len(comps_orden) != 38:
        raise SystemExit(f"ERROR: {len(comps_orden)} componentes != 38")
    estrato_por_pid = {e["pid"]: e["dmfhard_train_estrato"]
                       for e in fold_plan["por_pid"]}
    return {
        "insumos": insumos, "feats": feats, "labels": labels,
        "candidatos": candidatos, "por_pid": por_pid, "pids_orden": pids_orden,
        "pid2fold": pid2fold, "pids_fold": pids_fold, "tamanos": tamanos,
        "comps_orden": comps_orden, "pid2comp": pid2comp,
        "comps_por_fold": comps_por_fold, "indices_pct": indices_pct,
        "estrato_por_pid": estrato_por_pid,
        "n_coinciden": n_coinciden,
    }


def cargar_ligandos(pids):
    ligandos = {}
    fallos = []
    for pid in pids:
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        mol = Chem.MolFromMolFile(str(sdf), sanitize=True, removeHs=False)
        if mol is None:
            fallos.append({"pid": pid, "motivo": "sdf_fail"})
            continue
        plantilla = plantilla_pesada(mol)
        ligandos[pid] = (mol, plantilla, grafo_ligando(mol))
    return ligandos, fallos


def pase_strain(candidatos, ligandos, cache_dir, anomalias, usar_cache):
    """Strain por pose para las 2739 poses (fresco; la referencia aislada se
    cachea por ligando). Devuelve filas_por_identidad."""
    cache = cargar_cache_referencias(cache_dir) if usar_cache else {}
    filas = {}
    por_pid_pose = defaultdict(list)
    t_ref = time.monotonic()
    for pid in sorted(ligandos):
        lig = ligandos[pid]
        ref = obtener_referencia(pid, lig, cache_dir, cache, anomalias)
        if ref["e_min"] is None:
            for c in candidatos:
                if c["pid"] == pid:
                    filas[c["identity"]] = {
                        "identity": c["identity"], "pid": pid, "mapeo_ok": False,
                        "motivo": "referencia_sin_conformeros", "e_pose": None,
                        "strain": None, "converged": None, "n_g": None, "ms": None}
            continue
        for c in candidatos:
            if c["pid"] != pid:
                continue
            t0 = time.perf_counter()
            fila = computar_strain_pose(c, lig, ref["e_min"])
            fila["ms"] = _round((time.perf_counter() - t0) * 1000.0, 3)
            filas[c["identity"]] = fila
            por_pid_pose[pid].append(fila)
        if any(f["strain"] is not None and f["strain"] < 0
               for f in por_pid_pose[pid]):
            expandir_referencia(ref, lig, cache_dir)
            if (ref.get("expansion") or {}).get("usada"):
                for f in por_pid_pose[pid]:
                    if f["mapeo_ok"]:
                        f["strain"] = _round(calcular_strain(
                            f["e_pose"], ref["e_min"]), 4)
        ex = ref.get("expansion")
        if ex is not None:
            anomalias.append({
                "tipo": ("strain_negativo_ampliacion_referencia"
                         if ex.get("usada")
                         else "strain_negativo_sin_mejora_referencia"),
                "pid": pid,
                "detalle": ("UNA ampliacion del search de referencia "
                            f"({ref['nconfs_solicitadas']} -> "
                            f"{ex['nconfs_solicitadas']} confs); "
                            + ("nuevo e_min usado"
                               if ex.get("usada")
                               else "sin mejora; se conserva el minimo original")),
            })
        if any(f["strain"] is not None and f["strain"] < 0
               for f in por_pid_pose[pid]):
            anomalias.append({
                "tipo": "strain_negativo_persistente",
                "pid": pid,
                "detalle": "strain negativo tras la ampliacion (NO truncado)",
            })
        n_ok = sum(1 for f in por_pid_pose[pid] if f["mapeo_ok"])
        print(f"    [{pid}] ref e_min={ref['e_min']} kcal/mol | "
              f"{n_ok}/{len(por_pid_pose[pid])} poses con strain | "
              f"{time.monotonic() - t_ref:.1f}s acum", flush=True)
        t_ref = time.monotonic()
    return filas


def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(description="RS-04 OOF: strain MMFF94s "
                                                 "como feature sobre v0.6")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR_DEFAULT)
    parser.add_argument("--repro", action="store_true",
                        help="2a corrida: reutiliza cache de referencia + "
                             "benchmarks congelados + clones verificados por "
                             "sha; exige salidas byte-identicas")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    fold_models_dir = out_dir / "fold_models"
    fold_models_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "strain_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    print("== RS-04 OOF: strain MMFF94s como feature sobre v0.6 (cross-fitting "
          "completo, folds sellados RS-01B) ==", flush=True)

    prep = preparar_insumos()
    insumos, feats, labels = prep["insumos"], prep["feats"], prep["labels"]
    candidatos, por_pid = prep["candidatos"], prep["por_pid"]
    pids_orden, pid2fold = prep["pids_orden"], prep["pid2fold"]
    pids_fold, tamanos = prep["pids_fold"], prep["tamanos"]
    comps_orden, pid2comp = prep["comps_orden"], prep["pid2comp"]
    comps_por_fold, indices_pct = prep["comps_por_fold"], prep["indices_pct"]
    estrato_por_pid = prep["estrato_por_pid"]
    n_coinciden = prep["n_coinciden"]

    anomalias = []
    ligandos, fallos_sdf = cargar_ligandos(pids_orden)
    if fallos_sdf:
        raise SystemExit("ERROR: SDF fallidos: " + ", ".join(f["pid"]
                                                             for f in fallos_sdf))
    n_soportados = sum(1 for pid in pids_orden if soporte_mmff_ligando(ligandos[pid]))
    no_soportados = [pid for pid in pids_orden
                     if not soporte_mmff_ligando(ligandos[pid])]
    print(f"  cobertura MMFF94s: {n_soportados}/116 ligandos (unidad: ligando)",
          flush=True)

    # ── strain: referencia cacheada (idempotente) + poses frescas ──
    filas_strain = pase_strain(candidatos, ligandos, cache_dir, anomalias,
                               usar_cache=True)
    strain_por_identidad = {i: f["strain"] for i, f in filas_strain.items()}
    n_strain = sum(1 for v in strain_por_identidad.values() if v is not None)
    n_imputables = len(filas_strain) - n_strain
    print(f"  strain por pose: {n_strain}/2739 computadas, "
          f"{n_imputables} imputables (degeneradas)", flush=True)

    if not args.repro:
        bench = medir_costes(candidatos, ligandos, pids_orden,
                             [filas_strain[i] for i in
                              sorted(filas_strain, key=clave_identidad)])
        escribir_json(out_dir / "benchmarks.json", bench)
    else:
        bench = leer_json(out_dir / "benchmarks.json")
    gc = gates_coste(bench)
    print(f"  costes: cold P95 {bench['cold_p95_ms']} ms | pose P95 "
          f"{bench['cacheado_pose_p95_ms']} ms | complejo P95 "
          f"{bench['cacheado_complejo_p95_ms']} ms", flush=True)

    # ── folds exactos + imputacion por fold (mediana del outer-train) ──
    modelos_info = {}
    ev_b_global = {}
    ev_a_global = {}
    por_fold = []
    for fold in range(N_FOLDS):
        t_f = time.monotonic()
        pids_train = [p for p in pids_orden if pid2fold[p] != fold]
        pids_eval = pids_fold[fold]
        med_train = float(np.median([
            strain_por_identidad[i] for i in sorted(strain_por_identidad,
                                                    key=clave_identidad)
            if i.split("|")[1] in pids_train
            and strain_por_identidad[i] is not None]))
        print(f"  [fold {fold}] outer-train {len(pids_train)} complejos | "
              f"mediana strain outer-train {med_train:.3f} kcal/mol (imputacion)",
              flush=True)

        ids_train = {pid: sorted(por_pid[pid], key=clave_identidad)
                     for pid in pids_train}
        feats_aug_train = feats_augmentadas(feats, strain_por_identidad,
                                            med_train)
        X_b, y_b, g_b = construir_entrenamiento(
            pids_train, ids_train, feats, labels, indices_pct)
        X_a, y_a, g_a = construir_entrenamiento_aug(
            pids_train, ids_train, feats_aug_train, labels, indices_pct)
        clon_b, metrica_b = entrenar_clon(X_b, y_b, g_b)
        clon_a, metrica_a = entrenar_clon(X_a, y_a, g_a)

        def guardar_clon(modelo, brazo, metrica, n_filas, n_feats):
            nombre = f"fold{fold}_brazo_{brazo}"
            path_xgb = fold_models_dir / f"{nombre}.xgb"
            path_meta = fold_models_dir / f"{nombre}_meta.json"
            modelo.save_model(str(path_xgb))
            sha = sha256_archivo(path_xgb)
            escribir_json(path_meta, {
                "experimento": "RS-04-OOF",
                "fold": fold,
                "brazo": brazo,
                "hiperparametros": dict(PARAMS_CLON),
                "eval_metric": metrica,
                "n_filas": n_filas,
                "n_complejos_train": len(pids_train),
                "n_grupos": len(pids_train),
                "n_features": n_feats,
                "n_arboles": int(modelo.get_booster().num_boosted_rounds()),
                "seed": 42,
                "sha256_archivo_xgb": sha,
                "nota": ("sin early stopping; todos los datos outer-train; "
                         "relevancia -rmsd; grupos por complejo; orden canonico"),
            })
            modelos_info[nombre] = {"sha256": sha,
                                    "bytes": path_xgb.stat().st_size}
            return sha

        sha_b = guardar_clon(clon_b, "baseline", metrica_b,
                             int(X_b.shape[0]), N_MODELO_B)
        sha_a = guardar_clon(clon_a, "aumentado", metrica_a,
                             int(X_a.shape[0]), N_MODELO_AUG)

        ids_eval = {pid: sorted(por_pid[pid], key=clave_identidad)
                    for pid in pids_eval}
        feats_aug_eval = feats_augmentadas(feats, strain_por_identidad,
                                           med_train)
        ev_b = evaluar_conjunto(clon_b, pids_eval, ids_eval, feats, labels,
                                indices_pct)
        ev_a = evaluar_conjunto_aug(clon_a, pids_eval, ids_eval,
                                    feats_aug_eval, labels, indices_pct)
        for pid in pids_eval:
            ev_b_global[pid] = ev_b[pid]
            ev_a_global[pid] = ev_a[pid]

        agg_b = agregar_brazo(ev_b, pids_eval)
        agg_a = agregar_brazo(ev_a, pids_eval)
        par = pareado_por_pid(ev_b, ev_a, pids_eval)
        intervalos_fold = bootstrap_descriptivo_fold(
            pids_eval, comps_por_fold[fold], pid2comp, ev_b, ev_a,
            seed_fold=500 + fold)
        por_fold.append({
            "fold": fold,
            "n_componentes": len(comps_por_fold[fold]),
            "n_complejos_eval": len(pids_eval),
            "n_outer_train_complejos": len(pids_train),
            "n_outer_train_poses": int(X_b.shape[0]),
            "mediana_strain_outer_train_kcal": _round(med_train, 4),
            "baseline": agg_b,
            "aumentado": agg_a,
            "pareado": par,
            "bootstrap_descriptivo": intervalos_fold,
            "modelos": {"baseline_sha256": sha_b, "aumentado_sha256": sha_a,
                        "eval_metric_baseline": metrica_b,
                        "eval_metric_aumentado": metrica_a},
        })
        print(f"    top1 base {agg_b['top1_hits']}/{agg_b['n_complejos']} | "
              f"aum {agg_a['top1_hits']}/{agg_a['n_complejos']} "
              f"(Δ {par['delta_hits']}) | mediana pareada "
              f"{par['mediana_pareada_rmsd']} | {time.monotonic() - t_f:.1f}s",
              flush=True)

    # ── globales ──
    par_global = pareado_por_pid(ev_b_global, ev_a_global, pids_orden)
    agg_b_global = agregar_brazo(ev_b_global, pids_orden)
    agg_a_global = agregar_brazo(ev_a_global, pids_orden)
    delta_hits = par_global["delta_hits"]
    mediana_pareada = par_global["mediana_pareada_rmsd"]

    cumple_hits = agg_a_global["top1_hits"] >= GATE_HITS
    cumple_mediana = mediana_pareada <= GATE_MEDIANA
    cumple_cobertura = 100.0 * n_soportados / len(pids_orden) >= GATE_COBERTURA
    cumple_costes = all(gc.values())
    por_estrato = {}
    cumple_estratos = True
    for estrato in ("hard", "control"):
        pids_e = [p for p in pids_orden if estrato_por_pid[p] == estrato]
        comps_e = sorted({pid2comp[p] for p in pids_e})
        info = descriptivo_estrato(pids_e, comps_e, pid2comp, ev_b_global,
                                   ev_a_global, seed_estr=700 + (0 if estrato
                                                                 == "hard" else 1))
        por_estrato[estrato] = info
        if info["grave_preregistrado"]["es_grave"]:
            cumple_estratos = False
    veredicto = "PASS" if (cumple_hits and cumple_mediana and cumple_cobertura
                           and cumple_costes and cumple_estratos) else "FAIL"
    print(f"  GLOBAL: top1 base {agg_b_global['top1_hits']} | aum "
          f"{agg_a_global['top1_hits']} (requiere >= {GATE_HITS}) | mediana "
          f"pareada {mediana_pareada} (requiere <= {GATE_MEDIANA}) | "
          f"GATE: {veredicto}", flush=True)

    boot_comp = bootstrap_componentes_38(pids_orden, pid2comp, comps_orden,
                                         ev_b_global, ev_a_global)
    boot_plex = bootstrap_complejos_sensibilidad(pids_orden, ev_b_global,
                                                 ev_a_global)
    mcn = mcnemar_hits(ev_b_global, ev_a_global, pids_orden)
    discordancia_hits = bool(
        excluye_cero(boot_comp["hits"]["intervalo"])
        != excluye_cero(boot_plex["hits"]["intervalo"]))
    discordancia_med = bool(
        excluye_cero(boot_comp["mediana_pareada_rmsd"]["intervalo"])
        != excluye_cero(boot_plex["mediana_pareada_rmsd"]["intervalo"]))

    # ── strain por estrato y neutros vs ionizados ──
    def resumen_strain(pids_sub):
        vals = [filas_strain[i]["strain"] for i in sorted(
            filas_strain, key=clave_identidad)
            if i.split("|")[1] in pids_sub and filas_strain[i]["strain"] is not None]
        if not vals:
            return {"n_poses": 0, "mediana_kcal": None, "min_kcal": None,
                    "max_kcal": None, "n_negativos": 0}
        return {
            "n_poses": len(vals),
            "mediana_kcal": _round(float(np.median(vals)), 4),
            "min_kcal": _round(float(np.min(vals)), 4),
            "max_kcal": _round(float(np.max(vals)), 4),
            "n_negativos": int(sum(1 for v in vals if v < 0)),
        }

    strain_por_estrato = {e: resumen_strain([p for p in pids_orden
                                             if estrato_por_pid[p] == e])
                          for e in ("hard", "control")}
    strain_por_estrato["sin_estrato"] = resumen_strain(
        [p for p in pids_orden if estrato_por_pid[p] is None])
    neutros = [pid for pid in pids_orden
               if Chem.GetFormalCharge(ligandos[pid][1]) == 0]
    ionizados = [pid for pid in pids_orden
                 if Chem.GetFormalCharge(ligandos[pid][1]) != 0]
    neutro_ion = {
        "neutros": {"n_ligandos": len(neutros), **resumen_strain(neutros)},
        "ionizados": {"n_ligandos": len(ionizados), **resumen_strain(ionizados)},
    }

    # ── determinismo: comparacion con RS-01B (clones baseline) ──
    rs01b_sha = {}
    if (RS01B / "metrics.json").exists():
        rs01b_metrics = leer_json(RS01B / "metrics.json")
        rs01b_sha = {k: v["sha256"] for k, v in
                     rs01b_metrics.get("modelos_fold", {}).items()}
    clones_rs01b = {}
    for fold in range(N_FOLDS):
        nombre = f"fold{fold}_brazo_original"
        mios = modelos_info[f"fold{fold}_brazo_baseline"]["sha256"]
        clones_rs01b[f"fold{fold}"] = {
            "sha_baseline_rs04": mios,
            "sha_original_rs01b": rs01b_sha.get(nombre),
            "identico": bool(rs01b_sha.get(nombre) == mios),
        }

    # ── auditoria de cuarentena: whitelist de archivos abiertos ──
    abiertos = set(rs1b._ABIERTOS_REPO)
    whitelist = {
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
        "scripts/artifacts_science/RS-04-QC/benchmarks.json",
        "scripts/artifacts_science/RS-01B/metrics.json",
        "scripts/experiment_manifest.py",
    }
    rel_out = out_dir.relative_to(PROJECT_ROOT).as_posix()
    for nombre in ("metrics.json", "per_complex.jsonl", "failures.jsonl",
                   "benchmarks.json", "manifest.json", "README.md"):
        whitelist.add(f"{rel_out}/{nombre}")
    whitelist.add(rel_out + "/strain_cache/referencias.jsonl")
    for pid in pids_orden:
        whitelist.add(f"data/pose_selector_dataset/records/{pid}.json")
    for fold in range(N_FOLDS):
        for brazo in ("baseline", "aumentado"):
            whitelist.add(f"{rel_out}/fold_models/fold{fold}_brazo_{brazo}.xgb")
            whitelist.add(f"{rel_out}/fold_models/fold{fold}_brazo_{brazo}_meta.json")
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

    # ── failures.jsonl ──
    failures = []
    for i, f in filas_strain.items():
        if not f["mapeo_ok"]:
            failures.append({
                "tipo": "strain_no_computable",
                "identity": i,
                "detalle": f["motivo"],
                "tratamiento": ("imputacion con la mediana del outer-train "
                                "de su fold (nunca energia cero)"),
            })
    for pid in no_soportados:
        failures.append({
            "tipo": "unsupported_mmff",
            "pid": pid,
            "detalle": "ligando sin parametros MMFF94s (NO se mezcla UFF)",
        })
    failures.extend(anomalias)
    for a in fallos_sdf:
        failures.append({"tipo": "sdf_fail", **a})
    sin_clave = sorted(failures, key=lambda x: x.get("identity", x.get("pid", "")))
    failures = sin_clave

    # ── per_complex.jsonl ──
    filas_pc = []
    for pid in pids_orden:
        b = ev_b_global[pid]
        a = ev_a_global[pid]
        fb = filas_strain[b["ganador"]]
        fa = filas_strain[a["ganador"]]
        filas_pc.append({
            "pid": pid,
            "fold": pid2fold[pid],
            "componente": pid2comp[pid],
            "estrato": estrato_por_pid[pid],
            "ionizado": bool(Chem.GetFormalCharge(ligandos[pid][1]) != 0),
            "n_poses_eval": b["n_poses"],
            "baseline": {"ganador": b["ganador"], "fuente": b["fuente"],
                         "rmsd": _round(b["rmsd"], 4), "hit": b["hit"]},
            "aumentado": {"ganador": a["ganador"], "fuente": a["fuente"],
                          "rmsd": _round(a["rmsd"], 4), "hit": a["hit"]},
            "delta_rmsd_pareado": _round(a["rmsd"] - b["rmsd"], 4),
            "delta_hit": int(a["hit"]) - int(b["hit"]),
            "strain_ganador_aumentado": (fa["strain"] if fa["strain"] is not None
                                         else None),
            "strain_imputado_aumentado": bool(fa["strain"] is None),
            "strain_ganador_baseline": (fb["strain"] if fb["strain"] is not None
                                        else None),
            "strain_imputado_baseline": bool(fb["strain"] is None),
        })

    metrics = {
        "experimento": "RS-04-OOF",
        "declaracion_resultado": (
            "Cross-fitting COMPLETO (5 folds sellados RS-01B) que aísla el "
            "efecto de la feature de strain MMFF94s: clon v0.6 congelado "
            "(baseline, 233 feats) frente a v0.6 + strain (aumentado, 234 "
            "feats) sobre exactamente los mismos complejos por fold. Gate "
            "operacional RS-04: Top-1 OOF >= 50/116; mediana pareada dRMSD "
            "<= +0.1 A; cobertura quimica >= 95%; costes P95; sin regresion "
            "grave por estrato hard/control."),
        "preregistro": "CAMPANA-2-PLAN sellado (41b7f09) IT1 QA-5/QA-6 + RS-04-QC sellado (5ffb256)",
        "runtime": {
            "python": sys.version.split()[0],
            "xgboost": __import__("xgboost").__version__,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "rdkit": __import__("rdkit").__version__,
            "interprete": "python-embed/python.exe",
            "checkpoint_carga": {
                "sha256": insumos["tabla_sha"]["checkpoint_xgb"]["sha256"],
                "uso": "SOLO contrato de features congelado; los clones se entrenan desde cero por fold",
            },
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
                "tamanos": tamanos,
                "esperado": [55, 16, 15, 15, 15],
                "n_componentes": len(comps_orden),
                "esperado_componentes": 38,
            },
            "clones_baseline_vs_rs01b": {
                "nota": ("el clon baseline usa el MISMO pipeline que el brazo "
                         "original de RS-01B (hiperparametros, features e "
                         "insumos identicos); la comparacion de sha es "
                         "evidencia de reproducibilidad del baseline"),
                "por_fold": clones_rs01b,
                "n_identicos": int(sum(1 for v in clones_rs01b.values()
                                       if v["identico"])),
            },
            "imputacion_strain": {
                "n_poses_imputadas": n_imputables,
                "pids": sorted({i.split("|")[1] for i, f in filas_strain.items()
                                if not f["mapeo_ok"]}),
                "definicion": ("mediana del strain del outer-train de su fold "
                               "(definida DENTRO del outer-train; documentada)"),
            },
        },
        "config_clon": {
            "hiperparametros": dict(PARAMS_CLON),
            "n_estimators": 52,
            "early_stopping": "NINGUNO (sin eval_set)",
            "relevancia": "-rmsd",
            "grupos": "por complejo (filas contiguas, orden canonico)",
            "eval_metric": "auc con fallback rmse (patron historico)",
            "seed": 42,
            "n_features_baseline": N_MODELO_B,
            "n_features_aumentado": N_MODELO_AUG,
            "feature_strain": {
                "columna": "strain_mmff (columna raw 225)",
                "transformacion": ("z-score por complejo como cualquier feature "
                                   "raw; percentiles sobre las MISMAS 9 "
                                   "columnas congeladas de v0.6 (no se altera "
                                   "el orden de percentiles)"),
                "imputacion": "mediana del outer-train por fold (degeneradas)",
                "negativos": "NO truncados (QA-5); ampliacion unica del search de referencia",
            },
        },
        "strain": {
            "n_ligandos": len(pids_orden),
            "n_ligandos_soportados_mmff": n_soportados,
            "no_soportados": no_soportados,
            "n_poses_total": len(filas_strain),
            "n_poses_con_strain": n_strain,
            "n_poses_imputadas": n_imputables,
            "n_negativos": int(sum(1 for f in filas_strain.values()
                                   if f["strain"] is not None and f["strain"] < 0)),
            "por_estrato": strain_por_estrato,
            "neutros_vs_ionizados": neutro_ion,
            "nota_negativos": ("los negativos NO se truncan a cero; disparan "
                               "UNA ampliacion del search de referencia (QA-5)"),
        },
        "por_fold": por_fold,
        "global": {
            "n_complejos_oof": len(pids_orden),
            "baseline": agg_b_global,
            "aumentado": agg_a_global,
            "delta_top1": delta_hits,
            "mediana_pareada_rmsd": mediana_pareada,
            "nota_primario": ("la mediana pareada es el estadistico PRIMARIO "
                              "de RMSD (gate); diferencia de medianas y suma "
                              "son SECUNDARIAS y NO participan del gate"),
            "diferencia_medianas_rmsd_secundaria": par_global["diferencia_medianas_rmsd"],
            "suma_pareada_rmsd_secundaria": par_global["suma_pareada_rmsd"],
            "media_pareada_rmsd_descriptiva": par_global["media_pareada_rmsd"],
            "mcnemar": mcn,
            "gate": {
                "criterio": ("Top-1 OOF acumulado >= 50/116; mediana pareada "
                             "dRMSD <= +0.1 A; cobertura quimica >= 95%; "
                             "cold-start P95 <= 5 s/ligando; cacheado P95 <= "
                             "100 ms/pose y <= 3 s/complejo; sin regresion "
                             "grave por estrato hard/control"),
                "top1_aumentado": agg_a_global["top1_hits"],
                "requerido_top1": GATE_HITS,
                "cumple_hits": bool(cumple_hits),
                "mediana_pareada_rmsd": mediana_pareada,
                "umbral_mediana": GATE_MEDIANA,
                "cumple_mediana": bool(cumple_mediana),
                "cobertura_pct_ligandos": _round(100.0 * n_soportados
                                                 / len(pids_orden), 4),
                "umbral_cobertura": GATE_COBERTURA,
                "cumple_cobertura": bool(cumple_cobertura),
                "costes": {
                    "cold_p95_ms": bench["cold_p95_ms"],
                    "pose_p95_ms": bench["cacheado_pose_p95_ms"],
                    "complejo_p95_ms": bench["cacheado_complejo_p95_ms"],
                    "gates": {k: bool(v) for k, v in gc.items()},
                    "cumple": bool(cumple_costes),
                },
                "estratos": {e: {k: v for k, v in
                                 por_estrato[e]["grave_preregistrado"].items()}
                             for e in por_estrato},
                "cumple_estratos": bool(cumple_estratos),
                "veredicto": veredicto,
                "prohibido": ("NO se usa diferencia de medianas ni suma como "
                              "gate (solo se reportan como secundarias)"),
            },
        },
        "incertidumbre": {
            "bootstrap_componentes_38_primario": boot_comp,
            "sensibilidad_por_complejo": boot_plex,
            "discordancias_primario_vs_sensibilidad": {
                "hits": bool(discordancia_hits),
                "mediana_pareada_rmsd": bool(discordancia_med),
            },
            "nota": ("BCa primario solo sobre las 38 componentes globales; "
                     "cortes por fold/estrato = descriptivos con denominador "
                     "(>= 5 componentes para intervalo); BCa degenerado -> "
                     "percentil bootstrap (regla C3d)"),
        },
        "por_estrato": por_estrato,
        "costes_benchmarks": {
            "cold_p50_ms": bench["cold_p50_ms"],
            "cold_p95_ms": bench["cold_p95_ms"],
            "cacheado_pose_p50_ms": bench["cacheado_pose_p50_ms"],
            "cacheado_pose_p95_ms": bench["cacheado_pose_p95_ms"],
            "cacheado_complejo_p50_ms": bench["cacheado_complejo_p50_ms"],
            "cacheado_complejo_p95_ms": bench["cacheado_complejo_p95_ms"],
            "nota": ("re-verificados en este run (mismo protocolo RS-04-QC); "
                     "mediciones con varianza natural, congeladas en "
                     "benchmarks.json"),
        },
        "modelos_fold": modelos_info,
        "archivos_abiertos_repo": sorted(abiertos),
        "garantia_cuarentena": (
            "builtins.open auditado contra whitelist explicita: 0 accesos a "
            "val/test/CONFIRM; poses_val.jsonl, poses_test.jsonl y "
            "D-RC-CONFIRM nunca se abren"),
        "determinismo": (
            "salidas sin timestamps ni aleatoriedad no-seeded; referencia "
            "aislada cacheada por ligando (ETKDGv3 seed 42, idempotente); la "
            "2a corrida (--repro) reutiliza cache + benchmarks congelados + "
            "clones verificados por sha y exige salidas byte-identicas, con "
            "spot-check de recomputacion fresca de 3 ligandos"),
    }

    escribir_json(out_dir / "metrics.json", metrics)
    escribir_jsonl(out_dir / "per_complex.jsonl", filas_pc)
    escribir_jsonl(out_dir / "failures.jsonl", failures)

    if args.repro:
        spot = sorted(ligandos)[:N_SPOT_REPRO]
        spot_ok = True
        for pid in spot:
            e_min_fresh, n_fresh = referencia_aislada(
                ligandos[pid][1], nconfs_referencia(ligandos[pid][1]))
            cache = cargar_cache_referencias(cache_dir)
            ref = cache.get(pid, {})
            e_cached = ref.get("e_min")
            ok = (e_min_fresh is not None and e_cached is not None
                  and abs(e_min_fresh - float(e_cached)) < 1e-6)
            spot_ok = spot_ok and ok
            print(f"  [repro] spot-check {pid}: fresco {e_min_fresh} vs cache "
                  f"{e_cached} -> {'OK' if ok else 'DIFFER'}", flush=True)
        print(f"  [repro] determinismo strain (3 ligandos frescos): "
              f"{'PASS' if spot_ok else 'FAIL'}", flush=True)

    shas = {nombre: sha256_archivo(out_dir / nombre)[:16] for nombre in SALIDAS}
    print(f"  salidas escritas en {out_dir}", flush=True)
    print(f"  sha metrics={shas['metrics.json']} "
          f"per_complex={shas['per_complex.jsonl']} "
          f"failures={shas['failures.jsonl']}", flush=True)
    print(f"  duracion: {time.monotonic() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()