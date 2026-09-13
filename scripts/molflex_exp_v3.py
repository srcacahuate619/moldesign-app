# -*- coding: utf-8 -*-
"""
molflex_exp_v3.py — Fase 2 de validación de MolFlex + re-ejecución de E2 con
caché de grids (docs/40_MOLFLEX_PROTOCOL.md, secciones 3, 4 y 5).

  E2-re: re-ejecuta el criterio E2 (wall <120s) con el fix de caché de mapas
         de receptor (--write_maps/--maps, Vina 1.2.7) sobre los MISMOS 5
         complejos (1a4w, 1aaq, 1ajx, 10gs, 184l; 30 confs, top-3 relax,
         cpu=1 por Vina, pool global 12, olas de 2 — misma topología que v2).
  V4:   correlación de features Grupo B (vina_best_score, pose_score_variance,
        pose_score_range, poses_passing_ratio) entre el flexible (caché
        vina_redock_cache) y MolFlex (Fases 1+2, 20 confs, con grid cacheado)
        sobre 15 complejos con ambos. Spearman por feature. Criterio
        pre-registrado: rho ≥ 0.8 en vina_best_score y ≥ 0.7 en las otras tres.
  V2/R1: RMSD al cristal de MolFlex (min del ensemble y pose top-score) +
         referencia flexible (pose en disco cuando es recuperable, o re-dock
         flexible estándar acotado a 3 complejos).

Comparación like-for-like (documentada): el caché flexible guarda las features
de UNA búsqueda flexible (9 modos); MolFlex produce el mejor score del ensemble
(20 docks rígidos, 1 pose mejor por dock). La varianza/rango flexible es entre
los 9 modos; la de MolFlex entre los 20 mejores-por-conformero. Es la
comparación honesta entre ambas estrategias, no entre cuadrículas idénticas.

Resultado incremental: scripts/artifacts_molflex_v3.json (escrito tras CADA
complejo: una caída pierde a lo sumo un complejo).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402

E2_PIDS = ["1a4w", "1aaq", "1ajx", "10gs", "184l"]
# Paredes del E2 ORIGINAL (molflex_exp_v2, sin caché de grid):
E2_OLD = {
    "1a4w": {"wall_fase2_s": 166.4, "wall_total_s": 177.2},
    "1aaq": {"wall_fase2_s": 319.8, "wall_total_s": 329.7},
    "1ajx": {"wall_fase2_s": 178.6, "wall_total_s": 187.3},
    "10gs": {"wall_fase2_s": 234.0, "wall_total_s": 243.0},
    "184l": {"wall_fase2_s": 2.9, "wall_total_s": 12.2},
}

E2_N_CONF = 30
E2_TOP_K = 3
V4_N = 15
V4_N_CONF = 20
POOL = 12
WAVE = 2
CPU = 1
FLEX_TIMEOUT = 300       # mismo timeout que el protocolo flexible
MAX_FLEX_REDOCK = 3      # re-docks flexibles acotados para V2
FEATURES = ["vina_best_score", "pose_score_variance", "pose_score_range",
            "poses_passing_ratio"]
CRITERIO_V4 = {"vina_best_score": 0.8, "pose_score_variance": 0.7,
               "pose_score_range": 0.7, "poses_passing_ratio": 0.7}

ARTIFACTO = PROJECT_ROOT / "scripts" / "artifacts_molflex_v3.json"
WORK = PROJECT_ROOT / "scripts" / ".work_molflex_v3"


# ─────────────────────── utilidades de selección ───────────────────────────

def leer_cache_flexible(pid: str) -> dict:
    p = mf.PDBBIND / "vina_redock_cache" / f"{pid}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fallas_flexibles() -> dict:
    p = mf.PDBBIND / "vina_redock_cache" / "redock_failures.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def candidatos_v4(n: int) -> list:
    """Primeros n complejos (alfabéticos) con entrada en el caché flexible,
    SDF + proteína en disco y NO en redock_failures."""
    cache = mf.PDBBIND / "vina_redock_cache"
    fallas = fallas_flexibles()
    out = []
    for p in sorted(cache.glob("*.json")):
        pid = p.stem
        if pid == "redock_failures" or pid in fallas:
            continue
        if not (mf.PDBBIND / pid / f"{pid}_ligand.sdf").exists():
            continue
        if not (mf.PDBBIND / pid / f"{pid}_protein.pdb").exists():
            continue
        try:
            if all(k in json.loads(p.read_text(encoding="utf-8")) for k in FEATURES):
                out.append(pid)
        except Exception:
            continue
        if len(out) >= n:
            break
    return out


# ─────────────────────── Fase 2 con grid cacheado ──────────────────────────

def mapas_existen(pid: str) -> bool:
    maps_dir = WORK / pid / "maps"
    return maps_dir.exists() and any(maps_dir.glob("*.map"))


def fase2_cacheada_lote(lote: list, ex: ProcessPoolExecutor) -> dict:
    """Fase 2 de un lote de complejos con caché de grid: primero TODOS los
    writers (--write_maps) en paralelo; al terminar, TODOS los docks restantes
    con --maps (o receptor fresco si no se generaron mapas). `lote` = [(pid, cids)].
    Devuelve {pid: {"docks": {cid: dict}, "t_submit": ts, "t_last": ts}}."""
    res = {}
    for pid, cids in lote:
        res[pid] = {"docks": {}, "t_submit": None, "t_last": None}

    # ── 1) Writers (primer conformero de cada complejo sin mapas en disco) ──
    writers = {}
    for pid, cids in lote:
        if not cids:
            continue
        if mapas_existen(pid):
            continue  # mapas ya en disco (resumen de corrida previa)
        maps_dir = WORK / pid / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        mp = str(maps_dir / "grid")
        res[pid]["t_submit"] = time.monotonic()
        writers[ex.submit(mf.dock_rigido_archivo, pid, cids[0], str(WORK), CPU,
                          mp, True)] = (pid, cids[0])
    for f in as_completed(writers):
        pid, cid0 = writers[f]
        try:
            d = f.result(timeout=360)
        except Exception as e:  # noqa: BLE001
            d = {"pid": pid, "cid": cid0, "ok": False, "reason": type(e).__name__,
                 "t": 0.0}
        res[pid]["docks"][cid0] = d

    # ── 2) Docks restantes con --maps (o fresh si no se generaron mapas) ──
    futs = {}
    for pid, cids in lote:
        if not cids:
            continue
        if res[pid]["t_submit"] is None:
            res[pid]["t_submit"] = time.monotonic()
        hay = mapas_existen(pid)
        mp = str(WORK / pid / "maps" / "grid")
        restantes = [c for c in cids if c not in res[pid]["docks"]]
        for cid in restantes:
            futs[ex.submit(mf.dock_rigido_archivo, pid, cid, str(WORK), CPU,
                           mp if hay else None)] = (pid, cid)
    for f in as_completed(futs):
        pid, cid = futs[f]
        try:
            d = f.result(timeout=360)
        except Exception as e:  # noqa: BLE001
            d = {"pid": pid, "cid": cid, "ok": False, "reason": type(e).__name__,
                 "t": 0.0}
        res[pid]["docks"][cid] = d

    # ── 3) Fallback fresh para docks con maps que fallaron (raro: rc≠0) ──
    for pid in res:
        for cid, d in list(res[pid]["docks"].items()):
            if not d["ok"] and d.get("grid_mode") == "maps":
                try:
                    d2 = mf.dock_rigido_archivo(pid, cid, str(WORK), CPU)
                except Exception as e:  # noqa: BLE001
                    d2 = {"pid": pid, "cid": cid, "ok": False,
                          "reason": type(e).__name__, "t": 0.0}
                d2["fallback"] = "fresh_tras_maps"
                res[pid]["docks"][cid] = d2

    for pid in res:
        if res[pid]["docks"]:
            res[pid]["t_last"] = time.monotonic()
    return res


# ─────────────────────── features y RMSD ────────────────────────────────────

def features_molflex(docks: dict) -> dict | None:
    """Features Grupo B de MolFlex: distribución de los mejores scores por
    conformero (1 pose mejor por dock). Análogo honesto a los 9 modos del
    flexible: el ensemble es el conjunto de poses muestreadas."""
    import statistics

    bests = sorted(d["best"] for d in docks.values() if d.get("ok"))
    if not bests:
        return None
    var = statistics.pvariance(bests) if len(bests) > 1 else 0.0
    return {
        "vina_best_score": round(bests[0], 4),
        "pose_score_variance": round(var, 6),
        "pose_score_range": round(bests[-1] - bests[0], 4),
        "poses_passing_ratio": round(sum(1 for s in bests if s < -5.0) / len(bests), 6),
        "n_poses": len(bests),
    }


def spearman(xs: list, ys: list):
    """Spearman con empates (rangos promediados). Usa scipy si está; si no,
    implementación manual equivalente."""
    import numpy as np

    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if x.size < 2 or y.size < 2:
        return None
    try:
        from scipy.stats import spearmanr
        return float(spearmanr(x, y)[0])
    except Exception:
        pass
    # Fallback manual: Pearson sobre rangos con promedios para empates.
    def rangos(v):
        order = np.argsort(v, kind="mergesort")
        ranks = np.empty_like(v, dtype=float)
        ranks[order] = np.arange(1, v.size + 1)
        # empates: promedio de rangos
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        r = np.zeros_like(v, dtype=float)
        s = 0
        for k, c in enumerate(cnt):
            r[inv == k] = s + (c + 1) / 2.0
            s += c
        return r
    rx, ry = rangos(x), rangos(y)
    return float(np.corrcoef(rx, ry)[0, 1])


# ─────────────────────── referencia flexible (V2) ──────────────────────────

def flexible_desde_disco(pid: str) -> dict | None:
    """Intenta usar la pose flexible en disco (vina_redock_work/{pid}_out.pdbqt).
    Solo es válida si los átomos del {pid}_lig.pdbqt en disco coinciden en
    orden/serial/tipo/carga con una regeneración meeko del SDF cristalográfico
    (mismo pipeline → mismo orden atómico → el índice serial→mol aplica).
    Devuelve None si no es recuperable."""
    from meeko import MoleculePreparation
    from rdkit import Chem

    work_flex = mf.PDBBIND / "vina_redock_work" / pid
    out = work_flex / f"{pid}_out.pdbqt"
    lig_disco = work_flex / f"{pid}_lig.pdbqt"
    if not out.exists() or not lig_disco.exists():
        return None
    crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
    if crystal is None:
        return None
    try:
        mh = Chem.AddHs(crystal)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        _rigid, flex_str, mapa, _err = mf.escribir_pdbqt(setups[0])
        if not flex_str or not mapa:
            return None
        def atomos(s):
            return [l for l in s.splitlines() if l.startswith(("ATOM", "HETATM"))]
        def firma(l):
            return (l[6:11].strip(), l[77:79].strip())
        gen = [firma(l) for l in atomos(flex_str)]
        disco = [firma(l) for l in atomos(lig_disco.read_text(encoding="utf-8"))]
        if not gen or gen != disco:
            return None  # orden o tipos distintos: el índice no aplica
        modelos = mf.parsear_out_vina(out.read_text(encoding="utf-8"))
        if not modelos or modelos[0][1] is None:
            return None
        por_mol = mf.coords_pose_a_por_mol(modelos[0][1], mapa)
        rmsd = mf.rmsd_pose_pocket(crystal, por_mol)
        if rmsd is None:
            return None
        return {"ok": True, "fuente": "disco",
                "rmsd_best_pose": round(rmsd, 3)}
    except Exception:
        return None


def redock_flexible_referencia(pid: str) -> dict:
    """Protocolo flexible estándar (mismo que rescoring/scripts/redock_pdbbind.py:
    meeko completo desde el SDF, box 25³ centrada en el cristal, exh=8,
    num_modes=9, timeout 300s) + índice serial→mol para RMSD."""
    from meeko import MoleculePreparation
    from rdkit import Chem

    rp = mf.rp  # redock_pdbbind importado por el motor (mismo preparador)

    w = WORK / pid
    w.mkdir(parents=True, exist_ok=True)
    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    prot = mf.PDBBIND / pid / f"{pid}_protein.pdb"
    crystal = mf.leer_ligando(str(sdf))
    if crystal is None:
        return {"ok": False, "reason": "sdf_unreadable"}
    rec = str(w / "rec_flex.pdbqt")
    if not rp.prepare_receptor_pdbqt(str(prot), rec):
        return {"ok": False, "reason": "receptor_prep_failed"}
    center = rp.find_binding_center(str(sdf))
    if center is None:
        return {"ok": False, "reason": "binding_center_failed"}
    try:
        mh = Chem.AddHs(crystal)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        # OJO (bug corregido 2026-08-14): escribir_pdbqt devuelve
        # (rigid_str, flex_str, serial_a_mol, err) — desempaquetar mal ponia
        # el PDBQT RIGIDO como ligando del dock "flexible".
        _rigid, flex_str, mapa, _err = mf.escribir_pdbqt(setups[0])
        if not flex_str or not mapa:
            return {"ok": False, "reason": "meeko_failed"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"meeko: {type(e).__name__}"}
    lig = str(w / "lig_flex.pdbqt")
    Path(lig).write_text(flex_str, encoding="utf-8")
    out = str(w / "flex_out.pdbqt")
    cmd = [mf.VINA, "--receptor", rec, "--ligand", lig] + mf._args_box(center) + [
        "--exhaustiveness", "8", "--num_modes", "9", "--cpu", "1", "--out", out]
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FLEX_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "vina_timeout_300s", "t": FLEX_TIMEOUT}
    dt = round(time.monotonic() - t0, 1)
    if r.returncode != 0:
        return {"ok": False, "reason": f"rc={r.returncode}", "t": dt}
    scores = mf.parsear_scores_tabla(r.stdout)
    if not scores:
        return {"ok": False, "reason": "no_scores", "t": dt}
    modelos = mf.parsear_out_vina(Path(out).read_text(encoding="utf-8"))
    rmsd = None
    if modelos:
        por_mol = mf.coords_pose_a_por_mol(modelos[0][1], mapa)
        rmsd = mf.rmsd_pose_pocket(crystal, por_mol)
    import numpy as np
    return {"ok": True, "fuente": "redock", "t": dt,
            "vina_best_score": scores[0],
            "pose_score_variance": float(np.var(scores)) if len(scores) > 1 else 0.0,
            "pose_score_range": scores[-1] - scores[0] if len(scores) > 1 else 0.0,
            "poses_passing_ratio": sum(1 for s in scores if s < -5.0) / len(scores),
            "rmsd_best_pose": round(rmsd, 3) if rmsd is not None else None}


# ─────────────────────── agregación E2 ─────────────────────────────────────

def agregar_e2(pid: str, prep: dict, fase2: dict, relaxes: dict) -> dict:
    """Consolida el complejo E2: paredes, scores, deltas, RMSDs y modo de grid.
    Misma semántica que molflex_exp_v2.agregar_pid."""
    docks = fase2["docks"]
    out = {
        "pdb_id": pid, "ok": False, "reason": None,
        "n_conf": prep.get("n_conf"),
        "n_docks_ok": sum(1 for d in docks.values() if d["ok"]),
        "t_prep_s": prep.get("t"),
        "wall_fase2_s": None, "wall_fase3_s": None, "wall_total_s": None,
        "grid": {
            "mapas": mapas_existen(pid),
            "n_write": sum(1 for d in docks.values() if d.get("grid_mode") == "write_maps"),
            "n_maps": sum(1 for d in docks.values() if d.get("grid_mode") == "maps"),
            "n_fresh": sum(1 for d in docks.values() if d.get("grid_mode") == "fresh"),
            "n_fallback": sum(1 for d in docks.values() if d.get("fallback")),
        },
    }
    oks = {c: d for c, d in docks.items() if d["ok"]}
    ts_maps = [d["t"] for d in oks.values() if d.get("grid_mode") == "maps"]
    ts_writer = [d["t"] for d in oks.values() if d.get("grid_mode") == "write_maps"]
    out["t_dock_maps_media"] = round(sum(ts_maps) / len(ts_maps), 2) if ts_maps else None
    out["t_dock_writer"] = round(ts_writer[0], 2) if ts_writer else None
    out["speedup_vs_writer"] = (round(ts_writer[0] / (sum(ts_maps) / len(ts_maps)), 2)
                                if ts_writer and ts_maps else None)
    out["wall_fase2_s"] = (round(fase2["t_last"] - fase2["t_submit"], 1)
                           if fase2.get("t_submit") and fase2.get("t_last") else None)
    if relaxes:
        t_rel = [rr.get("t") or 0 for rr in relaxes.values()]
        out["wall_fase3_s"] = round(max(t_rel), 1)
    out["wall_total_s"] = round(sum(v for v in [out["t_prep_s"] or 0,
                                                out["wall_fase2_s"] or 0,
                                                out["wall_fase3_s"] or 0]), 1)
    out["rmsd_raw_min"] = None
    for cid, rmsd in prep.get("ensemble_rmsds", []):
        if rmsd is not None and (out["rmsd_raw_min"] is None or rmsd < out["rmsd_raw_min"]):
            out["rmsd_raw_min"] = rmsd
    if not oks:
        out["reason"] = "all_docks_failed"
        return out
    out["rigid_best"] = round(min(d["best"] for d in oks.values()), 3)
    ranking = sorted(oks.items(), key=lambda kv: kv[1]["best"])[:E2_TOP_K]

    crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
    serial_a_mol = mf.cargar_mapa_indices(WORK / pid)
    out["relaxed"] = []
    for cid, rr in relaxes.items():
        base = docks[cid]["best"] if cid in docks else None
        entrada = {"cid": cid, "ok": rr["ok"], "reason": rr.get("reason"),
                   "relaxed_score": rr.get("relaxed_rigid"),
                   "delta": (round(rr["relaxed_rigid"] - base, 3)
                             if rr["ok"] and base is not None else None),
                   "rmsd_to_crystal": None,
                   "grid_mode": rr.get("grid_mode")}
        if rr["ok"] and crystal is not None:
            por_mol = mf.coords_pose_a_por_mol(rr["coords"], serial_a_mol)
            rmsd = mf.rmsd_pose_pocket(crystal, por_mol)
            entrada["rmsd_to_crystal"] = round(rmsd, 3) if rmsd is not None else None
        out["relaxed"].append(entrada)
    rel_ok = [e for e in out["relaxed"] if e["ok"]]
    if rel_ok:
        out["relaxed_best"] = round(min(e["relaxed_score"] for e in rel_ok), 3)
        out["delta_best"] = round(out["relaxed_best"] - out["rigid_best"], 3)
        rmsds_rel = [e["rmsd_to_crystal"] for e in rel_ok
                     if e["rmsd_to_crystal"] is not None]
        out["rmsd_relaxed_min"] = round(min(rmsds_rel), 3) if rmsds_rel else None
        out["ok"] = True
    else:
        out["reason"] = out.get("reason") or "relax_unavailable"
    # RMSD de la pose top-score (R4: ¿el score selecciona el conformero correcto?)
    mejor_cid, mejor = ranking[0]
    por_mol = mf.coords_pose_a_por_mol(mejor["pose"], serial_a_mol)
    r = mf.rmsd_pose_pocket(crystal, por_mol) if crystal is not None else None
    out["rmsd_top_score_pose"] = round(r, 3) if r is not None else None
    return out


def evaluar_e2(agregados: dict) -> dict:
    e2_pasa, e2_total = 0, 0
    for pid, a in agregados.items():
        if a["wall_total_s"] is not None and a["n_docks_ok"] > 0:
            e2_total += 1
            if a["wall_total_s"] < 120.0:
                e2_pasa += 1
    return {"criterio": "≥90% con wall <120s (grid cacheado)",
            "n_pasa": e2_pasa, "n_total": e2_total,
            "fraccion": round(e2_pasa / e2_total, 3) if e2_total else None,
            "pass": e2_total > 0 and e2_pasa / e2_total >= 0.9}


# ─────────────────────── Fase E2-re ────────────────────────────────────────

def fase_e2(pids: list, ex: ProcessPoolExecutor, artefacto: dict) -> None:
    print(f"\n═══ E2-re: {len(pids)} complejos (grid cacheado, topología v2) ═══", flush=True)
    agregados = dict(artefacto["e2"].get("agregados", {}))
    for i in range(0, len(pids), WAVE):
        lote = [p for p in pids[i:i + WAVE] if p not in agregados]
        if not lote:
            continue
        print(f"  Lote: {', '.join(lote)}", flush=True)
        # Prep de la ola (paralelo).
        preps = {}
        fut_p = {ex.submit(mf.preparar_complejo, pid, E2_N_CONF, str(WORK)): pid
                 for pid in lote}
        for f in as_completed(fut_p):
            pid = fut_p[f]
            try:
                preps[pid] = f.result(timeout=600)
            except Exception as e:  # noqa: BLE001
                preps[pid] = {"ok": False, "reason": type(e).__name__}
        for pid in lote:
            if not preps[pid]["ok"]:
                agregados[pid] = {"pdb_id": pid, "ok": False,
                                  "reason": preps[pid].get("reason")}
                artefacto["e2"]["agregados"] = agregados
                guardar_artefacto(artefacto)
                continue
        lotes_ok = [(pid, preps[pid]["cids"]) for pid in lote if preps[pid]["ok"]]
        # Fase 2 con caché (writers → maps).
        fase2 = fase2_cacheada_lote(lotes_ok, ex)
        for pid in lote:
            print(f"  {pid}: prep={preps[pid].get('n_conf')} confs, "
                  f"docks ok={sum(1 for d in fase2[pid]['docks'].values() if d['ok'])}"
                  f"/{len(fase2[pid]['docks'])}, "
                  f"wall_f2={fase2[pid].get('t_submit') and round(fase2[pid]['t_last'] - fase2[pid]['t_submit'], 1)}s",
                  flush=True)
        # Relax top-3 por complejo (lote, en paralelo, con maps si existen).
        relaxes = {}
        futs = {}
        for pid in lote:
            if not preps[pid]["ok"]:
                continue
            docks = fase2[pid]["docks"]
            oks = [(c, d["best"]) for c, d in docks.items() if d["ok"]]
            oks.sort(key=lambda x: x[1])
            top = [c for c, _ in oks[:E2_TOP_K]]
            relaxes[pid] = {}
            mp = str(WORK / pid / "maps" / "grid") if mapas_existen(pid) else None
            for cid in top:
                futs[ex.submit(mf.relax_pose_archivo, pid, cid,
                               docks[cid]["pose"], str(WORK), CPU,
                               "vina_local_only", mp)] = (pid, cid)
        for f in as_completed(futs):
            pid, cid = futs[f]
            try:
                rr = f.result(timeout=360)
            except Exception as e:  # noqa: BLE001
                rr = {"pid": pid, "cid": cid, "ok": False,
                      "reason": type(e).__name__, "t": 0.0}
            relaxes[pid][cid] = rr
        for pid in lote:
            if not preps[pid]["ok"]:
                continue
            agregados[pid] = agregar_e2(pid, preps[pid], fase2[pid], relaxes[pid])
            artefacto["e2"]["agregados"] = agregados
            artefacto["e2"]["criterios"] = evaluar_e2(agregados)
            guardar_artefacto(artefacto)
    criterios = evaluar_e2(agregados)
    artefacto["e2"]["criterios"] = criterios
    imprimir_tabla_e2(agregados, criterios)


# ─────────────────────── Fase V4/V2 ────────────────────────────────────────

def fase_v4v2(ex: ProcessPoolExecutor, artefacto: dict) -> None:
    candidatos = candidatos_v4(V4_N + 5)  # margen para sustituciones
    v4 = artefacto["v4"]
    v4["pids_intento"] = candidatos
    print(f"\n═══ V4/V2: objetivo {V4_N} complejos, {V4_N_CONF} confs ═══", flush=True)
    print("Candidatos:", ", ".join(candidatos), flush=True)
    completados = dict(v4.get("complejos", {}))
    sustituciones = list(v4.get("sustituciones", []))
    flex_ref = dict(artefacto["v2"].get("referencia_flexible", {}))
    flex_pendiente = dict(artefacto["v2"].get("pendiente", {}))

    for pid in candidatos:
        if len(completados) >= V4_N:
            break
        if pid in completados:
            continue
        print(f"\n  [{len(completados) + 1}/{V4_N}] {pid} ...", flush=True)
        try:
            prep = mf.preparar_complejo(pid, V4_N_CONF, str(WORK))
        except Exception as e:  # noqa: BLE001
            prep = {"ok": False, "reason": type(e).__name__}
        if not prep["ok"]:
            sustituciones.append({"pid": pid, "reason": prep.get("reason")})
            artefacto["v4"]["sustituciones"] = sustituciones
            guardar_artefacto(artefacto)
            continue
        fase2 = fase2_cacheada_lote([(pid, prep["cids"])], ex)[pid]
        docks = fase2["docks"]
        feats = features_molflex(docks)
        crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
        serial_a_mol = mf.cargar_mapa_indices(WORK / pid)
        rmsd_min_ens = None
        for cid, r in prep.get("ensemble_rmsds", []):
            if r is not None and (rmsd_min_ens is None or r < rmsd_min_ens):
                rmsd_min_ens = r
        rmsd_top = None
        oks = [(c, d) for c, d in docks.items() if d["ok"]]
        if oks and crystal is not None:
            mejor_cid, mejor = min(oks, key=lambda kv: kv[1]["best"])
            por_mol = mf.coords_pose_a_por_mol(mejor["pose"], serial_a_mol)
            r = mf.rmsd_pesados(crystal, por_mol)
            rmsd_top = round(r, 3) if r is not None else None
        entrada = {
            "pdb_id": pid,
            "n_conf": prep.get("n_conf"),
            "n_docks_ok": sum(1 for d in docks.values() if d["ok"]),
            "features_molflex": feats,
            "rmsd_min_ensemble": round(rmsd_min_ens, 3) if rmsd_min_ens is not None else None,
            "rmsd_top_score_pose": rmsd_top,
            "t_prep_s": prep.get("t"),
            "wall_fase2_s": (round(fase2["t_last"] - fase2["t_submit"], 1)
                             if fase2.get("t_submit") and fase2.get("t_last") else None),
        }
        if feats is None:
            entrada["reason"] = "no_features"
        completados[pid] = entrada
        artefacto["v4"]["complejos"] = completados
        guardar_artefacto(artefacto)
        print(f"    features: {json.dumps(feats, ensure_ascii=False) if feats else None}", flush=True)
        print(f"    rmsd_min_ensemble={entrada['rmsd_min_ensemble']} "
              f"rmsd_top_score_pose={entrada['rmsd_top_score_pose']} "
              f"wall_f2={entrada['wall_fase2_s']}s", flush=True)

        # Referencia flexible (disco → re-dock acotado a 3).
        if pid in flex_ref or pid in flex_pendiente:
            continue
        ref = flexible_desde_disco(pid)
        if ref is None:
            n_redocks = sum(1 for v in flex_ref.values()
                            if v.get("fuente") == "redock")
            if n_redocks < MAX_FLEX_REDOCK:
                ref = redock_flexible_referencia(pid)
                if ref is None or not ref.get("ok"):
                    flex_pendiente[pid] = ref if ref else {"ok": False,
                                                           "reason": "no_reference"}
            else:
                flex_pendiente[pid] = {"ok": False, "reason": "presupuesto_redock"}
        if ref is not None:
            flex_ref[pid] = ref
        artefacto["v2"]["referencia_flexible"] = flex_ref
        artefacto["v2"]["pendiente"] = flex_pendiente
        guardar_artefacto(artefacto)

    # Spearman y criterio V4 sobre los complejos con ambos.
    comunes = []
    for pid, c in completados.items():
        cache = leer_cache_flexible(pid)
        feats = c.get("features_molflex")
        if feats and all(k in cache for k in FEATURES):
            comunes.append(pid)
    spearman_res = {}
    for feat in FEATURES:
        xs = [leer_cache_flexible(pid)[feat] for pid in comunes]
        ys = [completados[pid]["features_molflex"][feat] for pid in comunes]
        rho = spearman(xs, ys)
        spearman_res[feat] = {"n": len(comunes),
                              "rho": round(rho, 3) if rho is not None else None}
    media = None
    rhos = [v["rho"] for v in spearman_res.values() if v["rho"] is not None]
    if rhos:
        media = round(sum(rhos) / len(rhos), 3)
    criterio = {
        "pre_registrado": CRITERIO_V4,
        "n_complejos_comunes": len(comunes),
        "por_feature": spearman_res,
        "media_rho": media,
        "pass": (len(comunes) >= V4_N - 2 and
                 all(spearman_res[f]["rho"] is not None and
                     spearman_res[f]["rho"] >= CRITERIO_V4[f] for f in FEATURES)),
    }
    artefacto["v4"]["spearman"] = {"comunes": comunes, **criterio}
    artefacto["v4"]["criterio"] = criterio
    guardar_artefacto(artefacto)
    imprimir_tabla_v4(completados, comunes, criterio)
    imprimir_tabla_v2(completados, flex_ref, flex_pendiente)


# ─────────────────────── impresión y artifacto ─────────────────────────────

def guardar_artefacto(artefacto: dict) -> None:
    artefacto["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    ARTIFACTO.write_text(json.dumps(artefacto, indent=2, ensure_ascii=False),
                         encoding="utf-8")


def imprimir_tabla_e2(agregados: dict, criterios: dict | None = None) -> None:
    print("\n── E2-re por complejo (vs E2 original sin caché) ──")
    print(f"{'pid':6} {'n_conf':>6} {'prep':>4} {'f2_viejo':>8} {'f2_nuevo':>8} "
          f"{'tot_viejo':>8} {'tot_nuevo':>8} {'rigid':>7} {'delta':>7} {'<120s':>6}")
    for pid, a in sorted(agregados.items()):
        viejo = E2_OLD.get(pid, {})
        ok120 = "SÍ" if a.get("wall_total_s") is not None and a["wall_total_s"] < 120 else "no"
        print(f"{pid:6} {a.get('n_conf') or 0:6} {a.get('t_prep_s') or 0:4.0f} "
              f"{viejo.get('wall_fase2_s', float('nan')):8.1f} "
              f"{a.get('wall_fase2_s') or float('nan'):8.1f} "
              f"{viejo.get('wall_total_s', float('nan')):8.1f} "
              f"{a.get('wall_total_s') or float('nan'):8.1f} "
              f"{a.get('rigid_best', float('nan')):7.2f} "
              f"{a.get('delta_best', float('nan')):+7.2f} {ok120:>6}")
    if criterios:
        print(f"E2: {criterios['n_pasa']}/{criterios['n_total']} ({criterios['fraccion']}) "
              f"→ {'PASS' if criterios['pass'] else 'FAIL'} | {criterios['criterio']}")


def imprimir_tabla_v4(completados: dict, comunes: list, criterio: dict) -> None:
    print("\n── V4: features por complejo (flexible vs MolFlex) ──")
    print(f"{'pid':6} {'flex_best':>9} {'mf_best':>8} {'flex_var':>8} {'mf_var':>8} "
          f"{'flex_rng':>8} {'mf_rng':>7} {'flex_ppr':>8} {'mf_ppr':>7}")
    for pid in comunes:
        c = leer_cache_flexible(pid)
        m = completados[pid]["features_molflex"]
        print(f"{pid:6} {c['vina_best_score']:9.2f} {m['vina_best_score']:8.2f} "
              f"{c['pose_score_variance']:8.3f} {m['pose_score_variance']:8.3f} "
              f"{c['pose_score_range']:8.2f} {m['pose_score_range']:7.2f} "
              f"{c['poses_passing_ratio']:8.2f} {m['poses_passing_ratio']:7.2f}")
    print("\nSpearman por feature (criterio pre-registrado):")
    for feat, v in criterio["por_feature"].items():
        umbral = CRITERIO_V4[feat]
        pasa = "SÍ" if v["rho"] is not None and v["rho"] >= umbral else "no"
        print(f"  {feat:22} rho={v['rho']} (n={v['n']}, umbral {umbral}) → {pasa}")
    print(f"  media rho = {criterio['media_rho']} | n_comunes = {criterio['n_complejos_comunes']}")
    print(f"V4 → {'PASS' if criterio['pass'] else 'FAIL'} | "
          f"rho_best ≥ 0.8 y resto ≥ 0.7")


def imprimir_tabla_v2(completados: dict, flex_ref: dict, flex_pendiente: dict) -> None:
    print("\n── V2/R1: RMSD al cristal (Å) ──")
    print(f"{'pid':6} {'min_ensemble':>12} {'top_score_pose':>15} {'flex_rmsd':>10} {'flex_fuente':>12}")
    for pid in sorted(set(completados) | set(flex_ref) | set(flex_pendiente)):
        c = completados.get(pid, {})
        fr = flex_ref.get(pid)
        fp = flex_pendiente.get(pid)
        fuente = fr.get("fuente") if fr else (fp.get("reason") if fp else "")
        frms = fr.get("rmsd_best_pose") if fr and fr.get("ok") else None
        print(f"{pid:6} {c.get('rmsd_min_ensemble', float('nan')):>12} "
              f"{c.get('rmsd_top_score_pose', float('nan')):>15} "
              f"{frms if frms is not None else float('nan'):>10} {fuente:>12}")
    if not flex_ref and not flex_pendiente:
        print("  Referencia flexible: pendiente")
    else:
        print(f"  Referencia flexible: {len(flex_ref)} recuperadas, "
              f"{len(flex_pendiente)} pendientes")


# ───────────────────────────────── main ────────────────────────────────────

def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="MolFlex v3: E2-re + V4 + V2/R1")
    ap.add_argument("--solo-e2", action="store_true")
    ap.add_argument("--solo-v4", action="store_true")
    args = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    if ARTIFACTO.exists():
        try:
            artefacto = json.loads(ARTIFACTO.read_text(encoding="utf-8"))
        except Exception:
            artefacto = {}
    else:
        artefacto = {}
    artefacto.setdefault("config", {
        "e2": {"pids": E2_PIDS, "n_conf": E2_N_CONF, "top_k": E2_TOP_K,
               "cpu_vina": CPU, "pool": POOL, "wave": WAVE},
        "v4": {"n_objetivo": V4_N, "n_conf": V4_N_CONF, "criterio": CRITERIO_V4},
        "v2": {"max_flex_redock": MAX_FLEX_REDOCK},
        "box": mf.BOX_SIZE, "exhaustiveness": mf.EXHAUSTIVENESS,
        "num_modes": mf.NUM_MODES, "engine_relax": "vina_local_only",
    })
    artefacto.setdefault("probe", {
        "vina": "1.2.7",
        "hallazgos": [
            "--write_maps requiere --force_even_voxels (sin el flag aborta: "
            "número de voxels impar)",
            "--write_maps escribe los mapas Y ejecuta el dock completo (doble "
            "uso: escritor = dock del conformero 0)",
            "--maps y --receptor son mutuamente excluyentes (error explícito); "
            "con --maps no se pasan --center/--size (el grid sale de los mapas)",
            "--maps sin receptor funciona: scores idénticos en ranking, "
            "delta sistemático ≤0.3 kcal/mol por la discretización de voxels "
            "par (span 25.5Å vs 25.125Å)",
            "probe 1aaq: dock fresco 30.6s, dock con maps 30.9s, porción de "
            "grid ≈ 1.1s (3.5%) → el grid NO era el costo dominante en estos "
            "receptores; la búsqueda global (exh=8) domina",
        ],
    })
    artefacto.setdefault("e2", {"agregados": {}, "criterios": None,
                                "old": E2_OLD})
    artefacto.setdefault("v4", {"pids_intento": [], "sustituciones": [],
                                "complejos": {}, "spearman": None,
                                "criterio": None})
    artefacto.setdefault("v2", {"referencia_flexible": {}, "pendiente": {}})
    guardar_artefacto(artefacto)

    with ProcessPoolExecutor(max_workers=POOL) as ex:
        if not args.solo_v4:
            pendientes = [p for p in E2_PIDS
                          if p not in artefacto["e2"]["agregados"]]
            if pendientes:
                fase_e2(pendientes, ex, artefacto)
            if not pendientes:
                imprimir_tabla_e2(artefacto["e2"]["agregados"],
                                  artefacto["e2"].get("criterios"))
        if not args.solo_e2:
            fase_v4v2(ex, artefacto)

    print(f"\nArtifacto: {ARTIFACTO}")


if __name__ == "__main__":
    main()
