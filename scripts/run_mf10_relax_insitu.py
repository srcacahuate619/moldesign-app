#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf10_relax_insitu.py — MF-10: relajación in situ con un force field parametrizado.

Prerrequisito formal: `scripts/artifacts_science/MF-10-PRE/PREREGISTRO.md` sellado.
Corre en el contenedor `moldesign-lab` del servidor.

Por qué en el servidor y no en local
------------------------------------
`molflex.py` tiene una fase 3 de relax que **degrada a `vina --local_only`** porque
en la máquina local Python 3.14 bloquea `openff-toolkit`
(`moldesign-app/docs/SESSION_SUMMARY_v1.6.md`, lección 7). El contenedor tiene
Python 3.11 con openff-toolkit 0.18 y OpenMM 8.5.2, y `RS-03-PARAM-A` ya validó
que Sage 2.2.1 + NAGL parametriza 116/116 ligandos ahí.

Qué mide
--------
Para cada pose entregada por el docking, la minimiza **dentro del bolsillo** con la
proteína restringida y mide el RMSD en marco de pocket **antes y después**. La
pregunta es si el campo de fuerza termina de moldear la pose hacia la conformación
bioactiva, que es la única palanca de la hipótesis original que sigue sin probar
tras MF-08 (caja) y MF-02F (reinicios).

El sondeo de capacidad es el gate G1: si el stack no parametriza, eso **es** el
resultado y se registra, en vez de fingir que el experimento no se pudo hacer.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

AGUAS = {"HOH", "WAT", "DOD"}
UMBRAL_A = 2.0
K_RESTRAINT = 100.0          # kcal/mol/A^2 sobre pesados de proteína
MAX_ITER = 500


def filtrar_receptor(origen: Path, destino: Path) -> int:
    """Solo ATOM, sin aguas ni HETATM, altloc mayoritario (regla de preparer.py)."""
    lineas = origen.read_text(encoding="utf-8", errors="replace").splitlines()
    cuentas: Dict[tuple, Dict[str, int]] = {}
    for l in lineas:
        if l[:6].strip() != "ATOM" or len(l) < 27:
            continue
        rn = l[17:20].strip()
        if rn in AGUAS:
            continue
        try:
            k = (l[21:22].strip() or "A", int(l[22:26].strip()), rn)
        except ValueError:
            continue
        cuentas.setdefault(k, {})[l[16:17]] = cuentas.setdefault(k, {}).get(l[16:17], 0) + 1
    elegido = {k: (" " if c.get(" ", 0) >= max(c.values())
                   else max(c, key=lambda v: (c[v], v == " "))) for k, c in cuentas.items()}
    out, n = [], 0
    for l in lineas:
        if l[:6].strip() in {"TER", "END"}:
            out.append(l)
            continue
        if l[:6].strip() != "ATOM" or len(l) < 27:
            continue
        rn = l[17:20].strip()
        if rn in AGUAS:
            continue
        try:
            k = (l[21:22].strip() or "A", int(l[22:26].strip()), rn)
        except ValueError:
            continue
        if l[16:17] != elegido.get(k, " "):
            continue
        out.append(l[:16] + " " + l[17:])
        n += 1
    destino.write_text("\n".join(out) + "\nEND\n", encoding="utf-8", newline="\n")
    return n


def rmsd_pocket(ref_coords, coords) -> float:
    import numpy as np
    a = np.asarray(ref_coords, dtype=float)
    b = np.asarray(coords, dtype=float)
    return float(np.sqrt(((a - b) ** 2).sum(axis=1).mean()))


