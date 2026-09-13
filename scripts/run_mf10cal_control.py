#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf10cal_control.py — MF-10-CAL: control positivo y convergencia de MF-10.

Prerrequisito formal: `scripts/artifacts_science/MF-10-CAL-PRE/PREREGISTRO.md` sellado.
Corre en el contenedor `moldesign-lab` del servidor, igual que `MF-10`.

Qué arregla
-----------
La auditoría de `MF-10` (2026-08-18) encontró dos controles ausentes que limitan la
interpretación de su NO_GO, no su validez:

  §3.1  **No hay control positivo.** MF-10 midió cuánto acerca el campo de fuerza una
        pose dockeada al cristal, pero nunca midió dónde pone el campo de fuerza al
        **propio cristal**. Sin ese número no se distingue «el FF no ayuda» de «el
        mínimo del FF está a X A del cristal, y X es el suelo del instrumento».
        Agravante: la minimización es en vacío, donde el mínimo se desplaza de forma
        sistemática respecto del cristal.

  §3.2  **No se registró la convergencia.** `minimizeEnergy(maxIterations=500)` no
        deja constancia de si paró por tolerancia o por agotar presupuesto. PDBFixer
        acaba de añadir todos los hidrógenos de la proteína en posiciones
        idealizadas y esos hidrógenos están **libres** (el restraint es sólo sobre
        pesados). La correlación entre caída de energía y movimiento del ligando fue
        **0.134**: las caídas de ~1,400 kcal/mol no se gastaron en mover el ligando.
        Compatible con «el ligando ya estaba en un mínimo» y también con «el
        presupuesto se fue en los hidrógenos de la proteína».

Diseño
------
Reutiliza **exactamente** el mismo constructor de sistema que `MF-10`
(`construir_sistema`), de modo que cualquier diferencia medida sea del protocolo de
minimización y no de la preparación.

  BRAZO A — control positivo (48 complejos, 1 minimización cada uno)
    Minimiza la **pose cristalográfica** con el protocolo idéntico de MF-10 y mide
    el RMSD del ligando respecto del cristal después de minimizar. Ese número es el
    **suelo del instrumento**: ninguna pose puede acercarse más que eso.

  BRAZO B — convergencia (submuestra de poses reales)
    Para cada pose de la submuestra, minimiza con `maxIterations` en {500, 2000,
    10000} y registra, además del RMSD, la **fuerza residual RMS sobre los átomos
    pesados del ligando**. Si a 500 iteraciones esa fuerza ya es pequeña, el ligando
    estaba en un mínimo local y §3.2 queda refutada; si baja al subir el
    presupuesto, MF-10 midió con el minimizador a medio camino.

La submuestra del brazo B se elige por **score**, nunca por RMSD, y se declara en el
prerregistro: las poses de la banda 2-3 A de los complejos que sí se pudieron
parametrizar, que son las únicas donde una minimización local podría convertir.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_mf10_relax_insitu import construir_sistema, rmsd_pocket, UMBRAL_A  # noqa: E402

ITERACIONES = (500, 2000, 10000)


def _fuerza_rms_ligando(sim, idx_lig) -> float:
    """Fuerza RMS (kcal/mol/A) sobre los pesados del ligando tras minimizar.

    Es el diagnóstico directo de convergencia local: si es ~0 el ligando está en un
    mínimo, independientemente de cuántas iteraciones se hayan gastado en la proteína.
    """
    import numpy as np
    from openmm import unit
    st = sim.context.getState(getForces=True)
    f = st.getForces(asNumpy=True).value_in_unit(
        unit.kilocalories_per_mole / unit.angstrom)
    fl = f[idx_lig]
    return float(np.sqrt((fl ** 2).sum(axis=1).mean()))


def _cristal(ws: Path, pid: str):
    from rdkit import Chem
    sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
    mol = Chem.MolFromMolFile(str(sdf))
    if mol is None:
        mol = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if mol is None:
        return None, None, None
    cf = mol.GetConformer(0)
    pesados = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
    ref = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
           for i in pesados]
    return mol, pesados, ref


