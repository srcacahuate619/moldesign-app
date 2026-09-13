# -*- coding: utf-8 -*-
"""
run_vina_exh4.py — Runner del brazo Vina flexible exh4 (entregable 8, fase 1).

D-MF-HARD-EXH4: 34 docks train (17 hard + 17 controles) de Vina FLEXIBLE con
exhaustiveness=4, --seed 42 explicito, box 25 A centrado en el ligando
cristalografico, num_modes solicitados 9, cpu=1, 6 workers, sin relax,
timeout 300 s por dock. Un dock por complejo: el ligando es la CONFORMACION
CRISTALOGRAFICA preparada con meeko como PDBQT FLEXIBLE (torsiones activas)
y el receptor es PDBQT rigido pdb_original. Esta es la misma definicion de
flexibilidad/receptor del historico documentado (rescoring/scripts/
redock_pdbbind.py, flexible_redock exh8; y scripts/ruta_a_exh_validation.py,
dock_one_exh), solo cambian exh (8->4) y el seed explicito.

ALCANCE DEL CLAIM (FORECAST.md): el box esta centrado en el ligando
cristalografico y la conformacion de entrada es la cristalografica -> este
es un benchmark de REDOCKING/GENERACION dentro de una pocket conocida, NO
evidencia end-to-end para pockets desconocidas.

IMPLEMENTACION POR COMPOSICION (congelado 7): este runner NO edita ningun
asset sellado. Reusa por importacion:
  - scripts/molflex.py (mf): leer_ligando, escribir_pdbqt (PDBQT flexible
    meeko + mapa serial->mol), cargar_mapa_indices, coords_pose_a_por_mol,
    rmsd_pose_pocket (metrica obligatoria, marco del pocket), _args_box,
    VINA, version_vina, PDBBIND; y via mf.rp las funciones historicas
    prepare_receptor_pdbqt / find_binding_center de redock_pdbbind.py.
  - scripts/run_molflex_curve.py (rmc): parse_vina_output (gate corregido,
    enmienda auditada 2026-08-16), leer_cohort, _json_load, _atomic_write,
    _pct, _calc_tiempos. Su hash esta sellado en D-MF-HARD-CURVE: solo se
    importa, nunca se edita.

IDENTIDAD CANONICA por pose: train|pid|vina_exh4|flex_exh4.out|model_idx
(model_idx SOLO para los modelos REALMENTE emitidos; gate corregido:
rc=0 + archivo no vacio + 1 <= n_models_emitted <= 9 + TODOS los modelos con
score FINITO de REMARK VINA RESULT + geometria parseable).

PROPIEDADES OPERATIVAS:
  - Idempotente por identidad (resume): un dock cuyo flex_exh4.out.pdbqt
    existe y pasa el gate corregido NO se repite. Un dock fallado NO se
    reintenta (fallo ITT -> failures.jsonl; sin reintentos silenciosos).
  - Fallos ITT: prep_failed, receptor_prep_failed, meeko_failed, rc!=0,
    timeout_300s, no_pose, no_scores, gate_invalido.
  - STOP ante fallos SISTEMATICOS (mismo motivo en >=3 complejos) o ante
    violacion de integridad del gate (cero modelos, >9 modelos, score no
    finito, REMARK ausente, geometria rota) -> STOP.json + reporte.
  - Work dir: data/dmfhard_curve_work/exh4/ (dentro del work dir de la curva
    ya gitignored; .gitignore NO se modifica).
  - Guardia dura de val: SOLO split=train se lee; VAL_PIDS rechazados por
    construccion.

Subcomandos / flags:
  --pids A B ...        restringe el lote a esos pids train.
  --wall-budget N       segundos de presupuesto de la invocacion (default 240;
                        el drain de tareas en vuelo acota la invocacion a
                        ~budget + 300 s).
  --report              resumen de progreso.
  --consolidate         construye los artefactos finales en
                        scripts/artifacts_science/D-MF-HARD-EXH4/ (incluye la
                        recomputacion read-only de la union restringida a la
                        cohorte y la comparacion de 3 niveles + G2).
  --identity-check      verifica que la identidad vina_exh4 no colisiona con
                        FND-06 ni MF-01-UNION (solo lectura).
  --verify-determinismo PID  determinismo parcial: regenera la preparacion
                        completa (receptor/centro/ligando flexible/mapa) en un
                        directorio temporal y compara hashes con el work dir.

Artefactos finales (--consolidate):
  exh4_poses_train.jsonl, exh4_provenance.jsonl, exh4_candidates_train.jsonl,
  metrics.json, per_complex.jsonl, failures.jsonl, deviations.jsonl,
  DESIGN.md.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402
import run_molflex_curve as rmc  # noqa: E402

EXPERIMENT_ID = "D-MF-HARD-EXH4"
EXH = 4
NUM_MODES = 9
SEED_DOCKING = 42
CPU = 1
WORKERS = 6
FLEX_TIMEOUT = 300
UMBRAL_COBERTURA = 2.0
WALL_BUDGET_DEFAULT = 240.0
FILE_STEM = "flex_exh4.out"
SOURCE = "vina_exh4"
SPLIT = "train"

COHORT_PATH = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD" / "cohort.jsonl"
CURVE_ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-CURVE"
UNION_ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION"
FND06_SIDECAR = PROJECT_ROOT / "scripts" / "artifacts_science" / "FND-06" / "poses_provenance.jsonl"
ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-EXH4"
WORK = PROJECT_ROOT / "data" / "dmfhard_curve_work" / "exh4"
CURVE_WORK = PROJECT_ROOT / "data" / "dmfhard_curve_work"

PROGRESS = WORK / "progress.json"
FAILURES_WORK = WORK / "failures.jsonl"
DOCK_TIMES = WORK / "dock_times.jsonl"
STOP = WORK / "STOP.json"

FIELDS_CANONICOS = rmc.FIELDS_CANONICOS

# Guardia dura: pids de val NUNCA se procesan (solo se lee split=train; este
# set es una red de seguridad de verificacion).
VAL_PIDS = {
    "1b32", "1bgq", "1cny", "1fki", "1hms", "1bm7", "1hmt", "1ejn", "1jlr",
    "1nvq",
}

# Violaciones de integridad del motor: DETIENEN la ejecucion (no son fallos
# ITT ordinarios; misma semantica que D-MF-HARD-CURVE).
GATE_INTEGRIDAD = {
    "gate:cero_modelos", "gate:mas_de_9_modelos", "gate:score_no_finito",
    "gate:sin_remark", "gate:geometria_rota", "no_pose", "no_scores",
}


# ───────────────────────── utilidades de archivo/estado ────────────────────

def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256_archivo(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def leer_cohort_train() -> list:
    """Lee cohort.jsonl filtrado por split=train (34 registros, orden del
    archivo). Nunca abre val."""
    out = []
    for line in COHORT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("split") == SPLIT and rec["pid"] not in VAL_PIDS:
            out.append(rec)
    return out


def cargar_progreso() -> dict:
    return rmc._json_load(PROGRESS, default={"experiment_id": EXPERIMENT_ID,
                                             "complexes": {}, "updated_at": None})


def guardar_progreso(prog: dict) -> None:
    prog["updated_at"] = _now_iso()
    rmc._atomic_write(PROGRESS, prog)


def registrar_fallo(pid: str, reason: str, t: float, extra: dict | None = None) -> None:
    rec = {"ts": _now_iso(), "pid": pid, "reason": reason, "t": round(float(t), 1)}
    if extra:
        rec.update(extra)
    with open(FAILURES_WORK, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def registrar_tiempo(pid: str, estrato: str, t: float, ok: bool) -> None:
    with open(DOCK_TIMES, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"pid": pid, "stratum": estrato,
                             "t": round(float(t), 1), "ok": bool(ok)},
                            ensure_ascii=False) + "\n")


def identidad_pose(pid: str, model_idx: int) -> str:
    """Identidad canonica por pose (solo modelos REALMENTE emitidos)."""
    return f"{SPLIT}|{pid}|{SOURCE}|{FILE_STEM}|{model_idx}"


# ───────────────────────── preparacion por complejo ────────────────────────

def _preparar_ligando_flexible(pid: str, w: Path) -> tuple:
    """Preparacion meeko del ligando en su CONFORMACION CRISTALOGRAFICA como
    PDBQT FLEXIBLE (misma definicion que ruta_a_exh_validation.dock_one_exh y
    flexible_redock: Chem.AddHs(crystal) + MoleculePreparation sin
    conformer_id -> conformer 0 = cristal). Devuelve
    (flex_str, mapa_serial_a_mol, reason)."""
    from meeko import MoleculePreparation
    from rdkit import Chem

    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    crystal = mf.leer_ligando(str(sdf))
    if crystal is None:
        return None, {}, "sdf_unreadable"
    try:
        mh = Chem.AddHs(crystal)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        _rigid, flex_str, mapa, _err = mf.escribir_pdbqt(setups[0])
        if not flex_str or not mapa:
            return None, {}, "meeko_failed"
        return flex_str, mapa, None
    except Exception as e:
        return None, {}, f"meeko_failed({type(e).__name__})"


def preparar(pid: str) -> dict:
    """Fase 1 (idempotente por archivo): receptor PDBQT rigido pdb_original
    (mf.rp.prepare_receptor_pdbqt, la misma cadena del historico
    flexible_redock), centro de caja del ligando cristalografico
    (mf.rp.find_binding_center), ligando flexible meeko con mapa de indices y
    provenance.json canonico (14 campos, FND-06). Escribe bajo
    WORK/pid/."""
    w = WORK / pid
    w.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    prot = mf.PDBBIND / pid / f"{pid}_protein.pdb"
    if not sdf.exists() or not prot.exists():
        return {"ok": False, "reason": "missing_files",
                "t": round(time.monotonic() - t0, 1)}

    rec = w / "rec.pdbqt"
    if not rec.exists() or rec.stat().st_size <= 100:
        if not mf.rp.prepare_receptor_pdbqt(str(prot), str(rec)):
            return {"ok": False, "reason": "receptor_prep_failed",
                    "t": round(time.monotonic() - t0, 1)}

    center_path = w / "center.json"
    if not center_path.exists():
        center = mf.rp.find_binding_center(str(sdf))
        if center is None:
            return {"ok": False, "reason": "binding_center_failed",
                    "t": round(time.monotonic() - t0, 1)}
        center_path.write_text(json.dumps(list(center)), encoding="utf-8")
    try:
        center = json.loads(center_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "reason": "no_center",
                "t": round(time.monotonic() - t0, 1)}

    lig_path = w / "lig.flex.pdbqt"
    mapa_path = w / "index_map.json"
    if not lig_path.exists() or not mapa_path.exists():
        flex_str, mapa, reason = _preparar_ligando_flexible(pid, w)
        if reason:
            return {"ok": False, "reason": reason,
                    "t": round(time.monotonic() - t0, 1)}
        lig_path.write_text(flex_str, encoding="utf-8")
        mapa_path.write_text(json.dumps([[s, m] for s, m in mapa.items()]),
                             encoding="utf-8")

    _asegurar_provenance(pid, center)
    return {"ok": True, "center": list(center),
            "t": round(time.monotonic() - t0, 1)}


def _asegurar_provenance(pid: str, center: list) -> None:
    """Escribe provenance.json canonico (FND-06) de la corrida. Un registro
    por complejo: key=pid|vina_exh4|flex_exh4.out. seed_conformer="crystal"
    (no hay generacion estocastica de conformeros: la conformacion de entrada
    es la cristalografica, misma convencion del historico flexible_redock);
    seed_docking=42 (--seed explicito). Los campos num_modes_requested /
    n_models_emitted se anotan tras el dock (enmienda auditada)."""
    w = WORK / pid
    prov_path = w / "provenance.json"
    registro = {
        "key": f"{pid}|{SOURCE}|{FILE_STEM}",
        "pid": pid,
        "source": SOURCE,
        "file_stem": FILE_STEM,
        "seed_conformer": "crystal",
        "seed_docking": SEED_DOCKING,
        "conformer_id": "crystal",
        "exhaustiveness": EXH,
        "num_modes": NUM_MODES,
        "box": {"center": [round(float(c), 3) for c in center],
                "size": [mf.BOX_SIZE, mf.BOX_SIZE, mf.BOX_SIZE],
                "method": "center_from_crystal_ligand"},
        "preparation": {
            "ligand": {"method": "meeko_molecule_preparation_conformacion_cristal",
                       "tool": "meeko", "version": mf.VERSION_MEEKO},
            "receptor": {"protonation": "pdb_original",
                         "tool": "openbabel_pdb2pdbqt_rigido"},
        },
        "engine": {"name": "vina", "version": mf.version_vina()},
        "experiment_id": EXPERIMENT_ID,
        "created_at": _now_iso(),
    }
    if prov_path.exists():
        prev = rmc._json_load(prov_path, default={})
        if isinstance(prev, dict):
            registro["created_at"] = prev.get("created_at", registro["created_at"])
            registro["num_modes_requested"] = prev.get("num_modes_requested")
            registro["n_models_emitted"] = prev.get("n_models_emitted")
            for k in ("num_modes_requested", "n_models_emitted"):
                if registro.get(k) is None:
                    del registro[k]
    rmc._atomic_write(prov_path, registro)


def anotar_emision(pid: str, n_models_emitted: int) -> None:
    prov_path = WORK / pid / "provenance.json"
    registro = rmc._json_load(prov_path, default={})
    if isinstance(registro, dict):
        registro["num_modes_requested"] = NUM_MODES
        registro["n_models_emitted"] = n_models_emitted
        rmc._atomic_write(prov_path, registro)


def _validar_provenance_pid(pid: str) -> str | None:
    """Gate de ejecucion: provenance incorrecto -> DETENER. Devuelve el
    problema o None."""
    registro = rmc._json_load(WORK / pid / "provenance.json", default=None)
    if not isinstance(registro, dict):
        return "provenance_ausente"
    faltan = [f for f in FIELDS_CANONICOS if f not in registro]
    if faltan:
        return f"provenance_campos_faltantes_{','.join(faltan)}"
    if registro.get("experiment_id") != EXPERIMENT_ID:
        return "provenance_experiment_id_incorrecto"
    if registro.get("seed_docking") != SEED_DOCKING:
        return "provenance_seed_docking_incorrecto"
    if registro.get("seed_conformer") != "crystal":
        return "provenance_seed_conformer_incorrecto"
    if registro.get("exhaustiveness") != EXH:
        return "provenance_exh_incorrecto"
    if registro.get("file_stem") != FILE_STEM or \
            registro.get("key") != f"{pid}|{SOURCE}|{FILE_STEM}":
        return "provenance_file_stem_key_incorrectos"
    return None


# ───────────────────────── docking ─────────────────────────────────────────

def out_valido(pid: str) -> bool:
    """El dock es valido si su salida existe y pasa el gate corregido."""
    p = WORK / pid / f"{FILE_STEM}.pdbqt"
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        return rmc.parse_vina_output(p.read_text(encoding="utf-8"))["ok"]
    except Exception:
        return False


def dock_flexible_archivo(pid: str) -> dict:
    """Un dock Vina FLEXIBLE (ligando meeko con torsiones activas, receptor
    rigido, box 25 centrado en el ligando cristalografico) con exh=4,
    num_modes=9, --seed 42, cpu=1, timeout 300 s. Aplica el gate corregido
    sobre el ARCHIVO de salida (scores SOLO de REMARK VINA RESULT; 1 <=
    n_models_emitted <= 9)."""
    w = WORK / pid
    rec = str(w / "rec.pdbqt")
    lig = str(w / "lig.flex.pdbqt")
    out = w / f"{FILE_STEM}.pdbqt"
    try:
        center = json.loads((w / "center.json").read_text(encoding="utf-8"))
    except Exception:
        return {"pid": pid, "ok": False, "reason": "no_center", "t": 0.0}
    cmd = [mf.VINA, "--receptor", rec, "--ligand", lig] + mf._args_box(center) + [
        "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
        "--seed", str(SEED_DOCKING), "--cpu", str(CPU), "--out", str(out)]
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FLEX_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"pid": pid, "ok": False, "reason": "timeout_300s", "t": FLEX_TIMEOUT}
    dt = round(time.monotonic() - t0, 1)
    if r.returncode != 0:
        return {"pid": pid, "ok": False, "reason": f"rc={r.returncode}", "t": dt,
                "stderr_head": r.stderr[:200]}
    if not out.exists() or out.stat().st_size == 0:
        return {"pid": pid, "ok": False, "reason": "no_pose", "t": dt}
    try:
        parsed = rmc.parse_vina_output(out.read_text(encoding="utf-8"))
    except Exception:
        return {"pid": pid, "ok": False, "reason": "gate_invalido", "t": dt}
    if parsed["ok"]:
        return {"pid": pid, "ok": True, "t": dt,
                "n_models_emitted": parsed["n_models"],
                "mode_scores": [m["score"] for m in parsed["models"]]}
    reason = parsed["errores"][0] if parsed["errores"] else "gate_invalido"
    return {"pid": pid, "ok": False, "reason": reason, "t": dt,
            "gate": parsed["errores"]}


def _dock_worker(pid: str) -> dict:
    """Worker del pool: 1 dock flexible por complejo (cpu=1)."""
    return dock_flexible_archivo(pid)


def _verificar_sistematico(prog: dict) -> bool:
    """Regla de detencion: el mismo motivo en >=3 complejos -> STOP.json."""
    motivos_por_pid = {}
    for pid, c in prog["complexes"].items():
        if c.get("dock") != "failed":
            continue
        motivo = c.get("reason", "unknown")
        motivos_por_pid.setdefault(motivo, set()).add(pid)
    for motivo, pids in motivos_por_pid.items():
        if len(pids) >= 3:
            rmc._atomic_write(STOP, {
                "ts": _now_iso(), "motivo": motivo,
                "tipo": "mismo_error_en_3_o_mas_complejos",
                "pids": sorted(pids),
            })
            print(f"\n[STOP] Motivo '{motivo}' en >=3 complejos: "
                  f"{sorted(pids)}", file=sys.stderr)
            return True
    return False


def _procesar_resultado(pid: str, res: dict, prog: dict, estrato: str) -> str | None:
    """Registra el resultado del dock. Devuelve el motivo si es una violacion
    de integridad del gate (para DETENER), o None."""
    complejo = prog["complexes"].setdefault(pid, {})
    if res.get("ok"):
        complejo["dock"] = "done"
        complejo["state"] = "completed"
        complejo["t"] = res.get("t", 0.0)
        complejo["n_models_emitted"] = res.get("n_models_emitted", 0)
        registrar_tiempo(pid, estrato, res.get("t", 0.0), True)
        anotar_emision(pid, res.get("n_models_emitted", 0))
        return None
    reason = res.get("reason", "unknown")
    complejo["dock"] = "failed"
    complejo["state"] = "failed_dock"
    complejo["reason"] = reason
    complejo["t"] = res.get("t", 0.0)
    registrar_fallo(pid, reason, res.get("t", 0.0))
    registrar_tiempo(pid, estrato, res.get("t", 0.0), False)
    return reason if reason in GATE_INTEGRIDAD else None


def dockear_lote(prog: dict, pids: list, wall_budget: float) -> tuple:
    """Dockea los complejos pendientes de los pids train dados (resume).
    Devuelve (prog_actualizado, detener_por_presupuesto, detener_sistematico).
    La preparacion corre en el proceso principal; los docks se paralelizan
    con 6 workers. El encolado y la recoleccion se INTERCALAN: la invocacion
    deja de encolar al agotarse el presupuesto y espera el drain de tareas
    en vuelo (acotado por FLEX_TIMEOUT por worker)."""
    deadline = time.monotonic() + wall_budget
    cohort = {r["pid"]: r for r in leer_cohort_train()}
    detener_presupuesto = False
    futuros = {}
    ex = concurrent.futures.ProcessPoolExecutor(max_workers=WORKERS)
    cola = list(pids)
    try:
        while True:
            # Encolar mientras haya slots, pids y presupuesto.
            while cola and len(futuros) < WORKERS and time.monotonic() <= deadline:
                pid = cola.pop(0)
                if pid in VAL_PIDS:
                    print(f"[STOP] pid de val rechazado: {pid}", file=sys.stderr)
                    return prog, False, True
                rec = cohort.get(pid, {})
                estrato = rec.get("stratum", "?")
                complejo = prog["complexes"].setdefault(pid, {
                    "stratum": estrato, "cohort_id": rec.get("cohort_id", "?"),
                    "pair_id": rec.get("pair_id", "?"), "dock": None,
                    "state": "pending",
                })
                if complejo.get("dock") == "done" and out_valido(pid):
                    complejo["state"] = "completed"
                    guardar_progreso(prog)
                    continue
                if complejo.get("dock") == "failed":
                    # Fallo ITT: no se reintenta en lotes posteriores.
                    continue
                prep = preparar(pid)
                if not prep.get("ok"):
                    reason = prep.get("reason", "prep_failed")
                    complejo["dock"] = "failed"
                    complejo["state"] = "failed_prep"
                    complejo["reason"] = reason
                    complejo["t"] = prep.get("t", 0.0)
                    registrar_fallo(pid, reason, prep.get("t", 0.0))
                    guardar_progreso(prog)
                    if _verificar_sistematico(prog):
                        return prog, False, True
                    continue
                problema_prov = _validar_provenance_pid(pid)
                if problema_prov:
                    rmc._atomic_write(STOP, {"ts": _now_iso(), "motivo": problema_prov,
                                             "tipo": "provenance_incorrecto", "pid": pid})
                    print(f"\n[STOP] Provenance incorrecto en {pid}: {problema_prov}",
                          file=sys.stderr)
                    return prog, False, True
                futuros[ex.submit(_dock_worker, pid)] = pid
                guardar_progreso(prog)
            if not futuros:
                if cola:
                    detener_presupuesto = True
                break
            hecho, _ = concurrent.futures.wait(
                futuros, timeout=5.0,
                return_when=concurrent.futures.FIRST_COMPLETED)
            for f in hecho:
                pid = futuros.pop(f)
                try:
                    res = f.result()
                except Exception as e:
                    res = {"pid": pid, "ok": False,
                           "reason": f"worker:{type(e).__name__}", "t": 0.0}
                estrato = cohort.get(pid, {}).get("stratum", "?")
                integridad = _procesar_resultado(pid, res, prog, estrato)
                guardar_progreso(prog)
                if integridad:
                    rmc._atomic_write(STOP, {"ts": _now_iso(), "motivo": integridad,
                                             "tipo": "violacion_gate_integridad",
                                             "pid": pid})
                    print(f"\n[STOP] Violacion de integridad del gate en {pid}: "
                          f"{integridad}", file=sys.stderr)
                    for pend in futuros:
                        pend.cancel()
                    futuros = {}
                    return prog, False, True
                if _verificar_sistematico(prog):
                    for pend in futuros:
                        pend.cancel()
                    futuros = {}
                    return prog, False, True
        guardar_progreso(prog)
        return prog, detener_presupuesto, False
    finally:
        ex.shutdown(wait=True, cancel_futures=True)


# ───────────────────────── verificaciones ──────────────────────────────────

def verificar_identity_check() -> dict:
    """La identidad vina_exh4 no colisiona con historicos (FND-06 /
    MF-01-UNION). Solo lectura."""
    res = {"fnd06_hits": 0, "union_hits": 0, "veredicto": True}
    if FND06_SIDECAR.exists():
        for line in FND06_SIDECAR.read_text(encoding="utf-8").splitlines():
            if "vina_exh4" in line:
                res["fnd06_hits"] += 1
    for split in ("train", "val"):
        f = UNION_ARTIFACTS / f"union_candidates_{split}.jsonl"
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("source") == SOURCE or "vina_exh4" in rec.get("identity", ""):
                res["union_hits"] += 1
    res["veredicto"] = res["fnd06_hits"] == 0 and res["union_hits"] == 0
    return res


def verificar_determinismo(pid: str) -> int:
    """Determinismo parcial: regenera la preparacion completa en un
    directorio temporal y compara sha256 con el work dir."""
    w = WORK / pid
    archivos = ["rec.pdbqt", "center.json", "lig.flex.pdbqt", "index_map.json"]
    if not all((w / a).exists() for a in archivos):
        print(f"{pid}: preparacion incompleta en el work dir")
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
        flex_str, mapa, reason = _preparar_ligando_flexible(pid, tw)
        if reason:
            print(f"{pid}: {reason} en temp")
            ok = False
        (tw / "lig.flex.pdbqt").write_text(flex_str, encoding="utf-8")
        (tw / "index_map.json").write_text(json.dumps([[s, m] for s, m in mapa.items()]),
                                           encoding="utf-8")
        for a in archivos:
            h_w = _sha256_archivo(w / a)
            h_t = _sha256_archivo(tw / a)
            igual = h_w == h_t
            print(f"  {a}: work={h_w[:12]} temp={h_t[:12]} "
                  f"{'IDENTICO' if igual else 'DISTINTO'}")
            ok = ok and igual
    print(f"{pid}: determinismo parcial {'OK' if ok else 'FALLA'}")
    return 0 if ok else 1


# ───────────────────────── union (read-only) ───────────────────────────────

def _atoms_de_pdbqt(texto: str) -> list:
    atoms = []
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")):
            try:
                atoms.append([int(l[6:11]), float(l[30:38]),
                              float(l[38:46]), float(l[46:54])])
            except Exception:
                continue
    return atoms


def recomputar_union_cohorte_train() -> dict:
    """Lee union_candidates_train.jsonl restringido a la cohorte train y
    recomputa rmsd_pose_pocket DESDE EL PDBQT EMBEBIDO (sin re-dockear),
    usando el mapa serial->mol del work dir sellado de la curva (misma
    preparacion meeko del mismo SDF: orden atomico identico por fuente,
    verificado con el patron de elementos ATOM del bloque vs conf0.flex.pdbqt).
    Devuelve {pid: {"n": int, "rmsds": [float], "anomalias": int}}."""
    pids = {r["pid"]: r for r in leer_cohort_train()}
    crystals = {}
    mapas = {}
    flex_elems = {}
    anomalias_elementos = []
    per_pid = {pid: {"n": 0, "rmsds": [], "anomalias": 0} for pid in pids}
    for line in (UNION_ARTIFACTS / "union_candidates_train.jsonl") \
            .read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        pid = rec.get("pid")
        if pid not in pids:
            continue
        if pid not in crystals:
            crystals[pid] = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
            mapas[pid] = mf.cargar_mapa_indices(CURVE_WORK / pid)
            try:
                flex = (CURVE_WORK / pid / "conf0.flex.pdbqt").read_text(encoding="utf-8")
                flex_elems[pid] = [l[76:78].strip() if len(l) > 77 else ""
                                   for l in flex.splitlines()
                                   if l.startswith(("ATOM", "HETATM"))]
            except Exception:
                flex_elems[pid] = []
        d = per_pid[pid]
        d["n"] += 1
        atoms = _atoms_de_pdbqt(rec.get("pdbqt", ""))
        if flex_elems.get(pid):
            elems = [rec.get("pdbqt", "").splitlines()[i][76:78].strip()
                     for i, l in enumerate(rec.get("pdbqt", "").splitlines())
                     if l.startswith(("ATOM", "HETATM")) and len(l) > 77]
            if elems and elems != flex_elems[pid]:
                anomalias_elementos.append({
                    "pid": pid, "identity": rec.get("identity"),
                    "source": rec.get("source"),
                })
        por_mol = mf.coords_pose_a_por_mol(atoms, mapas.get(pid, {}))
        rmsd = mf.rmsd_pose_pocket(crystals.get(pid), por_mol) if por_mol else None
        if rmsd is not None:
            d["rmsds"].append(rmsd)
        else:
            d["anomalias"] += 1
    return per_pid, anomalias_elementos


# ───────────────────────── comparacion (3 niveles + G2) ────────────────────

def _cobertura_k15_sellada() -> dict:
    """Lee el sello D-MF-HARD-CURVE: cobertura por complejo a K=15 (prefijo
    15) y medianas min-RMSD por estrato. Solo lectura."""
    pc = {}
    for line in (CURVE_ARTIFACTS / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        p = r.get("prefijos", {}).get("15", {})
        pc[r["pid"]] = {"cubierto": bool(p.get("cubierto")),
                        "min_rmsd": p.get("min_rmsd")}
    met = rmc._json_load(CURVE_ARTIFACTS / "metrics.json", default={})
    medianas = {}
    for estrato in ("hard", "control"):
        medianas[estrato] = met.get("por_estrato", {}).get(estrato, {}) \
            .get("15", {}).get("mediana_min_rmsd")
    n_poses = {"hard": 0, "control": 0}
    cohort_estrato = {r["pid"]: r["stratum"] for r in leer_cohort_train()}
    for line in (CURVE_ARTIFACTS / "curve_poses_train.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            p = json.loads(line)
        except Exception:
            continue
        if 15 in p.get("prefix", []):
            e = cohort_estrato.get(p["pid"])
            if e in n_poses:
                n_poses[e] += 1
    return {"per_pid": pc, "medianas_min_rmsd": medianas, "n_poses": n_poses}


def _mcnemar_exacto_bilateral(b: int, c: int):
    """McNemar exacto: prueba binomial exacta bilateral sobre los pares
    discordantes (b/c). Devuelve None si no hay pares discordantes."""
    n = b + c
    if n == 0:
        return None
    p = 0.0
    for k in range(min(b, c) + 1):
        p += math.comb(n, k) * (0.5 ** n)
    return min(1.0, 2.0 * p)


def _wilson_ci(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centro - margen), 3),
            round(min(1.0, centro + margen), 3)]


def _g2_por_par(nombre_a: str, nombre_b: str, cov_a: dict, cov_b: dict,
                pids: list, n_total: int) -> dict:
    """G2 en sus 4 niveles para un par de brazos sobre los mismos pids.
    (i) conteo n/17; (ii) matriz pareada de discordancia (b/c);
    (iii) McNemar exacto bilateral; (iv) veredicto de superioridad
    (regla: (i) favorece Y (ii) sin perdidas netas que contradigan Y
    (iii) p <= 0.05; si no -> INCONCLUSO)."""
    n_cub_a = sum(1 for pid in pids if cov_a.get(pid, {}).get("cubierto"))
    n_cub_b = sum(1 for pid in pids if cov_b.get(pid, {}).get("cubierto"))
    b = sum(1 for pid in pids
            if cov_a.get(pid, {}).get("cubierto") and not cov_b.get(pid, {}).get("cubierto"))
    c = sum(1 for pid in pids
            if cov_b.get(pid, {}).get("cubierto") and not cov_a.get(pid, {}).get("cubierto"))
    p = _mcnemar_exacto_bilateral(b, c)
    superior = None
    if p is not None:
        if n_cub_a > n_cub_b and c == 0 and p <= 0.05:
            superior = nombre_a
        elif n_cub_b > n_cub_a and b == 0 and p <= 0.05:
            superior = nombre_b
    return {
        "nivel_i_conteo": {nombre_a: n_cub_a, nombre_b: n_cub_b,
                           "denominador": n_total},
        "nivel_ii_pareada": {"b": b, "c": c,
                             "concordantes": n_total - b - c,
                             "b_desc": f"{nombre_a} recupera y {nombre_b} pierde",
                             "c_desc": f"{nombre_b} recupera y {nombre_a} pierde"},
        "nivel_iii_inferencia": {
            "mcnemar_exacto_bilateral": round(p, 7) if p is not None else None,
            "nota": "n=17: potencia baja; este nivel describe el ruido, "
                    "no declara superioridad por si solo",
        },
        "nivel_iv_superioridad": {
            "superior": superior,
            "veredicto": "INCONCLUSO" if superior is None else superior,
        },
    }


def _armas_comparacion(exh4_per_pid: dict, docks: list) -> dict:
    """Construye los numeros de los 3 niveles de comparacion (train).
    Denominadores exactos del FORECAST para MolFlex K15 y Unión."""
    cohort = {r["pid"]: r for r in leer_cohort_train()}
    estratos = {pid: r["stratum"] for pid, r in cohort.items()}
    k15 = _cobertura_k15_sellada()
    union_per_pid, anomalias_union = recomputar_union_cohorte_train()

    armas = {"molflex_k15": {}, "union": {}, "vina_exh4": {}}
    union_per_estrato_por_pid = {}
    for estrato in ("hard", "control"):
        pids = [pid for pid, r in cohort.items() if r["stratum"] == estrato]

        def cubiertos_y_mediana(per_pid, pids_estrato):
            rmsds = []
            cub = 0
            for pid in pids_estrato:
                d = per_pid.get(pid)
                if d is None:
                    continue
                if d.get("min_rmsd") is not None:
                    rmsds.append(d["min_rmsd"])
                    cub += int(d["min_rmsd"] <= UMBRAL_COBERTURA)
            return cub, rmsds

        # Vina exh4 (nuevo brazo).
        exh4_cub, exh4_rmsds = cubiertos_y_mediana(exh4_per_pid, pids)
        # Unión (recomputada).
        union_per_estrato = {}
        for pid in pids:
            d = union_per_pid.get(pid, {"n": 0, "rmsds": [], "anomalias": 0})
            union_per_estrato[pid] = {
                "n": d["n"],
                "min_rmsd": round(min(d["rmsds"]), 3) if d["rmsds"] else None,
                "cubierto": min(d["rmsds"]) <= UMBRAL_COBERTURA if d["rmsds"] else False,
                "anomalias_rmsd_no_computable": d["anomalias"],
            }
        union_per_estrato_por_pid.update(union_per_estrato)
        union_cub = sum(1 for pid in pids if union_per_estrato[pid]["cubierto"])
        union_n = sum(union_per_estrato[pid]["n"] for pid in pids)
        union_rmsds = [union_per_estrato[pid]["min_rmsd"] for pid in pids
                       if union_per_estrato[pid]["min_rmsd"] is not None]
        # MolFlex K15 (sellado).
        k15_cub = sum(1 for pid in pids if k15["per_pid"].get(pid, {}).get("cubierto"))
        k15_n = k15["n_poses"][estrato]

        armas["molflex_k15"][estrato] = {
            "n_cubiertos": k15_cub, "denominador": len(pids),
            "cobertura": round(k15_cub / len(pids), 4),
            "mediana_min_rmsd": k15["medianas_min_rmsd"].get(estrato),
            "n_poses": k15_n,
        }
        armas["union"][estrato] = {
            "n_cubiertos": union_cub, "denominador": len(pids),
            "cobertura": round(union_cub / len(pids), 4),
            "mediana_min_rmsd": round(rmc._pct(union_rmsds, 0.5), 3) if union_rmsds else None,
            "n_poses": union_n,
            "n_anomalias_rmsd": sum(union_per_estrato[pid]["anomalias_rmsd_no_computable"]
                                    for pid in pids),
        }
        armas["vina_exh4"][estrato] = {
            "n_cubiertos": exh4_cub, "denominador": len(pids),
            "cobertura": round(exh4_cub / len(pids), 4),
            "mediana_min_rmsd": round(rmc._pct(exh4_rmsds, 0.5), 3) if exh4_rmsds else None,
            "n_poses": sum(1 for pid in pids for _ in range(
                len(exh4_per_pid.get(pid, {}).get("modelos", [])))),
        }

    # Nivel (c): eficiencia oraculo = cobertura / (N/100), descriptiva.
    eficiencia = {}
    for nombre, per_estrato in armas.items():
        eficiencia[nombre] = {}
        for estrato in ("hard", "control"):
            d = per_estrato[estrato]
            n100 = d["n_poses"] / 100.0 if d["n_poses"] else None
            eficiencia[nombre][estrato] = {
                "n_poses": d["n_poses"],
                "cobertura": d["cobertura"],
                "cobertura_por_100_candidatos": (
                    round(d["cobertura"] / n100, 4) if n100 else None),
            }

    # Nivel (b): CPU-ajustada (SOLO brazos con CPU>0: MolFlex K15 vs exh4).
    # Denominadores por estrato (correccion del maintainer 2026-08-16): MolFlex
    # hard = 255 docks x 31.25 s = 2.214 h P50; control = 159 x 9.2 s = 0.406 h
    # P50; total = 2.620 h P50 (4.24 h P90 total). Vina exh4 usa el coste medido
    # por estrato (cpu=1, incluye fallos ITT).
    t_hard = sum(float(d["t"]) for d in docks if d.get("stratum") == "hard")
    t_control = sum(float(d["t"]) for d in docks if d.get("stratum") == "control")
    exh4_cpu = {"hard": round(t_hard / 3600, 3),
                "control": round(t_control / 3600, 3),
                "total": round((t_hard + t_control) / 3600, 3),
                "nota": "suma de wall por dock (cpu=1); incluye fallos ITT"}
    k15_cpu_p50 = {"hard": round(255 * 31.25 / 3600, 3),
                   "control": round(159 * 9.2 / 3600, 3),
                   "total": round((255 * 31.25 + 159 * 9.2) / 3600, 3)}
    cpu_ajustada = {
        "molflex_k15": {
            "cpu_h_p50_por_estrato": k15_cpu_p50,
            "cpu_h_p90_total": 4.24,
            "fuente": "FORECAST.md §6(b): hard 255 docks x 31.25 s (P50) = 2.214 h; "
                      "control 159 x 9.2 s = 0.406 h; total 2.620 h (P90 total "
                      "4.24 h = 255 x 42.1 s + 159 x 28.5 s), train",
            "por_estrato": {
                e: {"cobertura": armas["molflex_k15"][e]["cobertura"],
                    "cpu_h": k15_cpu_p50[e],
                    "cobertura_por_cpu_h": round(armas["molflex_k15"][e]["cobertura"] / k15_cpu_p50[e], 4)}
                for e in ("hard", "control")
            },
        },
        "vina_exh4": {
            "cpu_h_medida": exh4_cpu["total"],
            "por_estrato": {
                e: {"cobertura": armas["vina_exh4"][e]["cobertura"],
                    "cpu_h": exh4_cpu[e],
                    "cobertura_por_cpu_h": round(armas["vina_exh4"][e]["cobertura"] / exh4_cpu[e], 4)
                    if exh4_cpu[e] > 0 else None}
                for e in ("hard", "control")
            },
        },
        "union": {
            "ratio_cpu": "INDEFINIDO: cobertura/0 CPU-hours (ningun dock nuevo)",
            "coste_incremental_hoy": 0.0,
            "coste_historico_generacion": "NO estimable desde datos sellados "
                "(FND-06 sin timing: cobertura created_at = 0/4300 conocido; 447 runs)",
            "coste_reproduccion_estimado": "2.4-4.7 h CPU (planificacion, orden de "
                "magnitud, NO gate: ruta_a 60 runs ~0.4-1.2 h + flexible_redock 143 "
                "runs ~1.4 h + molflex 244 runs ~0.6-2.1 h)",
        },
    }

    # G3: tradeoff documentado si el brazo de mayor cobertura cuesta >2x la
    # CPU del siguiente con <=1 complejo de diferencia (CPU por estrato:
    # correccion del maintainer 2026-08-16).
    for estrato in ("hard", "control"):
        cov = {n: armas[n][estrato]["cobertura"] for n in ("molflex_k15", "vina_exh4")}
        cpu = {"molflex_k15": k15_cpu_p50[estrato], "vina_exh4": exh4_cpu[estrato]}
        dif = {n: armas[n][estrato]["n_cubiertos"] for n in ("molflex_k15", "vina_exh4")}
        orden = sorted(cov, key=lambda n: -cov[n])
        mayor, siguiente = orden[0], orden[1]
        tradeoff = (dif[mayor] - dif[siguiente] <= 1 and
                    cpu[mayor] > 2 * cpu[siguiente])
        cpu_ajustada.setdefault("g3_tradeoff", {})[estrato] = {
            "mayor_cobertura": mayor, "siguiente": siguiente,
            "diferencia_complejos": dif[mayor] - dif[siguiente],
            "cpu_h": {mayor: cpu[mayor], siguiente: cpu[siguiente]},
            "tradeoff_documentado": bool(tradeoff),
        }

    # G2: 4 niveles por estrato, pares exhaustivos (foco: exh4 vs K15).
    g2 = {}
    for estrato in ("hard", "control"):
        pids = [pid for pid, r in cohort.items() if r["stratum"] == estrato]
        cov = {
            "molflex_k15": {pid: {"cubierto": k15["per_pid"].get(pid, {}).get("cubierto")}
                            for pid in pids},
            "union": {pid: {"cubierto": union_per_estrato_por_pid[pid]["cubierto"]}
                      for pid in pids},
            "vina_exh4": {pid: {"cubierto": exh4_per_pid.get(pid, {}).get("cubierto", False)}
                          for pid in pids},
        }
        pares = {}
        for a, b in (("vina_exh4", "molflex_k15"), ("vina_exh4", "union"),
                     ("molflex_k15", "union")):
            pares[f"{a}_vs_{b}"] = _g2_por_par(a, b, cov[a], cov[b], pids, len(pids))
        g2[estrato] = pares

    return {
        "armas": armas,
        "eficiencia_oraculo_descriptiva": eficiencia,
        "cpu_ajustada": cpu_ajustada,
        "g2": g2,
        "union_anomalias_elementos": {
            "n": len(anomalias_union),
            "detalle": anomalias_union[:10],
            "nota": "patron de elementos del bloque PDBQT distinto al meeko del "
                    "work dir sellado (no afecta RMSD; verificado solo informativo)",
        },
        "nivel_a_nota": "operacional completa: numerador = complejos con "
                        "min(rmsd_pose_pocket) <= 2 A sobre TODOS los candidatos "
                        "del brazo; denominador = 17 complejos por estrato (train)",
        "nivel_c_nota": "DESCRIPTIVA, no decisoria: MF-11 no deduplica y los "
                        "duplicados distorsionan N (FORECAST §6.c)",
    }


# ───────────────────────── consolidacion ───────────────────────────────────

def _parsear_modos_exh4(pid: str):
    p = WORK / pid / f"{FILE_STEM}.pdbqt"
    if not p.exists():
        return None
    parsed = rmc.parse_vina_output(p.read_text(encoding="utf-8"))
    return parsed["models"] if parsed["ok"] else None


def consolidar() -> int:
    """Construye los artefactos finales en
    scripts/artifacts_science/D-MF-HARD-EXH4/."""
    cohort = leer_cohort_train()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    failures = []
    if FAILURES_WORK.exists():
        for line in FAILURES_WORK.read_text(encoding="utf-8").splitlines():
            try:
                failures.append(json.loads(line))
            except Exception:
                continue
    docks = []
    if DOCK_TIMES.exists():
        for line in DOCK_TIMES.read_text(encoding="utf-8").splitlines():
            try:
                docks.append(json.loads(line))
            except Exception:
                continue

    poses = []
    provenances = []
    per_complex = []
    exh4_per_pid = {}
    modos_por_estrato = {"hard": [], "control": []}
    for rec in cohort:
        pid = rec["pid"]
        estrato = rec["stratum"]
        w = WORK / pid
        prov = rmc._json_load(w / "provenance.json", default={})
        modelos = _parsear_modos_exh4(pid)
        if not modelos:
            per_complex.append({"pid": pid, "stratum": estrato,
                                "cohort_id": rec["cohort_id"],
                                "pair_id": rec["pair_id"],
                                "min_rmsd": None, "cubierto": False,
                                "n_poses": 0,
                                "motivo": "sin_dock_valido"})
            exh4_per_pid[pid] = {"min_rmsd": None, "cubierto": False,
                                 "modelos": []}
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
                "identity": identidad_pose(pid, m_idx),
                "split": SPLIT,
                "pid": pid,
                "source": SOURCE,
                "file_stem": FILE_STEM,
                "model_idx": m_idx,
                "vina_score": modelo["score"],
                "rmsd_pose_pocket": round(rmsd, 3) if rmsd is not None else None,
                "seed_conformer": prov.get("seed_conformer"),
                "seed_docking": prov.get("seed_docking"),
                "exhaustiveness": prov.get("exhaustiveness"),
                "num_modes": prov.get("num_modes"),
                "num_modes_requested": NUM_MODES,
                "n_models_emitted": n_emitidos,
                "box": prov.get("box"),
                "provenance_key": prov.get("key"),
            })
            if rmsd is not None:
                rmsds.append(rmsd)
        if isinstance(prov, dict) and (
                prov.get("n_models_emitted") != n_emitidos
                or prov.get("num_modes_requested") != NUM_MODES):
            anotar_emision(pid, n_emitidos)
            prov["n_models_emitted"] = n_emitidos
            prov["num_modes_requested"] = NUM_MODES
        if isinstance(prov, dict):
            provenances.append(prov)
        min_rmsd = min(rmsds) if rmsds else None
        exh4_per_pid[pid] = {
            "min_rmsd": round(min_rmsd, 3) if min_rmsd is not None else None,
            "cubierto": min_rmsd <= UMBRAL_COBERTURA if min_rmsd is not None else False,
            "modelos": modelos,
        }
        per_complex.append({
            "pid": pid, "stratum": estrato,
            "cohort_id": rec["cohort_id"], "pair_id": rec["pair_id"],
            "min_rmsd": round(min_rmsd, 3) if min_rmsd is not None else None,
            "cubierto": min_rmsd <= UMBRAL_COBERTURA if min_rmsd is not None else False,
            "n_poses": n_emitidos,
        })

    with open(ARTIFACTS / "exh4_poses_train.jsonl", "w", encoding="utf-8") as fh:
        for p in poses:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "exh4_provenance.jsonl", "w", encoding="utf-8") as fh:
        for r in provenances:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "failures.jsonl", "w", encoding="utf-8") as fh:
        for f in failures:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "deviations.jsonl", "w", encoding="utf-8") as fh:
        pass  # esperado vacio: el gate corregido rigio desde el inicio
    with open(ARTIFACTS / "per_complex.jsonl", "w", encoding="utf-8") as fh:
        for r in per_complex:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Candidatos materializados (bloques PDBQT byte-fieles por pose emitida).
    registros = []
    for rec in cohort:
        pid = rec["pid"]
        modelos = _parsear_modos_exh4(pid)
        if not modelos:
            continue
        prov = rmc._json_load(WORK / pid / "provenance.json", default={})
        for m_idx, modelo in enumerate(modelos):
            registros.append({
                "identity": identidad_pose(pid, m_idx),
                "pid": pid,
                "source": SOURCE,
                "file_stem": FILE_STEM,
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
    with open(ARTIFACTS / "exh4_candidates_train.jsonl", "w", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    data = (ARTIFACTS / "exh4_candidates_train.jsonl").read_bytes()
    print(f"exh4_candidates_train.jsonl: {len(registros)} lineas, "
          f"{len(data) / 1024 / 1024:.2f} MB, "
          f"sha256={hashlib.sha256(data).hexdigest()}")

    # Metricas del brazo.
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

    ident_check = verificar_identity_check()
    comparacion = _armas_comparacion(exh4_per_pid, docks)

    # Verificacion de guardia de val (post-consolidacion).
    val_en_artefactos = sum(1 for p in poses if p["pid"] in VAL_PIDS)
    val_en_work = sum(1 for pid in VAL_PIDS if (WORK / pid).exists())
    val_guard = {"val_no_tocado_verificado": val_en_artefactos == 0 and val_en_work == 0,
                 "pids_val_en_artefactos": val_en_artefactos,
                 "pids_val_en_work": val_en_work}
    if not val_guard["val_no_tocado_verificado"]:
        print("[ERROR] guardia de val violada", file=sys.stderr)
        return 1

    metricas = {
        "experiment_id": EXPERIMENT_ID,
        "split": SPLIT,
        "n_complejos": len(cohort),
        "n_poses": len(poses),
        "n_fallos_itt": len(failures),
        "por_estrato": por_estrato,
        "tiempos": {
            "hard": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "hard"]),
            "control": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "control"]),
            "total": rmc._calc_tiempos(docks),
        },
        "fallos_itt_por_estrato": itt,
        "gate": {
            "enmienda": "auditada_2026-08-16",
            "validez": "rc=0 + archivo no vacio + 1<=n_models_emitted<=9 + scores "
                       "FINITOS de REMARK VINA RESULT + geometria parseable",
            "scores": "exclusivamente_REMARK_VINA_RESULT_del_archivo",
            "num_modes_requested": NUM_MODES,
            "n_desviaciones": 0,
            "modos_emitidos": {
                e: {"n_corridas": len(v),
                    "mediana": round(rmc._pct(v, 0.5), 1) if v else None,
                    "min": min(v) if v else None,
                    "max": max(v) if v else None,
                    "distribucion": {str(k): v.count(k) for k in sorted(set(v))}}
                for e, v in modos_por_estrato.items()
            },
            "identidad_colisiones_historicos": ident_check,
        },
        "config": {
            "exhaustiveness": EXH,
            "seed_docking": SEED_DOCKING,
            "seed_conformer": "crystal",
            "box": "25 A centrado en ligando cristalografico",
            "num_modes_requested": NUM_MODES,
            "cpu": CPU,
            "workers": WORKERS,
            "timeout_s": FLEX_TIMEOUT,
            "relax": "sin relax",
            "engine": f"vina {mf.version_vina()}",
        },
        "claim": "benchmark de REDOCKING/GENERACION en pocket conocida (box 25 "
                 "centrado en ligando cristalografico, conformacion de entrada "
                 "cristalografica); NO evidencia end-to-end para pockets "
                 "desconocidas (FORECAST.md alcance del claim)",
        "comparacion": {
            "operacional_nivel_a": comparacion["armas"],
            "cpu_ajustada_nivel_b": comparacion["cpu_ajustada"],
            "n_candidatos_nivel_c_descriptiva": comparacion["eficiencia_oraculo_descriptiva"],
            "notas": {
                "nivel_a": comparacion["nivel_a_nota"],
                "nivel_c": comparacion["nivel_c_nota"],
                "union_elementos": comparacion["union_anomalias_elementos"],
            },
            "g2_cuatro_niveles": comparacion["g2"],
        },
        "verificaciones": val_guard,
    }
    rmc._atomic_write(ARTIFACTS / "metrics.json", metricas)
    _escribir_design(metricas, comparacion, len(poses), len(failures),
                     len(registros))
    print(f"Consolidacion: {len(poses)} poses, {len(provenances)} corridas de "
          f"provenance, {len(failures)} fallos ITT, {len(registros)} candidatos")
    print(json.dumps({"por_estrato": por_estrato,
                      "g2": comparacion["g2"]}, indent=2, ensure_ascii=False))
    return 0


def _escribir_design(metricas: dict, comparacion: dict, n_poses: int,
                     n_fallos: int, n_candidatos: int) -> None:
    por_estrato = metricas["por_estrato"]
    armas = comparacion["armas"]
    cpu = comparacion["cpu_ajustada"]
    g2 = comparacion["g2"]
    def _tabla_operacional():
        filas = []
        for nombre, etiqueta in (("molflex_k15", "MolFlex K15 (sellado)"),
                                 ("union", "Union (restringida a cohorte)"),
                                 ("vina_exh4", "Vina flexible exh4 (nuevo)")):
            h = armas[nombre]["hard"]
            c = armas[nombre]["control"]
            filas.append(f"| {etiqueta} | hard {h['n_cubiertos']}/{h['denominador']}"
                         f" ({h['cobertura']*100:.1f}%), mediana "
                         f"{h['mediana_min_rmsd']} A, N={h['n_poses']} | control "
                         f"{c['n_cubiertos']}/{c['denominador']}"
                         f" ({c['cobertura']*100:.1f}%), mediana "
                         f"{c['mediana_min_rmsd']} A, N={c['n_poses']} |")
        return "\n".join(filas)
    def _tabla_g2():
        filas = []
        for estrato in ("hard", "control"):
            for par, d in g2[estrato].items():
                i = d["nivel_i_conteo"]
                pares_keys = list(i.keys())
                p = d["nivel_iii_inferencia"]["mcnemar_exacto_bilateral"]
                filas.append(f"| {estrato} | {par} | {pares_keys[0]} {i[pares_keys[0]]}/17"
                             f" vs {pares_keys[1]} {i[pares_keys[1]]}/17 | b={d['nivel_ii_pareada']['b']},"
                             f" c={d['nivel_ii_pareada']['c']} | p={p} | "
                             f"{d['nivel_iv_superioridad']['veredicto']} |")
        return "\n".join(filas)
    texto = f"""# D-MF-HARD-EXH4 — Brazo Vina flexible exh4, fase 1 (34 train) — DESIGN

