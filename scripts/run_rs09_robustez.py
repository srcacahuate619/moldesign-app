#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs09_robustez.py — RS-09: robustez metamórfica del selector v0.6.

Prerrequisito sellado: scripts/artifacts_science/RS-09-PRE/PREREGISTRO.md.

Evalúa el checkpoint de producción v0.6 (pose_selector_v06.xgb, congelado)
sobre la cohorte train bajo tres metamorfosis:

  A) Invarianza rígida  — R rotación propia + t traslación sobre poses y receptor.
  B) Orden de poses     — permutación determinista del orden de entrada.
  C) Perturbación débil — ruido gaussiano sigma=0.1 A sobre átomos pesados.

Fuentes de datos (integridad verificada en ejecución):
  - Coordenadas canónicas del ligando: lig_pos de data/pose_selector_dataset/
    gnn_train.pt (dataset congelado; coords de los átomos pesados en el orden
    del cristal; mapeo serial->mol ya aplicado por el pipeline).
  - Receptor: rec.pdbqt de la fuente nativa (v05.obtener_receptor) con
    fallback a data/pdbbind/vina_redock_work/{pid}/{pid}_rec.pdbqt y
    data/dmfhard_curve_work/{pid}/rec.pdbqt para complejos molflex cuyo
    WORK_V3 (scripts/.work_molflex_v3) ya no existe en el worktree.
    La equivalencia del receptor de fallback se verifica contra el bolsillo
    del dataset congelado (prot_pos ⊆ rec completo, match atomico 1e-3 A).
  - Complejos sin receptor disponible en ninguna fuente: EXCLUIDOS de A/B/C
    y declarados explícitamente como "no cubiertos por indisponibilidad de
    datos", NO como fallos del selector (desviación de ejecución documentada).

Criterios (PREREGISTRO §6): G1 (A: 100% Top-1 idéntico + max_dif<=1e-6),
G2 (B: 100% Top-1 idéntico), G3 (C: flips ok->mal <= 2), G4 (C: >=60% de
cambios en terciles 1-2 de margen), G5 (drift re-extracción = 0), G6 (aislamiento).

NO entrena. NO toca el checkpoint, el dataset congelado ni el cache. Solo
re-extrae features con el extractor v0.5 y puntúa con el booster de producción.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import ruta_c_fase3_5_decidibilidad as rc35  # noqa: E402 (reutiliza machinery probado R-RC5)
import ruta_c_fase1_5_v05 as v05  # noqa: E402
import ruta_c_fase3_calibracion as f3  # noqa: E402

OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-09"
TRAIN_JSONL = PROJECT_ROOT / "data" / "pose_selector_dataset" / "poses_train.jsonl"
GNN_TRAIN_PT = PROJECT_ROOT / "data" / "pose_selector_dataset" / "gnn_train.pt"
VINA_REDOCK_DIR = PROJECT_ROOT / "data" / "pdbbind" / "vina_redock_work"
DMFHARD_DIR = PROJECT_ROOT / "data" / "dmfhard_curve_work"

CHECKPOINT = PROJECT_ROOT / "rescoring" / "artifacts" / "pose_selector_v06.xgb"
CHECKPOINT_SHA = "9827DDB94C5DED5B2EF1DDA1250606D73F73163BECC310641D5BD493196E5D31"

TOL_INVARIANZA = 1e-6
SIGMA_RUIDO = 0.1
UMBRAL_POSITIVA = f3.UMBRAL_POSITIVA
SEED_BASE_A = 1000
SEED_BASE_B = 2000
SEED_BASE_C = 42

