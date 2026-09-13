# -*- coding: utf-8 -*-
"""
run_vina_exh4_val.py — Wrapper POR COMPOSICION del brazo Vina exh4 sobre val
(D-MF-HARD-EXH4-VAL, entregable 8 fase 2).

NO edita NINGUN asset sellado: scripts/run_vina_exh4.py es asset del sello
D-MF-HARD-EXH4 (commit a0524e3, GO) — este wrapper lo importa y
monkeypatchea (split/work/artifacts/experiment_id/guardia de val), patron
identico a run_molflex_curve_val.py. Se reusan sin modificacion: preparar,
_preparar_ligando_flexible, dock_flexible_archivo, _asegurar_provenance,
_validar_provenance_pid, _dock_worker, _procesar_resultado, dockear_lote
(resume + lotes con --wall-budget) y el gate corregido (parse_vina_output
via run_molflex_curve). Solo cambian: split train->val, identidad
val|pid|vina_exh4|flex_exh4.out|model_idx (file_stem identico), work dir
exh4_val y la consolidacion DESCRIPTIVA propia.

CONDICIONES DEL MAINTAINER (literales):
  1. Composicion: cero edicion de sellados (D-MF-HARD-EXH4/,
     D-MF-HARD-CURVE*, scripts sellados).
  2. SIN pilot sobre val: ninguna prueba previa sobre val; los 10 val se
     ejecutan UNA sola vez cada uno, en esta corrida. El determinismo
     parcial es SINTETICO (fixture en temp sobre un pid TRAIN, nunca val).
  3. Una sola ejecucion por pid, sin retries silenciosos; fallos -> ITT
     (failures.jsonl) sin reintentar.
  4. Resultados EXCLUSIVAMENTE descriptivos con Wilson CI95 (n=5 sin
     potencia; sin regla de decision, sin comparacion decisoria, sin
     bootstrap decisorio).
  5. Ningun resultado de val altera K=15 ni el claim train sellado
     (declarado en DESIGN.md val).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402
import run_molflex_curve as rmc  # noqa: E402
import run_vina_exh4 as rve  # noqa: E402

# ─────────────────── constantes capturadas ANTES del monkeypatch ──────────
EXPERIMENT_ID_VAL = "D-MF-HARD-EXH4-VAL"
EXPERIMENT_ID_TRAIN = "D-MF-HARD-EXH4"
TRAIN_WORK = rve.WORK
COHORT_PATH = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD" / "cohort.jsonl"

VAL_PIDS = {
    "1b32", "1bgq", "1cny", "1fki", "1hms", "1bm7", "1hmt", "1ejn", "1jlr",
    "1nvq",
}
TRAIN_PIDS = set()
for line in COHORT_PATH.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    rec = json.loads(line)
    if rec.get("split") == "train":
        TRAIN_PIDS.add(rec["pid"])

# ─────────────────── reasignacion de constantes de modulo ──────────────────

rve.EXPERIMENT_ID = EXPERIMENT_ID_VAL
rve.SPLIT = "val"
rve.WORK = PROJECT_ROOT / "data" / "dmfhard_curve_work" / "exh4_val"
rve.ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-EXH4-VAL"
rve.PROGRESS = rve.WORK / "progress.json"
rve.FAILURES_WORK = rve.WORK / "failures.jsonl"
rve.DOCK_TIMES = rve.WORK / "dock_times.jsonl"
rve.STOP = rve.WORK / "STOP.json"
# En modo val estos pids SON el objetivo; la guardia de val del modulo se
# neutraliza y la guardia PROPIA (contra train) vive en este wrapper.
rve.VAL_PIDS = set()


# ─────────────────── monkeypatch de funciones train-hardcodeadas ───────────

def _leer_cohort_val() -> list:
    """cohort.jsonl filtrado split=val (10: 5 hard + 5 controles), en el
    orden del archivo."""
    out = []
    for line in COHORT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("split") == "val":
            out.append(rec)
    return out


def _identidad_val(pid: str, model_idx: int) -> str:
    """Identidad canonica val: val|pid|vina_exh4|flex_exh4.out|model_idx
    (file_stem identico al train sellado; solo cambia el split)."""
    return f"val|{pid}|vina_exh4|flex_exh4.out|{model_idx}"


def _verificar_determinismo_sintetico(pid: str) -> int:
    """Determinismo parcial SINTETICO, SIN tocar val: regenera la
    preparacion completa de un pid TRAIN en un directorio temporal y compara
    sha256 contra el work dir train sellado de la fase 1."""
    if pid not in TRAIN_PIDS:
        print(f"[STOP] determinismo sintetico solo con pids train: {pid}",
              file=sys.stderr)
        return 1
    w = TRAIN_WORK / pid
    archivos = ["rec.pdbqt", "center.json", "lig.flex.pdbqt", "index_map.json"]
    if not all((w / a).exists() for a in archivos):
        print(f"{pid}: preparacion train incompleta en {w}")
        return 1
    with tempfile.TemporaryDirectory(prefix=f"exh4_det_{pid}_") as td:
        tw = Path(td) / pid
        tw.mkdir(parents=True)
        sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
        prot = mf.PDBBIND / pid / f"{pid}_protein.pdb"
        ok = True
        if not mf.rp.prepare_receptor_pdbqt(str(prot), str(tw / "rec.pdbqt")):
            print(f"{pid}: receptor_prep_failed en temp")
            ok = False
        center = mf.rp.find_binding_center(str(sdf))
        if center is None:
            print(f"{pid}: binding_center_failed en temp")
            ok = False
        (tw / "center.json").write_text(json.dumps(list(center)), encoding="utf-8")
        flex_str, mapa, reason = rve._preparar_ligando_flexible(pid, tw)
        if reason:
            print(f"{pid}: {reason} en temp")
            ok = False
        (tw / "lig.flex.pdbqt").write_text(flex_str, encoding="utf-8")
        (tw / "index_map.json").write_text(
            json.dumps([[s, m] for s, m in mapa.items()]), encoding="utf-8")
        for a in archivos:
            h_w = rve._sha256_archivo(w / a)
            h_t = rve._sha256_archivo(tw / a)
            igual = h_w == h_t
            print(f"  {a}: train_work={h_w[:12]} temp={h_t[:12]} "
                  f"{'IDENTICO' if igual else 'DISTINTO'}")
            ok = ok and igual
    print(f"{pid} (pid TRAIN, fixture en temp, cero val): determinismo "
          f"parcial {'OK' if ok else 'FALLA'}")
    return 0 if ok else 1


# ────────────────────── consolidacion val (descriptiva) ────────────────────

def _wilson_ci(k: int, n: int, z: float = 1.96) -> list:
    """Intervalo de confianza 95% de Wilson para una proporcion
    (descriptivo)."""
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centro - margen), 3),
            round(min(1.0, centro + margen), 3)]


def consolidar_val() -> int:
    """Consolidacion DESCRIPTIVA de val: cobertura n/5 por estrato con
    Wilson CI95, mediana min-RMSD, ITT, tiempos P50/P90. SIN regla de
    decision, SIN comparacion decisoria, SIN bootstrap decisorio."""
    cohort = _leer_cohort_val()
    ART = rve.ARTIFACTS
    ART.mkdir(parents=True, exist_ok=True)

    failures = []
    if rve.FAILURES_WORK.exists():
        for line in rve.FAILURES_WORK.read_text(encoding="utf-8").splitlines():
            try:
                failures.append(json.loads(line))
            except Exception:
                continue
    docks = []
    if rve.DOCK_TIMES.exists():
        for line in rve.DOCK_TIMES.read_text(encoding="utf-8").splitlines():
            try:
                docks.append(json.loads(line))
            except Exception:
                continue

    poses = []
    provenances = []
    per_complex = []
    modos_por_estrato = {"hard": [], "control": []}
    for rec in cohort:
        pid = rec["pid"]
        estrato = rec["stratum"]
        w = rve.WORK / pid
        prov = rmc._json_load(w / "provenance.json", default={})
        modelos = rve._parsear_modos_exh4(pid)
        if not modelos:
            per_complex.append({"pid": pid, "stratum": estrato,
                                "cohort_id": rec["cohort_id"],
                                "pair_id": rec["pair_id"],
                                "min_rmsd": None, "cubierto": False,
                                "n_poses": 0,
                                "motivo": "sin_dock_valido"})
            continue
        crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = mf.cargar_mapa_indices(w)
        n_emitidos = len(modelos)
        modos_por_estrato[estrato].append(n_emitidos)
        rmsds = []
        for m_idx, modelo in enumerate(modelos):
            por_mol = mf.coords_pose_a_por_mol(modelo["atoms"], serial_a_mol)
            rmsd = mf.rmsd_pose_pocket(crystal, por_mol) if por_mol else None
            poses.append({
                "identity": _identidad_val(pid, m_idx),
                "split": "val",
                "pid": pid,
                "source": "vina_exh4",
                "file_stem": "flex_exh4.out",
                "model_idx": m_idx,
                "vina_score": modelo["score"],
                "rmsd_pose_pocket": round(rmsd, 3) if rmsd is not None else None,
                "seed_conformer": prov.get("seed_conformer"),
                "seed_docking": prov.get("seed_docking"),
                "exhaustiveness": prov.get("exhaustiveness"),
                "num_modes": prov.get("num_modes"),
                "num_modes_requested": 9,
                "n_models_emitted": n_emitidos,
                "box": prov.get("box"),
                "provenance_key": prov.get("key"),
            })
            if rmsd is not None:
                rmsds.append(rmsd)
        if isinstance(prov, dict):
            provenances.append(prov)
        min_rmsd = min(rmsds) if rmsds else None
        per_complex.append({
            "pid": pid, "stratum": estrato,
            "cohort_id": rec["cohort_id"], "pair_id": rec["pair_id"],
            "min_rmsd": round(min_rmsd, 3) if min_rmsd is not None else None,
            "cubierto": min_rmsd <= rve.UMBRAL_COBERTURA if min_rmsd is not None else False,
            "n_poses": n_emitidos,
        })

    with open(ART / "exh4_poses_val.jsonl", "w", encoding="utf-8") as fh:
        for p in poses:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(ART / "exh4_provenance.jsonl", "w", encoding="utf-8") as fh:
        for r in provenances:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(ART / "failures.jsonl", "w", encoding="utf-8") as fh:
        for f in failures:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(ART / "deviations.jsonl", "w", encoding="utf-8") as fh:
        pass  # esperado vacio: el gate corregido rigio desde el inicio
    with open(ART / "per_complex.jsonl", "w", encoding="utf-8") as fh:
        for r in per_complex:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Candidatos materializados (bloques PDBQT byte-fieles por pose emitida).
    registros = []
    for rec in cohort:
        pid = rec["pid"]
        modelos = rve._parsear_modos_exh4(pid)
        if not modelos:
            continue
        prov = rmc._json_load(rve.WORK / pid / "provenance.json", default={})
        for m_idx, modelo in enumerate(modelos):
            registros.append({
                "identity": _identidad_val(pid, m_idx),
                "pid": pid,
                "source": "vina_exh4",
                "file_stem": "flex_exh4.out",
                "model_idx": m_idx,
                "vina_score": modelo["score"],
                "provenance_key": prov.get("key") if isinstance(prov, dict) else None,
                "pdbqt": f"MODEL {m_idx + 1}\n{modelo['raw']}ENDMDL\n",
            })
    registros.sort(key=lambda r: r["identity"])
    ids = [r["identity"] for r in registros]
    if len(set(ids)) != len(ids):
        print(f"[ERROR] identidades duplicadas: {len(ids) - len(set(ids))}",
              file=sys.stderr)
        return 1
    if any(not r["pdbqt"].strip() or not math.isfinite(r["vina_score"])
           for r in registros):
        print("[ERROR] bloques vacios o scores no finitos", file=sys.stderr)
        return 1
    with open(ART / "exh4_candidates_val.jsonl", "w", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    data = (ART / "exh4_candidates_val.jsonl").read_bytes()
    print(f"exh4_candidates_val.jsonl: {len(registros)} lineas, "
          f"{len(data) / 1024 / 1024:.2f} MB, "
          f"sha256={hashlib.sha256(data).hexdigest()}")

    # Metricas descriptivas por estrato.
    por_estrato = {}
    pc = {r["pid"]: r for r in per_complex}
    for estrato in ("hard", "control"):
        pids_estrato = [r["pid"] for r in cohort if r["stratum"] == estrato]
        rmsds = [pc[pid]["min_rmsd"] for pid in pids_estrato
                 if pc.get(pid, {}).get("min_rmsd") is not None]
        cubiertos = sum(1 for pid in pids_estrato if pc.get(pid, {}).get("cubierto"))
        n = len(pids_estrato)
        por_estrato[estrato] = {
            "n_complejos": n,
            "n_con_poses": len(rmsds),
            "cobertura": round(cubiertos / n, 4) if n else None,
            "n_cubiertos": cubiertos,
            "wilson_ci95_cobertura": _wilson_ci(cubiertos, n),
            "mediana_min_rmsd": round(rmc._pct(rmsds, 0.5), 3) if rmsds else None,
            "n_poses": sum(pc.get(pid, {}).get("n_poses", 0) for pid in pids_estrato),
        }
    itt = {}
    cohort_estrato = {r["pid"]: r["stratum"] for r in cohort}
    for f in failures:
        e = cohort_estrato.get(f["pid"], "desconocido")
        itt.setdefault(e, {"n": 0, "motivos": {}})
        itt[e]["n"] += 1
        itt[e]["motivos"][f["reason"]] = itt[e]["motivos"].get(f["reason"], 0) + 1

    # Guardias post-consolidacion (modo val): cero train, 10 val, 1 corrida/pid.
    pids_train_en_artefactos = sum(1 for p in poses if p["pid"] in TRAIN_PIDS)
    pids_train_en_work = sum(1 for pid in TRAIN_PIDS if (rve.WORK / pid).exists())
    n_val_unicos = len({r["pid"] for r in per_complex})
    una_corrida_por_pid = len({r["pid"] for r in provenances}) == len(provenances)
    guardia = {
        "pids_train_en_artefactos": pids_train_en_artefactos,
        "pids_train_en_work": pids_train_en_work,
        "guardia_train_verificada": pids_train_en_artefactos == 0
        and pids_train_en_work == 0,
        "n_val_unicos": n_val_unicos,
        "una_corrida_por_pid": una_corrida_por_pid,
    }
    if not guardia["guardia_train_verificada"]:
        print("[ERROR] guardia de train violada", file=sys.stderr)
        return 1

    metricas = {
        "experiment_id": EXPERIMENT_ID_VAL,
        "split": "val",
        "n_complejos": len(cohort),
        "n_poses": len(poses),
        "n_fallos_itt": len(failures),
        "tipo": "descriptivo_n5_sin_potencia",
        "primera_y_unica_ejecucion_exh4_sobre_val": True,
        "no_ciega_no_confirmatoria": "la cohorte val YA fue examinada con "
                                     "MolFlex K15 (sellada D-MF-HARD-CURVE-VAL)",
        "k15_inmutable": True,
        "claim_train_inmutable": "ningun resultado de val altera K=15 ni el "
                                 "claim train sellado (D-MF-HARD-EXH4 GO)",
        "por_estrato": por_estrato,
        "tiempos": {
            "hard": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "hard"]),
            "control": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "control"]),
            "total": rmc._calc_tiempos(docks),
        },
        "fallos_itt_por_estrato": itt,
        "gate": {
            "enmienda": "auditada_2026-08-16 (heredada de D-MF-HARD-CURVE §8)",
            "validez": "rc=0 + archivo no vacio + 1<=n_models_emitted<=9 + "
                       "scores FINITOS de REMARK VINA RESULT + geometria parseable",
            "scores": "exclusivamente_REMARK_VINA_RESULT_del_archivo",
            "num_modes_requested": 9,
            "n_desviaciones": 0,
            "modos_emitidos": {
                e: {"n_corridas": len(v),
                    "mediana": round(rmc._pct(v, 0.5), 1) if v else None,
                    "min": min(v) if v else None,
                    "max": max(v) if v else None,
                    "distribucion": {str(k): v.count(k) for k in sorted(set(v))}}
                for e, v in modos_por_estrato.items()
            },
        },
        "contexto_train_referencia": {
            "mismo_brazo_exh4": {"hard": "11/17 (64.7%), mediana 1.424 A",
                                 "control": "13/17 (76.5%), mediana 1.049 A"},
            "nota": "sin inferencia fuerte contra val (n=5 sin potencia); "
                    "solo descripcion lado a lado",
        },
        "verificaciones": guardia,
    }
    rmc._atomic_write(ART / "metrics.json", metricas)
    _escribir_design_val(metricas, len(poses), len(failures), len(registros))
    print(f"Consolidacion val: {len(poses)} poses, {len(provenances)} corridas, "
          f"{len(failures)} fallos ITT, {len(registros)} candidatos")
    print(json.dumps({"por_estrato": por_estrato, "verificaciones": guardia},
                     indent=2, ensure_ascii=False))
    return 0


def _escribir_design_val(metricas: dict, n_poses: int, n_fallos: int,
                         n_candidatos: int) -> None:
    por_estrato = metricas["por_estrato"]
    h = por_estrato["hard"]
    c = por_estrato["control"]
    texto = f"""# D-MF-HARD-EXH4-VAL — Brazo Vina flexible exh4, fase 2 (10 val) — DESIGN

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** D-MF-HARD-EXH4 (sello train GO, commit a0524e3) + FORECAST.md
(correcciones procedimentales commit 47a24a8) + docs/49 §15 entregable 8
(MF-06) + D-MF-HARD/DESIGN.md (cohorte sellada).
**Estado: EJECUTADO (descriptivo). NO sellado, NO finish.**

