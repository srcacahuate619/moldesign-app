#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf18_embudo_gb.py — MF-18: el embudo de un potencial CON solvatación implícita.

Corre en el contenedor `moldesign-lab` del servidor.

Por qué
-------
`MF-16` midió que el potencial amber14 + Sage **en vacío** no tiene embudo (ρ ≈ 0.00
frente a 0.13 de Vina en el estrato difícil y 0.53 en controles). Ese resultado venía
con una advertencia **declarada antes de ejecutar**: energía en vacío, sin solvatación
ni entropía, dominada por colapso electrostático. Es decir, `MF-16` no puede
distinguir «la física no orienta» de «esta física cruda no orienta».

`MF-18` hace la prueba justa: **el mismo cálculo con solvatación implícita GBn2**, que
es lo mínimo para que una energía de interacción proteína–ligando sea comparable entre
poses con distinto grado de exposición al disolvente.

Diseño idéntico a MF-16, pareado sobre las MISMAS poses
------------------------------------------------------
Las 878 poses de `mf10_poses.json`, elegidas por score y nunca por RMSD. Por complejo:

  * `rho_vina` = Spearman(rmsd, vina_score)
  * `rho_gb`   = Spearman(rmsd, energia_amber_sage_GBn2)
  * y se arrastra `rho_ff` de `MF-16` (vacío) para el contraste de tres vías.

Al ser las mismas poses, las diferencias son pareadas por complejo.

Lo que sigue sin medirse, y se declara
--------------------------------------
GBn2 añade solvatación pero **no entropía** ni penalización de desolvatación explícita
del bolsillo. Sigue siendo un puntuador de una sola conformación. Un `ρ` bajo aquí
tampoco cerraría la puerta a un MM-GBSA completo con promediado; lo que mediría es que
la solvatación implícita por sí sola no basta.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_mf10_relax_insitu import filtrar_receptor, K_RESTRAINT  # noqa: E402

MIN_POSES = 8
GB_XML = "implicit/gbn2.xml"
MIN_ITER = 300      # minimizacion antes de puntuar (leccion de MF-16-R1)
MAX_POSES = 12      # poses por complejo, elegidas POR SCORE nunca por RMSD


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < MIN_POSES:
        return None

    def rangos(v):
        orden = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
                j += 1
            prom = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[orden[k]] = prom
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def construir_sistema_gb(ws: Path, pid: str, lig_rdkit, coords_pose):
    """Idéntico al de MF-10 salvo que el ForceField incluye GBn2.

    Se replica en vez de importarse porque el de `MF-10` está sellado y no debe
    modificarse: cualquier cambio ahí invalidaría su registro.
    """
    from openmm import app, unit, Platform, LangevinIntegrator
    from openff.toolkit import Molecule
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator
    from rdkit import Chem

    rec = ws / "_mf10" / f"{pid}_rec.pdb"
    fixed = ws / "_mf10" / f"{pid}_fixed.pdb"
    rec.parent.mkdir(parents=True, exist_ok=True)
    if not fixed.exists():
        filtrar_receptor(ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb", rec)
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
    ff = app.ForceField("amber14-all.xml", GB_XML)     # <-- la unica diferencia
    ff.registerTemplateGenerator(gen.generator)

    lig_top = off.to_topology().to_openmm()
    lig_pos = off.conformers[0].to_openmm()
    modeller = app.Modeller(pdb.topology, pdb.positions)
    modeller.add(lig_top, lig_pos)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.NoCutoff,
                             constraints=app.HBonds)
    integ = LangevinIntegrator(300 * unit.kelvin, 1 / unit.picosecond,
                               0.002 * unit.picoseconds)
    sim = app.Simulation(modeller.topology, system, integ,
                         Platform.getPlatformByName("CPU"))
    sim.context.setPositions(modeller.positions)
    n_prot = pdb.topology.getNumAtoms()
    idx_lig = [n_prot + k for k, a in enumerate(off.atoms) if a.atomic_number > 1]
    return sim, idx_lig


