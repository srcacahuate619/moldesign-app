import sys
import numpy as np
import openmm
from openmm import app, unit

d = sys.argv[1]
top = app.AmberPrmtopFile(d + "/ligand.prmtop")
crd = app.AmberInpcrdFile(d + "/ligand.inpcrd")
s = top.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, removeCMMotion=False)
for i, f in enumerate(s.getForces()):
    f.setForceGroup(i)
ctx = openmm.Context(s, openmm.VerletIntegrator(0.001), openmm.Platform.getPlatformByName("Reference"))
ctx.setPositions(crd.positions)
for i, f in enumerate(s.getForces()):
    e = ctx.getState(getEnergy=True, groups={i}).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    print(type(f).__name__, round(e, 5))

xyz = np.array(crd.positions.value_in_unit(unit.angstrom))
names = [a.name for a in top.topology.atoms()]
tors = next(f for f in s.getForces() if isinstance(f, openmm.PeriodicTorsionForce))
ang = next(f for f in s.getForces() if isinstance(f, openmm.HarmonicAngleForce))


def angle(a, b, c):
    u, v = xyz[a] - xyz[b], xyz[c] - xyz[b]
    return np.degrees(np.arccos(np.clip(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v), -1, 1)))


print("ángulos casi lineales o casi nulos:")
for k in range(ang.getNumAngles()):
    a, b, c, t0, kk = ang.getAngleParameters(k)
    th = angle(a, b, c)
    if th > 170 or th < 30:
        print("  ", names[a], names[b], names[c], round(th, 3))
print("torsiones con un ángulo interno > 175 o < 5 grados:")
for k in range(tors.getNumTorsions()):
    a, b, c, dd, per, ph, kk = tors.getTorsionParameters(k)
    t1, t2 = angle(a, b, c), angle(b, c, dd)
    if max(t1, t2) > 175 or min(t1, t2) < 5:
        print("  ", names[a], names[b], names[c], names[dd], "per", per, "k", kk, "ángulos", round(t1, 3), round(t2, 3))
print("átomos 44, 14, 21:", names[44], names[14], names[21])
dist = np.linalg.norm(xyz[:, None] - xyz[None], axis=2) + np.eye(len(xyz)) * 99
i, j = np.unravel_index(np.argmin(dist), dist.shape)
print("par más cercano:", names[i], names[j], round(float(dist[i, j]), 3), "Å")
