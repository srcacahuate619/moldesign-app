"""Analiza el desajuste dibujo-3D medido por medir_desajuste.py.

CRITERIO FIJADO ANTES DE VER LOS DATOS (no se cambia después de mirar la cola):
    razon = desajuste_px (producto, candidatos por defecto) / longitud_media_de_enlace_px
    abstención si razon > 1.0  (la elevación movería algún átomo más de un enlace)
    Sensibilidad informativa: 0.5, 0.75 y 1.5.

Uso: python analizar_desajuste.py <carpeta_de_resultados>
"""
import json
import pathlib
import sys

import numpy as np

D = pathlib.Path(sys.argv[1])
UMBRAL = 1.0


def leer(nombre):
    with open(D / nombre, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def cuartiles(v):
    v = np.asarray(v, dtype=float)
    return {p: round(float(np.percentile(v, p)), 3) for p in (50, 75, 90, 95)} | {"max": round(float(v.max()), 3)}


def rho_spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return round(float(np.corrcoef(rx, ry)[0, 1]), 3)


mols = leer("moleculas.jsonl")
errores = [m for m in mols if "error" in m]
ok = [m for m in mols if "desajuste_defecto" in m and m.get("enlace_px") == m.get("enlace_px")]
print(f"moléculas: {len(mols)} | medidas: {len(ok)} | con error: {len(errores)}")
for m in errores:
    print(f"   ERROR {m['id']} ({m['origen']}): {m['error']}")

razon = np.array([m["desajuste_defecto"] / m["enlace_px"] for m in ok])
print("\n== Razón desajuste/enlace, producto (candidatos por defecto)")
print("   cuantiles:", cuartiles(razon))
for u in (0.5, 0.75, 1.0, 1.5):
    n = int((razon > u).sum())
    print(f"   > {u}: {n} de {len(ok)} ({100 * n / len(ok):.1f} %)")
print("   desajuste absoluto px:", cuartiles([m["desajuste_defecto"] for m in ok]))
print("   enlace px:", cuartiles([m["enlace_px"] for m in ok]))

print("\n== Por tamaño (átomos pesados): mediana razón, fracción > 1, candidatos")
for lo, hi in ((0, 20), (21, 40), (41, 80), (81, 999)):
    sub = [m for m in ok if lo <= m["pesados"] <= hi]
    if not sub:
        continue
    r = [m["desajuste_defecto"] / m["enlace_px"] for m in sub]
    n_cand = sorted({m["candidatos_defecto"] for m in sub})
    print(f"   {lo:>3}-{hi:<3} n={len(sub):>3}  mediana={np.median(r):.3f}  >1: {sum(x > 1 for x in r)}  candidatos={n_cand}")

print("\n== Por flexibilidad (enlaces rotables): mediana razón, fracción > 1")
for lo, hi in ((0, 1), (2, 4), (5, 99)):
    sub = [m for m in ok if lo <= m["enlaces_rotables"] <= hi]
    if not sub:
        continue
    r = [m["desajuste_defecto"] / m["enlace_px"] for m in sub]
    print(f"   {lo}-{hi} rotables  n={len(sub):>3}  mediana={np.median(r):.3f}  >1: {sum(x > 1 for x in r)}")

print("\n== Correlación de Spearman con la razón")
print("   pesados:", rho_spearman([m["pesados"] for m in ok], razon))
print("   rotables:", rho_spearman([m["enlaces_rotables"] for m in ok], razon))
print("   anillos:", rho_spearman([m["anillos"] for m in ok], razon))

print("\n== Robustez: mismo número de candidatos (16), tres semillas")
spread = []
for m in ok:
    s = [m["desajuste_16"][k] for k in ("1", "2", "3")]
    spread.append((max(s) - min(s)) / m["enlace_px"])
print("   rango entre semillas / enlace:", cuartiles(spread))
cambian = 0
for m in ok:
    s = [m["desajuste_16"][k] / m["enlace_px"] for k in ("1", "2", "3")]
    if any(x > UMBRAL for x in s) and not all(x > UMBRAL for x in s):
        cambian += 1
print(f"   moléculas cuya decisión cambia según la semilla: {cambian} de {len(ok)}")
c16 = [np.median([m["desajuste_16"][k] for k in ("1", "2", "3")]) / m["enlace_px"] for m in ok]
dif = [m["desajuste_defecto"] / m["enlace_px"] - c for m, c in zip(ok, c16)]
print(f"   producto (por defecto) menos 16 candidatos, mediana razón: {np.median(dif):+.3f}")
print("   moléculas que cambian de decisión por el número de candidatos:",
      sum(1 for m, c in zip(ok, c16) if (m["desajuste_defecto"] / m["enlace_px"] > UMBRAL) != (c > UMBRAL)))

poses = leer("poses.jsonl")
print("\n== Poses Vina reales (SMILES de entrada, desajuste del registro)")
for p in poses:
    if "desajuste" not in p:
        print(f"   ERROR {p['caso']} #{p['registro']}: {p.get('error')}")
        continue
    r = p["desajuste"] / p["enlace_px"]
    print(f"   {p['caso']:<40} #{p['registro']:>2}  desajuste={p['desajuste']:6.2f}px  enlace={p['enlace_px']:6.2f}px  "
          f"razon={r:5.2f}  estereo_inv={p['estereo_invertidos']}  carga {p['carga_smiles']}->{p['carga_acoplada']}  "
          f"afinidad={p['afinidad']}")
top1 = [p for p in poses if p.get("registro") == 1 and "desajuste" in p]
print("   top-1:", [round(p["desajuste"] / p["enlace_px"], 2) for p in top1])