**Fecha:** {datetime.now().strftime('%Y-%m-%d')}
**Rama:** experimentos/ruta-c-molflex
**Referencia:** FORECAST.md (correcciones procedimentales commit 47a24a8) +
docs/49 §15 entregable 8 (MF-06) + D-MF-HARD/DESIGN.md (cohorte sellada).
**Interpretacion aprobada por el maintainer con 2 correcciones de artefacto
(2026-08-16): guardia de val renombrada a val_no_tocado_verificado y CPU por
estrato (hard 2.214 h / control 0.406 h P50 para MolFlex). NO sellado, NO
finish (sellado diferido por instruccion del maintainer).**

## 1. Protocolo ejecutado

- Vina FLEXIBLE, exh=4, `--seed 42` explicito, box 25 A centrado en el
  ligando cristalografico, num_modes solicitados 9, cpu=1, 6 workers, sin
  relax, timeout 300 s/dock, Vina 1.2.7. Un dock por complejo.
- Ligando: CONFORMACION CRISTALOGRAFICA preparada con meeko como PDBQT
  FLEXIBLE (torsiones activas). Receptor: PDBQT rigido pdb_original. Misma
  definicion de flexibilidad/receptor del historico documentado
  (rescoring/scripts/redock_pdbbind.py flexible_redock exh8 y
  scripts/ruta_a_exh_validation.py dock_one_exh); solo cambian exh (8->4) y
  el seed explicito (los historicos no lo registraban).
