"""E6 — animación por torsiones frente a interpolación lineal (ver REGISTRO_PREVIO_E6.md).

    python docs/auditorias/elevacion-grandes-2026-10-24/e6_animacion_por_torsiones.py

Escribe `e6.jsonl` junto a este archivo y, al final, el veredicto.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, Chem, np  # noqa: E402
from rdkit.Chem import rdMolTransforms  # noqa: E402

CORTE = 0.25  # s en que acaba la recta del dibujo a F
FOTOGRAMAS = 16
MUESTRAS = np.linspace(0.0, 1.0, 101)


def rotables(mol: Chem.Mol) -> list[tuple[int, int, int, int]]:
    """(a, b, c, d) pesados con b–c sencillo, fuera de anillo y un vecino pesado más a cada lado."""
    diedros = []
    for e in mol.GetBonds():
        if e.GetBondType() != Chem.BondType.SINGLE or e.IsInRing():
            continue
        b, c = e.GetBeginAtom(), e.GetEndAtom()
        a = [x.GetIdx() for x in b.GetNeighbors() if x.GetIdx() != c.GetIdx() and x.GetAtomicNum() > 1]
        d = [x.GetIdx() for x in c.GetNeighbors() if x.GetIdx() != b.GetIdx() and x.GetAtomicNum() > 1]
        if a and d:
            diedros.append((a[0], b.GetIdx(), c.GetIdx(), d[0]))
    return diedros


def diedro_plano(plano: np.ndarray, a: int, b: int, c: int, d: int) -> float:
    """0 si a y d quedan del mismo lado de la recta b–c en el dibujo, 180 si no."""
    eje = plano[c] - plano[b]
    lado = lambda p: np.sign(eje[0] * (p[1] - plano[b][1]) - eje[1] * (p[0] - plano[b][0]))  # noqa: E731
    return 0.0 if lado(plano[a]) == lado(plano[d]) else 180.0


def camino_por_torsiones(con_h: Chem.Mol, cid: int, n: int, plano: np.ndarray, pesos: np.ndarray):
    """Fotogramas alineados al dibujo: [F, …, C]."""
    diedros = [t for t in rotables(con_h) if max(t) < n]
    conf_c = con_h.GetConformer(cid)
    final = [rdMolTransforms.GetDihedralDeg(conf_c, *t) for t in diedros]
    inicio = [diedro_plano(plano, *t) for t in diedros]
    giro = [((f - i + 180.0) % 360.0) - 180.0 for i, f in zip(inicio, final)]
    trabajo = Chem.Mol(con_h, confId=cid)
    conf = trabajo.GetConformer()
    fotogramas = []
    for k in range(FOTOGRAMAS):
        t = k / (FOTOGRAMAS - 1)
        for (a, b, c, d), i, g in zip(diedros, inicio, giro):
            rdMolTransforms.SetDihedralDeg(conf, a, b, c, d, i + t * g)
        fotogramas.append(comun._ajuste(conf.GetPositions()[:n].copy(), plano, pesos)[0])
    return fotogramas, len(diedros)


def posiciones_a(dibujo: np.ndarray, final: np.ndarray, s: float) -> np.ndarray:
    return (1 - s) * dibujo + s * final


def posiciones_b(dibujo: np.ndarray, fotogramas: list[np.ndarray], s: float) -> np.ndarray:
    if s <= CORTE:
        return posiciones_a(dibujo, fotogramas[0], s / CORTE)
    x = (s - CORTE) / (1 - CORTE) * (FOTOGRAMAS - 1)
    k = min(int(x), FOTOGRAMAS - 2)
    return posiciones_a(fotogramas[k], fotogramas[k + 1], x - k)


def metricas(mol: Chem.Mol, camino, L: float) -> dict:
    enlaces = [(e.GetBeginAtomIdx(), e.GetEndAtomIdx()) for e in mol.GetBonds()]
    topo = Chem.GetDistanceMatrix(mol)
    i, j = np.where(np.triu(topo >= 3))
    p0, p1 = camino(0.0), camino(1.0)
    def lon(p):
        return np.array([np.linalg.norm(p[a] - p[b]) for a, b in enlaces])
    d0, d1 = lon(p0), lon(p1)
    deformacion, minimo = 0.0, np.inf
    for s in MUESTRAS:
        p = camino(s)
        deformacion = max(deformacion, float(np.max(np.abs(lon(p) - ((1 - s) * d0 + s * d1)))) / L)
        if len(i):
            minimo = min(minimo, float(np.min(np.linalg.norm(p[i] - p[j], axis=1))) / L)
    extremos = min((float(np.min(np.linalg.norm(q[i] - q[j], axis=1))) / L for q in (p0, p1)), default=np.inf) if len(i) else np.inf
    return {"deformacion": round(deformacion, 3), "minimo": round(minimo, 3),
            "cruce": bool(minimo < 0.5 <= extremos)}


def main() -> None:
    conjuntos = [("G37", d) for d in comun.g37()] + [("O167", d) for d in comun.o167()]
    with open(AQUI / "e6.jsonl", "w", encoding="utf-8") as f:
        for conjunto, d in conjuntos:
            mol = Chem.MolFromSmiles(d["smiles"])
            plano = comun.dibujo_2d(Chem.Mol(mol)).plano
            pesos = comun._pesos(mol)
            n = mol.GetNumAtoms()
            L = comun.longitud_media(mol, plano)
            rms_semilla, mejor = [], None
            for s in comun.SEMILLAS_CRITERIO:
                h, ids, _ = comun.candidatos(mol, s, comun._candidatos(n))
                if not ids:
                    continue
                rs = [(comun._ajuste(comun.pesados(h, c, n), plano, pesos)[1], c) for c in ids]
                r, c = min(rs)
                rms_semilla.append(r)
                if mejor is None or r < mejor[0]:
                    mejor = (r, h, c)
            fila = {"conjunto": conjunto, "smiles": d["smiles"], "pesados": n}
            if mejor is None:
                fila["sin_conformador"] = True
                f.write(json.dumps(fila) + "\n")
                continue
            fila["fiel"] = bool(np.median(rms_semilla) / L <= 1.0)
            _, h, c = mejor
            dibujo = np.column_stack([plano, np.zeros(n)])
            final = comun._ajuste(comun.pesados(h, c, n), plano, pesos)[0]
            t0 = time.perf_counter()
            fotogramas, rot = camino_por_torsiones(h, c, n, plano, pesos)
            fila["tiempo_b_s"] = round(time.perf_counter() - t0, 3)
            fila["rotables"] = rot
            fila["kb_b"] = round(len(json.dumps([np.round(q, 2).tolist() for q in fotogramas])) / 1024, 1)
            fila["extremo_b"] = round(float(np.max(np.abs(fotogramas[-1] - final))), 4)
            fila["A"] = metricas(mol, lambda s: posiciones_a(dibujo, final, s), L)
            fila["B"] = metricas(mol, lambda s: posiciones_b(dibujo, fotogramas, s), L)
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(conjunto, n, fila["fiel"], fila["A"], fila["B"], fila["tiempo_b_s"], flush=True)
    resumir()


def resumir() -> None:
    filas = [json.loads(l) for l in open(AQUI / "e6.jsonl", encoding="utf-8")]
    filas = [x for x in filas if not x.get("sin_conformador") and x["fiel"]]
    r = {}
    for conj in ("G37", "O167"):
        sub = [x for x in filas if x["conjunto"] == conj]
        for brazo in ("A", "B"):
            r[(conj, brazo, "cruces")] = sum(x[brazo]["cruce"] for x in sub)
            r[(conj, brazo, "def")] = st.median(x[brazo]["deformacion"] for x in sub)
            print(f"  {conj} {brazo}: n={len(sub)}, cruces {r[(conj, brazo, 'cruces')]}, deformación mediana "
                  f"{r[(conj, brazo, 'def')]:.3f}, máx {max(x[brazo]['deformacion'] for x in sub):.2f}, "
                  f"acercamiento mínimo mediano {st.median(x[brazo]['minimo'] for x in sub):.2f}")
        r[(conj, "t")] = st.median(x["tiempo_b_s"] for x in sub)
        r[(conj, "kb")] = st.median(x["kb_b"] for x in sub)
        r[(conj, "ext")] = max(x["extremo_b"] for x in sub)
        print(f"  {conj}: tiempo B mediano {r[(conj, 't')]:.3f} s, tamaño mediano {r[(conj, 'kb')]:.1f} kB, "
              f"extremo máx {r[(conj, 'ext')]:.4f}, rotables mediana {st.median(x['rotables'] for x in sub)}")
    criterios = {
        "G37 A >= 4 cruces": r[("G37", "A", "cruces")] >= 4,
        "G37 B <= mitad de A": r[("G37", "B", "cruces")] <= r[("G37", "A", "cruces")] / 2,
        "O167 B <= A cruces": r[("O167", "B", "cruces")] <= r[("O167", "A", "cruces")],
        "deformación G37 B <= 0,5 A": r[("G37", "B", "def")] <= 0.5 * r[("G37", "A", "def")],
        "deformación O167 B <= 0,5 A": r[("O167", "B", "def")] <= 0.5 * r[("O167", "A", "def")],
        "extremos": max(r[("G37", "ext")], r[("O167", "ext")]) <= 0.01,
        "tiempo G37 <= 0,3 s": r[("G37", "t")] <= 0.3,
        "tamaño G37 <= 40 kB": r[("G37", "kb")] <= 40,
    }
    for k, v in criterios.items():
        print(f"  {'cumple' if v else 'NO cumple'}: {k}")
    print("Veredicto E6:", "GO" if all(criterios.values()) else "NO_GO")


if __name__ == "__main__":
    main()
