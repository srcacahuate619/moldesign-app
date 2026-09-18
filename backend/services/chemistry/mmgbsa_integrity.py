"""Necessary integrity checks, not scientific validation of a force field."""
from itertools import combinations
import math


class MMGBSAIntegrityError(ValueError):
    pass


def validate_ligand_system(system, topology, ligand_ids):
    from openmm import CustomGBForce, HarmonicAngleForce, HarmonicBondForce, NonbondedForce, unit
    atoms = list(topology.atoms())
    selected = set(ligand_ids)
    if not selected or system.getNumParticles() != len(atoms) or not selected.issubset(range(len(atoms))):
        raise MMGBSAIntegrityError("MM-GBSA no evaluado: correspondencia topológica inválida")
    neighbors = {i: set() for i in range(len(atoms))}
    bonds = set()
    for a,b in topology.bonds():
        neighbors[a.index].add(b.index)
        neighbors[b.index].add(a.index)
        if a.index in selected or b.index in selected:
            bonds.add(tuple(sorted((a.index,b.index))))
    covered_bonds = set()
    for i in range(system.getNumConstraints()):
        a,b,_ = system.getConstraintParameters(i)
        covered_bonds.add(tuple(sorted((a,b))))
    covered_angles = set()
    for force in system.getForces():
        if isinstance(force, HarmonicBondForce):
            for i in range(force.getNumBonds()):
                a,b,_,k = force.getBondParameters(i)
                if k.value_in_unit(unit.kilojoules_per_mole/unit.nanometer**2) > 0:
                    covered_bonds.add(tuple(sorted((a,b))))
        elif isinstance(force, HarmonicAngleForce):
            for i in range(force.getNumAngles()):
                a,b,c,_,k = force.getAngleParameters(i)
                if k.value_in_unit(unit.kilojoules_per_mole/unit.radian**2) > 0:
                    covered_angles.add((min(a,c),b,max(a,c)))
    angles = {(min(a,c),b,max(a,c)) for b in selected for a,c in combinations(neighbors[b],2)}
    issues = []
    if bonds-covered_bonds:
        issues.append(f"{len(bonds-covered_bonds)} enlaces sin parámetro ni restricción")
    if angles-covered_angles:
        issues.append(f"{len(angles-covered_angles)} ángulos sin parámetro")
    nonbonded = [f for f in system.getForces() if isinstance(f,NonbondedForce)]
    gb_forces = [f for f in system.getForces() if isinstance(f,CustomGBForce)]
    if len(nonbonded) != 1 or len(gb_forces) != 1:
        issues.append("fuerzas electrostática/GB no identificables")
    else:
        nb,gb = nonbonded[0],gb_forces[0]
        names = [gb.getPerParticleParameterName(i) for i in range(gb.getNumPerParticleParameters())]
        if "charge" not in names or gb.getNumParticles() != len(atoms):
            issues.append("cargas GB no verificables")
        else:
            index = names.index("charge")
            for atom in selected:
                q = nb.getParticleParameters(atom)[0].value_in_unit(unit.elementary_charge)
                qgb = gb.getParticleParameters(atom)[index]
                if not math.isfinite(q) or not math.isfinite(qgb) or abs(q-qgb)>1e-8:
                    issues.append("cargas electrostáticas y GB inconsistentes")
                    break
        # With the current Amber protocol a graph-distance-three pair has a
        # nonzero scaled charge product whenever both charges are nonzero.
        for i in range(nb.getNumExceptions()):
            a,b,product,_,_ = nb.getExceptionParameters(i)
            if a not in selected or b not in selected or b in neighbors[a] or neighbors[a]&neighbors[b]:
                continue
            qa = nb.getParticleParameters(a)[0].value_in_unit(unit.elementary_charge)
            qb = nb.getParticleParameters(b)[0].value_in_unit(unit.elementary_charge)
            qprod = product.value_in_unit(unit.elementary_charge**2)
            if abs(qa*qb)>1e-10 and abs(qprod)<1e-12:
                issues.append("excepciones electrostáticas sin actualizar")
                break
    if issues:
        raise MMGBSAIntegrityError("MM-GBSA no evaluado: parametrización inconsistente; "+"; ".join(issues))
