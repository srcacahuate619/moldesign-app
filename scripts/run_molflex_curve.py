# -*- coding: utf-8 -*-
"""
run_molflex_curve.py — Runner de la curva MolFlex 5/15/30 (entregable 7).

Curva anidada de conformeros sobre la cohorte D-MF-HARD (solo split=train,
17 hard + 17 controles). Genera UNA vez el ensemble ETKDG de 30 conformeros
por complejo y dockea cada conformero (1 invocacion Vina = 9 modos). Los
puntos de la curva se evaluan sobre PREFIJOS del ensemble: {0..4} = K5,
{0..14} = K15, {0..29} = K30 (anidamiento verificado en FORECAST.md /
prefix_smoke.json: el prefijo ETKDG se conserva byte a byte).

Config base (preregistrada, FORECAST.md §5): seed ETKDG=42 y --seed 42
explicito en TODAS las invocaciones de Vina (SEMILLA_VINA de molflex.py,
preregistro FND-06), box 25 A centrado en ligando cristalografico, exh=8,
9 modos, CPU=1 por Vina, 6 workers, Vina 1.2.7, sin relax.

FIDELIDAD DE CONFIGURACION: este runner NO reimplementa la generacion de
conformeros ni el docking. Reusa las funciones de scripts/molflex.py:
  - preparar_complejo(pid, 30, work, experiment_id)  -> Fase 1 completa
    (receptor PDBQT, centro de caja, ensemble ETKDG seed 42, PDBQTs
    rigido/flexible por conformero, index_map, provenance.json canonico).
  - dock_rigido_archivo(pid, cid, work, cpu=1, maps_prefix, write_maps)
    -> Fase 2, una invocacion Vina por conformero (exh=8, 9 modos, box 25,
    --seed 42, timeout 240 s). El unico paso posterior es RENOMBRAR la
    salida conf{cid}.out.pdbqt a curve30_conf{cid}.out.pdbqt: la identidad
    de la curva usa el file_stem curve30_conf{cid}.out (los historicos usan
    conf{cid}.out sin prefijo; colision verificada = 0 en FND-06 y
    MF-01-UNION).
  - rmsd_pose_pocket + coords_pose_a_por_mol -> metrica de pose en el marco
    del pocket contra el ligando cristalografico data/pdbbind/{pid}/{pid}_ligand.sdf
    (metrica congelada; caveat documentado en DESIGN.md).

Identidad canonica por pose: train|pid|molflex|curve30_conf{cid}.out|model_idx
(model_idx 0..8 = los 9 modos del archivo de salida).

Propiedades operativas:
  - GATE CORREGIDO (enmienda auditada 2026-08-16, autorizada por el
    maintainer): validez = rc=0 + archivo no vacio + 1 <= n_models_emitted
    <= 9 + TODOS los modelos con score FINITO de REMARK VINA RESULT +
    geometria parseable. Scores EXCLUSIVAMENTE del archivo (nunca de la
    tabla stdout). Por corrida se registran num_modes_requested=9 y
    n_models_emitted. Identidades SOLO para modelos realmente emitidos
    (sin model_idx fantasma). Cero modelos, >9 modelos, score/geometria
    invalidos o provenance incorrecto -> DETENCION (violacion de integridad,
    STOP.json + reporte; no es fallo ITT ordinario).
  - Idempotente por identidad (resume): un dock cuya salida existe y pasa
    el gate corregido NO se repite. Un dock marcado como FALLIDO (ITT) NO se
    reintenta en lotes posteriores; reintento manual unico con --retry PID
    (retry TECNICO documentado en retry_log.jsonl, contado en
    metrics.gate.technical_retries; si el re-dock pasa no cuenta como
    fracaso cientifico).
  - Desviaciones: los falsos fallos del gate anterior (mode_count_mismatch
    del pilot) se reclasifican en consolidacion a
    scripts/artifacts_science/D-MF-HARD-CURVE/deviations.jsonl (FUERA del
    ITT), recuperando sus tiempos ya medidos.
  - Mapas de grid TRANSIENT (FORECAST §3.6): el primer dock del complejo los
    escribe (--write_maps + --force_even_voxels, que tambien ES el dock del
    conformero 0); los demas los reutilizan (--maps); se borran al completar
    el complejo. Si tras un resume parcial los mapas ya no existen, los
    conformeros pendientes dockean con receptor fresco (misma config
    nominal; el grid de mapas usa voxels pares, side effect documentado en
    molflex.py).
  - Sin reintentos silenciosos: fallos por conformero -> ITT registrados en
    failures (continue). Fallos SISTEMATICOS (todos los conformeros de un
    complejo fallan con el mismo motivo, o el mismo motivo aparece en >=3
    complejos) -> DETENER con STOP.json y reporte.
  - Lotes con resume: --wall-budget N (default 300 s) limita cada invocacion;
    se invoca en bucle hasta completar (el drain de tareas en vuelo acota la
    invocacion a ~budget + 240 s).

Subcomandos / flags:
  --pids A B ...      restringe el lote de docking a esos pids (pilot).
  --wall-budget N     segundos de presupuesto de la invocacion (default 300).
  --report            resumen de progreso (completados/pendientes/fallos).
  --check-pilot PID PID  verificaciones del pilot (seed/provenance/geometrias/
                         mapeo identidad). Exit != 0 si falla.
  --verify-confs PID ...  determinismo: regenera el ensemble (2 corridas) y
                         compara hashes con los guardados en el work dir.
  --consolidate       construye los artefactos finales en
                      scripts/artifacts_science/D-MF-HARD-CURVE/.
  --identity-check    verifica que las identidades curve30_* no colisionan
                      con FND-06 ni MF-01-UNION (solo lectura).
  --retry PID         reintento manual unico documentado de los confs
                      fallidos de un complejo.

Artifacts finales (--consolidate):
  curve_poses_train.jsonl, curve_provenance.jsonl, metrics.json,
  per_complex.jsonl, failures.jsonl, DESIGN.md.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import random
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402

EXPERIMENT_ID = "D-MF-HARD-CURVE"
COHORT = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD" / "cohort.jsonl"
SMOKE = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-CURVE" / "prefix_smoke.json"
ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-CURVE"
WORK = PROJECT_ROOT / "data" / "dmfhard_curve_work"

N_CONF = 30
PREFIJOS = [5, 15, 30]
NUM_MODES = 9
WORKERS = 6
CPU = 1
UMBRAL_COBERTURA = 2.0
N_BOOT = 2000
SEED_BOOT = 42
WALL_BUDGET_DEFAULT = 300.0

FIELDS_CANONICOS = [
    "key", "pid", "source", "file_stem", "seed_conformer", "seed_docking",
    "conformer_id", "exhaustiveness", "num_modes", "box", "preparation",
    "engine", "experiment_id", "created_at",
]

# PIDs de val: NUNCA se procesan (guardia dura por construccion: solo se leen
# registros con split=train; este set es una red de seguridad de verificacion).
VAL_PIDS = {
    "1b32", "1bgq", "1cny", "1fki", "1hms", "1bm7", "1hmt", "1ejn", "1jlr",
    "1nvq",
}

PROGRESS = WORK / "progress.json"
FAILURES_WORK = WORK / "failures.jsonl"
DOCK_TIMES = WORK / "dock_times.jsonl"
RETRY_LOG = WORK / "retry_log.jsonl"
STOP = WORK / "STOP.json"

# Enmienda auditada del gate (2026-08-16): estos motivos son VIOLACIONES DE
# INTEGRIDAD del motor y DETIENEN la ejecucion (no se tratan como fallos ITT
# ordinarios): cero modelos emitidos, mas de 9 modelos, score no finito,
# REMARK ausente, geometria rota, y las formas equivalentes del motor
# (no_pose = cero modelos a nivel de archivo; no_scores = stdout sin tabla).
GATE_INTEGRIDAD = {
    "gate:cero_modelos", "gate:mas_de_9_modelos", "gate:score_no_finito",
    "gate:sin_remark", "gate:geometria_rota", "no_pose", "no_scores",
}


# ───────────────────────── utilidades de archivo/estado ────────────────────

def _json_load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data if isinstance(data, str)
                   else json.dumps(data, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def leer_cohort(split: str = "train") -> list:
    """Lee cohort.jsonl filtrado por split, en el orden del archivo."""
    out = []
    for line in COHORT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("split") == split:
            out.append(rec)
    return out


def cargar_progreso() -> dict:
    return _json_load(PROGRESS, default={"experiment_id": EXPERIMENT_ID,
                                         "complexes": {}, "updated_at": None})


def guardar_progreso(prog: dict) -> None:
    prog["updated_at"] = _now_iso()
    _atomic_write(PROGRESS, prog)


def registrar_fallo(pid: str, cid, reason: str, t: float,
                    extra: dict | None = None) -> None:
    rec = {"ts": _now_iso(), "pid": pid, "cid": cid, "reason": reason,
           "t": round(float(t), 1)}
    if extra:
        rec.update(extra)
    with open(FAILURES_WORK, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def registrar_tiempo(pid: str, cid, estrato: str, t: float) -> None:
    with open(DOCK_TIMES, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"pid": pid, "cid": cid, "stratum": estrato,
                             "t": round(float(t), 1)}, ensure_ascii=False) + "\n")


def out_valido(pid: str, cid: int) -> bool:
    """Un dock es valido si su salida existe y pasa el gate corregido
    (1 <= n_models_emitted <= 9, todos los modelos con score FINITO de
    REMARK VINA RESULT y geometria parseable)."""
    p = WORK / pid / f"curve30_conf{cid}.out.pdbqt"
    if not p.exists():
        return False
    try:
        return parse_vina_output(p.read_text(encoding="utf-8"))["ok"]
    except Exception:
        return False


def identidad_pose(pid: str, cid: int, model_idx: int) -> str:
    """Identidad canonica por pose: train|pid|molflex|curve30_conf{cid}.out|model_idx
    (solo para modelos REALMENTE emitidos)."""
    return f"train|{pid}|molflex|curve30_conf{cid}.out|{model_idx}"


def parse_vina_output(pdbqt_texto: str) -> dict:
    """Gate corregido (enmienda auditada 2026-08-16): valida y parsea el
    PDBQT de salida de Vina.

    Reglas:
      - Validez: 1 <= n_models_emitted <= 9; TODOS los modelos con score
        FINITO parseable de REMARK VINA RESULT; geometria parseable (todo
        atomo con coords numericas).
      - Scores: EXCLUSIVAMENTE de REMARK VINA RESULT del archivo (nunca de
        la tabla stdout).
      - 0 modelos emitidos o >9 modelos = violacion de integridad (detencion
        en ejecucion).

    Devuelve:
      {ok: bool, n_models: int, models: [{"score": float|None,
        "atoms": [[serial, x, y, z], ...]}], errores: [str, ...]}
    """
    lineas = pdbqt_texto.splitlines()
    # Separar en bloques MODEL...ENDMDL; si no hay marcadores MODEL, todo el
    # texto es un unico bloque (formato sin MODEL/ENDMDL, p. ej. local_only).
    bloques = []
    actual = []
    hay_model = False
    for l in lineas:
        if l.startswith("MODEL"):
            hay_model = True
            if actual:
                bloques.append(actual)
                actual = []
        elif l.startswith("ENDMDL"):
            if actual:
                bloques.append(actual)
                actual = []
        else:
            actual.append(l)
    if actual and not hay_model:
        bloques = [actual]
    errores = []
    n = len(bloques)
    if n == 0:
        return {"ok": False, "n_models": 0, "models": [],
                "errores": ["gate:cero_modelos"]}
    if n > 9:
        return {"ok": False, "n_models": n, "models": [],
                "errores": [f"gate:mas_de_9_modelos({n})"]}
    modelos = []
    for idx, bloque in enumerate(bloques, start=1):
        score = None
        atoms = []
        for l in bloque:
            if l.startswith("REMARK VINA RESULT"):
                try:
                    score = float(l.split()[3])
                except Exception:
                    score = None
            elif l.startswith(("ATOM", "HETATM")):
                try:
                    atoms.append([int(l[6:11]), float(l[30:38]),
                                  float(l[38:46]), float(l[46:54])])
                except Exception:
                    errores.append(f"gate:geometria_rota(modelo_{idx})")
                    break
        if score is None:
            errores.append(f"gate:sin_remark(modelo_{idx})")
            continue
        if not math.isfinite(score):
            errores.append(f"gate:score_no_finito(modelo_{idx})")
            continue
        if not atoms:
            errores.append(f"gate:sin_atomos(modelo_{idx})")
            continue
        raw = "\n".join(bloque) + "\n" if bloque else ""
        modelos.append({"score": score, "atoms": atoms, "raw": raw})
    if errores:
        return {"ok": False, "n_models": n, "models": modelos,
                "errores": errores}
    return {"ok": True, "n_models": n, "models": modelos, "errores": []}


def cids_en_disco(pid: str) -> list:
    """cids con rigid.pdbqt en disco (ensemble ya preparado), ordenados."""
    d = WORK / pid
    if not d.exists():
        return []
    cids = []
    for f in sorted(d.glob("conf*.rigid.pdbqt")):
        try:
            cids.append(int(f.name.split("conf")[1].split(".")[0]))
        except Exception:
            continue
    return cids


# ───────────────────────── hashes de conformeros (smoke) ───────────────────

def hash_conformero(mh, cid: int) -> str:
    """sha256 de las coords 3D crudas (dobles little-endian) de TODOS los
    atomos del conformero — metodo identico al prefix_smoke.json (verificado
    contra su hash de 1aaq conf0 durante el pilot)."""
    conf = mh.GetConformer(cid)
    coords = []
    for i in range(mh.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        coords += [p.x, p.y, p.z]
    buf = struct.pack("<%dd" % (3 * mh.GetNumAtoms()), *coords)
    return hashlib.sha256(buf).hexdigest()


def generar_hashes_ensemble(pid: str) -> dict:
    """Regenera el ensemble ETKDG (seed 42, identico a preparar_complejo) y
    devuelve {cid: hash} — el ensemble es determinista (verificado en el
    smoke)."""
    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    crystal = mf.leer_ligando(sdf)
    if crystal is None:
        return {}
    mh, ids = mf.construir_ensemble(crystal, N_CONF)
    return {cid: hash_conformero(mh, cid) for cid in ids}


# ───────────────────────── preparacion por complejo ────────────────────────

def preparar(pid: str) -> dict:
    """Fase 1 (reusa mf.preparar_complejo) + patch de provenance a file_stem
    curve30 + persistencia de hashes de ensemble. Idempotente."""
    w = WORK / pid
    if not w.exists() or not (w / "rec.pdbqt").exists() or not cids_en_disco(pid):
        res = mf.preparar_complejo(pid, N_CONF, WORK, EXPERIMENT_ID)
        if not res.get("ok"):
            return res
    cids = cids_en_disco(pid)
    if not cids:
        return {"ok": False, "reason": "no_conformers", "t": 0.0}
    _asegurar_provenance_curve30(pid, cids)
    hashes_path = w / "ensemble_hashes.json"
    if not hashes_path.exists():
        hashes = generar_hashes_ensemble(pid)
        _atomic_write(hashes_path, {
            "pid": pid,
            "method": "sha256_struct_pack_d_3n_little_endian",
            "n_conf": len(hashes),
            "hashes": {str(c): h for c, h in hashes.items()},
        })
    return {"ok": True, "n_conf": len(cids), "cids": cids, "t": 0.0}


def _asegurar_provenance_curve30(pid: str, cids: list) -> None:
    """Patcha provenance.json: file_stem/key conf{cid}.out ->
    curve30_conf{cid}.out (identidad de la curva). El resto de los 14 campos
    canonicos no cambia."""
    w = WORK / pid
    prov_path = w / "provenance.json"
    registros = _json_load(prov_path, default=[])
    if not isinstance(registros, list):
        registros = [registros] if isinstance(registros, dict) else []
    patched = {}
    for r in registros:
        cid = r.get("conformer_id")
        stem = f"curve30_conf{cid}.out"
        r["file_stem"] = stem
        r["key"] = f"{pid}|molflex|{stem}"
        r["experiment_id"] = EXPERIMENT_ID
        patched[cid] = r
    # Si falta algun cid (resume sobre prep incompleto), regenerar desde cero.
    if any(c not in patched for c in cids):
        patched = {}
        center = _json_load(w / "center.json", default=None)
        created_at = _now_iso()
        for cid in cids:
            stem = f"curve30_conf{cid}.out"
            patched[cid] = {
                "key": f"{pid}|molflex|{stem}",
                "pid": pid,
                "source": "molflex",
                "file_stem": stem,
                "seed_conformer": mf.SEMILLA_ETKDG,
                "seed_docking": mf.SEMILLA_VINA,
                "conformer_id": cid,
                "exhaustiveness": mf.EXHAUSTIVENESS,
                "num_modes": mf.NUM_MODES,
                "box": {"center": center, "size": [mf.BOX_SIZE] * 3,
                        "method": "center_from_crystal_ligand"},
                "preparation": {
                    "ligand": {"method": "meeko_molecule_preparation_etkdg",
                               "tool": "meeko", "version": mf.VERSION_MEEKO},
                    "receptor": {"protonation": "pdb_original",
                                 "tool": "openbabel_pdb2pdbqt_rigido"},
                },
                "engine": {"name": "vina", "version": mf.version_vina()},
                "experiment_id": EXPERIMENT_ID,
                "created_at": created_at,
            }
    _atomic_write(prov_path, [patched[c] for c in cids])


# ───────────────────────── docking (worker + flujo) ────────────────────────

def _finalizar_dock(pid: str, cid: int, r: dict) -> dict:
    """Renombra conf{cid}.out.pdbqt -> curve30_conf{cid}.out.pdbqt y aplica
    el gate corregido sobre el ARCHIVO (scores SOLO de REMARK VINA RESULT;
    1 <= n_models <= 9; nunca la tabla stdout). Devuelve r con
    n_models_emitted/mode_scores si ok, o reason del gate."""
    if not r.get("ok"):
        return r
    w = WORK / pid
    out = w / f"conf{cid}.out.pdbqt"
    dst = w / f"curve30_conf{cid}.out.pdbqt"
    try:
        out.replace(dst)
    except Exception:
        pass
    parsed = parse_vina_output(dst.read_text(encoding="utf-8"))
    if parsed["ok"]:
        r["n_models_emitted"] = parsed["n_models"]
        r["mode_scores"] = [m["score"] for m in parsed["models"]]
        return r
    r["ok"] = False
    r["gate"] = parsed["errores"]
    r["reason"] = parsed["errores"][0] if parsed["errores"] else "gate:invalido"
    return r


def _anotar_emision(pid: str, cid: int, n_models_emitted: int) -> None:
    """Anota en provenance.json (por corrida) los campos de la enmienda:
    num_modes_requested=9 y n_models_emitted (solo en el proceso principal,
    tras el dock, para evitar escrituras concurrentes)."""
    prov_path = WORK / pid / "provenance.json"
    registros = _json_load(prov_path, default=[])
    if not isinstance(registros, list):
        return
    for r in registros:
        if r.get("conformer_id") == cid:
            r["num_modes_requested"] = NUM_MODES
            r["n_models_emitted"] = n_models_emitted
    _atomic_write(prov_path, registros)


def _dock_worker(payload: tuple) -> dict:
    """Worker del pool: 1 dock = 1 invocacion Vina (cpu=1), con mapas si se
    indican; si no, receptor fresco."""
    pid, cid, maps_prefix = payload
    r = mf.dock_rigido_archivo(pid, cid, WORK, cpu=CPU, maps_prefix=maps_prefix)
    return _finalizar_dock(pid, cid, r)


def _dock_writemaps(pid: str, cid: int, maps_prefix: str) -> dict:
    """Primer dock del complejo: --write_maps + --force_even_voxels (el
    escritor de mapas ES el dock del conformero). Secuencial en el proceso
    principal para que los mapas existan antes de paralelizar el resto."""
    r = mf.dock_rigido_archivo(pid, cid, WORK, cpu=CPU,
                               maps_prefix=maps_prefix, write_maps=True)
    return _finalizar_dock(pid, cid, r)


def _procesar_resultado(pid: str, res: dict, prog: dict, estrato: str) -> str:
    """Registra el resultado de un dock. Devuelve el reason si el resultado
    es una violacion de integridad del gate (para DETENER), o None."""
    cid = res.get("cid")
    complejo = prog["complexes"].setdefault(pid, {})
    docks = complejo.setdefault("docks", {})
    if res.get("ok"):
        docks[str(cid)] = "done"
        registrar_tiempo(pid, cid, estrato, res.get("t", 0.0))
        _anotar_emision(pid, cid, res.get("n_models_emitted", 0))
        return None
    reason = res.get("reason", "unknown")
    docks[str(cid)] = "failed"
    registrar_fallo(pid, cid, reason, res.get("t", 0.0))
    complejo.setdefault("failures", []).append(
        {"cid": cid, "reason": reason, "t": round(float(res.get("t", 0.0)), 1)})
    return reason if reason in GATE_INTEGRIDAD else None


def _validar_provenance_pid(pid: str) -> str | None:
    """Gate de ejecucion: provenance incorrecto -> DETENER. Devuelve el
    problema encontrado o None si los 14 campos canonicos, las semillas,
    el experiment_id y el file_stem/key son correctos."""
    prov = _json_load(WORK / pid / "provenance.json", default=[])
    if not isinstance(prov, list) or not prov:
        return "provenance_ausente"
    for r in prov:
        faltan = [f for f in FIELDS_CANONICOS if f not in r]
        if faltan:
            return f"provenance_campos_faltantes_{','.join(faltan)}"
        if r.get("experiment_id") != EXPERIMENT_ID:
            return "provenance_experiment_id_incorrecto"
        if r.get("seed_conformer") != 42 or r.get("seed_docking") != 42:
            return "provenance_semillas_incorrectas"
        stem = f"curve30_conf{r.get('conformer_id')}.out"
        if r.get("file_stem") != stem or r.get("key") != f"{pid}|molflex|{stem}":
            return "provenance_file_stem_key_incorrectos"
    return None


def _verificar_sistematico(prog: dict) -> bool:
    """Reglas de detencion: (a) todos los conformeros de un complejo fallan
    con el mismo motivo; (b) el mismo motivo en >=3 complejos. Devuelve True
    si hay que detenerse (escribe STOP.json)."""
    motivos_por_pid = {}
    for pid, c in prog["complexes"].items():
        motivos = {f["reason"] for f in c.get("failures", [])}
        n_total = len(c.get("docks", {}))
        n_fallidos = sum(1 for v in c.get("docks", {}).values() if v == "failed")
        if n_total > 0 and n_fallidos == n_total and len(motivos) == 1:
            motivo = next(iter(motivos))
            _atomic_write(STOP, {
                "ts": _now_iso(), "motivo": motivo,
                "tipo": "todos_los_conformeros_del_complejo",
                "pid": pid,
            })
            print(f"\n[STOP] Todos los conformeros de {pid} fallaron con el "
                  f"mismo motivo: {motivo}", file=sys.stderr)
            return True
        for m in motivos:
            motivos_por_pid.setdefault(m, set()).add(pid)
    for motivo, pids in motivos_por_pid.items():
        if len(pids) >= 3:
            _atomic_write(STOP, {
                "ts": _now_iso(), "motivo": motivo,
                "tipo": "mismo_error_en_3_o_mas_complejos",
                "pids": sorted(pids),
            })
            print(f"\n[STOP] Motivo '{motivo}' en >=3 complejos: "
                  f"{sorted(pids)}", file=sys.stderr)
            return True
    return False


def dockear_lote(prog: dict, pids: list, wall_budget: float) -> tuple:
    """Dockea los confs pendientes de los pids dados (resume). Devuelve
    (prog_actualizado, detener_por_presupuesto, detener_sistematico)."""
    deadline = time.monotonic() + wall_budget
    cohort = {r["pid"]: r for r in leer_cohort()}
    detener_presupuesto = False
    for pid in pids:
        if time.monotonic() > deadline - 30.0:
            detener_presupuesto = True
            break
        rec = cohort.get(pid, {})
        estrato = rec.get("stratum", "?")
        complejo = prog["complexes"].setdefault(pid, {
            "stratum": estrato, "cohort_id": rec.get("cohort_id", "?"),
            "pair_id": rec.get("pair_id", "?"), "docks": {},
        })
        prep = preparar(pid)
        if not prep.get("ok"):
            reason = prep.get("reason", "prep_failed")
            registrar_fallo(pid, None, reason, prep.get("t", 0.0))
            complejo["prep_failed"] = reason
            complejo["state"] = "failed_prep"
            guardar_progreso(prog)
            if _verificar_sistematico(prog):
                return prog, False, True
            continue
        # Gate de ejecucion: provenance incorrecto -> DETENER (enmienda 7).
        problema_prov = _validar_provenance_pid(pid)
        if problema_prov:
            _atomic_write(STOP, {"ts": _now_iso(), "motivo": problema_prov,
                                 "tipo": "provenance_incorrecto", "pid": pid})
            print(f"\n[STOP] Provenance incorrecto en {pid}: {problema_prov}",
                  file=sys.stderr)
            return prog, False, True
        cids = prep["cids"]
        fallidos = {int(c) for c, v in complejo.get("docks", {}).items()
                    if v == "failed"}
        pendientes = [c for c in cids
                      if c not in fallidos and not out_valido(pid, c)]
        if not pendientes:
            complejo["n_conf"] = len(cids)
            complejo["state"] = "completed"
            guardar_progreso(prog)
            continue
        maps_dir = WORK / pid / "maps"
        maps_prefix = str(maps_dir / "grid")
        hay_mapas = any(maps_dir.glob("*.map"))
        if not hay_mapas and 0 in pendientes:
            # Primer dock del complejo escribe los mapas (y ES el dock).
            # El directorio de mapas DEBE existir antes (Vina no lo crea:
            # sin el, --write_maps falla con rc=1 "could not open ... for
            # writing" — mismo requisito que ejecutar_complejo de molflex.py).
            maps_dir.mkdir(parents=True, exist_ok=True)
            r = _dock_writemaps(pid, 0, maps_prefix)
            integridad = _procesar_resultado(pid, r, prog, estrato)
            pendientes = [c for c in pendientes if c != 0]
            if integridad:
                _atomic_write(STOP, {"ts": _now_iso(), "motivo": integridad,
                                     "tipo": "violacion_gate_integridad",
                                     "pid": pid, "cid": 0})
                print(f"\n[STOP] Violacion de integridad del gate en {pid} "
                      f"conf0: {integridad}", file=sys.stderr)
                return prog, False, True
        if pendientes:
            hay_mapas = any((WORK / pid / "maps").glob("*.map"))
            payloads = [(pid, c, maps_prefix if hay_mapas else None)
                        for c in pendientes]
            with concurrent.futures.ProcessPoolExecutor(
                    max_workers=WORKERS) as ex:
                futuros = {ex.submit(_dock_worker, p): p for p in payloads}
                restantes = set(futuros)
                while restantes:
                    hecho, restantes = concurrent.futures.wait(
                        restantes, timeout=1.0,
                        return_when=concurrent.futures.FIRST_COMPLETED)
                    for f in hecho:
                        r = f.result()
                        integridad = _procesar_resultado(pid, r, prog, estrato)
                        if integridad:
                            _atomic_write(STOP, {"ts": _now_iso(),
                                                 "motivo": integridad,
                                                 "tipo": "violacion_gate_integridad",
                                                 "pid": pid,
                                                 "cid": r.get("cid")})
                            print(f"\n[STOP] Violacion de integridad del gate "
                                  f"en {pid} conf{r.get('cid')}: {integridad}",
                                  file=sys.stderr)
                            return prog, False, True
        sin_pendientes = not any(c not in fallidos and not out_valido(pid, c)
                                 for c in cids)
        if sin_pendientes:
            for f in maps_dir.glob("*.map"):
                try:
                    f.unlink()
                except Exception:
                    pass
        complejo["n_conf"] = len(cids)
        complejo["state"] = "completed" if sin_pendientes else "partial"
        guardar_progreso(prog)
        if _verificar_sistematico(prog):
            return prog, False, True
    guardar_progreso(prog)
    return prog, detener_presupuesto, False


# ───────────────────────── verificaciones ──────────────────────────────────

def verificar_identity_check() -> dict:
    """Las identidades curve30_* no colisionan con historicos (FND-06 /
    MF-01-UNION). Solo lectura."""
    res = {"fnd06_hits": 0, "union_hits": 0, "veredicto": True}
    sidecar = PROJECT_ROOT / "scripts" / "artifacts_science" / "FND-06" / \
        "poses_provenance.jsonl"
    for line in sidecar.read_text(encoding="utf-8").splitlines():
        if "curve30" in line:
            res["fnd06_hits"] += 1
    for split in ("train", "val"):
        f = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-01-UNION" / \
            f"union_candidates_{split}.jsonl"
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if "curve30" in rec.get("identity", "") or \
                    "curve30" in rec.get("file_stem", ""):
                res["union_hits"] += 1
    res["veredicto"] = res["fnd06_hits"] == 0 and res["union_hits"] == 0
    return res


def verificar_pilot(pids: list) -> int:
    """Verificaciones del pilot, punto por punto. Exit 0 = todo OK."""
    fallos = []
    print("── Verificacion de identidad (colision con historicos) ──")
    ident = verificar_identity_check()
    print(json.dumps(ident, indent=2))
    if not ident["veredicto"]:
        fallos.append("colision de identidades curve30 con historicos")

    smoke = _json_load(SMOKE, default={})
    for pid in pids:
        print(f"── Pilot {pid} ──")
        w = WORK / pid
        prov = _json_load(w / "provenance.json", default=[])
        if not isinstance(prov, list) or not prov:
            fallos.append(f"{pid}: provenance.json ausente/invalido")
            continue
        prov_ok = True
        for r in prov:
            faltan = [f for f in FIELDS_CANONICOS if f not in r]
            if faltan:
                fallos.append(f"{pid}: provenance campos faltantes {faltan}")
                prov_ok = False
            if r.get("experiment_id") != EXPERIMENT_ID:
                fallos.append(f"{pid}: experiment_id incorrecto "
                              f"{r.get('experiment_id')}")
                prov_ok = False
            if r.get("seed_conformer") != 42 or r.get("seed_docking") != 42:
                fallos.append(f"{pid}: semillas incorrectas "
                              f"{r.get('seed_conformer')}/{r.get('seed_docking')}")
                prov_ok = False
            if r.get("file_stem") != f"curve30_conf{r['conformer_id']}.out":
                fallos.append(f"{pid}: file_stem inconsistente {r.get('file_stem')}")
                prov_ok = False
        print(f"  provenance: {len(prov)} registros, 14 campos, "
              f"experiment_id {EXPERIMENT_ID}, seeds 42/42 -> "
              f"{'OK' if prov_ok else 'FALLA'}")
        hashes_disco = _json_load(w / "ensemble_hashes.json", default={})
        disc = {int(c): h for c, h in hashes_disco.get("hashes", {}).items()}
        en_smoke = smoke.get("ligandos", {}).get(pid)
        if en_smoke:
            smoke_hashes = en_smoke["runs"]["30"]["hashes"]
            smoke_ids = en_smoke["runs"]["30"]["ids"]
            ok = (len(disc) == len(smoke_ids)
                  and all(disc.get(c) == h for c, h in zip(smoke_ids, smoke_hashes)))
            print(f"  seed vs smoke ({len(smoke_ids)} confs): "
                  f"{'IDENTICO' if ok else 'MISMATCH'}")
            if not ok:
                fallos.append(f"{pid}: hashes de conformeros != prefix_smoke")
        else:
            print("  seed vs smoke: ligando no esta en el smoke -> se exige "
                  "determinismo por 2 regeneraciones")
        regen1 = generar_hashes_ensemble(pid)
        regen2 = generar_hashes_ensemble(pid)
        det = regen1 == regen2 == disc
        print(f"  determinismo (2 regeneraciones vs disco): "
              f"{'IDENTICO' if det else 'MISMATCH'}")
        if not det:
            fallos.append(f"{pid}: determinismo de conformeros roto")
        cids = sorted(disc) or cids_en_disco(pid)
        n_ok = 0
        n_emitidos_total = 0
        distribucion = {}
        for cid in cids:
            p = w / f"curve30_conf{cid}.out.pdbqt"
            if not p.exists() or p.stat().st_size == 0:
                fallos.append(f"{pid}: salida conf{cid} ausente/vacia")
                continue
            parsed = parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                fallos.append(f"{pid}: conf{cid} gate corregido FALLA: "
                              f"{parsed['errores']}")
                continue
            n = parsed["n_models"]
            distribucion[n] = distribucion.get(n, 0) + 1
            n_emitidos_total += n
            n_ok += 1
        print(f"  geometrias (gate corregido): {n_ok}/{len(cids)} docks "
              f"validos, 1<={n_emitidos_total}<=9, scores REMARK finitos")
        print(f"  distribucion n_models_emitted: {dict(sorted(distribucion.items()))}")
        prov_emit_ok = True
        for cid in cids:
            p = w / f"curve30_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            rec = next((r for r in prov if r.get("conformer_id") == cid), {})
            if rec.get("num_modes_requested") != NUM_MODES or \
                    rec.get("n_models_emitted") != parsed["n_models"]:
                fallos.append(f"{pid}: conf{cid} provenance sin "
                              f"num_modes_requested/n_models_emitted correctos")
                prov_emit_ok = False
        print(f"  provenance por corrida (num_modes_requested=9 / "
              f"n_models_emitted): {'OK' if prov_emit_ok else 'FALLA'}")
        identidades = set()
        for cid in cids:
            p = w / f"curve30_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            for m in range(parsed["n_models"]):
                identidades.add(identidad_pose(pid, cid, m))
        print(f"  mapeo identidad: {len(identidades)} identidades unicas, "
              f"solo modelos emitidos (esperado {n_emitidos_total})")
        if len(identidades) != n_emitidos_total:
            fallos.append(f"{pid}: identidades != modelos emitidos")
    if fallos:
        print(f"\n[PILOT FALLIDO] {len(fallos)} problemas:")
        for f in fallos[:20]:
            print("  -", f)
        return 1
    print("\n[PILOT OK] seed/provenance/geometrias/mapeo verificados")
    return 0


def verificar_confs(pids: list) -> int:
    """Determinismo parcial: regenera el ensemble de cada pid y compara
    hashes con los guardados en el work dir."""
    ok_total = True
    for pid in pids:
        w = WORK / pid
        disc = _json_load(w / "ensemble_hashes.json", default={})
        hashes_disco = {int(c): h for c, h in disc.get("hashes", {}).items()}
        if not hashes_disco:
            print(f"{pid}: sin hashes guardados en work dir")
            ok_total = False
            continue
        regen = generar_hashes_ensemble(pid)
        igual = regen == hashes_disco
        print(f"{pid}: regeneracion vs work dir "
              f"{'IDENTICA' if igual else 'DISTINTA'} ({len(regen)} confs)")
        ok_total = ok_total and igual
    return 0 if ok_total else 1


# ───────────────────────── consolidacion ───────────────────────────────────

def _parsear_modos(pid: str, cid: int):
    """Devuelve los modelos EMITIDOS (gate corregido) de la salida curve30:
    [{"score": float, "atoms": [[serial,x,y,z], ...]}, ...] o None si invalida."""
    p = WORK / pid / f"curve30_conf{cid}.out.pdbqt"
    if not p.exists():
        return None
    parsed = parse_vina_output(p.read_text(encoding="utf-8"))
    if not parsed["ok"]:
        return None
    return parsed["models"]


def _cargar_fallos_raw() -> list:
    if not FAILURES_WORK.exists():
        return []
    out = []
    for line in FAILURES_WORK.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _particionar_fallos(cohort: list) -> dict:
    """Particiona los fallos del work dir bajo la enmienda auditada:
      - mode_count_mismatch del gate anterior que HOY es valido (1<=n<=9,
        score finito) -> DESVIACION (fuera del ITT, tiempo medido recuperado);
      - (pid,cid) reintentado (retry tecnico documentado) y ahora valido ->
        TECHNICAL RETRY resuelto (no cuenta como fracaso cientifico);
      - resto -> ITT.
    Tambien recupera los tiempos ya medidos a dock_times.jsonl y reclasifica
    progress.json (failed -> done)."""
    estratos = {r["pid"]: r["stratum"] for r in cohort}
    fallos_raw = _cargar_fallos_raw()
    retried = {}
    if RETRY_LOG.exists():
        for line in RETRY_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            for c in e.get("cids", []):
                retried[(e["pid"], int(c))] = e.get("ts")
    times_existentes = set()
    if DOCK_TIMES.exists():
        for line in DOCK_TIMES.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                times_existentes.add((d["pid"], d["cid"]))
            except Exception:
                continue

    def recuperar_tiempo(pid, cid, t):
        if t is None or (pid, cid) in times_existentes:
            return
        registrar_tiempo(pid, cid, estratos.get(pid, "?"), t)
        times_existentes.add((pid, cid))

    desviaciones = []
    retries = []
    itt = []
    reclasificados = set()
    for f in fallos_raw:
        pid, cid = f["pid"], f.get("cid")
        clave = (pid, cid) if cid is not None else None
        if f.get("reason") == "mode_count_mismatch" and clave and out_valido(pid, cid):
            parsed = parse_vina_output(
                (WORK / pid / f"curve30_conf{cid}.out.pdbqt").read_text(encoding="utf-8"))
            desviaciones.append({
                "ts_original": f.get("ts"),
                "ts_reclasificacion": _now_iso(),
                "pid": pid, "cid": cid,
                "t_medido_s": f.get("t"),
                "motivo_original": "mode_count_mismatch",
                "tipo": "falso_fallo_gate_anterior_pilot",
                "n_models_emitted": parsed["n_models"],
            })
            recuperar_tiempo(pid, cid, f.get("t"))
            reclasificados.add(clave)
            continue
        if clave and clave in retried and out_valido(pid, cid):
            retries.append({
                "ts_original": f.get("ts"),
                "ts_reintento": retried[clave],
                "ts_reclasificacion": _now_iso(),
                "pid": pid, "cid": cid,
                "motivo_original": f.get("reason"),
                "resultado": "resuelto",
            })
            reclasificados.add(clave)
            continue
        itt.append(f)
    if reclasificados:
        prog = cargar_progreso()
        for pid, cid in reclasificados:
            c = prog.get("complexes", {}).get(pid, {})
            docks = c.setdefault("docks", {})
            if docks.get(str(cid)) == "failed":
                docks[str(cid)] = "done"
        guardar_progreso(prog)
    return {"desviaciones": desviaciones, "technical_retries": retries,
            "itt": itt, "reclasificados": sorted(str(p) + "|" + str(c)
                                                 for p, c in reclasificados)}


def consolidar() -> int:
    """Construye los artefactos finales en scripts/artifacts_science/D-MF-HARD-CURVE/."""
    cohort = leer_cohort("train")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    particion = _particionar_fallos(cohort)
    failures = particion["itt"]
    poses = []
    provenances = []
    per_complex = []
    modos_por_corrida = {"hard": [], "control": []}
    for rec in cohort:
        pid = rec["pid"]
        estrato = rec["stratum"]
        w = WORK / pid
        prov = _json_load(w / "provenance.json", default=[])
        prov_por_cid = {r["conformer_id"]: r for r in prov} \
            if isinstance(prov, list) else {}
        hashes_disco = _json_load(w / "ensemble_hashes.json", default={})
        disc = {int(c): h for c, h in hashes_disco.get("hashes", {}).items()}
        cids = sorted(disc) or cids_en_disco(pid)
        cids_validos = [c for c in cids if out_valido(pid, c)]
        if not cids_validos:
            per_complex.append({"pid": pid, "stratum": estrato,
                                "cohort_id": rec["cohort_id"],
                                "pair_id": rec["pair_id"],
                                "yield_30": 0, "n_conf_5": 0, "n_conf_15": 0,
                                "n_conf_30": 0, "prefijos": {},
                                "motivo": "sin_docks_validos"})
            continue
        crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = mf.cargar_mapa_indices(w)
        prefijos_por_complejo = {K: [] for K in PREFIJOS}
        for cid in cids_validos:
            modelos = _parsear_modos(pid, cid)
            if modelos is None:
                continue
            n_emitidos = len(modelos)
            modos_por_corrida[estrato].append(n_emitidos)
            prov_cid = prov_por_cid.get(cid, {})
            if prov_cid and (prov_cid.get("n_models_emitted") != n_emitidos
                             or prov_cid.get("num_modes_requested") != NUM_MODES):
                _anotar_emision(pid, cid, n_emitidos)
                prov_cid["n_models_emitted"] = n_emitidos
                prov_cid["num_modes_requested"] = NUM_MODES
            for m_idx, modelo in enumerate(modelos):
                score = modelo["score"]
                atoms = modelo["atoms"]
                por_mol = mf.coords_pose_a_por_mol(atoms, serial_a_mol)
                rmsd = mf.rmsd_pose_pocket(crystal, por_mol) if por_mol else None
                poses.append({
                    "identity": identidad_pose(pid, cid, m_idx),
                    "split": "train",
                    "pid": pid,
                    "source": "molflex",
                    "file_stem": f"curve30_conf{cid}.out",
                    "model_idx": m_idx,
                    "vina_score": score,
                    "prefix": [K for K in PREFIJOS if cid < K],
                    "conformer_id": cid,
                    "rmsd_pose_pocket": round(rmsd, 3) if rmsd is not None else None,
                    "seed_conformer": prov_cid.get("seed_conformer"),
                    "seed_docking": prov_cid.get("seed_docking"),
                    "exhaustiveness": prov_cid.get("exhaustiveness"),
                    "num_modes": prov_cid.get("num_modes"),
                    "num_modes_requested": NUM_MODES,
                    "n_models_emitted": n_emitidos,
                    "box": prov_cid.get("box"),
                    "provenance_key": prov_cid.get("key"),
                })
                if rmsd is not None:
                    for K in PREFIJOS:
                        if cid < K:
                            prefijos_por_complejo[K].append(rmsd)
            if prov_cid:
                prov_cid["n_conf"] = len(cids_validos)
                provenances.append(prov_cid)
        per_complex.append({
            "pid": pid, "stratum": estrato,
            "cohort_id": rec["cohort_id"], "pair_id": rec["pair_id"],
            "yield_30": len(cids_validos),
            "n_conf_5": len([c for c in cids_validos if c < 5]),
            "n_conf_15": len([c for c in cids_validos if c < 15]),
            "n_conf_30": len(cids_validos),
            "prefijos": {str(K): {
                "min_rmsd": round(min(v), 3) if v else None,
                "cubierto": min(v) <= UMBRAL_COBERTURA if v else False,
            } for K, v in prefijos_por_complejo.items()},
        })
    with open(ARTIFACTS / "curve_poses_train.jsonl", "w", encoding="utf-8") as fh:
        for p in poses:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "curve_provenance.jsonl", "w", encoding="utf-8") as fh:
        for r in provenances:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "failures.jsonl", "w", encoding="utf-8") as fh:
        for f in failures:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "deviations.jsonl", "w", encoding="utf-8") as fh:
        for d in particion["desviaciones"]:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "technical_retries.jsonl", "w", encoding="utf-8") as fh:
        for t in particion["technical_retries"]:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(ARTIFACTS / "per_complex.jsonl", "w", encoding="utf-8") as fh:
        for r in per_complex:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metricas = _calcular_metricas(cohort, poses, per_complex, failures,
                                  particion, modos_por_corrida)
    _atomic_write(ARTIFACTS / "metrics.json", metricas)
    _escribir_design(metricas, len(poses), len(failures))
    print(f"Consolidacion: {len(poses)} poses, {len(provenances)} corridas, "
          f"{len(failures)} fallos ITT, "
          f"{len(particion['desviaciones'])} desviaciones (falsos fallos del "
          f"gate anterior), {len(particion['technical_retries'])} retries "
          f"tecnicos resueltos")
    print(json.dumps({"k_elegido": metricas.get("decision", {}).get("k_elegido"),
                      "razones": metricas.get("decision", {}).get("razones")},
                     indent=2, ensure_ascii=False))
    return 0


def _calc_tiempos(docks: list) -> dict:
    """P50/P90 wall y CPU por dock (CPU = wall x cpu=1)."""
    if not docks:
        return {"n": 0, "wall_p50": None, "wall_p90": None,
                "cpu_p50": None, "cpu_p90": None}
    ts = sorted(float(d["t"]) for d in docks)
    def pct(q):
        k = (len(ts) - 1) * q
        lo = int(k)
        hi = min(lo + 1, len(ts) - 1)
        return round(ts[lo] + (ts[hi] - ts[lo]) * (k - lo), 2)
    return {"n": len(ts), "wall_p50": pct(0.5), "wall_p90": pct(0.9),
            "cpu_p50": pct(0.5), "cpu_p90": pct(0.9),
            "nota": "cpu = wall x 1 (cpu=1 por Vina)"}


def _pct(vals: list, q: float):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _phi_inv(p: float) -> float:
    """Cuantil normal (aproximacion de Acklam), stdlib."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _bootstrap_bca_pareado(deltas: list, n: int = N_BOOT,
                           seed: int = SEED_BOOT) -> dict:
    """Bootstrap pareado BCa (INFORMATIVO) de la media de deltas. stdlib.
    p bilateral = 2*min(P(media* <= 0), P(media* >= 0))."""
    if len(deltas) < 2:
        return {"n": len(deltas), "error": "insuficientes_pares"}
    rng = random.Random(seed)
    media_obs = sum(deltas) / len(deltas)
    medias = []
    for _ in range(n):
        muestra = [rng.choice(deltas) for _ in range(len(deltas))]
        medias.append(sum(muestra) / len(muestra))
    medias.sort()
    jk = []
    for i in range(len(deltas)):
        resto = deltas[:i] + deltas[i + 1:]
        jk.append(sum(resto) / len(resto))
    media_jk = sum(jk) / len(jk)
    num = sum((media_jk - x) ** 3 for x in jk)
    den = sum((media_jk - x) ** 2 for x in jk) ** 1.5
    a = num / (6 * den) if den > 0 else 0.0
    z0 = _phi_inv(sum(1 for m in medias if m < media_obs) / n)
    alfa = 0.025
    z_alfa = _phi_inv(alfa)
    def bc_alpha(p):
        z = _phi_inv(p)
        t = z0 + (z0 + z) / (1 - a * (z0 + z))
        return max(0.0, min(1.0, _norm_cdf(t)))
    lo_q, hi_q = bc_alpha(alfa), bc_alpha(1 - alfa)
    lo = medias[max(0, min(n - 1, int(lo_q * n)))]
    hi = medias[max(0, min(n - 1, int(hi_q * n)))]
    p_bil = 2 * min(sum(1 for m in medias if m <= 0) / n,
                    sum(1 for m in medias if m >= 0) / n)
    return {"n_pares": len(deltas), "media_delta": round(media_obs, 4),
            "ci95_bca": [round(lo, 4), round(hi, 4)],
            "p_bilateral": round(p_bil, 4),
            "metodo": f"bootstrap_pareado_BCa_n{n}_seed{seed}_informativo"}