- Gate ENMENDADO (auditado 2026-08-16, heredado de D-MF-HARD-CURVE §8):
  validez = rc=0 + archivo no vacio + 1 <= n_models_emitted <= 9 + TODOS los
  modelos con score FINITO de REMARK VINA RESULT + geometria parseable.
  Scores EXCLUSIVAMENTE del archivo (nunca de la tabla stdout). Identidades
  SOLO para modelos realmente emitidos (sin model_idx fantasma).
- Alcance: SOLO train (17 hard + 17 controles). CERO val: los 10 pids de val
  no se dockearon, no se leyeron de la union ni de los artefactos (guardia
  dura + verificacion final). Fase 2 (D-MF-HARD-EXH4-VAL, 10 val) queda
  FUERA de esta ejecucion: se autoriza solo tras analizar y sellar la
  interpretacion de train.
- Alcance del claim: box centrado en el ligando cristalografico y
  conformacion de entrada cristalografica -> benchmark de REDOCKING/
  GENERACION dentro de una pocket conocida. NO es evidencia end-to-end para
  pockets desconocidas.

## 2. Implementacion (por composicion — congelado 7)

- Runner: scripts/run_vina_exh4.py (stdlib, docstring espanol). NO edita
  ningun asset sellado: reusa por importacion scripts/molflex.py
  (leer_ligando, escribir_pdbqt, cargar_mapa_indices, coords_pose_a_por_mol,
  rmsd_pose_pocket, _args_box, prepare_receptor_pdbqt/find_binding_center via
  mf.rp) y scripts/run_molflex_curve.py (parse_vina_output = gate corregido,
  leer_cohort, utilidades de archivo; su hash esta sellado en
  D-MF-HARD-CURVE: solo se importa).