## 1. Alcance y naturaleza de la fase

- **10 complejos val** (5 hard + 5 controles) del cohort sellado D-MF-HARD:
  1b32, 1cny, 1hms, 1hmt, 1jlr (hard) y 1bgq, 1fki, 1bm7, 1ejn, 1nvq
  (control).
- **PRIMERA y ÚNICA ejecución de Vina exh4 sobre val**: un dock flexible
  por complejo, UNA sola vez cada uno, sin retries silenciosos (fallos ->
  ITT en failures.jsonl, sin reintentar).
- **DESCRIPTIVA, NO ciega y NO confirmatoria:** la cohorte val YA fue
  examinada con MolFlex K15 (sellada D-MF-HARD-CURVE-VAL); val NO es ciega
  para el entregable 8 (FORECAST §6, congelado 5). n=5 por estrato: sin
  potencia; solo Wilson CI95 descriptivo.
- **No cambia la interpretación train:** los números de val se reportan
  como descripción; K=15 y el claim train sellado (D-MF-HARD-EXH4 GO,
  DESIGN.md §7 "Interpretación para el sello") permanecen INALTERADOS pase
  lo que pase.

## 2. Configuración (idéntica a la fase 1 sellada)

| Parámetro | Valor |
|---|---|
| engine | Vina 1.2.7, ligando FLEXIBLE meeko (conformación cristalográfica) |
| receptor | PDBQT rígido pdb_original (openbabel, misma cadena histórica) |
| exhaustiveness | 4 |
| seed | `--seed 42` explícito (seed_docking=42; seed_conformer="crystal") |
| box | 25 Å centrado en ligando cristalográfico |
| num_modes | 9 solicitados |
| cpu / workers | 1 / 6 físicos |
| timeout | 300 s por dock |
| relax | sin relax |
| gate | enmendado (heredado D-MF-HARD-CURVE §8): rc=0, archivo no vacío, 1<=n_models_emitted<=9, scores FINITOS solo de REMARK VINA RESULT, identidades solo para modelos emitidos |
| work dir | `data/dmfhard_curve_work/exh4_val/` (gitignored, separado del train) |
| identidad | `val|pid|vina_exh4|flex_exh4.out|model_idx` |
| experiment_id | D-MF-HARD-EXH4-VAL |