def _calcular_metricas(cohort: list, poses: list, per_complex: list,
                       failures: list, particion: dict | None = None,
                       modos_por_corrida: dict | None = None) -> dict:
    docks = []
    if DOCK_TIMES.exists():
        for line in DOCK_TIMES.read_text(encoding="utf-8").splitlines():
            try:
                docks.append(json.loads(line))
            except Exception:
                continue
    t_hard = _calc_tiempos([d for d in docks if d.get("stratum") == "hard"])
    t_control = _calc_tiempos([d for d in docks if d.get("stratum") == "control"])
    t_all = _calc_tiempos(docks)

    por_estrato = {}
    pc = {r["pid"]: r for r in per_complex}
    for estrato in ("hard", "control"):
        ids_estr = [r["pid"] for r in cohort if r["stratum"] == estrato]
        por_prefijo = {}
        for K in PREFIJOS:
            rmsds, cubiertos = [], 0
            for pid in ids_estr:
                r = pc.get(pid, {})
                p = r.get("prefijos", {}).get(str(K), {})
                if p.get("min_rmsd") is not None:
                    rmsds.append(p["min_rmsd"])
                    cubiertos += int(p["cubierto"])
            n_con_min_rmsd = len(rmsds)
            por_prefijo[str(K)] = {
                "n_complejos": len(ids_estr),
                "n_con_poses": n_con_min_rmsd,
                "cobertura": round(cubiertos / n_con_min_rmsd, 4) if n_con_min_rmsd else None,
                "n_cubiertos": cubiertos,
                "mediana_min_rmsd": round(_pct(rmsds, 0.5), 3) if rmsds else None,
                "degeneracion_yield_lt_k": sum(
                    1 for pid in ids_estr
                    if pc.get(pid, {}).get("n_conf_30", 0) < K),
            }
        por_estrato[estrato] = por_prefijo
    pareadas = {}
    for a, b in ((5, 15), (15, 30)):
        deltas = []
        for r in per_complex:
            pa = r.get("prefijos", {}).get(str(a), {})
            pb = r.get("prefijos", {}).get(str(b), {})
            if pa.get("min_rmsd") is not None and pb.get("min_rmsd") is not None:
                deltas.append(round(pb["min_rmsd"] - pa["min_rmsd"], 3))
        pareadas[f"{a}_{b}"] = {
            "n_pares": len(deltas),
            "delta_mediana": round(_pct(deltas, 0.5), 3) if deltas else None,
            "delta_media": round(sum(deltas) / len(deltas), 3) if deltas else None,
            "bootstrap": _bootstrap_bca_pareado(deltas),
        }
    por_estrato_cohort = {r["pid"]: r["stratum"] for r in cohort}
    itt = {"hard": {"n": 0, "motivos": {}}, "control": {"n": 0, "motivos": {}}}
    for f in failures:
        e = por_estrato_cohort.get(f["pid"], "desconocido")
        itt.setdefault(e, {"n": 0, "motivos": {}})
        itt[e]["n"] += 1
        itt[e]["motivos"][f["reason"]] = itt[e]["motivos"].get(f["reason"], 0) + 1
    hard = por_estrato.get("hard", {})
    ctrl = por_estrato.get("control", {})
    k30_hard = hard.get("30", {})
    k30_ctrl = ctrl.get("30", {})
    numeros = {"k30": {"hard": k30_hard, "control": k30_ctrl}}
    k_elegido = 30
    razones = {}
    if k30_hard.get("mediana_min_rmsd") is not None:
        for K in (5, 15):
            kh = hard.get(str(K), {})
            kc = ctrl.get(str(K), {})
            perdidas_hard = max(0, k30_hard["n_cubiertos"] - kh.get("n_cubiertos", 0))
            perdidas_ctrl = max(0, k30_ctrl["n_cubiertos"] - kc.get("n_cubiertos", 0))
            deg_hard = max(0.0, (kh.get("mediana_min_rmsd") or 0.0)
                           - (k30_hard["mediana_min_rmsd"] or 0.0))
            deg_ctrl = max(0.0, (kc.get("mediana_min_rmsd") or 0.0)
                           - (k30_ctrl["mediana_min_rmsd"] or 0.0))
            cumple = (perdidas_hard <= 1 and deg_hard <= 0.1 and
                      perdidas_ctrl <= 1 and deg_ctrl <= 0.1)
            numeros[str(K)] = {
                "perdidas_hard_cubiertos": perdidas_hard,
                "deg_mediana_hard": round(deg_hard, 3),
                "perdidas_control_cubiertos": perdidas_ctrl,
                "deg_mediana_control": round(deg_ctrl, 3),
                "cumple": cumple,
            }
            razones[str(K)] = (
                f"K{K}: hard cubiertos {kh.get('n_cubiertos')}/{k30_hard['n_cubiertos']}"
                f" (pierde {perdidas_hard}), mediana {kh.get('mediana_min_rmsd')}"
                f" vs {k30_hard['mediana_min_rmsd']} (deg {deg_hard:.3f}); "
                f"control cubiertos {kc.get('n_cubiertos')}/{k30_ctrl['n_cubiertos']}"
                f" (pierde {perdidas_ctrl}), mediana {kc.get('mediana_min_rmsd')}"
                f" vs {k30_ctrl['mediana_min_rmsd']} (deg {deg_ctrl:.3f})")
            if cumple and k_elegido == 30:
                k_elegido = K
    desviaciones = particion.get("desviaciones", []) if particion else []
    retries = particion.get("technical_retries", []) if particion else []
    modos_emitidos = {}
    if modos_por_corrida:
        for estrato in ("hard", "control"):
            vals = modos_por_corrida.get(estrato, [])
            modos_emitidos[estrato] = {
                "n_corridas": len(vals),
                "mediana": round(_pct(vals, 0.5), 1) if vals else None,
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "distribucion": {str(k): vals.count(k) for k in sorted(set(vals))},
            }
    return {
        "experiment_id": EXPERIMENT_ID,
        "split": "train",
        "n_complejos": len(cohort),
        "n_poses": len(poses),
        "n_fallos_itt": len(failures),
        "por_estrato": por_estrato,
        "tiempos": {"hard": t_hard, "control": t_control, "total": t_all},
        "ganancias_pareadas": pareadas,
        "fallos_itt_por_estrato": itt,
        "gate": {
            "enmienda": "auditada_2026-08-16",
            "validez": "rc=0 + 1<=n_models_emitted<=9 + scores FINITOS de "
                       "REMARK VINA RESULT + geometria parseable",
            "scores": "exclusivamente_REMARK_VINA_RESULT_del_archivo",
            "num_modes_requested": NUM_MODES,
            "n_desviaciones_gate_anterior": len(desviaciones),
            "technical_retries": {
                "n_eventos": len(retries),
                "n_resueltos": sum(1 for r in retries
                                   if r.get("resultado") == "resuelto"),
            },
            "modos_emitidos": modos_emitidos,
        },
        "decision": {"k_elegido": k_elegido, "numeros": numeros,
                     "razones": razones,
                     "regla": "menor K en {5,15} vs 30 train: pierde <=1/17 hard "
                              "cubiertos, deg mediana hard <=0.1, pierde <=1 "
                              "control cubierto, deg mediana control <=0.1; "
                              "si ninguno -> 30"},
    }


