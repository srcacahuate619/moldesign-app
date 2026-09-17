"""Read-only reproduction of the legacy MM-GBSA parameter defects.

Run with the scientific runtime: python backend/audits/mmgbsa_parameter_integrity.py
Exit 1 means a defect was reproduced, NOT a valid energy calculation.
No downloads, minimization, production database or scientific artifacts are used.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def inspect(smiles):
    from rdkit import Chem
    import openmm
    from openmm import app, unit
    from services.chemistry.molchamb_v2 import _register_ligand_template, _override_charges

    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    topology = app.Topology()
    residue = topology.addResidue("LIG", topology.addChain("L"))
    atoms = [topology.addAtom(f"{a.GetSymbol()}{a.GetIdx()+1}",
             app.Element.getBySymbol(a.GetSymbol()), residue) for a in molecule.GetAtoms()]
    for bond in molecule.GetBonds():
        topology.addBond(atoms[bond.GetBeginAtomIdx()], atoms[bond.GetEndAtomIdx()])
    ff = app.ForceField("amber14-all.xml", "implicit/gbn2.xml")
    _register_ligand_template(ff, molecule)
    system = ff.createSystem(topology, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
    expected = set()
    for center in molecule.GetAtoms():
        for a, b in itertools.combinations([n.GetIdx() for n in center.GetNeighbors()], 2):
            expected.add((min(a,b), center.GetIdx(), max(a,b)))
    actual = set()
    for force in system.getForces():
        if isinstance(force, openmm.HarmonicAngleForce):
            for i in range(force.getNumAngles()):
                a,b,c,_,_ = force.getAngleParameters(i)
                actual.add((min(a,c),b,max(a,c)))
    # Deliberate diagnostic perturbation, not a calculated molecular charge.
    _override_charges(system, list(range(len(atoms))), [0.25]*len(atoms))
    nb = next(f for f in system.getForces() if isinstance(f, openmm.NonbondedForce))
    gb = next(f for f in system.getForces() if isinstance(f, openmm.CustomGBForce))
    charge_index = [gb.getPerParticleParameterName(i)
                    for i in range(gb.getNumPerParticleParameters())].index("charge")
    nb_charge = nb.getParticleParameters(0)[0].value_in_unit(unit.elementary_charge)
    gb_charge = gb.getParticleParameters(0)[charge_index]
    # A graph distance of three is a 1-4 pair; Amber scales rather than excludes it.
    distance = Chem.GetDistanceMatrix(molecule)
    zero_14 = []
    for i in range(nb.getNumExceptions()):
        a,b,charge_product,_,_ = nb.getExceptionParameters(i)
        if distance[a,b] == 3 and charge_product.value_in_unit(unit.elementary_charge**2) == 0:
            zero_14.append([a,b])
    return {"smiles": smiles, "openmm_version": openmm.__version__,
            "expected_angles": len(expected), "actual_angles": len(actual),
            "missing_angles": sorted(expected-actual),
            "diagnostic_nb_charge": nb_charge, "diagnostic_gb_charge": gb_charge,
            "unchanged_zero_14_pairs": zero_14,
            "integrity_ok": not (expected-actual) and nb_charge == gb_charge and not zero_14}


def main():
    results = []
    for smiles in ("CCO", "c1ccccc1", "CCOP(=O)(O)O"):
        try:
            results.append(inspect(smiles))
        except Exception as exc:
            results.append({"smiles": smiles, "integrity_ok": False,
                            "error": f"{type(exc).__name__}: {exc}"})
    sys.stdout.write(json.dumps(results, indent=2) + "\n")
    return 0 if all(r["integrity_ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