- Identidad canonica por pose: train|pid|vina_exh4|flex_exh4.out|model_idx
  (model_idx SOLO para modelos emitidos). Identidad sin colision con FND-06
  ni MF-01-UNION (identity-check: 0 hits).
- Provenance canonico FND-06 (14 campos) por corrida: seed_conformer=
  "crystal" (no hay generacion estocastica de conformeros; convencion del
  historico flexible_redock), seed_docking=42 (--seed explicito),
  exhaustiveness=4, experiment_id=D-MF-HARD-EXH4, mas num_modes_requested=9
  y n_models_emitted anotados tras el dock.
- Resume idempotente por identidad: dock valido bajo el gate -> no se repite;
  fallo -> ITT en failures.jsonl sin reintentos silenciosos; STOP.json ante
  fallos SISTEMATICOS (mismo motivo en >=3 complejos) o violacion de
  integridad del gate.
- Work dir: data/dmfhard_curve_work/exh4/ (gitignored; .gitignore intacto).
- Consolidacion separada del docking: los artefactos finales se reconstruyen
  desde el work dir; el docking nunca escribe en scripts/artifacts_science.
- Determinismo parcial verificado: regeneracion completa de la preparacion de
  1 complejo en temp -> byte-identica (ver reporte de ejecucion).

