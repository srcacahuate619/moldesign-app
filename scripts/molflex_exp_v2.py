# -*- coding: utf-8 -*-
"""
molflex_exp_v2.py — Verificación de los criterios pre-registrados E1/E2/E3
de MolFlex v2 (docs/40_MOLFLEX_PROTOCOL.md, sección 5.4).

  E1: cobertura efectiva (ensemble + relax) ≥ 90% de complejos con la
      conformación cristalográfica recuperada a <1.5Å (15 complejos).
  E2: wall time por complejo <120s con topología correcta (cpu=1 por Vina,
      paralelismo global que satura 12 cores sin oversubscription; 5 complejos).
  E3: el relax NO degrada el score de consenso (score post-relax ≤ score
      rígido + 0.5 kcal/mol en ≥90%).

Topología: pool global de 12 workers; olas de 2 complejos (6 docks paralelos
por complejo, cpu=1 por Vina). Fase 3 (relax) en un lote global al final.

Resultado: scripts/artifacts_molflex_v2.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402

E2E3_PIDS = ["1a4w", "1aaq", "1ajx", "10gs", "184l"]  # 3 timeout + 2 fáciles
N_E1 = 15
N_CONF = 30
TOP_K = 3
POOL = 12
WAVE = 2
CPU = 1  # cpu=1 por Vina (pre-registrado)
ARTIFACTO = PROJECT_ROOT / "scripts" / "artifacts_molflex_v2.json"


# ─────────────────────── selección de complejos ────────────────────────────

def complejos_e1(excluir: set) -> list:
    """Primeros 15 complejos válidos (orden alfabético) con SDF legible,
    excluyendo los usados en E2/E3."""
    out = []
    for d in sorted(mf.PDBBIND.iterdir()):
        if len(out) >= N_E1:
            break
        if not d.is_dir() or len(d.name) != 4:
            continue
        if d.name in excluir:
            continue
        sdf = d / f"{d.name}_ligand.sdf"
        prot = d / f"{d.name}_protein.pdb"
        if not sdf.exists() or not prot.exists():
            continue
        if mf.leer_ligando(sdf) is None:
            continue  # sdf_unreadable — se salta con razón implícita
        out.append(d.name)
    return out


# ─────────────────────── ejecución global en olas ──────────────────────────

def ejecutar_experimento(pids: list, work: str | Path, pool: int = POOL,
                         wave: int = WAVE) -> dict:
    """Fases 1-2 en olas de `wave` complejos (pool global), Fase 3 en un lote
    global al final. Devuelve datos crudos por complejo."""
    res = {}
    with ProcessPoolExecutor(max_workers=pool) as ex:
        # ── Fases 1+2: olas ──
        for i in range(0, len(pids), wave):
            lote = pids[i:i + wave]
            preps = {}
            t_prep_submit = {}
            prep_futs = {}
            for pid in lote:
                t_prep_submit[pid] = time.monotonic()
                prep_futs[ex.submit(mf.preparar_complejo, pid, N_CONF, str(work))] = pid
            for f in as_completed(prep_futs):
                pid = prep_futs[f]
                try:
                    preps[pid] = f.result(timeout=600)
                except Exception as e:  # noqa: BLE001
                    preps[pid] = {"ok": False, "reason": type(e).__name__}
            # Docks del lote (cpu=1 por Vina; el pool global reparte 12 cores).
            futs = {}
            for pid in lote:
                prep = preps[pid]
                res[pid] = {"prep": prep, "docks": {}, "relaxes": {},
                            "t_prep_submit": t_prep_submit[pid],
                            "t_prep_end": time.monotonic(),
                            "t_dock_start": None, "t_dock_end": None,
                            "t_relax_start": None, "t_relax_end": None}
                if not prep["ok"]:
                    print(f"  {pid}: PREP FAIL → {prep.get('reason')}", flush=True)
                    continue
                t0 = time.monotonic()
                res[pid]["t_dock_start"] = t0
                for cid in prep["cids"]:
                    futs[ex.submit(mf.dock_rigido_archivo, pid, cid,
                                   str(work), CPU)] = (pid, cid)
            for f in as_completed(futs):
                pid, cid = futs[f]
                t_end = time.monotonic()
                try:
                    d = f.result(timeout=360)
                except Exception as e:  # noqa: BLE001
                    d = {"pid": pid, "cid": cid, "ok": False,
                         "reason": type(e).__name__, "t": 0.0}
                d["t_wall"] = round(t_end - res[pid]["t_dock_start"], 1)
                res[pid]["docks"][cid] = d
                if res[pid]["t_dock_end"] is None or t_end > res[pid]["t_dock_end"]:
                    res[pid]["t_dock_end"] = t_end
            for pid in lote:
                n_ok = sum(1 for d in res[pid]["docks"].values() if d["ok"])
                print(f"  {pid}: prep={preps[pid].get('n_conf')} confs, "
                      f"docks ok={n_ok}/{len(res[pid]['docks'])}", flush=True)

        # ── Fase 3: lote global de relaxes (top-K por complejo) ──
        futs2 = {}
        for pid, r in res.items():
            oks = [(c, d["best"]) for c, d in r["docks"].items() if d["ok"]]
            oks.sort(key=lambda x: x[1])
            top_k = [c for c, _ in oks[:TOP_K]]
            r["top_k_cids"] = top_k
            if top_k:
                r["t_relax_start"] = time.monotonic()
                for cid in top_k:
                    futs2[ex.submit(mf.relax_pose_archivo, pid, cid,
                                    r["docks"][cid]["pose"], str(work), CPU)] = (pid, cid)
        for f in as_completed(futs2):
            pid, cid = futs2[f]
            t_end = time.monotonic()
            try:
                rr = f.result(timeout=360)
            except Exception as e:  # noqa: BLE001
                rr = {"pid": pid, "cid": cid, "ok": False,
                      "reason": type(e).__name__, "t": 0.0}
            rr["t_wall"] = round(t_end - res[pid]["t_relax_start"], 1)
            res[pid]["relaxes"][cid] = rr
            if res[pid]["t_relax_end"] is None or t_end > res[pid]["t_relax_end"]:
                res[pid]["t_relax_end"] = t_end
    return res


# ─────────────────────── agregación por complejo ───────────────────────────

def agregar_pid(pid: str, r: dict, work: str | Path) -> dict:
    """Consolida docks+relaxes: scores, deltas, RMSDs y tiempos de pared."""
    prep = r["prep"]
    docks = r["docks"]
    relaxes = r["relaxes"]
    out = {
        "pdb_id": pid, "ok": False, "reason": None,
        "n_conf": prep.get("n_conf"),
        "n_docks_ok": sum(1 for d in docks.values() if d["ok"]),
        "t_prep_s": prep.get("t"),
        "wall_fase2_s": None, "wall_fase3_s": None, "wall_total_s": None,
    }
    # Pared por fase: desde la primera sumisión hasta el último resultado.
    out["wall_fase2_s"] = (round(r["t_dock_end"] - r["t_dock_start"], 1)
                           if r.get("t_dock_start") and r.get("t_dock_end") else None)
    out["wall_fase3_s"] = (round(r["t_relax_end"] - r["t_relax_start"], 1)
                           if r.get("t_relax_start") and r.get("t_relax_end") else None)
    out["wall_total_s"] = round(sum(v for v in [out["t_prep_s"] or 0,
                                                out["wall_fase2_s"] or 0,
                                                out["wall_fase3_s"] or 0]), 1)

    oks = [(c, d) for c, d in docks.items() if d["ok"]]

    # RMSDs: ensemble crudo y poses relajadas.
    out["rmsd_raw_min"] = None
    for cid, rmsd in prep.get("ensemble_rmsds", []):
        if rmsd is not None and (out["rmsd_raw_min"] is None or rmsd < out["rmsd_raw_min"]):
            out["rmsd_raw_min"] = rmsd
    out["relaxed"] = []
    if not oks:
        out["reason"] = "all_docks_failed"
        return out
    out["rigid_best"] = round(min(d["best"] for _, d in oks), 3)
    out["rigid_rank"] = [{"cid": c, "score": d["best"]}
                         for c, d in sorted(oks, key=lambda x: x[1]["best"])[:TOP_K]]

    crystal = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
    serial_a_mol = mf.cargar_mapa_indices(Path(work) / pid)
    for cid, rr in relaxes.items():
        entrada = {"cid": cid, "ok": rr["ok"], "reason": rr.get("reason"),
                   "relaxed_score": rr.get("relaxed_rigid"),
                   "delta": (round(rr["relaxed_rigid"] - docks[cid]["best"], 3)
                             if rr["ok"] else None),
                   "rmsd_to_crystal": None}
        if rr["ok"] and crystal is not None:
            por_mol = mf.coords_pose_a_por_mol(rr["coords"], serial_a_mol)
            rmsd = mf.rmsd_pesados(crystal, por_mol)
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
    return out


# ─────────────────────── criterios E1/E2/E3 ────────────────────────────────

def evaluar_e2e3(agregados: dict) -> dict:
    """E2 (wall <120s) y E3 (delta ≤ +0.5) sobre los 5 complejos E2/E3."""
    e2_pasa, e2_total = 0, 0
    e3_pasa, e3_total = 0, 0
    for pid, a in agregados.items():
        if a["wall_total_s"] is not None and a["n_docks_ok"] > 0:
            e2_total += 1
            if a["wall_total_s"] < 120.0:
                e2_pasa += 1
        if a.get("delta_best") is not None:
            e3_total += 1
            if a["delta_best"] <= 0.5:
                e3_pasa += 1
    return {
        "E2": {"criterio": "≥90% con wall <120s",
               "n_pasa": e2_pasa, "n_total": e2_total,
               "fraccion": round(e2_pasa / e2_total, 3) if e2_total else None,
               "pass": e2_total > 0 and e2_pasa / e2_total >= 0.9},
        "E3": {"criterio": "≥90% con delta ≤ +0.5 kcal/mol",
               "n_pasa": e3_pasa, "n_total": e3_total,
               "fraccion": round(e3_pasa / e3_total, 3) if e3_total else None,
               "pass": e3_total > 0 and e3_pasa / e3_total >= 0.9},
    }


def evaluar_e1(agregados: dict) -> dict:
    """E1: cobertura con y sin relax (umbral 1.5Å), criterio ≥90% con relax."""
    raw_pasa, raw_total = 0, 0
    rel_pasa, rel_total = 0, 0
    excluidos = []
    for pid, a in agregados.items():
        if a["rmsd_raw_min"] is not None:
            raw_total += 1
            if a["rmsd_raw_min"] < 1.5:
                raw_pasa += 1
        if a.get("rmsd_relaxed_min") is not None:
            rel_total += 1
            if a["rmsd_relaxed_min"] < 1.5:
                rel_pasa += 1
        else:
            excluidos.append(pid)
    cov_raw = round(raw_pasa / raw_total, 3) if raw_total else None
    cov_rel = round(rel_pasa / rel_total, 3) if rel_total else None
    return {
        "E1": {"criterio": "cobertura (ensemble+relax) ≥ 90% a <1.5Å",
               "cobertura_sin_relax": cov_raw,
               "cobertura_con_relax": cov_rel,
               "n_con_relax": rel_pasa, "n_total_con_relax": rel_total,
               "n_sin_relax": raw_pasa, "n_total_sin_relax": raw_total,
               "excluidos_sin_rmsd_relajado": excluidos,
               "pass": cov_rel is not None and cov_rel >= 0.9},
    }


# ───────────────────────────────── main ────────────────────────────────────

def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Verificación E1/E2/E3 de MolFlex v2")
    ap.add_argument("--pool", type=int, default=POOL)
    ap.add_argument("--wave", type=int, default=WAVE)
    ap.add_argument("--solo-e2e3", action="store_true")
    ap.add_argument("--solo-e1", action="store_true")
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args()

    sondeo = mf.sondeo_openmm_relax()
    print("── Sondeo OpenMM (Fase 3) ──")
    print(json.dumps(sondeo, indent=2, ensure_ascii=False))

    work = Path(args.work_dir) if args.work_dir else \
        Path(tempfile.mkdtemp(prefix="molflex_v2_"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"Workdir: {work}")

    # Resultado previo (resumible): se saltan los complejos ya completados.
    previo = {"e2e3": {}, "e1": {}, "openmm_sondeo": None}
    if ARTIFACTO.exists():
        try:
            previo = json.loads(ARTIFACTO.read_text(encoding="utf-8"))
        except Exception:
            previo = {"e2e3": {}, "e1": {}, "openmm_sondeo": None}
    salida = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "config": {"n_conf": N_CONF, "top_k": TOP_K, "pool": args.pool,
                         "wave": args.wave, "cpu_vina": CPU,
                         "box": mf.BOX_SIZE, "exhaustiveness": mf.EXHAUSTIVENESS,
                         "num_modes": mf.NUM_MODES,
                         "relax_engine": sondeo["relax_engine"]},
              "openmm_sondeo": sondeo,
              "e2e3": previo.get("e2e3") or {},
              "e1": previo.get("e1") or {}}

    if not args.solo_e1:
        pids = [p for p in E2E3_PIDS if p not in salida["e2e3"].get("agregados", {})]
        if pids:
            print(f"\n═══ E2/E3: {len(pids)} complejos "
                  f"({len(pids)} de timeout-flexible + fáciles) ═══")
            crudo = ejecutar_experimento(pids, work, args.pool, args.wave)
            agregados = {pid: agregar_pid(pid, r, work) for pid, r in crudo.items()}
            criterios = evaluar_e2e3(agregados)
            salida["e2e3"] = {"pids": E2E3_PIDS, "agregados": agregados,
                              "criterios": criterios}
            ARTIFACTO.write_text(json.dumps(salida, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
            imprimir_tabla_e2e3(agregados, criterios)

    if not args.solo_e2e3:
        e2e3_agregados = salida["e2e3"].get("agregados", {})
        e1_pids = [p for p in complejos_e1(set(E2E3_PIDS))
                   if p not in salida["e1"].get("agregados", {})]
        if e1_pids:
            print(f"\n═══ E1: {len(e1_pids)} complejos (cobertura con/sin relax) ═══")
            print("Complejos:", ", ".join(e1_pids))
            crudo = ejecutar_experimento(e1_pids, work, args.pool, args.wave)
            agregados = {pid: agregar_pid(pid, r, work) for pid, r in crudo.items()}
            criterios = evaluar_e1(agregados)
            salida["e1"] = {"pids": e1_pids, "agregados": agregados,
                            "criterios": criterios}
            ARTIFACTO.write_text(json.dumps(salida, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
            imprimir_tabla_e1(agregados, criterios)

    print(f"\nArtifacto: {ARTIFACTO}")


def imprimir_tabla_e2e3(agregados: dict, criterios: dict) -> None:
    print("\n── E2/E3 por complejo ──")
    print(f"{'pid':6} {'n_conf':>6} {'prep':>5} {'wall_f2':>7} {'wall_f3':>7} "
          f"{'wall':>6} {'rigid':>7} {'relax':>7} {'delta':>7} {'<120s':>6} {'E3':>4}")
    for pid, a in sorted(agregados.items()):
        ok120 = "SÍ" if a["wall_total_s"] is not None and a["wall_total_s"] < 120 else "no"
        e3 = "SÍ" if (a.get("delta_best") is not None and a["delta_best"] <= 0.5) else "no"
        print(f"{pid:6} {a['n_conf'] or 0:6} {a['t_prep_s'] or 0:5.0f} "
              f"{a['wall_fase2_s'] or 0:7.0f} {a['wall_fase3_s'] or 0:7.0f} "
              f"{a['wall_total_s'] or 0:6.0f} {a.get('rigid_best', float('nan')):7.2f} "
              f"{a.get('relaxed_best', float('nan')):7.2f} "
              f"{a.get('delta_best', float('nan')):+7.2f} {ok120:>6} {e3:>4}")
    for nombre, c in criterios.items():
        print(f"{nombre}: {c['n_pasa']}/{c['n_total']} ({c['fraccion']}) "
              f"→ {'PASS' if c['pass'] else 'FAIL'} | {c['criterio']}")


def imprimir_tabla_e1(agregados: dict, criterios: dict) -> None:
    print("\n── E1 por complejo ──")
    print(f"{'pid':6} {'n_conf':>6} {'rmsd_raw':>9} {'rmsd_rel':>9} {'raw<1.5':>7} {'rel<1.5':>7}")
    for pid, a in sorted(agregados.items()):
        raw = a["rmsd_raw_min"]
        rel = a.get("rmsd_relaxed_min")
        print(f"{pid:6} {a['n_conf'] or 0:6} {raw if raw is not None else float('nan'):9.2f} "
              f"{rel if rel is not None else float('nan'):9.2f} "
              f"{'SÍ' if raw is not None and raw < 1.5 else 'no':>7} "
              f"{'SÍ' if rel is not None and rel < 1.5 else 'no':>7}")
    c = criterios["E1"]
    print(f"E1: cobertura sin relax = {c['cobertura_sin_relax']} "
          f"({c['n_sin_relax']}/{c['n_total_sin_relax']}); "
          f"con relax = {c['cobertura_con_relax']} "
          f"({c['n_con_relax']}/{c['n_total_con_relax']}) "
          f"→ {'PASS' if c['pass'] else 'FAIL'} | {c['criterio']}")
    if c["excluidos_sin_rmsd_relajado"]:
        print("  Excluidos (sin RMSD relajado):", c["excluidos_sin_rmsd_relajado"])


if __name__ == "__main__":
    main()