def construir_sistema(ws: Path, pid: str, lig_rdkit, coords_pose):
    """(simulation, indices_ligando) con proteína restringida y ligando libre."""
    import numpy as np
    from openmm import app, unit, CustomExternalForce, LangevinIntegrator, Platform
    from openff.toolkit import Molecule
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator
    from rdkit import Chem
    from rdkit.Chem import AllChem

    rec = ws / "_mf10" / f"{pid}_rec.pdb"
    fixed = ws / "_mf10" / f"{pid}_fixed.pdb"
    rec.parent.mkdir(parents=True, exist_ok=True)
    if not fixed.exists():
        filtrar_receptor(ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb", rec)
        # Los PDB de PDBBind traen residuos incompletos y amber14 exige residuos
        # completos con terminos reconocibles. PDBFixer anade atomos pesados que
        # faltan y protones, pero NO reconstruye loops ausentes (missingResidues
        # se vacia a proposito): inventar estructura lejos del bolsillo anadiria
        # ruido sin informar la pregunta. Los cortes de cadena quedan como
        # terminos, y la proteina va restringida de todos modos.
        from pdbfixer import PDBFixer
        fx = PDBFixer(filename=str(rec))
        fx.findMissingResidues()
        fx.missingResidues = {}
        fx.findNonstandardResidues()
        fx.replaceNonstandardResidues()
        fx.findMissingAtoms()
        fx.addMissingAtoms()
        fx.addMissingHydrogens(7.0)
        with open(fixed, "w") as fh:
            app.PDBFile.writeFile(fx.topology, fx.positions, fh, keepIds=True)
    pdb = app.PDBFile(str(fixed))

    mol = Chem.Mol(lig_rdkit)
    conf = mol.GetConformer(0)
    pesados = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
    for j, i in enumerate(pesados):
        conf.SetAtomPosition(i, coords_pose[j])
    molh = Chem.AddHs(mol, addCoords=True)
    off = Molecule.from_rdkit(molh, allow_undefined_stereo=True)
    off.assign_partial_charges(partial_charge_method="openff-gnn-am1bcc-1.0.0.pt")

    gen = SMIRNOFFTemplateGenerator(molecules=off, forcefield="openff-2.2.1.offxml")
    ff = app.ForceField("amber14-all.xml")
    ff.registerTemplateGenerator(gen.generator)

    lig_top = off.to_topology().to_openmm()
    lig_pos = off.conformers[0].to_openmm()
    modeller = app.Modeller(pdb.topology, pdb.positions)
    modeller.add(lig_top, lig_pos)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.NoCutoff,
                             constraints=app.HBonds)

    n_prot = pdb.topology.getNumAtoms()
    restr = CustomExternalForce("k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    restr.addGlobalParameter("k", K_RESTRAINT * unit.kilocalories_per_mole / unit.angstroms**2)
    for p in ("x0", "y0", "z0"):
        restr.addPerParticleParameter(p)
    posiciones = modeller.positions
    for i, atom in enumerate(modeller.topology.atoms()):
        if i < n_prot and atom.element is not None and atom.element.symbol != "H":
            restr.addParticle(i, posiciones[i].value_in_unit(unit.nanometers))
    system.addForce(restr)

    integ = LangevinIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
    sim = app.Simulation(modeller.topology, system, integ,
                         Platform.getPlatformByName("CPU"))
    sim.context.setPositions(modeller.positions)
    idx_lig = [n_prot + k for k, a in enumerate(off.atoms) if a.atomic_number > 1]
    return sim, idx_lig, pesados


def sondeo(ws: Path, pid: str) -> Dict[str, Any]:
    """Gate G1: ¿el stack parametriza proteína + ligando con Sage 2.2.1?"""
    from rdkit import Chem
    import numpy as np
    t0 = time.time()
    try:
        sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        mol = Chem.MolFromMolFile(str(sdf))
        if mol is None:
            mol = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
        cf = mol.GetConformer(0)
        pesados = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
        coords = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
                  for i in pesados]
        sim, idx, _ = construir_sistema(ws, pid, mol, coords)
        from openmm import unit
        e = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
            unit.kilocalories_per_mole)
        return {"ok": True, "pid": pid, "energia_kcal": round(float(e), 2),
                "n_atomos_ligando": len(idx), "t_s": round(time.time() - t0, 1)}
    except Exception as ex:
        return {"ok": False, "pid": pid, "error": f"{type(ex).__name__}: {str(ex)[-400:]}",
                "t_s": round(time.time() - t0, 1)}