def _escribir_design(metricas: dict, n_poses: int, n_fallos: int) -> None:
    d = metricas.get("decision", {})
    razones = "\n".join(f"- {v}" for v in d.get("razones", {}).values()) \
        or "- (sin datos)"
    texto = f"""# D-MF-HARD-CURVE — Curva MolFlex 5/15/30 (entregable 7) — DESIGN

**Fecha:** {datetime.now().strftime('%Y-%m-%d')}
**Rama:** experimentos/ruta-c-molflex
**Referencia:** docs/49 §15 entregable 7 (MF-02) + FORECAST.md (preregistro) +
D-MF-HARD/DESIGN.md (cohorte sellada). **NO sellado, NO finish** (instruccion
del maintainer: entregable ejecutado y documentado, sellado diferido).

## 1. Protocolo ejecutado

- Curva anidada: 30 conformeros ETKDG UNA vez por complejo (seed 42,
  pruneRmsThresh 0.4), docks por conformero (1 invocacion Vina = 9 modos).
  Prefijos {{0..4}} = K5, {{0..14}} = K15, {{0..29}} = K30 (anidamiento
  byte-idempotente verificado en FORECAST/prefix_smoke.json).
- Config: seed ETKDG=42, --seed 42 explicito en TODAS las invocaciones de
  Vina (SEMILLA_VINA de molflex.py, preregistro FND-06), box 25 A centrado en
  ligando cristalografico, exh=8, 9 modos, CPU=1 por Vina, 6 workers,
  Vina 1.2.7, timeout 240 s/dock, sin relax.
- Alcance: SOLO train (17 hard + 17 controles). Los 10 pids de val NO se
  dockearon ni evaluaron (cero val tocado; guardia dura en el runner +
  verificacion final).
- Generacion reusada de scripts/molflex.py (construir_ensemble,
  preparar_complejo, dock_rigido_archivo): cero reimplementacion manual de
  la config. La unica transformacion es el RENOMBRADO de la salida a
  curve30_conf{{cid}}.out.pdbqt (identidad de la curva; colision con
  historicos verificada = 0 en FND-06 y MF-01-UNION).

## 2. Decisiones de implementacion

- Identidad canonica por pose: train|pid|molflex|curve30_conf{{cid}}.out|model_idx
  — model_idx SOLO sobre modelos REALMENTE emitidos (gate corregido: Vina
  1.2.7 puede emitir 1..9 modelos por clustering de poses de salida; si
  emite 4, existen 4 identidades, nada de model_idx fantasma).
- GATE CORREGIDO (enmienda auditada 2026-08-16): validez = rc=0 + archivo no
  vacio + 1 <= n_models_emitted <= 9 + todos los modelos con score FINITO de
  REMARK VINA RESULT + geometria parseable. Scores EXCLUSIVAMENTE del
  archivo (nunca de la tabla stdout, que puede listar mas modos que el
  archivo). Por corrida: num_modes_requested=9 + n_models_emitted (en
  provenance.json y curve_provenance.jsonl).
- Resume idempotente por identidad: salida valida bajo el gate corregido ->
  salta; fallo -> ITT registrado en failures.jsonl, NO reintentado (reintento
  manual unico via --retry PID: retry TECNICO documentado en
  retry_log.jsonl / technical_retries.jsonl, contado en metrics; si pasa no
  cuenta como fracaso cientifico).
- Desviaciones: los falsos fallos del gate anterior del pilot
  (mode_count_mismatch, hoy validos) se reclasifican a deviations.jsonl
  FUERA del ITT, recuperando sus tiempos medidos.
- Mapas de grid transient (FORECAST §3.6): primer dock escribe mapas
  (--write_maps + --force_even_voxels, ES el dock del conf 0); el resto
  reutiliza (--maps); se borran al completar el complejo. Resume parcial sin
  mapas -> docks fresh (misma config nominal).
- Lotes con resume: --wall-budget 300 s por invocacion bash (<=10 min),
  progress.json con completados/pendientes/fallos entre lotes.
- DETENCION (enmienda 7) -> STOP.json + reporte, sin continuar: cero modelos
  emitidos, >9 modelos, score/geometria invalidos, provenance incorrecto
  (14 campos/semillas/experiment_id/file_stem), o fallos SISTEMATICOS
  (todos los conformeros de un complejo fallan con el mismo motivo, o el
  mismo motivo en >=3 complejos).
- Consolidacion separada del docking (--consolidate): los artefactos finales
  se reconstruyen desde el work dir; el docking nunca escribe en
  scripts/artifacts_science.

## 3. Metrica de pose y caveats

- rmsd_pose_pocket (molflex.py) sobre los modelos EMITIDOS de cada dock
  contra el ligando cristalografico data/pdbbind/{{pid}}/{{pid}}_ligand.sdf:
  compara coordenadas 1:1 EN EL MARCO DEL POCKET (sin alineamiento; el
  receptor es fijo). Caveat documentado: traslacion/rotacion de la pose no
  se compensan (esa es la intencion — mide si la pose esta en el sitio
  bioactivo, no solo si su geometria interna coincide). GetBestRMS queda
  excluido de esta metrica.
- Degeneracion por yield: controles poco flexibles rinden <30 confs (pruning
  RMSD 0.4); los prefijos 15/30 degeneran al ensemble completo. Documentado
  por complejo en per_complex.jsonl (n_conf_5/15/30 reales).
- Grid del dock que escribe mapas usa voxels pares (span 25.5 vs 25.125 A),
  side effect documentado en molflex.py (fix E2); el resto del complejo
  reutiliza ese grid. Config nominal box 25 identica en todos.
- Bootstrap BCa (n=2000, seed 42) es INFORMATIVO: no decide (FORECAST §6).

## 4. Resultados

- Poses train consolidadas: {n_poses}; fallos ITT: {n_fallos}.
- Regla de decision corregida (FORECAST.md, preregistrada): el menor
  K en {{5,15}} que frente a 30 en train pierda <=1/17 hard cubiertos, degrade
  la mediana min-RMSD hard <=0.1 A, no pierda >1 control cubierto ni degrade
  su mediana >0.1 A; si ninguno cumple -> 30.
- **K ELEGIDO: {d.get('k_elegido')}**
- Numeros de soporte:
{razones}
- Metricas completas: metrics.json (incluye gate: desviaciones y retries
  tecnicos, distribucion de n_models_emitted).

## 5. Archivos

| Archivo | Contenido |
|---|---|
| curve_poses_train.jsonl | una linea por pose (solo modelos emitidos), train |
| curve_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| metrics.json | cobertura/medianas/tiempos/fallos/ganancias/decision/gate |
| per_complex.jsonl | una linea por complejo con prefijos y degeneracion |
| failures.jsonl | fallos ITT (sin reintentos; reclasificados fuera) |
| deviations.jsonl | falsos fallos del gate anterior del pilot (fuera de ITT) |
| technical_retries.jsonl | retries tecnicos documentados |
| FORECAST.md / prefix_smoke.json | preregistro y smoke de prefijo (previos) |
"""
    _atomic_write(ARTIFACTS / "DESIGN.md", texto)