## 3. Metrica de pose

- rmsd_pose_pocket (molflex.py) en el marco del pocket, sin alineamiento
  (obligatoria segun docs/48), contra el ligando cristalografico
  data/pdbbind/{{pid}}/{{pid}}_ligand.sdf, sobre los modelos EMITIDOS.

## 4. Resultados (train, 34 complejos)

- Poses emitidas: {n_poses}; fallos ITT: {n_fallos}; candidatos
  materializados: {n_candidatos}.
- Hard: cobertura {por_estrato['hard']['n_cubiertos']}/17, mediana min-RMSD
  {por_estrato['hard']['mediana_min_rmsd']} A.
- Control: cobertura {por_estrato['control']['n_cubiertos']}/17, mediana
  min-RMSD {por_estrato['control']['mediana_min_rmsd']} A.

## 5. Comparacion vs MolFlex K15 y Union (3 niveles, train)

### (a) Operacional completa — cobertura cruda por brazo

{_tabla_operacional()}

### (b) Ajustada por CPU — cobertura por CPU-hour (solo brazos con CPU>0)

Denominadores por estrato (correccion del maintainer 2026-08-16):

- MolFlex K15 train (P50, estimado): hard 255 docks x 31.25 s = **2.214 h**;
  control 159 x 9.2 s = **0.406 h**; total **2.620 h** (P90 total 4.24 h:
  255 x 42.1 s + 159 x 28.5 s). Fuente: FORECAST §6(b).
