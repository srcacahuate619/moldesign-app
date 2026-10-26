"""E5 — enderezar cadenas y girar colas, como MolTalk (ver REGISTRO_PREVIO_E5.md).

`extender_cadenas` y `girar_cola` son una adaptación de `_extend_chains` y
`_swing_tail` de MolTalk (Dominic Fico, MIT; `moltalk/conformer.py`, `44da199`):
misma lógica, con la puntuación de MolDesign (`_ajuste` y sus pesos).

    python docs/auditorias/elevacion-grandes-2026-10-24/e5_cadenas_y_colas.py

Escribe `e5.jsonl` junto a este archivo y, al final, el veredicto.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st
import sys
import time
from itertools import product

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, Chem, np  # noqa: E402
from rdkit import rdBase  # noqa: E402
from rdkit.Chem import AllChem, rdMolTransforms  # noqa: E402
from chem.elevacion import _estereo_de_la_pose  # noqa: E402
from e2_delta_e_xtb import energia_xtb  # noqa: E402


def _relajar(mol: Chem.Mol, cid: int, iteraciones: int) -> None:
    with rdBase.BlockLogs():
        AllChem.MMFFOptimizeMolecule(mol, confId=cid, maxIters=iteraciones)


def energia_mmff(mol: Chem.Mol, cid: int) -> float:
    props = AllChem.MMFFGetMoleculeProperties(mol)
    return float(AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid).CalcEnergy())


def extender_cadenas(mol: Chem.Mol, cid: int, minimo: int = 4) -> Chem.Mol | None:
    """Las torsiones de las cadenas abiertas de carbonos sp3 a 180° y relajado; None si no hay cadena."""
    cadena = lambda a: a.GetSymbol() == "C" and not a.IsInRing() and a.GetHybridization() == Chem.HybridizationType.SP3
    carbonos = {a.GetIdx() for a in mol.GetAtoms() if cadena(a)}
    if len(carbonos) < minimo:
        return None
    torsiones = []
    for enlace in mol.GetBonds():
        b, c = enlace.GetBeginAtom(), enlace.GetEndAtom()
        if (enlace.GetBondType() != Chem.BondType.SINGLE or enlace.IsInRing()
                or b.GetIdx() not in carbonos or c.GetIdx() not in carbonos):
            continue
        a = next((n.GetIdx() for n in b.GetNeighbors() if n.GetIdx() != c.GetIdx() and n.GetAtomicNum() > 1), None)
        d = next((n.GetIdx() for n in c.GetNeighbors() if n.GetIdx() != b.GetIdx() and n.GetAtomicNum() > 1), None)
        if a is not None and d is not None:
            torsiones.append((a, b.GetIdx(), c.GetIdx(), d))
    if len(torsiones) < minimo - 2:
        return None
    salida = Chem.Mol(mol)
    conf = salida.GetConformer(cid)
    for t in torsiones:
        try:
            rdMolTransforms.SetDihedralDeg(conf, *t, 180.0)
        except (RuntimeError, ValueError):
            continue
    _relajar(salida, cid, 500)
    return salida


def girar_cola(mol: Chem.Mol, cid: int, puntua, pesados: int, max_enlaces: int = 4, min_cola: int = 6):
    """La cola larga que sale de un anillo, con sus primeras torsiones donde mejor encaja; None si no hay cola."""
    anillo = {a.GetIdx() for a in mol.GetAtoms() if a.IsInRing() and a.GetIdx() < pesados}
    if not anillo:
        return None
    dist = Chem.GetDistanceMatrix(mol)
    alcance = {i: min(dist[i][r] for r in anillo) for i in range(pesados)}
    alcance = {i: d for i, d in alcance.items() if d < mol.GetNumAtoms()}
    lejano = max(alcance, key=alcance.get)
    if alcance[lejano] < min_cola:
        return None
    inicio = min(anillo, key=lambda r: dist[lejano][r])
    camino = list(Chem.GetShortestPath(mol, inicio, lejano))
    if len(camino) - 1 < min_cola:
        return None
    torsiones = []
    for k in range(len(camino) - 1):
        b, c = camino[k], camino[k + 1]
        enlace = mol.GetBondBetweenAtoms(b, c)
        if enlace.GetBondType() != Chem.BondType.SINGLE or enlace.IsInRing():
            continue
        a = next((n.GetIdx() for n in mol.GetAtomWithIdx(b).GetNeighbors() if n.GetIdx() != c and n.GetAtomicNum() > 1), None)
        d = next((n.GetIdx() for n in mol.GetAtomWithIdx(c).GetNeighbors() if n.GetIdx() != b and n.GetAtomicNum() > 1), None)
        if a is not None and d is not None:
            torsiones.append((a, b, c, d))
        if len(torsiones) == max_enlaces:
            break
    if not torsiones:
        return None
    pares = np.argwhere(np.triu(dist[:pesados, :pesados] >= 4, 1))
    mejor = None
    for angulos in product((60.0, 180.0, 300.0), repeat=len(torsiones)):
        prueba = Chem.Mol(mol)
        conf = prueba.GetConformer(cid)
        try:
            for t, angulo in zip(torsiones, angulos):
                rdMolTransforms.SetDihedralDeg(conf, *t, angulo)
        except (RuntimeError, ValueError):
            continue
        pos = conf.GetPositions()
        if len(pares) and np.min(np.linalg.norm(pos[pares[:, 0]] - pos[pares[:, 1]], axis=1)) < 2.5:
            continue  # átomos pesados a ≥ 4 enlaces y a < 2,5 Å: choque
        puntos = puntua(prueba)
        if mejor is None or puntos < mejor[0]:
            mejor = (puntos, prueba)
    if mejor is None:
        return None
    salida = mejor[1]
    _relajar(salida, cid, 300)
    return salida


def refinar(h: Chem.Mol, cid: int, puntua, n: int) -> tuple[Chem.Mol, list[str]]:
    """Los dos pasos, en el orden de MolTalk; cada uno se conserva sólo si encaja mejor."""
    actual, aplicados = h, []
    for nombre, paso in (("cadenas", lambda m: extender_cadenas(m, cid)),
                         ("cola", lambda m: girar_cola(m, cid, puntua, n))):
        try:
            nuevo = paso(actual)
        except Exception:  # noqa: BLE001 — como MolTalk: si un paso falla, se sigue sin él
            nuevo = None
        if nuevo is None:
            continue
        aplicados.append(f"{nombre}:intentado")
        if puntua(nuevo) < puntua(actual):
            actual = nuevo
            aplicados.append(f"{nombre}:conservado")
    return actual, aplicados


def main() -> None:
    conjuntos = [("G37", d) for d in comun.g37()] + [("O167", d) for d in comun.o167()]
    with open(AQUI / "e5.jsonl", "w", encoding="utf-8") as f:
        for conjunto, d in conjuntos:
            mol = Chem.MolFromSmiles(d["smiles"])
            if not AllChem.MMFFHasAllMoleculeParams(Chem.AddHs(mol)):
                f.write(json.dumps({"conjunto": conjunto, "smiles": d["smiles"], "sin_mmff": True}) + "\n")
                continue
            plano = comun.dibujo_2d(Chem.Mol(mol)).plano
            pesos = comun._pesos(mol)
            n = mol.GetNumAtoms()
            L = comun.longitud_media(mol, plano)
            xtb = conjunto == "G37"
            t0 = time.perf_counter()
            semillas = []
            for s in comun.SEMILLAS_CRITERIO:
                h, ids, energias = comun.candidatos(mol, s, comun._candidatos(n))
                cands = [{"cid": c, "mmff": e, "rms": comun._ajuste(comun.pesados(h, c, n), plano, pesos)[1]}
                         for c, e in zip(ids, energias)]
                semillas.append((h, cands))
            t_producto = time.perf_counter() - t0
            t1 = time.perf_counter()
            refinados = []
            for h, cands in semillas:
                mejor = min(cands, key=lambda c: c["rms"])
                cid = mejor["cid"]
                puntua = lambda m, cid=cid: comun._ajuste(comun.pesados(m, cid, n), plano, pesos)[1]
                ref, aplicados = refinar(h, cid, puntua, n)
                refinados.append({"mol": ref, "cid": cid, "rms": puntua(ref), "mmff": energia_mmff(ref, cid),
                                  "aplicados": aplicados, "original": mejor, "h": h})
            t_e5 = t_producto + (time.perf_counter() - t1)
            # Referencia unida: todos los candidatos del producto y los refinados.
            todos_mmff = [c["mmff"] for _, cands in semillas for c in cands] + [r["mmff"] for r in refinados]
            e_min = min(todos_mmff)
            ens_p = min((r["original"] for r in refinados), key=lambda c: c["rms"])
            ens_5 = min(refinados, key=lambda r: r["rms"])
            fila = {
                "conjunto": conjunto, "smiles": d["smiles"], "pesados": n,
                "razon_producto": round(float(np.median([r["original"]["rms"] for r in refinados])) / L, 3),
                "razon_e5": round(float(np.median([r["rms"] for r in refinados])) / L, 3),
                "delta_mmff_producto": round(ens_p["mmff"] - e_min, 2),
                "delta_mmff_e5": round(ens_5["mmff"] - e_min, 2),
                "aplicados": sorted({a for r in refinados for a in r["aplicados"]}),
                "segundos_producto": round(t_producto, 2), "segundos_e5": round(t_e5, 2),
            }
            estereo = _estereo_de_la_pose(mol, comun.pesados(ens_5["mol"], ens_5["cid"], n))
            fila["estereo_cambia"] = bool(estereo["invertidos"] or estereo["no_asignables"])
            if xtb:
                alpb = [energia_xtb(h, c["cid"], True) for h, cands in semillas for c in cands]
                alpb_ref = [energia_xtb(r["mol"], r["cid"], True) for r in refinados]
                validos = [e for e in alpb + alpb_ref if e is not None]
                base = min(validos)
                prod_h = next(h for h, cands in semillas if ens_p in cands)
                e_prod = energia_xtb(prod_h, ens_p["cid"], True)
                e_e5 = energia_xtb(ens_5["mol"], ens_5["cid"], True)
                fila["delta_alpb_producto"] = None if e_prod is None else round(e_prod - base, 2)
                fila["delta_alpb_e5"] = None if e_e5 is None else round(e_e5 - base, 2)
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(conjunto, n, fila["razon_producto"], "->", fila["razon_e5"], fila["aplicados"], flush=True)
    resumir()


def resumir() -> None:
    filas = [json.loads(l) for l in open(AQUI / "e5.jsonl", encoding="utf-8")]
    print("sin MMFF:", sum(1 for x in filas if x.get("sin_mmff")))
    filas = [x for x in filas if not x.get("sin_mmff")]
    res = {}
    for conj in ("G37", "O167"):
        sub = [x for x in filas if x["conjunto"] == conj]
        ap = sum(any(a.endswith("intentado") for a in x["aplicados"]) for x in sub)
        co = sum(any(a.endswith("conservado") for a in x["aplicados"]) for x in sub)
        res[conj] = {
            "abst_p": sum(x["razon_producto"] > 1 for x in sub), "abst_5": sum(x["razon_e5"] > 1 for x in sub),
            "de_p": st.median(x["delta_mmff_producto"] for x in sub), "de_5": st.median(x["delta_mmff_e5"] for x in sub),
            "t_p": st.median(x["segundos_producto"] for x in sub), "t_5": st.median(x["segundos_e5"] for x in sub),
            "estereo": sum(x["estereo_cambia"] for x in sub), "n": len(sub),
        }
        r = res[conj]
        linea = (f"  {conj}: se abstienen {r['abst_p']}/{r['n']} -> {r['abst_5']}/{r['n']}; "
                 f"razón mediana {st.median(x['razon_producto'] for x in sub):.2f} -> {st.median(x['razon_e5'] for x in sub):.2f}; "
                 f"ΔE MMFF {r['de_p']:.1f} -> {r['de_5']:.1f}; tiempo {r['t_p']:.1f} -> {r['t_5']:.1f} s; "
                 f"algún paso intentado {ap}, conservado {co}; estereo cambia {r['estereo']}")
        if conj == "G37":
            a_p = [x["delta_alpb_producto"] for x in sub if x.get("delta_alpb_producto") is not None]
            a_5 = [x["delta_alpb_e5"] for x in sub if x.get("delta_alpb_e5") is not None]
            linea += f"; ΔE xTB-ALPB {st.median(a_p):.1f} -> {st.median(a_5):.1f}"
        print(linea)
    g, o = res["G37"], res["O167"]
    go = (g["abst_5"] <= 4 and o["abst_5"] <= o["abst_p"] and g["de_5"] <= g["de_p"]
          and g["t_5"] <= 1.5 * g["t_p"] and g["estereo"] + o["estereo"] == 0)
    print(f"E5 -> {'GO' if go else 'NO_GO'}")


if __name__ == "__main__":
    main()