def backfill_emision(pids=None) -> int:
    """Backfill de la anotacion por corrida (enmienda 3): para cada dock
    VALIDO en disco cuya provenance no registre num_modes_requested /
    n_models_emitted, anota ambos campos desde la evidencia del archivo
    (parse_vina_output). Sin docking, idempotente."""
    pids = pids or [r["pid"] for r in leer_cohort("train")]
    n_anotados = 0
    for pid in pids:
        w = WORK / pid
        prov = _json_load(w / "provenance.json", default=[])
        if not isinstance(prov, list):
            continue
        por_cid = {r.get("conformer_id"): r for r in prov}
        for cid in sorted(int(k) for k in
                          (_json_load(w / "ensemble_hashes.json", default={})
                           .get("hashes", {}) or {})) or cids_en_disco(pid):
            p = w / f"curve30_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            r = por_cid.get(cid)
            if r is not None and (r.get("n_models_emitted") != parsed["n_models"]
                                  or r.get("num_modes_requested") != NUM_MODES):
                _anotar_emision(pid, cid, parsed["n_models"])
                n_anotados += 1
    print(f"Backfill de emision: {n_anotados} corridas anotadas "
          f"(num_modes_requested={NUM_MODES}, n_models_emitted desde disco)")
    return 0


def materializar_candidatos() -> int:
    """Artefacto candidato: una linea JSON por pose EMITIDA (4329 esperadas)
    con el bloque PDBQT individual (MODEL + REMARK VINA RESULT + atomos, sin
    mutar) extraido del .pdbqt de cada corrida. Determinista: lineas
    ordenadas por identity. Verifica identidades unicas, bloques no vacios y
    scores finitos."""
    out_path = ARTIFACTS / "curve_candidates_train.jsonl"
    registros = []
    cohort = leer_cohort("train")
    for rec in cohort:
        pid = rec["pid"]
        prov = _json_load(WORK / pid / "provenance.json", default=[])
        prov_por_cid = {r["conformer_id"]: r for r in prov} \
            if isinstance(prov, list) else {}
        hashes_disco = _json_load(WORK / pid / "ensemble_hashes.json", default={})
        disc = {int(c): h for c, h in hashes_disco.get("hashes", {}).items()}
        cids = sorted(disc) or cids_en_disco(pid)
        for cid in cids:
            p = WORK / pid / f"curve30_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            prov_cid = prov_por_cid.get(cid, {})
            for m_idx, modelo in enumerate(parsed["models"]):
                score = modelo["score"]
                raw = modelo["raw"]
                pdbqt = f"MODEL {m_idx + 1}\n{raw}ENDMDL\n"
                registros.append({
                    "identity": identidad_pose(pid, cid, m_idx),
                    "pid": pid,
                    "source": "molflex",
                    "file_stem": f"curve30_conf{cid}.out",
                    "model_idx": m_idx,
                    "conformer_id": cid,
                    "prefix": [K for K in PREFIJOS if cid < K],
                    "vina_score": score,
                    "provenance_key": prov_cid.get("key"),
                    "pdbqt": pdbqt,
                })
    registros.sort(key=lambda r: r["identity"])
    ids = [r["identity"] for r in registros]
    if len(set(ids)) != len(ids):
        print(f"[ERROR] identidades duplicadas: {len(ids) - len(set(ids))}",
              file=sys.stderr)
        return 1
    vacios = sum(1 for r in registros if not r["pdbqt"].strip())
    no_finitos = sum(1 for r in registros
                     if not math.isfinite(r["vina_score"]))
    if vacios or no_finitos:
        print(f"[ERROR] bloques vacios: {vacios}, scores no finitos: "
              f"{no_finitos}", file=sys.stderr)
        return 1
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    data = out_path.read_bytes()
    print(f"curve_candidates_train.jsonl: {len(registros)} lineas, "
          f"{len(data) / 1024 / 1024:.2f} MB, "
          f"sha256={hashlib.sha256(data).hexdigest()}")
    return 0