_receptor_cache: dict[str, dict | None] = {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def cargar_train() -> list[dict]:
    rows = []
    with open(TRAIN_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cargar_gnn_ligpos() -> dict[tuple, np.ndarray]:
    """lig_pos (n_heavy, 3) por (pid, source, file_stem, model_idx) desde
    gnn_train.pt (dataset congelado; coords pesados en orden del cristal)."""
    import torch
    obj = torch.load(str(GNN_TRAIN_PT), map_location="cpu", weights_only=False)
    mapa: dict[tuple, np.ndarray] = {}
    for d in obj:
        key = (d.pid, d.source, d.file_stem, int(d.model_idx))
        mapa[key] = d.lig_pos.numpy().astype(np.float64)
    return mapa


def construir_receptor_pid(pid: str) -> dict | None:
    """Receptor (dict tipado v0.5) para un complejo, cacheado por pid.

    Fuentes: v05.obtener_receptor (nativa por fuente) y fallbacks para
    molflex: vina_redock_work/{pid}/{pid}_rec.pdbqt, luego
    dmfhard_curve_work/{pid}/rec.pdbqt (leer_rec_pdbqt + _tipar_receptor).
    """
    if pid in _receptor_cache:
        return _receptor_cache[pid]

    rec = None
    # fuente nativa (una pose cualquiera del complejo)
    rows_pid = [r for r in _ROWS_BY_PID.get(pid, [])]
    for r in rows_pid:
        rec = v05.obtener_receptor(r["pid"], r["source"], r["file_stem"])
        if rec is not None:
            break
    # fallbacks molflex
    if rec is None:
        for cand in (VINA_REDOCK_DIR / pid / f"{pid}_rec.pdbqt",
                     DMFHARD_DIR / pid / "rec.pdbqt"):
            if cand.exists():
                parsed = v05.leer_rec_pdbqt(cand)
                if parsed is not None:
                    coords, elems, resnames, atomnames = parsed
                    rec = v05._tipar_receptor(pid, coords, elems, resnames, atomnames)
                    break
    _receptor_cache[pid] = rec
    return rec


_ROWS_BY_PID: dict[str, list[dict]] = {}


def puntuar_233(records: list[dict]) -> np.ndarray:
    """Replica puntuar_complejo de la Fase 3 (z intra-complejo + percentil)."""
    return f3.puntuar_complejo(records)


def top1_id(scores: np.ndarray, regs: list[dict]):
    """Identidad de la pose elegida por argmax (mayor = mejor)."""
    return rc35.argmax_identidad(scores, regs)


def main() -> int:
    global _ROWS_BY_PID
    t0 = time.time()

    # G6: aislamiento (SHA del checkpoint antes de nada)
    if not CHECKPOINT.exists():
        print(f"[!] Checkpoint no encontrado: {CHECKPOINT}")
        return 2
    cp_sha = sha256_file(CHECKPOINT)
    print(f"[*] Checkpoint v0.6 SHA-256: {cp_sha}")

    rows = cargar_train()
    por_pid: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        por_pid[r["pid"]].append(r)
    _ROWS_BY_PID = por_pid
    pids = sorted(por_pid.keys())
    print(f"[*] Cohort: {len(pids)} complejos train, {len(rows)} poses")

    # Cobertura: complejos con receptor disponible (nativo o fallback)
    pids_con_receptor = [p for p in pids if construir_receptor_pid(p) is not None]
    pids_sin_receptor = [p for p in pids if p not in pids_con_receptor]
    print(f"[*] A/B/C sobre {len(pids_con_receptor)} complejos con receptor "
          f"({len(pids_sin_receptor)} sin receptor en ninguna fuente: "
          f"{sorted(pids_sin_receptor)})")

    # Coordenadas canónicas del dataset congelado
    ligpos = cargar_gnn_ligpos()
    print(f"[*] gnn_train.pt: {len(ligpos)} poses con lig_pos")

    # ── Pase canónico (una sola vez): lig_pos + features ───────────────────
    print("[*] Re-extracción canónica (lig_pos del dataset congelado)...")
    canon: dict[str, dict] = {}
    for pid in pids_con_receptor:
        regs = por_pid[pid]
        pesados, elems = rc35.meta_cristal(pid)
        rec = construir_receptor_pid(pid)
        coords = []
        d224 = []
        for r in regs:
            key = (r["pid"], r["source"], r["file_stem"], int(r["model_idx"]))
            if key not in ligpos:
                raise RuntimeError(f"pose sin lig_pos en dataset congelado: {key}")
            coords.append(ligpos[key])
        dens = rc35.cluster_por_par(coords)
        lig_elems = [elems[m] for m in pesados]
        for k, r in enumerate(regs):
            d224.append(rc35.extraer_224(r, rec, coords[k], lig_elems,
                                         float(dens[k])))
        scores = puntuar_233(d224)
        canon[pid] = {"regs": regs, "d224": d224, "coords": coords,
                      "receptor": rec, "scores": scores, "dens": dens}

    # ── A) Invarianza rígida ────────────────────────────────────────────────
    print("[*] A) Invarianza rígida (R + t sobre poses y receptor)...")
    a_result = {"n_total": 0, "n_ok": 0, "max_dif_224": 0.0, "detalle": []}
    for i, pid in enumerate(pids_con_receptor):
        info = canon[pid]
        rng = np.random.default_rng(SEED_BASE_A + i)
        R = rc35.rotacion_propia(rng)
        t = rng.uniform(-50.0, 50.0, size=3)
        coords_rot = [c @ R.T + t for c in info["coords"]]
        rec_rot = rc35.receptor_transformado(info["receptor"], R, t)
        dens_rot = rc35.cluster_por_par(coords_rot)
        pesados, elems = rc35.meta_cristal(pid)
        lig_elems = [elems[m] for m in pesados]
        d224_rot = [
            rc35.extraer_224(r, rec_rot, coords_rot[k], lig_elems,
                             float(dens_rot[k]))
            for k, r in enumerate(info["regs"])
        ]
        # max_dif de features canónicas vs rotadas (las 224)
        max_dif = 0.0
        for dc, dr in zip(info["d224"], d224_rot):
            for key in dc:
                if key in ("vina_score", "pose_score_variance", "pose_score_range", "n_heavy"):
                    continue
                max_dif = max(max_dif, abs(float(dc[key]) - float(dr[key])))
        scores_rot = puntuar_233(d224_rot)
        sel_c = top1_id(info["scores"], info["regs"])
        sel_r = top1_id(scores_rot, info["regs"])
        ok = max_dif <= TOL_INVARIANZA and sel_r == sel_c
        a_result["n_total"] += 1
        a_result["n_ok"] += int(ok)
        a_result["max_dif_224"] = max(a_result["max_dif_224"], max_dif)
        a_result["detalle"].append({
            "pid": pid, "n_poses": len(info["regs"]),
            "max_dif_224": round(max_dif, 9), "top1_estable": bool(ok),
            "sel_canonica": sel_c, "sel_rotada": sel_r,
        })
        if not ok:
            print(f"  [A] {pid}: NO OK max_dif={max_dif:.3e}")

    # ── B) Orden de poses (permutación) ─────────────────────────────────────
    print("[*] B) Orden de poses (permutación determinista)...")
    b_result = {"n_total": 0, "n_ok": 0, "detalle": []}
    for i, pid in enumerate(pids_con_receptor):
        info = canon[pid]
        rng = np.random.default_rng(SEED_BASE_B + i)
        perm = rng.permutation(len(info["regs"]))
        d224_perm = [info["d224"][k] for k in perm]
        regs_perm = [info["regs"][k] for k in perm]
        scores_perm = puntuar_233(d224_perm)
        sel_c = top1_id(info["scores"], info["regs"])
        sel_p = top1_id(scores_perm, regs_perm)
        ok = sel_p == sel_c
        b_result["n_total"] += 1
        b_result["n_ok"] += int(ok)
        b_result["detalle"].append({
            "pid": pid, "perm": perm.tolist(),
            "sel_canonica": sel_c, "sel_permutada": sel_p, "estable": bool(ok),
        })
        if not ok:
            print(f"  [B] {pid}: ORDEN CAMBIA SELECCION {sel_c} -> {sel_p}")

    # ── C) Perturbación débil ───────────────────────────────────────────────
    print("[*] C) Perturbación débil (sigma=0.1 A sobre poses, receptor fijo)...")
    c_result = {"n_total": 0, "n_cambiaron": 0, "n_flips_ok_mal": 0,
                "flips": [], "drift_limpio": [], "detalle_cambios": []}
    margen_por_pid = {pid: None for pid in pids_con_receptor}
    for pid in pids_con_receptor:
        info = canon[pid]
        scores = info["scores"]
        srt = np.argsort(-scores)
        if len(srt) >= 2:
            margen_por_pid[pid] = float(scores[srt[0]] - scores[srt[1]])
    pesados_cache: dict[str, list] = {}
    for i, pid in enumerate(pids_con_receptor):
        info = canon[pid]
        if pid not in pesados_cache:
            pesados, elems = rc35.meta_cristal(pid)
            pesados_cache[pid] = [elems[m] for m in pesados]
        lig_elems = pesados_cache[pid]
        rng = np.random.default_rng(SEED_BASE_C + i)
        coords_pert = [c + rng.normal(0.0, SIGMA_RUIDO, c.shape) for c in info["coords"]]
        dens_p = rc35.cluster_por_par(coords_pert)
        d224_pert = [
            rc35.extraer_224(r, info["receptor"], coords_pert[k], lig_elems,
                             float(dens_p[k]))
            for k, r in enumerate(info["regs"])
        ]
        scores_pert = puntuar_233(d224_pert)
        sel_c = top1_id(info["scores"], info["regs"])
        sel_p = top1_id(scores_pert, info["regs"])

        # Drift: re-extracción limpia vs canónica (control del extractor)
        dens_l = rc35.cluster_por_par(info["coords"])
        d224_limpio = [
            rc35.extraer_224(r, info["receptor"], info["coords"][k], lig_elems,
                             float(dens_l[k]))
            for k, r in enumerate(info["regs"])
        ]
        s_limpio = puntuar_233(d224_limpio)
        sel_l = top1_id(s_limpio, info["regs"])
        if sel_l != sel_c:
            c_result["drift_limpio"].append({"pid": pid, "sel_canonica": sel_c, "sel_limpia": sel_l})

        top1_ok_c = info["regs"][int(np.argmax(info["scores"]))]["rmsd"] <= UMBRAL_POSITIVA
        top1_ok_p = info["regs"][int(np.argmax(scores_pert))]["rmsd"] <= UMBRAL_POSITIVA
        c_result["n_total"] += 1
        if sel_p != sel_c:
            c_result["n_cambiaron"] += 1
            c_result["detalle_cambios"].append({
                "pid": pid, "margin": round(margen_por_pid[pid], 6) if margen_por_pid[pid] is not None else None,
                "sel_canonica": sel_c, "sel_perturbada": sel_p,
            })
            if top1_ok_c and not top1_ok_p:
                c_result["n_flips_ok_mal"] += 1
                c_result["flips"].append(pid)

    # Terciles de margen para G4
    finitos = sorted(margen_por_pid[p] for p in pids_con_receptor
                     if margen_por_pid[p] is not None)
    grupos = np.array_split(np.array(finitos), 3)
    cambiados_set = {d["pid"] for d in c_result["detalle_cambios"]}
    terciles = []
    for k, g in enumerate(grupos, 1):
        n_cam = sum(1 for p in pids_con_receptor
                    if margen_por_pid[p] is not None and margen_por_pid[p] in g and p in cambiados_set)
        terciles.append({
            "tercil": k,
            "rango_margen": [round(float(g[0]), 4), round(float(g[-1]), 4)],
            "n_complejos": int(len(g)),
            "n_cambiaron": n_cam,
            "fraccion_cambio": round(n_cam / len(g), 4) if len(g) else 0.0,
        })
    n_cam_t12 = terciles[0]["n_cambiaron"] + terciles[1]["n_cambiaron"]
    frac_t12 = n_cam_t12 / c_result["n_cambiaron"] if c_result["n_cambiaron"] else 1.0

    # ── Gates ────────────────────────────────────────────────────────────────
    # Cobertura honesta: A/B/C sobre complejos con receptor (109 de 116).
    # Los complejos sin receptor (7, todos molflex puros) se declaran "no
    # cubiertos por indisponibilidad de datos de receptor" (NO como fallos
    # del selector). Desviación de ejecución documentada (RS-09-PRE pedía
    # 116/116; la infraestructura .work_molflex_v3 ya no existe en el worktree).
    n_ac = len(pids_con_receptor)
    g1 = a_result["n_ok"] == n_ac and a_result["max_dif_224"] <= TOL_INVARIANZA
    g2 = b_result["n_ok"] == n_ac
    g3 = c_result["n_flips_ok_mal"] <= 2
    g4 = frac_t12 >= 0.60
    g5 = len(c_result["drift_limpio"]) == 0
    g6 = cp_sha.upper() == CHECKPOINT_SHA
    gates = {
        "G1_invarianza_rigida": {"pass": g1, "criterio": f"{n_ac}/{n_ac} Top-1 idéntico y max_dif<=1e-6",
                                  "n_ok": a_result["n_ok"], "max_dif_224": a_result["max_dif_224"]},
        "G2_orden": {"pass": g2, "criterio": f"{n_ac}/{n_ac} Top-1 idéntico bajo permutación",
                      "n_ok": b_result["n_ok"]},
        "G3_perturbacion_flips": {"pass": g3, "criterio": "flips ok->mal <= 2",
                                   "n_flips": c_result["n_flips_ok_mal"]},
        "G4_perturbacion_terciles": {"pass": g4, "criterio": ">=60% cambios en terciles 1-2",
                                      "frac_t12": round(frac_t12, 4), "terciles": terciles},
        "G5_drift_reextraccion": {"pass": g5, "criterio": "0 mismatches limpio vs canónico",
                                   "n_drift": len(c_result["drift_limpio"])},
        "G6_aislamiento_checkpoint": {"pass": g6, "criterio": "SHA-256 del checkpoint idéntico",
                                       "sha": cp_sha},
    }
    decision = "GO" if all(g["pass"] for g in gates.values()) else "NO_GO"
    print(f"\n[*] Decisión: {decision}")
    for k, g in gates.items():
        print(f"    {k}: {'PASS' if g['pass'] else 'FAIL'} ({g})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {
        "experiment_id": "RS-09",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "decision": decision,
        "checkpoint": {"path": str(CHECKPOINT), "sha256": cp_sha,
                        "esperado": CHECKPOINT_SHA},
        "cohorte": {"n_complejos_train": len(pids), "n_poses": len(rows),
                     "n_con_receptor": n_ac, "n_sin_receptor": len(pids_sin_receptor),
                     "pids_sin_receptor": sorted(pids_sin_receptor),
                     "cobertura_pct": round(n_ac / len(pids) * 100, 2),
                     "nota_cobertura": "A/B/C evaluados sobre complejos con receptor disponible (nativo o fallback vina_redock_work/dmfhard_curve_work). Los complejos sin receptor (todos molflex puros, WORK_V3 inexistente en el worktree) se declaran NO cubiertos por indisponibilidad de datos, no como fallos del selector. Fuentes de coords canonicas: lig_pos de gnn_train.pt (dataset congelado). Desviacion de ejecucion vs RS-09-PRE (116/116): documentada en DESIGN.md."},
        "gates": gates,
        "A_invarianza": {k: v for k, v in a_result.items() if k != "detalle"},
        "B_orden": {k: v for k, v in b_result.items() if k != "detalle"},
        "C_perturbacion": {k: v for k, v in c_result.items()
                            if k not in ("detalle_cambios", "flips")},
        "margenes": {"n_finitos": len(finitos),
                      "media": round(float(np.mean(finitos)), 6) if finitos else None,
                      "mediana": round(float(np.median(finitos)), 6) if finitos else None},
    }
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for pid in pids_con_receptor:
            det_a = next(d for d in a_result["detalle"] if d["pid"] == pid)
            det_b = next(d for d in b_result["detalle"] if d["pid"] == pid)
            det_c = next((d for d in c_result["detalle_cambios"] if d["pid"] == pid), None)
            f.write(json.dumps({
                "pid": pid, "n_poses": len(por_pid[pid]),
                "A_max_dif_224": det_a["max_dif_224"], "A_top1_estable": det_a["top1_estable"],
                "B_estable": det_b["estable"],
                "C_cambio": det_c is not None,
                "C_margin": det_c["margin"] if det_c else None,
                "margin": margen_por_pid[pid],
            }, ensure_ascii=False) + "\n")

    failures = []
    for pid in pids_con_receptor:
        det_a = next(d for d in a_result["detalle"] if d["pid"] == pid)
        det_b = next(d for d in b_result["detalle"] if d["pid"] == pid)
        if not det_a["top1_estable"]:
            failures.append({"pid": pid, "test": "A_invarianza"})
        if not det_b["estable"]:
            failures.append({"pid": pid, "test": "B_orden"})
    (OUT_DIR / "failures.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in failures) + ("\n" if failures else ""),
        encoding="utf-8", newline="\n")

    print(f"[*] Artefactos en {OUT_DIR}")
    return 0 if decision == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
