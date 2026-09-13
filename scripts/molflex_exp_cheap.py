"""MolFlex experiments — V3, R2, R3 (cheap: ETKDG + MMFF, no docking).

Pre-registered protocol: docs/40_MOLFLEX_PROTOCOL.md

V3: coverage of the bioactive (crystal) conformation by the ETKDG ensemble.
R2: is the crystal conformation in the top-K of MMFF energy? (strain objection)
R3: coverage curve vs ensemble size (5/10/20/40/80) — ceiling detection.

Usage:
  python scripts/molflex_exp_cheap.py --limit 30 --out artifacts_molflex_cheap.json
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
ENSEMBLE_SIZES = [5, 10, 20, 40, 80]

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdMolAlign

RDLogger.logger().setLevel(RDLogger.ERROR)


def rmsd_to_crystal(ensemble_mol, crystal_mol, conf_ids):
    """Min RMSD between ensemble conformers and the crystal conformation.

    Uses GetBestRMS (symmetry-correct, multiple atom mappings) on heavy
    atoms only. Returns min RMSD or None."""
    try:
        probe_h = Chem.RemoveHs(ensemble_mol)
        ref_h = Chem.RemoveHs(crystal_mol)
        if probe_h is None or ref_h is None:
            return None
        best = float("inf")
        for cid in conf_ids:
            try:
                r = rdMolAlign.GetBestRMS(probe_h, ref_h, cid, -1)
                if r < best:
                    best = r
            except Exception:
                continue
        return best if best != float("inf") else None
    except Exception:
        return None


def generate_ensemble(ligand_sdf: Path, n_conf: int, seed: int = 42):
    """ETKDG ensemble (up to n_conf, pruned 0.5A). Returns (mol, conf_ids)."""
    try:
        m = Chem.MolFromMolFile(str(ligand_sdf), sanitize=False, removeHs=False)
        if m is None:
            return None, []
        m = Chem.AddHs(m)
        ids = list(AllChem.EmbedMultipleConfs(
            m, numConfs=n_conf, randomSeed=seed,
            useExpTorsionAnglePrefs=True, useBasicKnowledge=True,
            pruneRmsThresh=0.5, numThreads=0,
        ))
        return m, ids
    except Exception:
        return None, []


def mmff_energies(mol, conf_ids):
    """MMFF94 energy per conformer. Returns sorted [(energy, cid)]."""
    props = AllChem.MMFFGetMoleculeProperties(mol)
    energies = []
    for cid in conf_ids:
        try:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
            if ff is not None:
                energies.append((float(ff.CalcEnergy()), cid))
        except Exception:
            continue
    energies.sort(key=lambda x: x[0])
    return energies


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--out", type=str, default="artifacts_molflex_cheap.json")
    args = ap.parse_args()

    complexes = []
    for d in sorted(PDBBIND.iterdir()):
        if not d.is_dir() or len(d.name) != 4:
            continue
        sdf = d / f"{d.name}_ligand.sdf"
        pdb = d / f"{d.name}_protein.pdb"
        if sdf.exists() and pdb.exists():
            complexes.append(d.name)
        if len(complexes) >= args.limit:
            break

    print(f"Complejos: {len(complexes)} | ensemble sizes: {ENSEMBLE_SIZES}")
    results = {"v3": {}, "r2": {}, "r3": {}, "per_complex": []}
    t0 = time.time()

    for pid in complexes:
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        crystal = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
        if crystal is None or crystal.GetNumConformers() == 0:
            continue

        # R3: coverage curve (subsample the max ensemble)
        m80, ids80 = generate_ensemble(sdf, max(ENSEMBLE_SIZES))
        if m80 is None or not ids80:
            continue

        cov_curve = []
        for n in ENSEMBLE_SIZES:
            ids = ids80[:n] if len(ids80) >= n else ids80
            r = rmsd_to_crystal(m80, crystal, ids)
            cov_curve.append(r)

        # V3 metric: min RMSD with the full ensemble
        min_rmsd_full = cov_curve[-1] if cov_curve else None

        # R2: energy rank of the crystal conformation
        energies = mmff_energies(m80, ids80)
        # crystal MMFF energy: preservar los H explicitos del SDF cristalino
        # (AddHs re-generaria geometria de H artificial -> energia inflada)
        crystal_energy = None
        crystal_raw = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
        if crystal_raw is not None:
            try:
                props_c = AllChem.MMFFGetMoleculeProperties(crystal_raw)
                ff = AllChem.MMFFGetMoleculeForceField(crystal_raw, props_c)
                if ff is not None:
                    crystal_energy = float(ff.CalcEnergy())
            except Exception:
                crystal_energy = None
        # rank of crystal energy among ensemble energies
        rank_pct = None
        if crystal_energy is not None and energies:
            rank_pct = (sum(1 for e, _ in energies if e < crystal_energy)
                        / len(energies))

        results["per_complex"].append({
            "pdb_id": pid,
            "n_conf_80": len(ids80),
            "v3_min_rmsd_full": min_rmsd_full,
            "r2_crystal_energy": crystal_energy,
            "r2_energy_rank_pct": rank_pct,
            "r3_coverage_curve": {str(n): cov_curve[i] for i, n in enumerate(ENSEMBLE_SIZES)},
        })
        print(f"  {pid}: conf={len(ids80)} minRMSD={min_rmsd_full:.2f}A "
              f"crystal_energy_rank={rank_pct if rank_pct is None else round(rank_pct*100)}%")

    # Aggregate
    def agg(key, fn):
        vals = [c[key] for c in results["per_complex"] if c.get(key) is not None]
        return fn(vals) if vals else None

    results["v3"]["min_rmsd_median"] = agg("v3_min_rmsd_full", st.median)
    results["v3"]["frac_lt_1p5"] = (
        sum(1 for c in results["per_complex"]
            if c.get("v3_min_rmsd_full") is not None and c["v3_min_rmsd_full"] < 1.5)
        / max(len([c for c in results["per_complex"] if c.get("v3_min_rmsd_full") is not None]), 1)
    )
    results["r2"]["crystal_rank_pct_median"] = agg("r2_energy_rank_pct", st.median)
    results["r2"]["frac_crystal_in_top20pct"] = (
        sum(1 for c in results["per_complex"]
            if c.get("r2_energy_rank_pct") is not None and c["r2_energy_rank_pct"] < 0.20)
        / max(len([c for c in results["per_complex"] if c.get("r2_energy_rank_pct") is not None]), 1)
    )
    # R3 curve aggregate
    curve_medians = {}
    for n in ENSEMBLE_SIZES:
        vals = [c["r3_coverage_curve"][str(n)] for c in results["per_complex"]
                if c["r3_coverage_curve"].get(str(n)) is not None]
        curve_medians[str(n)] = st.median(vals) if vals else None
    results["r3"]["coverage_curve_median"] = curve_medians

    out = Path(args.out)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nV3 mediana minRMSD: {results['v3']['min_rmsd_median']}  "
          f"frac<1.5A: {results['v3']['frac_lt_1p5']}")
    print(f"R2 rank energia cristal (mediana): {results['r2']['crystal_rank_pct_median']}  "
          f"in-top20%: {results['r2']['frac_crystal_in_top20pct']}")
    print(f"R3 curva: {curve_medians}")
    print(f"Total: {time.time() - t0:.1f}s -> {out}")


if __name__ == "__main__":
    main()