def analizar(ws: Path, pid: str, datos: Dict[str, Any], mf16: Dict[str, Any]) -> Dict[str, Any]:
    from openmm import unit
    from rdkit import Chem
    import numpy as np

    out: Dict[str, Any] = {"pid": pid, "estrato": datos["estrato"],
                           "rho_ff_vacio_mf16": mf16.get(pid)}
    t0 = time.time()
    sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
    crystal = Chem.MolFromMolFile(str(sdf))
    if crystal is None:
        crystal = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    poses = datos["poses"]
    try:
        coords0 = [poses[0]["coords"][str(i)] for i in pesados]
    except KeyError:
        out["error"] = "MAPEO_INCOMPLETO"
        return out
    try:
        sim, idx_lig = construir_sistema_gb(ws, pid, crystal, coords0)
    except Exception as ex:
        out["error"] = f"{type(ex).__name__}: {str(ex)[-160:]}"
        out["t_s"] = round(time.time() - t0, 1)
        return out

    pos = sim.context.getState(getPositions=True).getPositions(
        asNumpy=True).value_in_unit(unit.angstroms)
    cf = crystal.GetConformer(0)
    ref_xyz = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
               for i in pesados]
    rmsds, vinas, energias, rmsds_post = [], [], [], []
    n_err = 0
    for p in poses[:MAX_POSES]:
        try:
            c = [p["coords"][str(i)] for i in pesados]
        except KeyError:
            n_err += 1
            continue
        nuevo = np.array(pos, copy=True)
        for k, j in enumerate(idx_lig):
            nuevo[j] = c[k]
        try:
            sim.context.setPositions(nuevo * unit.angstroms)
            # MF-16-R1: puntuar SIN relajar mide severidad de choque, no calidad de union
            # (36 de 714 energias de punto unico superan 1e4 kcal/mol). Se minimiza antes.
            sim.minimizeEnergy(maxIterations=MIN_ITER)
            st = sim.context.getState(getPositions=True, getEnergy=True)
            e = st.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
            if not np.isfinite(e):
                n_err += 1
                continue
            fin = st.getPositions(asNumpy=True).value_in_unit(unit.angstroms)
            rr = float(np.sqrt(((np.asarray([fin[j] for j in idx_lig])
                                 - np.asarray(ref_xyz)) ** 2).sum(axis=1).mean()))
        except Exception:
            n_err += 1
            continue
        rmsds_post.append(round(rr, 3))
        rmsds.append(p["rmsd"])
        vinas.append(p["score"])
        energias.append(float(e))

    out["n_poses"] = len(rmsds)
    out["n_errores"] = n_err
    if len(rmsds) < MIN_POSES:
        out["error"] = "POCAS_POSES"
        out["t_s"] = round(time.time() - t0, 1)
        return out
    rv, rg = _spearman(rmsds, vinas), _spearman(rmsds, energias)
    out["rmsd_post_relax"] = rmsds_post
    out["rho_gb_post"] = _spearman(rmsds_post, energias)
    out.update({"rho_vina": rv, "rho_gb": rg,
                "delta_rho": round(rg - rv, 4) if (rv is not None and rg is not None) else None,
                "energia_min": round(min(energias), 1), "energia_max": round(max(energias), 1),
                "t_s": round(time.time() - t0, 1)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-18: embudo con solvatacion implicita")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-18"
    out_dir.mkdir(parents=True, exist_ok=True)

    poses = json.loads((ws / "scripts" / "mf10_poses.json").read_text(encoding="utf-8"))
    mf16: Dict[str, Any] = {}
    p16 = ws / "scripts" / "artifacts_science" / "MF-16" / "per_complex.jsonl"
    if p16.exists():
        for l in p16.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                mf16[d["pid"]] = d.get("rho_ff")
    pids = list(poses)[:args.limite] if args.limite else list(poses)
    print(f"[MF-18] {len(pids)} complejos | solvente {GB_XML}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    for i, pid in enumerate(pids, 1):
        filas.append(analizar(ws, pid, poses[pid], mf16))
        r = filas[-1]
        print(f"  [{i}/{len(pids)}] {pid} [{r['estrato']}] rho_vina={r.get('rho_vina')} "
              f"rho_gb={r.get('rho_gb')} (vacio {r.get('rho_ff_vacio_mf16')}) "
              f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
        with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for x in filas:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("delta_rho") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        vac = [r["rho_ff_vacio_mf16"] for r in g if r.get("rho_ff_vacio_mf16") is not None]
        resumen[est] = {
            "n": len(g),
            "rho_vina_mediano": round(median(r["rho_vina"] for r in g), 4),
            "rho_gb_mediano": round(median(r["rho_gb"] for r in g), 4),
            "rho_ff_vacio_mediano": round(median(vac), 4) if vac else None,
            "delta_rho_mediano": round(median(r["delta_rho"] for r in g), 4),
            "complejos_gb_mejor_que_vina": sum(1 for r in g if r["delta_rho"] > 0),
        }
    metrics = {
        "experiment_id": "MF-18",
        "tipo": "medicion pareada sobre las mismas poses",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "solvente": GB_XML,
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "advertencia": ("GBn2 anade solvatacion pero NO entropia ni promediado "
                        "conformacional; un rho bajo no cierra la puerta a un MM-GBSA "
                        "completo, mide que la solvatacion implicita por si sola no basta"),
        "lectura": ("rho_gb > rho_vina en la mayoria => la solvatacion era lo que faltaba y "
                    "hay direccion concreta. rho_gb ~ rho_ff_vacio => el problema no era la "
                    "solvatacion. rho_gb <= 0 => el potencial de una sola conformacion no "
                    "orienta, con o sin disolvente"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-18] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
