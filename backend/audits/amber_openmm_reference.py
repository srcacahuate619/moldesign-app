"""Independent Amber/OpenMM energy parity, NOT a binding-affinity benchmark.

Runs only in the isolated reference environment. All generated inputs, tool
logs, hashes and energies remain under --output. No production configuration
or weights are changed. A failed case remains a failed case in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CASES = {
    "ethanol": "CCO", "benzene": "c1ccccc1", "aspirin": "CC(=O)Oc1ccccc1C(=O)O",
    "chlorobenzene": "Clc1ccccc1", "acetate": "CC(=O)[O-]",
    "methylammonium": "C[NH3+]", "dimethylphosphate": "COP(=O)([O-])OC",
    "imidazole": "c1ncc[nH]1",
}


def command(args, directory, name):
    with (directory / (name + ".stdout")).open("w") as out, (directory / (name + ".stderr")).open("w") as err:
        process = subprocess.Popen(args, cwd=directory, stdout=out, stderr=err, start_new_session=True)
        try:
            process.wait(timeout=300)
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
    if process.returncode:
        raise RuntimeError(f"{name} failed ({process.returncode}); see saved stdout/stderr")


def evaluate_case(name, smiles, root):
    import numpy as np
    import openmm
    from openmm import app, unit
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import parmed
    import sander

    directory = root / name
    directory.mkdir(exist_ok=False)
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    if AllChem.EmbedMolecule(molecule, randomSeed=20260917) != 0:
        raise RuntimeError("Fixture embedding failed")
    # These are diagnostic fixtures, not replacement conformers for docked poses.
    with Chem.SDWriter(str(directory / "input.sdf")) as writer:
        writer.write(molecule)
    formal = Chem.GetFormalCharge(molecule)
    command(["antechamber", "-i", "input.sdf", "-fi", "sdf", "-o", "ligand.mol2", "-fo", "mol2",
             "-at", "gaff2", "-c", "bcc", "-nc", str(formal), "-rn", "LIG", "-s", "2"], directory, "antechamber")
    # AmberTools prints Mulliken charges at 0.001 e precision. OpenFF's
    # AmberTools wrapper normalizes their sum by a uniform offset by default.
    # Preserve raw output, bound the rounding deficit, and record the correction.
    raw_mol2 = (directory / "ligand.mol2").read_text()
    (directory / "ligand.raw.mol2").write_text(raw_mol2)
    lines = raw_mol2.splitlines()
    first = lines.index("@<TRIPOS>ATOM")+1
    last = lines.index("@<TRIPOS>BOND")
    atom_lines = [i for i in range(first,last) if lines[i].strip()]
    raw_charges = [float(lines[i].split()[8]) for i in atom_lines]
    charge_deficit = formal-sum(raw_charges)
    if abs(charge_deficit) > len(raw_charges)*0.0005 + 1e-6:
        raise RuntimeError("Charge deficit exceeds the upstream rounding bound")
    correction = charge_deficit/len(raw_charges)
    for i,q in zip(atom_lines,raw_charges):
        fields = lines[i].split()
        fields[8] = f"{q+correction:.10f}"
        lines[i] = " ".join(fields)
    (directory / "ligand.mol2").write_text("\n".join(lines)+"\n")
    command(["parmchk2", "-i", "ligand.mol2", "-f", "mol2", "-o", "ligand.frcmod", "-s", "gaff2"], directory, "parmchk2")
    if "ATTN" in (directory / "ligand.frcmod").read_text():
        raise RuntimeError("parmchk2 produced unresolved parameters requiring review")
    (directory / "leap.in").write_text("source leaprc.gaff2\nset default PBRadii mbondi3\n"
        "loadamberparams ligand.frcmod\nLIG = loadmol2 ligand.mol2\ncheck LIG\n"
        "saveamberparm LIG ligand.prmtop ligand.inpcrd\nquit\n")
    command(["tleap", "-f", "leap.in"], directory, "tleap")
    topology = app.AmberPrmtopFile(str(directory / "ligand.prmtop"))
    coordinates = app.AmberInpcrdFile(str(directory / "ligand.inpcrd"))
    amber = parmed.load_file(str(directory / "ligand.prmtop"), xyz=str(directory / "ligand.inpcrd"))
    if len(amber.atoms) != molecule.GetNumAtoms():
        raise RuntimeError("Atom count changed during parametrization")
    charge_sum = sum(a.charge for a in amber.atoms)
    if abs(charge_sum-formal) > 1e-4 + 1e-8:
        raise RuntimeError("Partial charges do not sum to the formal charge")
    # GAFF atom types are not SYBYL Mol2 types: RDKit's Mol2 parser cannot
    # interpret them. Verify a bijection independently using elements, the full
    # coordinate matrix and the graph exported in the actual Amber topology.
    from scipy.optimize import linear_sum_assignment
    source = molecule.GetConformer().GetPositions()
    converted = np.asarray(amber.coordinates)
    distances = np.linalg.norm(source[:,None,:]-converted[None,:,:], axis=2)
    for i, atom in enumerate(molecule.GetAtoms()):
        for j, parameterized in enumerate(amber.atoms):
            if atom.GetAtomicNum() != parameterized.atomic_number:
                distances[i,j] = 1e9
    rows, columns = linear_sum_assignment(distances)
    max_coordinate_change = float(np.max(distances[rows, columns]))
    if max_coordinate_change > 0.001:
        raise RuntimeError(f"Coordinates/elements changed during parametrization: {max_coordinate_change} A")
    amber_to_source = {int(j): int(i) for i,j in zip(rows, columns)}
    original_bonds = {tuple(sorted((b.GetBeginAtomIdx(),b.GetEndAtomIdx()))) for b in molecule.GetBonds()}
    parameterized_bonds = {tuple(sorted((amber_to_source[b.atom1.idx],amber_to_source[b.atom2.idx])))
                           for b in amber.bonds}
    if original_bonds != parameterized_bonds:
        raise RuntimeError("Bond connectivity changed during parametrization")
    expected_angles = sum(a.GetDegree()*(a.GetDegree()-1)//2 for a in molecule.GetAtoms())
    if len(amber.angles) != expected_angles:
        raise RuntimeError(f"Incomplete angle terms: {len(amber.angles)}/{expected_angles}")
    comparisons = []
    for label, solvent, sasa in [("vacuum", None, None), ("GBn2_no_SA", app.GBn2, None),
                                 ("GBn2_LCPO", app.GBn2, "LCPO")]:
        system = topology.createSystem(nonbondedMethod=app.NoCutoff, constraints=None,
            implicitSolvent=solvent, soluteDielectric=1.0, solventDielectric=78.5,
            sasaMethod=None, removeCMMotion=False)
        if sasa:
            from services.chemistry.amber_compatibility import add_gaff_lcpo_force
            add_gaff_lcpo_force(system, topology)
        phosphorus_corrections = 0
        if solvent:
            from services.chemistry.amber_compatibility import apply_amber_gbn2_phosphorus
            phosphorus_corrections = apply_amber_gbn2_phosphorus(system, topology.topology)
        nb = next(f for f in system.getForces() if isinstance(f, openmm.NonbondedForce))
        if solvent:
            gb = next(f for f in system.getForces() if isinstance(f, openmm.CustomGBForce))
            qidx = [gb.getPerParticleParameterName(i) for i in range(gb.getNumPerParticleParameters())].index("charge")
            for i in range(system.getNumParticles()):
                q = nb.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge)
                if abs(q-gb.getParticleParameters(i)[qidx]) > 1e-10:
                    raise RuntimeError("GB and nonbonded charges differ")
        integrator = openmm.VerletIntegrator(0.001)
        context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName("Reference"))
        context.setPositions(coordinates.positions)
        state = context.getState(getEnergy=True, getForces=True)
        energy = state.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
        force = state.getForces(asNumpy=True).value_in_unit(unit.kilocalories_per_mole/unit.angstrom)
        options = sander.gas_input() if solvent is None else sander.gas_input(8)
        options.cut = 999.0
        options.gbsa = 1 if sasa else 0
        options.extdiel = 78.5
        options.intdiel = 1.0
        with sander.setup(str(directory / "ligand.prmtop"), amber.coordinates, None, options):
            reference, forces = sander.energy_forces()
        error = abs(float(energy)-float(reference.tot))
        force_error = float(np.max(np.abs(force-np.asarray(forces).reshape((-1,3)))))
        # Amber prmtop uses 18.2223^2; OpenMM NB and GB use documented SI
        # Coulomb constants. This is an analytical conversion, NOT a fit.
        amber_coulomb = 18.2223**2
        nb_ratio = (138.93545764438198*10/4.184)/amber_coulomb-1
        gb_ratio = (138.935485*10/4.184)/amber_coulomb-1
        expected_constant_difference = nb_ratio*(reference.elec+reference.elec_14)+gb_ratio*reference.gb
        residual = abs(float(energy)-float(reference.tot)-expected_constant_difference)
        comparisons.append({"condition": label, "openmm_kcal_mol": energy,
            "amber_kcal_mol": reference.tot, "absolute_error_kcal_mol": error,
            "amber_forces_kcal_mol_A": np.asarray(forces).reshape((-1,3)).tolist(),
            "max_force_error_kcal_mol_A": force_error,
            "raw_strict_parity": error < 0.001 and force_error < 0.001,
            "documented_constant_difference_kcal_mol": expected_constant_difference,
            "residual_after_constant_conversion_kcal_mol": residual,
            "phosphorus_parameters_corrected": phosphorus_corrections,
            "passed": residual < 0.001 and force_error < 0.001})
        del context, integrator
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in directory.iterdir() if p.is_file()}
    return {"name": name, "smiles": smiles, "formal_charge": formal, "partial_charge_sum": charge_sum, "raw_charge_sum": sum(raw_charges),
            "normalization_offset_e": correction,
            "atoms": len(amber.atoms), "angles": len(amber.angles),
            "maximum_coordinate_change_A": max_coordinate_change,
            "comparisons": comparisons, "hashes": hashes,
            "passed": all(c["passed"] for c in comparisons)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    import openmm
    import rdkit
    results = []
    for name, smiles in CASES.items():
        started = time.monotonic()
        try:
            result = evaluate_case(name, smiles, args.output)
        except Exception as exc:
            result = {"name": name, "smiles": smiles, "passed": False,
                      "error": f"{type(exc).__name__}: {exc}"}
        result["seconds"] = time.monotonic()-started
        results.append(result)
        (args.output / "report.json").write_text(json.dumps({"openmm": openmm.__version__,
            "rdkit": rdkit.__version__, "protocol": "GAFF2/AM1-BCC; identical coordinates; Reference double precision",
            "scope": "ligand parameter integrity and energy/force parity only; no binding validation",
            "executables": {n: shutil.which(n) for n in ["antechamber","parmchk2","tleap"]},
            "results": results}, indent=2))
        print(json.dumps({"name": name, "passed": result["passed"], "error": result.get("error")}), flush=True)
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
