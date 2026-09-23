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



# ── GBn2 descreening exactly as Amber's egb.F90 evaluates it ───────────────
#
# OpenMM 8.5.2 evaluates the Hawkins-Cramer-Truhlar descreening integral in
# closed form for every pair. Amber (AmberClassic src/msander/egb.F90, the
# code GBn2 was parametrized with) does not: for a pair it first drops
# dij > rgbmax + sj, uses a smoothed tail for dij > rgbmax - sj, a Taylor
# series (ta..tdd) for dij > 4*sj, and only then the closed form; and it
# clamps a negative inverse Born radius to 1/30 A^-1. For every element but
# sulfur the series and the closed form agree to ~1e-6 kcal/mol at those
# distances (measured, MMGBSA-H5-R1). Sulfur has a NEGATIVE GBn2 screen
# (-0.703469), so sj < 0, dij > 4*sj always holds, and Amber ALWAYS uses the
# series for S: the two programs then disagree by up to 11 kcal/mol
# (MMGBSA-H5-GBN2-PARIDAD, 2weg). This rewrites OpenMM's expression with the
# same branches, instead of choosing whichever implementation is "nicer".

OPENMM_852_GBN2_I = (
    "Ivdw+neckScale*Ineck;Ineck=step(radius1+radius2+neckCut-r)*getm0(radindex1,radindex2)/"
    "(1+100*(r-getd0(radindex1,radindex2))^2+0.3*1000000*(r-getd0(radindex1,radindex2))^6);"
    "Ivdw=select(step(r+sr2-or1), 0.5*(1/L-1/U+0.25*(r-sr2^2/r)*(1/(U^2)-1/(L^2))+0.5*log(L/U)/r), 0);"
    "U=r+sr2;L=max(or1, D);D=abs(r-sr2);radius1=or1+offset; radius2=or2+offset;"
    "neckScale=0.826836; neckCut=0.68; offset=0.0195141"
)
OPENMM_852_GBN2_B = (
    "1/(1/or-tanh(alpha*psi-beta*psi^2+gamma*psi^3)/radius);psi=I*or; radius=or+offset; offset=0.0195141"
)
AMBER_RGBMAX_A = 25.0   # sander default for igb=8 (pysander gas_input(8).rgbmax)


def amber_gbn2_descreening_expressions(rgbmax_angstrom: float = AMBER_RGBMAX_A) -> tuple[str, str]:
    """The two computed values of GBn2 with egb.F90's branch structure, in nm."""
    rgbmax = rgbmax_angstrom / 10.0
    i_expr = (
        "Ivdw+neckScale*Ineck;"
        "Ineck=step(rgbmax+sr2-r)*step(radius1+radius2+neckCut-r)*getm0(radindex1,radindex2)/"
        "(1+100*(r-getd0(radindex1,radindex2))^2+0.3*1000000*(r-getd0(radindex1,radindex2))^6);"
        "Ivdw=select(step(r-rgbmax-sr2), 0, select(step(r-rgbmax+sr2), Itail, select(step(r-4*sr2), Iseries, Iexact)));"
        "Itail=0.125/r*(1+2*r/(r-sr2)+(r^2-4*rgbmax*r-sr2^2)/rgbmax^2+2*log((r-sr2)/rgbmax));"
        "Iseries=sr2^3/r^4*(1/3+x*(2/5+x*(3/7+x*(4/9+x*5/11))));x=sr2^2/r^2;"
        "Iexact=select(step(r+sr2-or1), 0.5*(1/L-1/U+0.25*(r-sr2^2/r)*(1/(U^2)-1/(L^2))+0.5*log(L/U)/r), 0);"
        "U=r+sr2;L=max(or1, D);D=abs(r-sr2);radius1=or1+offset; radius2=or2+offset;"
        f"neckScale=0.826836; neckCut=0.68; offset=0.0195141; rgbmax={rgbmax!r}"
    )
    b_expr = (
        "1/select(step(invB), invB, 1/3);invB=1/or-tanh(alpha*psi-beta*psi^2+gamma*psi^3)/radius;"
        "psi=I*or; radius=or+offset; offset=0.0195141"
    )
    return i_expr, b_expr


def apply_amber_gbn2_descreening(system, rgbmax_angstrom: float = AMBER_RGBMAX_A) -> None:
    """Make OpenMM's GBn2 descreen like Amber's egb.F90. Refuses unknown schemas.

    Candidate protocol only; not connected to production MM-GBSA.
    """
    from openmm import CustomGBForce
    forces = [f for f in system.getForces() if isinstance(f, CustomGBForce)
              and [f.getPerParticleParameterName(i) for i in range(f.getNumPerParticleParameters())]
              == ["charge", "or", "sr", "alpha", "beta", "gamma", "radindex"]]
    if len(forces) != 1:
        raise ValueError("GBn2 descreening correction requires exactly one GBn2 CustomGBForce")
    force = forces[0]
    names = [force.getComputedValueParameters(i)[0] for i in range(force.getNumComputedValues())]
    if names != ["I", "B"]:
        raise ValueError(f"Unexpected GBn2 computed values {names}; refusing to rewrite them")
    (_, i_now, i_type), (_, b_now, b_type) = (force.getComputedValueParameters(0),
                                             force.getComputedValueParameters(1))
    if i_now != OPENMM_852_GBN2_I or b_now != OPENMM_852_GBN2_B:
        raise ValueError("GBn2 expressions differ from OpenMM 8.5.2's; refusing to rewrite them")
    i_new, b_new = amber_gbn2_descreening_expressions(rgbmax_angstrom)
    force.setComputedValueParameters(0, "I", i_new, i_type)
    force.setComputedValueParameters(1, "B", b_new, b_type)


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