## 3. Implementación (por composición — congelado 7)

- Runner: `scripts/run_vina_exh4_val.py` — wrapper que importa
  `scripts/run_vina_exh4.py` SIN editarlo (asset sellado del commit
  a0524e3) y monkeypatchea split/work/artifacts/experiment_id/guardia de
  val (patrón `run_molflex_curve_val.py`). Se reusan sin modificación:
  preparar, `_preparar_ligando_flexible`, `dock_flexible_archivo`,
  `_asegurar_provenance`, `_validar_provenance_pid`, `_dock_worker`,
  `_procesar_resultado`, `dockear_lote` (resume + lotes con --wall-budget)
  y el gate corregido (`parse_vina_output` de `run_molflex_curve.py`).
- Sin pilot sobre val: el determinismo parcial es SINTÉTICO (fixture en
  temp sobre un pid TRAIN, nunca val).
- Consolidación val PROPIA: sin regla de decisión, sin comparación
  decisoria, sin bootstrap decisorio. Solo descripción.

## 4. Resultados descriptivos (val, 10 complejos)

- Poses emitidas: {n_poses}; fallos ITT: {n_fallos}; candidatos
  materializados: {n_candidatos}.
- Hard (n=5): cobertura {h['n_cubiertos']}/5, Wilson CI95
  {h['wilson_ci95_cobertura']}, mediana min-RMSD {h['mediana_min_rmsd']} A.
