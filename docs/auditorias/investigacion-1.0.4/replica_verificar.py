"""Réplica de Claude (2026-11-15): recalcula de forma independiente cifras de la investigación 1.0.4.

No importa nada de la carpeta de la investigación ni reutiliza sus scripts: lee los per_complex sellados y
recalcula con su propio Spearman, McNemar exacto y bootstrap. Los IC salen de 2000 remuestreos, no de 10 000,
así que difieren en la tercera cifra; las ρ y los recuentos deben coincidir exactos.

Uso, desde la raíz del repositorio:
    ./python-embed/python.exe -I docs/auditorias/investigacion-1.0.4/replica_verificar.py .
"""
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

raiz = Path(sys.argv[1])
art = raiz / "scripts" / "artifacts_science"


def leer(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def rangos(xs):
    orden = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and xs[orden[j + 1]] == xs[orden[i]]:
            j += 1
        m = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[orden[k]] = m
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def spearman(a, b):
    return pearson(rangos(a), rangos(b))


def binom_bilateral(k, n):
    k = min(k, n - k)
    s = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * s)


print("== REC-11")
rec = leer(art / "REC-11" / "per_complex.jsonl")
con = sum(1 for r in rec if r["CON"]["cubierto"])
sin = sum(1 for r in rec if r["SIN"]["cubierto"])
gc = sum(1 for r in rec if r.get("gana_CON"))
gs = sum(1 for r in rec if r.get("gana_SIN"))
print(f"n={len(rec)} CON={con} SIN={sin} gana_CON={gc} gana_SIN={gs} p={binom_bilateral(gc, gc + gs):.6f}")

print("== DEC-104-D03-R1")
d3 = leer(art / "DEC-104-D03-R1" / "per_complex.jsonl")
exito = {}
for r in d3:
    for brazo, datos in r["brazos"].items():
        ok = sum(1 for c in datos["casos"] if c["rmsd_top1_A"] is not None and c["rmsd_top1_A"] <= 2.0)
        exito[(r["pdb"], brazo)] = ok >= 3
por = Counter()
for (pdb, brazo), ok in exito.items():
    fam = next(x["familia"] for x in d3 if x["pdb"] == pdb)
    if ok:
        por[(fam, brazo)] += 1
        por[("TOTAL", brazo)] += 1
print(dict(sorted(por.items())))
solo_sel = [r["pdb"] for r in d3 if exito[(r["pdb"], "SELECTIVAS")] and not exito[(r["pdb"], "SIN")]]
solo_sin = [r["pdb"] for r in d3 if exito[(r["pdb"], "SIN")] and not exito[(r["pdb"], "SELECTIVAS")]]
print("solo selectivas", solo_sel, "solo seco", solo_sin,
      f"p={binom_bilateral(len(solo_sin), len(solo_sel) + len(solo_sin)):.3f}")
con_agua = sum(1 for r in d3 if any(a["selectiva"] for a in r["aguas"]))
print("complejos con alguna selectiva:", con_agua, "de", len(d3))
ctrl = {r["pdb"]: (exito[(r["pdb"], "SIN")], exito[(r["pdb"], "SELECTIVAS")]) for r in d3 if r["desplazamiento_control"]}
print("controles de desplazamiento (SIN, SEL):", ctrl)
semillas = sum(len(d["casos"]) for r in d3 for d in r["brazos"].values())
print("resultados brazo-semilla:", semillas)


def rho_ic(xs, ys, b=2000, semilla=20261025):
    rho = spearman(xs, ys)
    rng = random.Random(semilla)
    n = len(xs)
    vals = []
    for _ in range(b):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(spearman([xs[i] for i in idx], [ys[i] for i in idx]))
    vals.sort()
    return rho, vals[int(0.025 * b)], vals[int(0.975 * b) - 1]


print("== SUP-04 (8T69), rho de -E contra pKi; Q = -E")
s4 = leer(art / "SUP-04-EXHAUSTIVIDAD-8T69" / "per_complex.jsonl")
pki = [r["pki"] for r in s4]
for brazo in ("Q_e8", "Q_e8s43", "Q_e16", "Q_e32"):
    print(brazo, "rho=%.3f IC~[%.3f, %.3f]" % rho_ic([r[brazo] for r in s4], pki))
cerca = sum(1 for r in s4 if abs(r["Q_e32"] - r["Q_e8"]) < 0.1)
print("padres con |Q32-Q8|<0,1:", cerca, "de", len(s4))

print("== DEC-104-D06-8HFI")
d6 = leer(art / "DEC-104-D06-8HFI" / "per_complex.jsonl")
print("corridas:", len(d6), "estados:", Counter(r["estado"] for r in d6),
      "receptores:", {r["receptor_sha256"][:8] for r in d6})
for brazo in ("e8", "e8s43", "e16", "e32"):
    filas = sorted((r for r in d6 if r["brazo"] == brazo and r["pki"] is not None), key=lambda r: r["padre"])
    xs = [-r["energia_kcal"] for r in filas]
    ys = [r["pki"] for r in filas]
    red = [r for r in d6 if r["brazo"] == brazo and r["pki"] is None]
    ok = sum(1 for r in red if r["rmsd"] is not None and r["rmsd"] <= 2.0 and r["posebusters"] == "passed")
    seg = sorted(sum(i["segundos"] for i in r["intentos"]) for r in filas + red)
    med = seg[len(seg) // 2] if len(seg) % 2 else (seg[len(seg) // 2 - 1] + seg[len(seg) // 2]) / 2
    print(brazo, "n=%d rho=%.3f IC~[%.3f, %.3f]" % ((len(filas),) + rho_ic(xs, ys)),
          f"redocking {ok}/{len(red)} mediana_s={med:.1f}")

print("== DEC-104-D08-REPLAY")
d8 = leer(art / "DEC-104-D08-REPLAY" / "per_complex.jsonl")
pos = [r for r in d8 if r.get("familia_esperada")]
neg = [r for r in d8 if not r.get("familia_esperada")]
print("filas", len(d8), "positivos", len(pos), "negativos", len(neg))
por_fam = Counter()
for r in pos:
    por_fam[(r["familia_esperada"], "antes")] += r["familia_esperada"] in r["antes"]
    por_fam[(r["familia_esperada"], "despues")] += r["familia_esperada"] in r["despues"]
print(dict(sorted(por_fam.items())))
print("negativos sin familia antes:", sum(1 for r in neg if not r["antes"]),
      "despues:", sum(1 for r in neg if not r["despues"]))
anion = [r for r in pos if r["forma"] != "neutra"]
print("UMS aniónicos antes", {round(r["ums_antes"], 4) for r in anion}, "despues", {round(r["ums_despues"], 4) for r in anion})