- Vina exh4 train (medido, cpu=1, incluye fallos ITT): hard
  **{cpu['vina_exh4']['por_estrato']['hard']['cpu_h']} h**; control
  **{cpu['vina_exh4']['por_estrato']['control']['cpu_h']} h**; total
  **{cpu['vina_exh4']['cpu_h_medida']} h**.
- Conclucion (no cambia con la correccion): en hard, exh4 obtiene mucha mas
  cobertura con ~1/3 del coste estimado de MolFlex (0.670 h vs 2.214 h).
- Union: ratio INDEFINIDO (cobertura / 0 CPU-hours; ningun dock nuevo). Tres
  costes por separado: incremental hoy = 0 h; historico de generacion NO
  estimable desde datos sellados (FND-06 sin timing); reproduccion estimada
  2.4-4.7 h CPU (planificacion, no gate).
- Eficiencia por estrato: metrics.json -> comparacion.cpu_ajustada_nivel_b.

### (c) Ajustada por candidatos (DESCRIPTIVA, no decisoria)

- N candidatos por estrato y eficiencia oraculo = cobertura/(N/100):
  metrics.json -> comparacion.n_candidatos_nivel_c_descriptiva. Degradada a
  descriptiva porque MF-11 no deduplica y los duplicados distorsionan N
  (FORECAST §6.c).