- Control (n=5): cobertura {c['n_cubiertos']}/5, Wilson CI95
  {c['wilson_ci95_cobertura']}, mediana min-RMSD {c['mediana_min_rmsd']} A.

## 5. Descriptivo lado a lado vs train (MISMO brazo exh4)

| Estrato | Train (17+17, sello GO) | Val (5+5, descriptivo) |
|---|---|---|
| hard | 11/17 (64.7%), mediana 1.424 A | {h['n_cubiertos']}/5, mediana {h['mediana_min_rmsd']} A |
| control | 13/17 (76.5%), mediana 1.049 A | {c['n_cubiertos']}/5, mediana {c['mediana_min_rmsd']} A |

SIN inferencia fuerte: n=5 por estrato no admite pruebas pareadas con
potencia; esta tabla es descripción, no decisión.

## 6. Declaraciones

- 0 docks de val previos: los 10 val se ejecutaron UNA sola vez cada uno
  en esta corrida (work dir `exh4_val/` inexistente antes de arrancar).
- 0 pids train tocados (guardia verificada en metrics.json).
- K=15 INMUTABLE (sello f31bfeb); exh2 permanece CERRADO.
- Cero v0.6, cero MF-11, cero producción, cero relax, cero test histórico.
- **Ningún resultado de val altera K=15 ni el claim train sellado
  (D-MF-HARD-EXH4 GO).**

