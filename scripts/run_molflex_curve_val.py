# -*- coding: utf-8 -*-
"""
run_molflex_curve_val.py — Runner de la validacion UNICA de val con K=15
(entregable 7, fase val).

IMPORTANTE (decision de implementacion documentada): el sello train
(f31bfeb) incluye scripts/run_molflex_curve.py como asset con hash sellado.
Por eso este runner NO edita el modulo train: lo importa y MONKEYPATCHEA
(reasigna constantes de modulo y envuelve solo las funciones con strings
hardcodeados de train: file_stem curve30 -> curve15, split train -> val).
El gate corregido (parse_vina_output) y todo el flujo de docking (preparar,
dock_rigido_archivo via _dock_worker/_dock_writemaps, dockear_lote, resume,
lotes con --wall-budget) se REUSAN sin modificacion.

DIFERENCIAS vs train (autorizadas por el maintainer):
  - N_CONF = 15 (el ensemble de 15 es el prefijo exacto del de 30 — propiedad
    verificada en FORECAST/prefix_smoke.json).
  - split = val (10 pids: 5 hard + 5 controles del cohort D-MF-HARD sellado).
  - file_stem curve15_conf{cid}.out; identidades val|pid|molflex|...
  - PREFIJOS = [15] (solo K15; K30 NO se abre, K NO cambia por el resultado).
  - WORK dir: data/dmfhard_curve_work/val/ (dentro del work dir train ya
    gitignored; .gitignore NO modificado).
  - Consolidacion descriptiva propia (n=5 sin potencia, Wilson CI 95%,
    SIN regla de decision).

Modos: lote default (resume), --wall-budget, --report, --consolidate,
--verify-confs, --backfill-emision, --materialize-candidates, --retry.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import run_molflex_curve as rmc  # noqa: E402
import molflex as mf  # noqa: E402

# ─────────────────── reasignacion de constantes de modulo ──────────────────

rmc.EXPERIMENT_ID = "D-MF-HARD-CURVE-VAL"
rmc.N_CONF = 15
rmc.PREFIJOS = [15]
rmc.WORK = PROJECT_ROOT / "data" / "dmfhard_curve_work" / "val"
rmc.ARTIFACTS = PROJECT_ROOT / "scripts" / "artifacts_science" / "D-MF-HARD-CURVE-VAL"
rmc.PROGRESS = rmc.WORK / "progress.json"
rmc.FAILURES_WORK = rmc.WORK / "failures.jsonl"
rmc.DOCK_TIMES = rmc.WORK / "dock_times.jsonl"
rmc.RETRY_LOG = rmc.WORK / "retry_log.jsonl"
rmc.STOP = rmc.WORK / "STOP.json"
rmc.VAL_PIDS = set()  # en modo val estos pids SON el objetivo; guardia propia abajo

STEM_VAL = "curve15"
SPLIT_VAL = "val"

_LEER_COHORT_ORIG = rmc.leer_cohort
TRAIN_PIDS = {r["pid"] for r in _LEER_COHORT_ORIG("train")}


# ─────────────────── monkeypatch de funciones train-hardcodeadas ───────────

def _leer_cohort_val(split: str = "train") -> list:
    return _LEER_COHORT_ORIG(SPLIT_VAL if split == "train" else split)


def _out_valido_val(pid: str, cid: int) -> bool:
    p = rmc.WORK / pid / f"{STEM_VAL}_conf{cid}.out.pdbqt"
    if not p.exists():
        return False
    try:
        return rmc.parse_vina_output(p.read_text(encoding="utf-8"))["ok"]
    except Exception:
        return False


def _identidad_val(pid: str, cid: int, model_idx: int,
                   split: str | None = None) -> str:
    s = split if split is not None else SPLIT_VAL
    return f"{s}|{pid}|molflex|{STEM_VAL}_conf{cid}.out|{model_idx}"


def _asegurar_provenance_val(pid: str, cids: list) -> None:
    """La original escribe stems curve30; este wrapper los reescribe a
    curve15 (mismos 14 campos canonicos, semillas y experiment_id)."""
    rmc._asegurar_provenance_curve30(pid, cids)
    prov_path = rmc.WORK / pid / "provenance.json"
    prov = rmc._json_load(prov_path, default=[])
    if isinstance(prov, list):
        for r in prov:
            r["file_stem"] = r.get("file_stem", "").replace(
                "curve30_conf", f"{STEM_VAL}_conf")
            r["key"] = r.get("key", "").replace(
                "curve30_conf", f"{STEM_VAL}_conf")
        rmc._atomic_write(prov_path, prov)


def _finalizar_val(pid: str, cid: int, r: dict) -> dict:
    """Equivalente a _finalizar_dock con el stem val: renombra
    conf{cid}.out.pdbqt -> curve15_conf{cid}.out.pdbqt y aplica el gate
    corregido (parse_vina_output reusado; scores SOLO de REMARK)."""
    if not r.get("ok"):
        return r
    w = rmc.WORK / pid
    out = w / f"conf{cid}.out.pdbqt"
    dst = w / f"{STEM_VAL}_conf{cid}.out.pdbqt"
    try:
        out.replace(dst)
    except Exception:
        pass
    parsed = rmc.parse_vina_output(dst.read_text(encoding="utf-8"))
    if parsed["ok"]:
        r["n_models_emitted"] = parsed["n_models"]
        r["mode_scores"] = [m["score"] for m in parsed["models"]]
        return r
    r["ok"] = False
    r["gate"] = parsed["errores"]
    r["reason"] = parsed["errores"][0] if parsed["errores"] else "gate:invalido"
    return r


def _validar_prov_val(pid: str) -> str | None:
    prov = rmc._json_load(rmc.WORK / pid / "provenance.json", default=[])
    if not isinstance(prov, list) or not prov:
        return "provenance_ausente"
    for r in prov:
        faltan = [f for f in rmc.FIELDS_CANONICOS if f not in r]
        if faltan:
            return f"provenance_campos_faltantes_{','.join(faltan)}"
        if r.get("experiment_id") != rmc.EXPERIMENT_ID:
            return "provenance_experiment_id_incorrecto"
        if r.get("seed_conformer") != 42 or r.get("seed_docking") != 42:
            return "provenance_semillas_incorrectas"
        stem = f"{STEM_VAL}_conf{r.get('conformer_id')}.out"
        if r.get("file_stem") != stem or \
                r.get("key") != f"{pid}|molflex|{stem}":
            return "provenance_file_stem_key_incorrectos"
    return None


def _parsear_modos_val(pid: str, cid: int):
    p = rmc.WORK / pid / f"{STEM_VAL}_conf{cid}.out.pdbqt"
    if not p.exists():
        return None
    parsed = rmc.parse_vina_output(p.read_text(encoding="utf-8"))
    return parsed["models"] if parsed["ok"] else None


def _backfill_emision_val() -> int:
    n = 0
    for pid in [r["pid"] for r in _LEER_COHORT_ORIG(SPLIT_VAL)]:
        w = rmc.WORK / pid
        prov = rmc._json_load(w / "provenance.json", default=[])
        if not isinstance(prov, list):
            continue
        por_cid = {r.get("conformer_id"): r for r in prov}
        for cid in sorted(int(k) for k in
                          (rmc._json_load(w / "ensemble_hashes.json", default={})
                           .get("hashes", {}) or {})) or rmc.cids_en_disco(pid):
            p = w / f"{STEM_VAL}_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = rmc.parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            r = por_cid.get(cid)
            if r is not None and (
                    r.get("n_models_emitted") != parsed["n_models"]
                    or r.get("num_modes_requested") != 9):
                rmc._anotar_emision(pid, cid, parsed["n_models"])
                n += 1
    print(f"Backfill de emision (val): {n} corridas anotadas")
    return 0


def _materializar_val() -> int:
    out_path = rmc.ARTIFACTS / "curve_candidates_val.jsonl"
    registros = []
    for rec in _LEER_COHORT_ORIG(SPLIT_VAL):
        pid = rec["pid"]
        prov = rmc._json_load(rmc.WORK / pid / "provenance.json", default=[])
        prov_por_cid = {r["conformer_id"]: r for r in prov} \
            if isinstance(prov, list) else {}
        hashes_disco = rmc._json_load(rmc.WORK / pid / "ensemble_hashes.json",
                                      default={})
        disc = {int(c): h for c, h in hashes_disco.get("hashes", {}).items()}
        cids = sorted(disc) or rmc.cids_en_disco(pid)
        for cid in cids:
            p = rmc.WORK / pid / f"{STEM_VAL}_conf{cid}.out.pdbqt"
            if not p.exists():
                continue
            parsed = rmc.parse_vina_output(p.read_text(encoding="utf-8"))
            if not parsed["ok"]:
                continue
            prov_cid = prov_por_cid.get(cid, {})
            for m_idx, modelo in enumerate(parsed["models"]):
                registros.append({
                    "identity": _identidad_val(pid, cid, m_idx),
                    "pid": pid,
                    "source": "molflex",
                    "file_stem": f"{STEM_VAL}_conf{cid}.out",
                    "model_idx": m_idx,
                    "conformer_id": cid,
                    "prefix": [15],
                    "vina_score": modelo["score"],
                    "provenance_key": prov_cid.get("key"),
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
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    data = out_path.read_bytes()
    print(f"curve_candidates_val.jsonl: {len(registros)} lineas, "
          f"{len(data) / 1024 / 1024:.2f} MB, "
          f"sha256={__import__('hashlib').sha256(data).hexdigest()}")
    return 0


rmc.leer_cohort = _leer_cohort_val
rmc.out_valido = _out_valido_val
rmc.identidad_pose = _identidad_val
rmc._asegurar_provenance_curve30 = _asegurar_provenance_val
rmc._finalizar_dock = _finalizar_val
rmc._validar_provenance_pid = _validar_prov_val
rmc._parsear_modos = _parsear_modos_val
rmc.backfill_emision = _backfill_emision_val
rmc.materializar_candidatos = _materializar_val


# ───────────────────────── consolidacion val (descriptiva) ─────────────────

def _wilson_ci(k: int, n: int, z: float = 1.96) -> list:
    """Intervalo de confianza 95% de Wilson para una proporcion (descriptivo)."""
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centro - margen), 3),
            round(min(1.0, centro + margen), 3)]


def _particion_val(cohort: list) -> dict:
    """Particion de fallos para val: los registros del work dir son TODOS
    ITT salvo los reintentos tecnicos resueltos (retry_log). Desviaciones
    esperadas: 0 (el gate corregido rigio desde el inicio)."""
    fallos_raw = []
    if rmc.FAILURES_WORK.exists():
        for line in rmc.FAILURES_WORK.read_text(encoding="utf-8").splitlines():
            try:
                fallos_raw.append(json.loads(line))
            except Exception:
                continue
    retried = {}
    if rmc.RETRY_LOG.exists():
        for line in rmc.RETRY_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            for c in e.get("cids", []):
                retried[(e["pid"], int(c))] = e.get("ts")
    desviaciones = []
    retries = []
    itt = []
    for f in fallos_raw:
        clave = (f["pid"], f.get("cid")) if f.get("cid") is not None else None
        if clave and clave in retried and rmc.out_valido(f["pid"], f["cid"]):
            retries.append({"ts_original": f.get("ts"),
                            "ts_reintento": retried[clave],
                            "pid": f["pid"], "cid": f["cid"],
                            "motivo_original": f.get("reason"),
                            "resultado": "resuelto"})
            continue
        itt.append(f)
    return {"desviaciones": desviaciones, "technical_retries": retries,
            "itt": itt}


def consolidar_val() -> int:
    """Consolidacion DESCRIPTIVA de val: n=5 por estrato, sin regla de
    decision, sin bootstrap decisorio, K=15 inmutable."""
    cohort = _LEER_COHORT_ORIG(SPLIT_VAL)
    ART = rmc.ARTIFACTS
    ART.mkdir(parents=True, exist_ok=True)
    particion = _particion_val(cohort)
    failures = particion["itt"]
    poses = []
    provenances = []
    per_complex = []
    modos_por_estrato = {"hard": [], "control": []}
    for rec in cohort:
        pid = rec["pid"]
        estrato = rec["stratum"]
        w = rmc.WORK / pid
        prov = rmc._json_load(w / "provenance.json", default=[])
        prov_por_cid = {r["conformer_id"]: r for r in prov} \
            if isinstance(prov, list) else {}
        hashes_disco = rmc._json_load(w / "ensemble_hashes.json", default={})
        disc = {int(c): h for c, h in hashes_disco.get("hashes", {}).items()}
        cids = sorted(disc) or rmc.cids_en_disco(pid)
        cids_validos = [c for c in cids if rmc.out_valido(pid, c)]
        if not cids_validos:
            per_complex.append({"pid": pid, "stratum": estrato,
                                "cohort_id": rec["cohort_id"],
                                "pair_id": rec["pair_id"],
                                "yield_15": 0, "min_rmsd": None,
                                "cubierto": False,
                                "motivo": "sin_docks_validos"})
            continue
        crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = mf.cargar_mapa_indices(w)
        rmsds_complejo = []
        for cid in cids_validos:
            modelos = rmc._parsear_modos(pid, cid)
            if modelos is None:
                continue
            n_emitidos = len(modelos)
            modos_por_estrato[estrato].append(n_emitidos)
            prov_cid = prov_por_cid.get(cid, {})
            for m_idx, modelo in enumerate(modelos):
                por_mol = mf.coords_pose_a_por_mol(modelo["atoms"], serial_a_mol)
                rmsd = mf.rmsd_pose_pocket(crystal, por_mol) if por_mol else None
                poses.append({
                    "identity": rmc.identidad_pose(pid, cid, m_idx),
                    "split": "val",
                    "pid": pid,
                    "source": "molflex",
                    "file_stem": f"{STEM_VAL}_conf{cid}.out",
                    "model_idx": m_idx,
                    "vina_score": modelo["score"],
                    "prefix": [15],
                    "conformer_id": cid,
                    "rmsd_pose_pocket": round(rmsd, 3) if rmsd is not None else None,
                    "seed_conformer": prov_cid.get("seed_conformer"),
                    "seed_docking": prov_cid.get("seed_docking"),
                    "exhaustiveness": prov_cid.get("exhaustiveness"),
                    "num_modes": prov_cid.get("num_modes"),
                    "num_modes_requested": 9,
                    "n_models_emitted": n_emitidos,
                    "box": prov_cid.get("box"),
                    "provenance_key": prov_cid.get("key"),
                })
                if rmsd is not None:
                    rmsds_complejo.append(rmsd)
            if prov_cid:
                prov_cid["n_conf"] = len(cids_validos)
                provenances.append(prov_cid)
        per_complex.append({
            "pid": pid, "stratum": estrato,
            "cohort_id": rec["cohort_id"], "pair_id": rec["pair_id"],
            "yield_15": len(cids_validos),
            "min_rmsd": round(min(rmsds_complejo), 3) if rmsds_complejo else None,
            "cubierto": (min(rmsds_complejo) <= rmc.UMBRAL_COBERTURA
                         if rmsds_complejo else False),
        })
    with open(ART / "curve_poses_val.jsonl", "w", encoding="utf-8") as fh:
        for p in poses:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(ART / "curve_provenance.jsonl", "w", encoding="utf-8") as fh:
        for r in provenances:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(ART / "failures.jsonl", "w", encoding="utf-8") as fh:
        for f in failures:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(ART / "deviations.jsonl", "w", encoding="utf-8") as fh:
        for d in particion["desviaciones"]:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(ART / "technical_retries.jsonl", "w", encoding="utf-8") as fh:
        for t in particion["technical_retries"]:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(ART / "per_complex.jsonl", "w", encoding="utf-8") as fh:
        for r in per_complex:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    docks = []
    if rmc.DOCK_TIMES.exists():
        for line in rmc.DOCK_TIMES.read_text(encoding="utf-8").splitlines():
            try:
                docks.append(json.loads(line))
            except Exception:
                continue
    por_estrato = {}
    pc = {r["pid"]: r for r in per_complex}
    for estrato in ("hard", "control"):
        ids_estr = [r["pid"] for r in cohort if r["stratum"] == estrato]
        rmsds = [pc[pid]["min_rmsd"] for pid in ids_estr
                 if pc.get(pid, {}).get("min_rmsd") is not None]
        cubiertos = sum(1 for pid in ids_estr if pc.get(pid, {}).get("cubierto"))
        n = len(ids_estr)
        por_estrato[estrato] = {
            "n_complejos": n,
            "n_con_poses": len(rmsds),
            "cobertura": round(cubiertos / n, 4) if n else None,
            "n_cubiertos": cubiertos,
            "wilson_ci95_cobertura": _wilson_ci(cubiertos, n),
            "mediana_min_rmsd": round(rmc._pct(rmsds, 0.5), 3) if rmsds else None,
            "degeneracion_yield_lt_15": sum(
                1 for pid in ids_estr
                if pc.get(pid, {}).get("yield_15", 0) < 15),
            "itt_fallos": sum(1 for f in failures
                              if {r["pid"]: r["stratum"] for r in cohort}
                              .get(f["pid"]) == estrato),
        }
    itt_motivos = {}
    for f in failures:
        itt_motivos[f["reason"]] = itt_motivos.get(f["reason"], 0) + 1
    metricas = {
        "experiment_id": "D-MF-HARD-CURVE-VAL",
        "split": "val",
        "n_complejos": len(cohort),
        "n_poses": len(poses),
        "n_fallos_itt": len(failures),
        "k_fijado": 15,
        "k_inmutable": True,
        "tipo": "descriptivo_n5_sin_potencia",
        "por_estrato": por_estrato,
        "tiempos": {
            "hard": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "hard"]),
            "control": rmc._calc_tiempos([d for d in docks if d.get("stratum") == "control"]),
            "total": rmc._calc_tiempos(docks),
        },
        "modos_emitidos": {
            e: {"n_corridas": len(v), "mediana": round(rmc._pct(v, 0.5), 1) if v else None,
                "distribucion": {str(k): v.count(k) for k in sorted(set(v))}}
            for e, v in modos_por_estrato.items()
        },
        "itt_motivos": itt_motivos,
        "n_desviaciones": len(particion["desviaciones"]),
        "n_technical_retries": len(particion["technical_retries"]),
        "train_referencia": "D-MF-HARD-CURVE sellado GO K=15 (commit f31bfeb)",
    }
    rmc._atomic_write(ART / "metrics.json", metricas)
    texto = f"""# D-MF-HARD-CURVE-VAL — Validacion unica de val con K=15 — DESIGN

