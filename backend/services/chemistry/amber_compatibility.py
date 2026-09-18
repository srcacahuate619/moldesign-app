"""Explicit compatibility correction for the candidate Amber GBn2 protocol.

Not connected to production MM-GBSA. OpenMM 8.5.2 assigns default OBC-like
alpha/beta/gamma to phosphorus outside nucleic-acid residues, while Amber
assigns its P GBn2 parameters regardless of the residue name.
Source: AmberClassic src/msander/mdread.F90, gbalphaP and atomicnumber==15.
Radii, screening, charges and every other element remain unchanged.
"""
from __future__ import annotations

AMBER_GBN2_PHOSPHORUS = (0.418365, 0.290054, 0.1064245)
_OPENMM_DEFAULT = (1.0, 0.8, 4.851)


def apply_amber_gbn2_phosphorus(system, topology) -> int:
    from openmm import CustomGBForce
    atoms = list(topology.atoms())
    phosphorus = [a.index for a in atoms if a.element and a.element.atomic_number == 15]
    if not phosphorus:
        return 0
    forces = [f for f in system.getForces() if isinstance(f, CustomGBForce)
              and [f.getPerParticleParameterName(i) for i in range(f.getNumPerParticleParameters())]
              == ["charge", "or", "sr", "alpha", "beta", "gamma", "radindex"]]
    if len(forces) != 1 or forces[0].getNumParticles() != len(atoms):
        raise ValueError("GBn2 phosphorus correction requires the expected explicit force schema")
    force = forces[0]
    changes = []
    for index in phosphorus:
        values = list(force.getParticleParameters(index))
        old = tuple(values[3:6])
        if old == AMBER_GBN2_PHOSPHORUS:
            continue
        if old != _OPENMM_DEFAULT:
            raise ValueError("Unrecognized phosphorus GB parameters; refusing to overwrite them")
        values[3:6] = AMBER_GBN2_PHOSPHORUS
        changes.append((index, values))
    for index, values in changes:
        force.setParticleParameters(index, values)
    return len(changes)



def add_gaff_lcpo_force(system, amber_prmtop):
    """Match Amber's uppercase GAFF type lookup without changing bonded types.

    OpenMM 8.5.2 compares e.g. O/N3/SH case-sensitively, while Amber calls
    upper(atype) before its LCPO lookup. Chlorine deliberately retains the
    published LCPO Cl parameters; Amber's carbon fallback is NOT reproduced.
    """
    from openmm import LCPOForce
    from openmm.app.internal import lcpo
    if any(isinstance(force, LCPOForce) for force in system.getForces()):
        raise ValueError("LCPO is already present; refusing to double-count solvation")
    class UppercaseTypes:
        def __init__(self, original):
            self.original = original
        def getAtomType(self, index):
            return self.original.getAtomType(index).upper()
        def __getattr__(self, name):
            return getattr(self.original, name)
    params = lcpo.getLCPOParamsAmber(UppercaseTypes(amber_prmtop._prmtop), amber_prmtop.elements)
    lcpo.addLCPOForce(system, params, usePeriodic=False)