# ───────────────────────── CLI ─────────────────────────────────────────────

def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        description="Curva MolFlex 5/15/30 en D-MF-HARD train (entregable 7)")
    ap.add_argument("--pids", nargs="*", default=None,
                    help="restringe el lote a estos pids (pilot)")
    ap.add_argument("--wall-budget", type=float, default=WALL_BUDGET_DEFAULT,
                    help="segundos de presupuesto por invocacion (default 300)")
    ap.add_argument("--report", action="store_true", help="resumen de progreso")
    ap.add_argument("--check-pilot", nargs="+", metavar="PID",
                    help="verificaciones del pilot sobre esos pids")
    ap.add_argument("--verify-confs", nargs="+", metavar="PID",
                    help="determinismo parcial de conformeros")
    ap.add_argument("--identity-check", action="store_true",
                    help="verifica no colision de identidades curve30")
    ap.add_argument("--consolidate", action="store_true",
                    help="construye artefactos finales")
    ap.add_argument("--retry", metavar="PID",
                    help="reintento manual unico de confs fallidos (documentado)")
    ap.add_argument("--backfill-emision", action="store_true",
                    help="anota num_modes_requested/n_models_emitted desde disco")
    ap.add_argument("--materialize-candidates", action="store_true",
                    help="materializa geometrias PDBQT crudas por pose emitida")
    args = ap.parse_args()

    if args.identity_check:
        print(json.dumps(verificar_identity_check(), indent=2))
        return 0
    if args.check_pilot:
        return verificar_pilot(args.check_pilot)
    if args.verify_confs:
        return verificar_confs(args.verify_confs)
    if args.consolidate:
        return consolidar()
    if args.report:
        return reportar()
    if args.retry:
        return reintentar(args.retry)
    if args.backfill_emision:
        return backfill_emision()
    if args.materialize_candidates:
        return materializar_candidatos()

    cohort = leer_cohort("train")
    pids = args.pids if args.pids else [r["pid"] for r in cohort]
    val_fuera = [p for p in pids if p in VAL_PIDS]
    if val_fuera:
        print(f"[STOP] pids de val rechazados: {val_fuera}", file=sys.stderr)
        return 2
    if not pids:
        print("Sin pids train pendientes.", file=sys.stderr)
        return 1
    prog = cargar_progreso()
    if STOP.exists():
        print(f"[STOP] STOP.json presente: "
              f"{STOP.read_text(encoding='utf-8')[:200]}", file=sys.stderr)
        return 2
    t0 = time.monotonic()
    prog, detener_presupuesto, sistematico = dockear_lote(
        prog, pids, args.wall_budget)
    guardar_progreso(prog)
    if sistematico:
        return 2
    print(f"Lote terminado en {time.monotonic()-t0:.0f}s"
          f"{' (presupuesto agotado)' if detener_presupuesto else ''}")
    return 0