**Fecha:** 2026-08-16
**Rama:** experimentos/ruta-c-molflex
**Referencia:** sello train D-MF-HARD-CURVE (commit f31bfeb, K=15 GO) +
FORECAST.md. **NO sellado, NO finish.**

## 1. Alcance y autorizacion

- Autorizacion del maintainer: SOLO K=15 (15 conformeros, NO 30), SOLO los
  5 hard + 5 controles de val del cohort D-MF-HARD sellado, config identica
  al train sellado (seed ETKDG=42, --seed 42 Vina, box 25 A, exh=8,
  num_modes_requested=9, vina 1.2.7, cpu=1, 6 workers, sin relax, gate
  enmendado), reporte descriptivo.
- **K NO cambia y K30 NO se abre pase lo que pase.** K=15 quedo fijado por la
  regla corregida sobre train ANTES de tocar val; esta corrida es
  verificacion piloto descriptiva (n=5 sin potencia, D-MF-HARD DESIGN §5).

## 2. Implementacion

- Runner: scripts/run_molflex_curve_val.py — REUSA las funciones del runner
  train SIN tocar el archivo sellado (scripts/run_molflex_curve.py es asset
  del sello f31bfeb con hash 46fd2d35...): importa el modulo y monkeypatchea
  (constantes N_CONF=15/PREFIJOS=[15]/WORK/ARTIFACTS/EXPERIMENT_ID +
  wrappers de las funciones con strings train-hardcodeados: file_stem
  curve30 -> curve15, split train -> val). El gate corregido
  (parse_vina_output), el docking por conformero (dock_rigido_archivo via
  _dock_worker/_dock_writemaps) y el flujo de lotes con resume se reusan sin
  modificacion.