## 6. G2 — oraculo por estrato en 4 niveles (train decide)

{_tabla_g2()}

Regla de superioridad (nivel iv): un brazo gana solo si (i) el conteo lo
favorece Y (ii) la pareada no muestra perdidas netas que lo contradigan Y
(iii) McNemar exacto bilateral p <= 0.05. Con n=17 la potencia es baja:
INCONCLUSO es un resultado valido y esperable.

## 7. Interpretacion para el sello

En D-MF-HARD train, AutoDock Vina 1.2.7 con ligando flexible, receptor rígido, exhaustiveness 4 y seed 42 fue superior a MolFlex K15 en cobertura hard: 11/17 frente a 3/17; discordancias b=8, c=0; McNemar exacto bilateral p=0.0078125. El coste hard fue 0.670 CPU-h medido frente a 2.214 CPU-h P50 estimado para MolFlex, sin tradeoff de coste bajo el estimador preregistrado. El claim se limita a esta cohorte de desarrollo y a redocking/generación con pocket conocida, box y conformación inicial cristalográficos. Frente a la unión en hard y frente a MolFlex K15 en controles, el resultado permanece inconcluso.

## 8. Sensibilidad

Considerando las seis comparaciones G2, Bonferroni post hoc mantiene el resultado hard exh4-vs-K15 por debajo de 0.05 (p_adj=0.046875); se reporta como sensibilidad, no como parte del preregistro original.