def reportar() -> int:
    prog = cargar_progreso()
    complejos = prog.get("complexes", {})
    cohort = {r["pid"]: r for r in leer_cohort("train")}
    completados = parciales = prep_fallidos = 0
    n_done = n_failed = 0
    lineas = []
    for pid, c in sorted(complejos.items(),
                         key=lambda kv: kv[1].get("cohort_id", kv[0])):
        docks = c.get("docks", {})
        done = sum(1 for v in docks.values() if v == "done")
        failed = sum(1 for v in docks.values() if v == "failed")
        estr = c.get("stratum", "?")
        state = c.get("state", "partial")
        if state == "completed":
            completados += 1
        elif state == "failed_prep":
            prep_fallidos += 1
        else:
            parciales += 1
        n_done += done
        n_failed += failed
        lineas.append(f"  {c.get('cohort_id','?'):>4} {pid} {estr:<7} {state:<11} "
                      f"done={done} failed={failed}")
    pend_sin_estado = [r["pid"] for r in cohort.values() if r["pid"] not in complejos]
    print(f"Complejos: {completados} completados, {parciales} parciales, "
          f"{prep_fallidos} prep_failed, {len(pend_sin_estado)} sin empezar")
    print(f"Docks: {n_done} done, {n_failed} failed")
    for l in lineas:
        print(l)
    if pend_sin_estado:
        print(f"Sin empezar: {pend_sin_estado}")
    return 0


def reintentar(pid: str) -> int:
    """Reintento manual unico: limpia los marcadores de fallo del complejo y
    lo reencola. Documentado en retry_log.jsonl (retry TECNICO, contado en
    metrics.technical_retries)."""
    prog = cargar_progreso()
    c = prog.get("complexes", {}).get(pid)
    if not c:
        print(f"{pid}: sin estado previo")
        return 1
    cids_fallidos = sorted(int(k) for k, v in c.get("docks", {}).items()
                           if v == "failed")
    if not cids_fallidos:
        print(f"{pid}: sin confs fallidos")
        return 0
    c["docks"] = {k: v for k, v in c.get("docks", {}).items() if v != "failed"}
    c["failures"] = []
    c["state"] = "partial"
    c["retried_once"] = True
    guardar_progreso(prog)
    with open(RETRY_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _now_iso(), "pid": pid,
                             "cids": cids_fallidos,
                             "n_conf_reencolados": len(cids_fallidos)},
                            ensure_ascii=False) + "\n")
    print(f"{pid}: {len(cids_fallidos)} confs fallidos reencolados "
          f"(retry tecnico unico documentado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