def brazo_a(ws: Path, pid: str, estrato: str) -> Dict[str, Any]:
    """Control positivo: minimizar el propio cristal y medir cuánto se aleja."""
    from openmm import unit
    t0 = time.time()
    mol, pesados, ref = _cristal(ws, pid)
    if mol is None:
        return {"pid": pid, "estrato": estrato, "error": "SDF_ILEGIBLE"}
    try:
        sim, idx_lig, _ = construir_sistema(ws, pid, mol, ref)
        e0 = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
            unit.kilocalories_per_mole)
        sim.minimizeEnergy(maxIterations=500)
        st = sim.context.getState(getPositions=True, getEnergy=True)
        e1 = st.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
        pos = st.getPositions(asNumpy=True).value_in_unit(unit.angstroms)
        nuevas = [pos[i].tolist() for i in idx_lig]
        deriva = rmsd_pocket(ref, nuevas)
        return {"pid": pid, "estrato": estrato,
                "deriva_cristal_A": round(deriva, 3),
                "energia_antes": round(float(e0), 2), "energia_despues": round(float(e1), 2),
                "fuerza_rms_ligando": round(_fuerza_rms_ligando(sim, idx_lig), 4),
                "t_s": round(time.time() - t0, 1)}
    except Exception as ex:
        return {"pid": pid, "estrato": estrato,
                "error": f"{type(ex).__name__}: {str(ex)[-200:]}",
                "t_s": round(time.time() - t0, 1)}