def relajar_complejo(ws: Path, pid: str, datos: Dict[str, Any], max_poses: int) -> Dict[str, Any]:
    from openmm import unit
    from rdkit import Chem
    import numpy as np

    out: Dict[str, Any] = {"pid": pid, "estrato": datos["estrato"], "poses": []}
    sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
    crystal = Chem.MolFromMolFile(str(sdf))
    if crystal is None:
        crystal = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    cf = crystal.GetConformer(0)
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    ref = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
           for i in pesados]

    for p in datos["poses"][:max_poses]:
        t0 = time.time()
        try:
            coords = [p["coords"][str(i)] for i in pesados]
        except KeyError:
            out["poses"].append({"rmsd_antes": p["rmsd"], "error": "MAPEO_INCOMPLETO"})
            continue
        try:
            sim, idx_lig, _ = construir_sistema(ws, pid, crystal, coords)
            e0 = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
                unit.kilocalories_per_mole)
            sim.minimizeEnergy(maxIterations=MAX_ITER)
            st = sim.context.getState(getPositions=True, getEnergy=True)
            e1 = st.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
            pos = st.getPositions(asNumpy=True).value_in_unit(unit.angstroms)
            nuevas = [pos[i].tolist() for i in idx_lig]
            r1 = rmsd_pocket(ref, nuevas)
            out["poses"].append({
                "score": p["score"], "rmsd_antes": p["rmsd"], "rmsd_despues": round(r1, 3),
                "delta": round(r1 - p["rmsd"], 3),
                "energia_antes": round(float(e0), 2), "energia_despues": round(float(e1), 2),
                "finita": bool(np.isfinite(e1)), "t_s": round(time.time() - t0, 1)})
        except Exception as ex:
            out["poses"].append({"score": p["score"], "rmsd_antes": p["rmsd"],
                                 "error": f"{type(ex).__name__}: {str(ex)[-200:]}",
                                 "t_s": round(time.time() - t0, 1)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-10: relajacion in situ con Sage 2.2.1")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--max-poses", type=int, default=20)
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--solo-sondeo", action="store_true")
    args = ap.parse_args()

    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-10"
    out_dir.mkdir(parents=True, exist_ok=True)
    poses = json.loads((ws / "scripts" / "mf10_poses.json").read_text(encoding="utf-8"))
    pids = list(poses)[:args.limite] if args.limite else list(poses)
    t0 = time.time()

    # ── G1: sondeo de capacidad ──
    print(f"[MF-10] sondeo de capacidad sobre {pids[0]}...", flush=True)
    s = sondeo(ws, pids[0])
    print(f"[MF-10] sondeo: {json.dumps(s, ensure_ascii=False)[:400]}", flush=True)
    (out_dir / "sondeo.json").write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
    if not s["ok"] or args.solo_sondeo:
        metrics = {"experiment_id": "MF-10", "timestamp": datetime.now(timezone.utc).isoformat(),
                   "sondeo": s,
                   "gates": {"G1_capacidad": {"criterio": "el stack parametriza proteina+ligando con Sage 2.2.1",
                                              "pass": bool(s["ok"])}},
                   "decision": "NO_GO" if not s["ok"] else "PENDIENTE"}
        (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
        return 0 if s["ok"] else 3

    filas: List[Dict[str, Any]] = []
    for i, pid in enumerate(pids, 1):
        filas.append(relajar_complejo(ws, pid, poses[pid], args.max_poses))
        n_ok = sum(1 for f in filas for p in f.get("poses", []) if "rmsd_despues" in p)
        print(f"  [{i}/{len(pids)}] {pid} | {n_ok} poses relajadas ({round(time.time()-t0)}s)",
              flush=True)
        with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in filas:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    todas = [p for f in filas for p in f.get("poses", []) if "rmsd_despues" in p]
    err = [p for f in filas for p in f.get("poses", []) if "error" in p]
    banda = [p for p in todas if 2.0 < p["rmsd_antes"] <= 3.0]
    cruzan = [p for p in todas if p["rmsd_antes"] > UMBRAL_A >= p["rmsd_despues"]]
    empeoran = [p for p in todas if p["delta"] > 0]
    metrics = {
        "experiment_id": "MF-10",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "sondeo": s,
        "config": {"max_poses_por_complejo": args.max_poses, "k_restraint_kcal_A2": K_RESTRAINT,
                   "max_iter": MAX_ITER, "ff": "amber14-all + openff-2.2.1 (SMIRNOFF)",
                   "cargas": "openff-gnn-am1bcc-1.0.0 (NAGL, validado en RS-03-PARAM-A)"},
        "n_complejos": len(filas), "n_poses_relajadas": len(todas), "n_errores": len(err),
        "delta_rmsd": {"mediana": round(median([p["delta"] for p in todas]), 3) if todas else None,
                       "mejoran": sum(1 for p in todas if p["delta"] < 0),
                       "empeoran": len(empeoran)},
        "banda_2_3A": {"n": len(banda),
                       "delta_mediano": round(median([p["delta"] for p in banda]), 3) if banda else None,
                       "cruzan": sum(1 for p in banda if p["rmsd_despues"] <= UMBRAL_A)},
        "cruzan_umbral": len(cruzan),
        "energias_finitas": sum(1 for p in todas if p["finita"]),
        "errores_ejemplo": err[:5],
    }
    metrics["gates"] = {
        "G1_capacidad": {"criterio": "el stack parametriza proteina+ligando con Sage 2.2.1",
                         "pass": True},
        "G2_validez": {"criterio": ">=95% de poses relajadas con energia finita",
                       "tasa": round(len(todas) / max(1, len(todas) + len(err)), 4),
                       "pass": len(todas) >= 0.95 * (len(todas) + len(err))},
        "G3_mejora": {"criterio": "la mediana de delta RMSD es negativa (la relajacion acerca)",
                      "mediana": metrics["delta_rmsd"]["mediana"],
                      "pass": bool(todas and metrics["delta_rmsd"]["mediana"] < 0)},
        "G4_conversion": {"criterio": "al menos 5 poses de la banda 2-3 A cruzan el umbral",
                          "cruzan": metrics["banda_2_3A"]["cruzan"],
                          "de": len(banda), "pass": metrics["banda_2_3A"]["cruzan"] >= 5},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(f"\n[MF-10] decision {metrics['decision']} | {len(todas)} poses relajadas, "
          f"{len(err)} errores")
    print(f"  delta RMSD mediano {metrics['delta_rmsd']['mediana']} A | "
          f"mejoran {metrics['delta_rmsd']['mejoran']} empeoran {metrics['delta_rmsd']['empeoran']}")
    print(f"  banda 2-3 A: {len(banda)} poses, delta mediano "
          f"{metrics['banda_2_3A']['delta_mediano']}, cruzan {metrics['banda_2_3A']['cruzan']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