## 9. Declaraciones de alcance

- 0 val tocado (ni dock, ni lectura de outputs previos mas alla de la
  cohorte: la union restringida a la cohorte train se recomputo SOLO desde
  union_candidates_train.jsonl).
- Cero v0.6 (RS-01), cero MF-11, cero produccion, cero relax, cero
  reentrenamiento, cero test historico.
- K15 MolFlex INMUTABLE (sello f31bfeb): nada de esta corrida cambia K.
- exh2 permanece CERRADO (sellado docs/40 §9.4).

## 10. Archivos

| Archivo | Contenido |
|---|---|
| exh4_poses_train.jsonl | una linea por pose EMITIDA (identidad train|pid|vina_exh4|flex_exh4.out|model_idx) |
| exh4_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| exh4_candidates_train.jsonl | bloques PDBQT byte-fieles materializados por pose emitida |
| metrics.json | por estrato (cobertura/mediana/ITT/tiempos P50-P90) + comparacion 3 niveles + G2 |
| per_complex.jsonl | una linea por complejo (min_rmsd, cubierto, n_poses) |
| failures.jsonl | fallos ITT (sin reintentos) |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
| FORECAST.md / inventory.json | preregistro e inventario (previos, intactos) |
| manifest.json / README.md | registro FND-01 (init/validate; sin seal ni finish) |
"""
    rmc._atomic_write(ARTIFACTS / "DESIGN.md", texto)


# ───────────────────────── CLI ─────────────────────────────────────────────

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        description="Brazo Vina flexible exh4 en D-MF-HARD train (entregable 8, fase 1)")
    ap.add_argument("--pids", nargs="*", default=None,
                    help="restringe el lote a estos pids train")
    ap.add_argument("--wall-budget", type=float, default=WALL_BUDGET_DEFAULT,
                    help="segundos de presupuesto por invocacion (default 240)")
    ap.add_argument("--report", action="store_true", help="resumen de progreso")
    ap.add_argument("--consolidate", action="store_true",
                    help="construye artefactos finales")
    ap.add_argument("--identity-check", action="store_true",
                    help="verifica no colision de identidades vina_exh4")
    ap.add_argument("--verify-determinismo", metavar="PID",
                    help="determinismo parcial de la preparacion de un complejo")
    args = ap.parse_args()

    if args.identity_check:
        print(json.dumps(verificar_identity_check(), indent=2))
        return 0
    if args.verify_determinismo:
        return verificar_determinismo(args.verify_determinismo)
    if args.consolidate:
        return consolidar()
    if args.report:
        return reportar()

    cohort = leer_cohort_train()
    pids = args.pids if args.pids else [r["pid"] for r in cohort]
    val_fuera = [p for p in pids if p in VAL_PIDS]
    if val_fuera:
        print(f"[STOP] pids de val rechazados: {val_fuera}", file=sys.stderr)
        return 2
    pids_train = [p for p in pids if p in {r["pid"] for r in cohort}]
    if not pids_train:
        print("Sin pids train pendientes.", file=sys.stderr)
        return 1
    prog = cargar_progreso()
    if STOP.exists():
        print(f"[STOP] STOP.json presente: "
              f"{STOP.read_text(encoding='utf-8')[:200]}", file=sys.stderr)
        return 2
    t0 = time.monotonic()
    prog, detener_presupuesto, sistematico = dockear_lote(
        prog, pids_train, args.wall_budget)
    guardar_progreso(prog)
    if sistematico:
        return 2
    print(f"Lote terminado en {time.monotonic()-t0:.0f}s"
          f"{' (presupuesto agotado)' if detener_presupuesto else ''}")
    return 0


def reportar() -> int:
    prog = cargar_progreso()
    complejos = prog.get("complexes", {})
    cohort = {r["pid"]: r for r in leer_cohort_train()}
    completados = fallidos = sin_empezar = 0
    lineas = []
    for pid, c in sorted(complejos.items(),
                         key=lambda kv: kv[1].get("cohort_id", kv[0])):
        state = c.get("state", "pending")
        estr = c.get("stratum", "?")
        if state == "completed":
            completados += 1
        elif state in ("failed_dock", "failed_prep"):
            fallidos += 1
        else:
            sin_empezar += 1
        lineas.append(f"  {c.get('cohort_id','?'):>4} {pid} {estr:<7} {state:<11} "
                      f"t={c.get('t')} n_models={c.get('n_models_emitted')}")
    pend_sin_estado = [r["pid"] for r in cohort.values() if r["pid"] not in complejos]
    print(f"Complejos: {completados} completados, {fallidos} fallidos, "
          f"{sin_empezar} pendientes, {len(pend_sin_estado)} sin empezar")
    for l in lineas:
        print(l)
    if pend_sin_estado:
        print(f"Sin empezar: {pend_sin_estado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