def brazo_b(ws: Path, pid: str, pose: Dict[str, Any], estrato: str) -> Dict[str, Any]:
    """Convergencia: barrido de maxIterations sobre una misma pose."""
    from openmm import unit
    mol, pesados, ref = _cristal(ws, pid)
    fila: Dict[str, Any] = {"pid": pid, "estrato": estrato, "score": pose["score"],
                            "rmsd_antes": pose["rmsd"], "barrido": []}
    if mol is None:
        fila["error"] = "SDF_ILEGIBLE"
        return fila
    try:
        coords = [pose["coords"][str(i)] for i in pesados]
    except KeyError:
        fila["error"] = "MAPEO_INCOMPLETO"
        return fila
    for it in ITERACIONES:
        t0 = time.time()
        try:
            sim, idx_lig, _ = construir_sistema(ws, pid, mol, coords)
            sim.minimizeEnergy(maxIterations=it)
            st = sim.context.getState(getPositions=True, getEnergy=True)
            e1 = st.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
            pos = st.getPositions(asNumpy=True).value_in_unit(unit.angstroms)
            r1 = rmsd_pocket(ref, [pos[i].tolist() for i in idx_lig])
            fila["barrido"].append({
                "max_iter": it, "rmsd_despues": round(r1, 3),
                "delta": round(r1 - pose["rmsd"], 3),
                "energia_despues": round(float(e1), 2),
                "fuerza_rms_ligando": round(_fuerza_rms_ligando(sim, idx_lig), 4),
                "t_s": round(time.time() - t0, 1)})
        except Exception as ex:
            fila["barrido"].append({"max_iter": it,
                                    "error": f"{type(ex).__name__}: {str(ex)[-200:]}",
                                    "t_s": round(time.time() - t0, 1)})
    return fila


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-10-CAL: control positivo y convergencia")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--poses-banda", type=int, default=24,
                    help="tamano de la submuestra del brazo B (declarado en el prerregistro)")
    ap.add_argument("--solo-brazo", choices=["A", "B"], default=None)
    args = ap.parse_args()

    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-10-CAL"
    out_dir.mkdir(parents=True, exist_ok=True)
    poses = json.loads((ws / "scripts" / "mf10_poses.json").read_text(encoding="utf-8"))
    t0 = time.time()
    filas_a: List[Dict[str, Any]] = []
    filas_b: List[Dict[str, Any]] = []

    # ── BRAZO A: control positivo sobre los 48 ──
    if args.solo_brazo in (None, "A"):
        for i, (pid, datos) in enumerate(poses.items(), 1):
            filas_a.append(brazo_a(ws, pid, datos["estrato"]))
            print(f"  [A {i}/{len(poses)}] {pid} -> "
                  f"{filas_a[-1].get('deriva_cristal_A', filas_a[-1].get('error'))} "
                  f"({round(time.time()-t0)}s)", flush=True)
            with open(out_dir / "brazo_a.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for r in filas_a:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ── BRAZO B: convergencia sobre la banda 2-3 A, elegida por score ──
    if args.solo_brazo in (None, "B"):
        cand = []
        for pid, datos in poses.items():
            for p in datos["poses"][:20]:
                if 2.0 < p["rmsd"] <= 3.0:
                    cand.append((pid, datos["estrato"], p))
        # orden por score (mas negativo primero); NUNCA por rmsd
        cand.sort(key=lambda t: t[2]["score"])
        cand = cand[:args.poses_banda]
        for i, (pid, estrato, p) in enumerate(cand, 1):
            filas_b.append(brazo_b(ws, pid, p, estrato))
            print(f"  [B {i}/{len(cand)}] {pid} score={p['score']} "
                  f"({round(time.time()-t0)}s)", flush=True)
            with open(out_dir / "brazo_b.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for r in filas_b:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ── métricas y gates ──
    derivas = [r["deriva_cristal_A"] for r in filas_a if "deriva_cristal_A" in r]
    fuerzas_a = [r["fuerza_rms_ligando"] for r in filas_a if "fuerza_rms_ligando" in r]
    metrics: Dict[str, Any] = {
        "experiment_id": "MF-10-CAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"iteraciones_barrido": list(ITERACIONES), "poses_banda": args.poses_banda,
                   "protocolo": "identico a MF-10 (construir_sistema reutilizado)"},
        "brazo_a": {
            "n": len(filas_a), "n_ok": len(derivas),
            "deriva_mediana_A": round(median(derivas), 3) if derivas else None,
            "deriva_p90_A": round(sorted(derivas)[int(0.9 * (len(derivas) - 1))], 3) if derivas else None,
            "deriva_max_A": round(max(derivas), 3) if derivas else None,
            "fuerza_rms_mediana": round(median(fuerzas_a), 4) if fuerzas_a else None,
        },
    }
    if filas_b:
        por_it = {}
        for it in ITERACIONES:
            ds = [b["delta"] for r in filas_b for b in r["barrido"]
                  if b.get("max_iter") == it and "delta" in b]
            fs = [b["fuerza_rms_ligando"] for r in filas_b for b in r["barrido"]
                  if b.get("max_iter") == it and "fuerza_rms_ligando" in b]
            por_it[str(it)] = {
                "n": len(ds),
                "delta_mediano": round(median(ds), 3) if ds else None,
                "fuerza_rms_mediana": round(median(fs), 4) if fs else None,
                "cruzan": sum(1 for r in filas_b for b in r["barrido"]
                              if b.get("max_iter") == it and "rmsd_despues" in b
                              and r["rmsd_antes"] > UMBRAL_A >= b["rmsd_despues"]),
            }
        metrics["brazo_b"] = {"n_poses": len(filas_b), "por_iteraciones": por_it}

    d_med = metrics["brazo_a"]["deriva_mediana_A"]
    b = metrics.get("brazo_b", {}).get("por_iteraciones", {})
    delta_500 = b.get("500", {}).get("delta_mediano")
    delta_max = b.get(str(ITERACIONES[-1]), {}).get("delta_mediano")
    metrics["gates"] = {
        "C1_suelo": {
            "criterio": "la deriva mediana del cristal minimizado se reporta (medicion, sin umbral)",
            "deriva_mediana_A": d_med, "pass": d_med is not None},
        "C2_suelo_informativo": {
            "criterio": "la deriva mediana del cristal es menor que |delta| que MF-10 habria necesitado (~1.0 A)",
            "pass": (d_med is not None and d_med < 1.0)},
        "C3_convergencia": {
            "criterio": "el delta mediano no mejora materialmente (>0.1 A) al subir de 500 a "
                        f"{ITERACIONES[-1]} iteraciones",
            "delta_500": delta_500, "delta_max": delta_max,
            "pass": (delta_500 is not None and delta_max is not None
                     and (delta_500 - delta_max) <= 0.1)},
    }
    metrics["lectura"] = (
        "C3 PASS => MF-10 midio con el minimizador convergido y su NO_GO es una medicion "
        "del campo de fuerza. C3 FAIL => MF-10 midio con el presupuesto agotado y su G3 "
        "debe releerse como inconcluso."
    )
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(f"\n[MF-10-CAL] suelo del instrumento: deriva mediana del cristal = {d_med} A")
    if filas_b:
        print(f"  convergencia: delta mediano {delta_500} (500 it) -> {delta_max} "
              f"({ITERACIONES[-1]} it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
