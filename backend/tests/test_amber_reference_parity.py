"""Real Amber reference replay in the shipped Windows OpenMM, offline.

23/24 reference conditions pass; the chlorine LCPO reference discrepancy is
explicitly retained as a blocker, not included in successful parity cases.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from services.chemistry.amber_compatibility import apply_amber_gbn2_phosphorus

ROOT = Path(__file__).resolve().parents[1] / "audits" / "amber_reference"
REPORT = json.loads((ROOT / "report.json").read_text())
CASES = [(case, condition) for case in REPORT["results"] for condition in case["comparisons"]
         if condition["passed"]]


def test_reference_files_match_manifest():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
    assert manifest["protocol_status"] == "EXPERIMENTAL_NOT_ENABLED"


@pytest.mark.parametrize("case,reference", CASES,
                         ids=[f"{case['name']}-{condition['condition']}" for case,condition in CASES])
def test_energy_and_forces_match_independent_amber(case, reference):
    openmm = pytest.importorskip("openmm")
    from openmm import app, unit
    directory = ROOT/case["name"]
    topology = app.AmberPrmtopFile(str(directory/"ligand.prmtop"))
    positions = app.AmberInpcrdFile(str(directory/"ligand.inpcrd")).positions
    solvent = app.GBn2 if reference["condition"].startswith("GBn2") else None
    system = topology.createSystem(nonbondedMethod=app.NoCutoff, constraints=None,
        implicitSolvent=solvent, soluteDielectric=1.0, solventDielectric=78.5,
        sasaMethod=None, removeCMMotion=False)
    if reference["condition"] == "GBn2_LCPO":
        from services.chemistry.amber_compatibility import add_gaff_lcpo_force
        add_gaff_lcpo_force(system, topology)
        with pytest.raises(ValueError, match="already present"):
            add_gaff_lcpo_force(system, topology)
    if solvent:
        changed = apply_amber_gbn2_phosphorus(system, topology.topology)
        assert changed == reference["phosphorus_parameters_corrected"]
        assert apply_amber_gbn2_phosphorus(system, topology.topology) == 0
    integrator = openmm.VerletIntegrator(0.001)
    context = openmm.Context(system,integrator,openmm.Platform.getPlatformByName("Reference"))
    context.setPositions(positions)
    state = context.getState(getEnergy=True,getForces=True)
    energy = state.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    force = state.getForces(asNumpy=True).value_in_unit(unit.kilocalories_per_mole/unit.angstrom)
    # Keep raw Amber energy intact; account explicitly for the documented SI
    # versus legacy Coulomb constants, not a fitted/calibrated offset.
    expected = reference["amber_kcal_mol"]+reference["documented_constant_difference_kcal_mol"]
    assert abs(energy-expected) < 0.001
    assert np.max(np.abs(force-np.array(reference["amber_forces_kcal_mol_A"]))) < 0.001



def test_chlorine_discrepancy_remains_an_explicit_activation_blocker():
    failures = [(case["name"],c) for case in REPORT["results"] for c in case["comparisons"] if not c["passed"]]
    assert len(failures) == 1
    name,comparison = failures[0]
    assert name == "chlorobenzene" and comparison["condition"] == "GBn2_LCPO"
    assert comparison["residual_after_constant_conversion_kcal_mol"] > 0.1
    assert json.loads((ROOT/"manifest.json").read_text())["protocol_status"] == "EXPERIMENTAL_NOT_ENABLED"