- WORK dir: data/dmfhard_curve_work/val/ (dentro del work dir train ya
  gitignored; .gitignore NO modificado).
- El ensemble de 15 es el prefijo exacto del ensemble de 30 (propiedad
  verificada en FORECAST/prefix_smoke.json).
- Consolidacion val PROPIA (sin regla de decision, sin bootstrap decisorio):
  cobertura n/5 por estrato con Wilson CI 95% (descriptivo), mediana
  min-RMSD, ITT, tiempos P50/P90, degeneracion por yield.

## 3. Resultados

- Poses val: {metricas['n_poses']}; fallos ITT: {metricas['n_fallos_itt']}.
- Hard (n=5): cobertura {por_estrato['hard']['n_cubiertos']}/5, mediana
  min-RMSD {por_estrato['hard']['mediana_min_rmsd']}.
- Control (n=5): cobertura {por_estrato['control']['n_cubiertos']}/5, mediana
  min-RMSD {por_estrato['control']['mediana_min_rmsd']}.
- Detalle: metrics.json.

## 4. Declaraciones

- **K permanece 15.** Ningun numero de esta corrida cambia K ni abre K30.
- n=5 por estrato: SIN inferencia fuerte contra train (solo descripcion).

## 5. Archivos

| Archivo | Contenido |
|---|---|
| curve_poses_val.jsonl | una linea por pose emitida (identidades val|pid|molflex|curve15_...) |
| curve_provenance.jsonl | sidecar FND-06 canonico por corrida |
| curve_candidates_val.jsonl | bloques PDBQT crudos por pose emitida |
| metrics.json | metricas descriptivas por estrato + Wilson CI |
| per_complex.jsonl | una linea por complejo val |
| failures.jsonl | fallos ITT |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
"""
    rmc._atomic_write(ART / "DESIGN.md", texto)
    print(f"Consolidacion val: {len(poses)} poses, {len(provenances)} "
          f"corridas, {len(failures)} fallos ITT, "
          f"{len(particion['desviaciones'])} desviaciones")
    print(json.dumps({"k_fijado": 15,
                      "hard": por_estrato["hard"],
                      "control": por_estrato["control"]},
                     indent=2, ensure_ascii=False))
    return 0


rmc.consolidar = consolidar_val


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
    return rmc.main()


if __name__ == "__main__":
    sys.exit(main())