## 7. Archivos

| Archivo | Contenido |
|---|---|
| exh4_poses_val.jsonl | una linea por pose EMITIDA (identidad val|pid|vina_exh4|flex_exh4.out|model_idx) |
| exh4_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| exh4_candidates_val.jsonl | bloques PDBQT byte-fieles materializados por pose emitida |
| metrics.json | descriptivas por estrato (cobertura n/5, Wilson CI95, mediana, ITT, tiempos P50/P90) |
| per_complex.jsonl | una linea por complejo val |
| failures.jsonl | fallos ITT (sin reintentos) |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
| manifest.json / README.md | registro FND-01 (init/validate; sin seal ni finish) |
"""
    rmc._atomic_write(rve.ARTIFACTS / "DESIGN.md", texto)


rve.leer_cohort_train = _leer_cohort_val
rve.identidad_pose = _identidad_val
rve.consolidar = consolidar_val
rve.verificar_determinismo = _verificar_determinismo_sintetico


# ───────────────────────── CLI ─────────────────────────────────────────────

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    argv = sys.argv[1:]
    pids_argv = []
    if "--pids" in argv:
        i = argv.index("--pids")
        j = i + 1
        while j < len(argv) and not argv[j].startswith("--"):
            pids_argv.append(argv[j])
            j += 1
    fuera = [p for p in pids_argv if p in TRAIN_PIDS]
    if fuera:
        print(f"[STOP] pids de train rechazados en modo val: {fuera}",
              file=sys.stderr)
        return 2
    return rve.main()


if __name__ == "__main__":
    sys.exit(main())
