"""E3 — plegado restringido al dibujo (ver REGISTRO_PREVIO.md).

ETKDGv3 con `coordMap`: los átomos aromáticos en su sitio del dibujo normal,
escalado a 1,40 Å de enlace aromático medio. Lo demás, como el producto.

    python docs/auditorias/elevacion-grandes-2026-10-24/e3_plegado_restringido.py

Escribe `e3.jsonl` junto a este archivo.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, Chem, np  # noqa: E402
from rdkit.Geometry import Point3D  # noqa: E402

ENLACE_AROMATICO_A = 1.40


def mapa_aromatico(mol: Chem.Mol, plano: np.ndarray) -> dict[int, Point3D] | None:
    anillos = [r for r in mol.GetRingInfo().AtomRings() if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in r)]
    if len(anillos) < 2:
        return None
    atomos = sorted({i for r in anillos for i in r})
    aromaticos = [e for e in mol.GetBonds() if e.GetIsAromatic()]
    media = float(np.mean([np.linalg.norm(plano[e.GetBeginAtomIdx()] - plano[e.GetEndAtomIdx()]) for e in aromaticos]))
    k = ENLACE_AROMATICO_A / media
    return {i: Point3D(float(plano[i][0] * k), float(plano[i][1] * k), 0.0) for i in atomos}


def brazo(mol, plano, pesos, coord_map):
    """(razón como el producto: mediana de las semillas; elegido (rms, energía); energías; s; fallos)."""
    n = mol.GetNumAtoms()
    t0 = time.perf_counter()
    mejores, todas, elegido, fallos = [], [], None, 0
    for s in comun.SEMILLAS_CRITERIO:
        h, ids, energias = comun.candidatos(mol, s, comun._candidatos(n), coord_map)
        if not ids:
            fallos += 1
            continue
        todas += energias
        de_la_semilla = min(((comun._ajuste(comun.pesados(h, c, n), plano, pesos)[1], e) for c, e in zip(ids, energias)))
        mejores.append(de_la_semilla[0])
        if elegido is None or de_la_semilla[0] < elegido[0]:
            elegido = de_la_semilla
    L = comun.longitud_media(mol, plano)
    razon = float(np.median(mejores)) / L if mejores else None
    return razon, elegido, todas, round(time.perf_counter() - t0, 2), fallos


def main() -> None:
    with open(AQUI / "e3.jsonl", "w", encoding="utf-8") as f:
        for d in comun.g37():
            mol = Chem.MolFromSmiles(d["smiles"])
            plano = comun.dibujo_2d(Chem.Mol(mol)).plano
            pesos = comun._pesos(mol)
            mapa = mapa_aromatico(mol, plano)
            r_p, el_p, e_p, t_p, _ = brazo(mol, plano, pesos, None)
            fila = {"smiles": d["smiles"], "pesados": mol.GetNumAtoms(), "restringida": mapa is not None,
                    "razon_producto": round(r_p, 3), "segundos_producto": t_p}
            if mapa is None:
                fila.update({"razon_e3": fila["razon_producto"], "segundos_e3": t_p,
                             "delta_producto": round(el_p[1] - min(e_p), 2), "delta_e3": round(el_p[1] - min(e_p), 2),
                             "fallos_e3": 0})
            else:
                r_3, el_3, e_3, t_3, fallos = brazo(mol, plano, pesos, mapa)
                referencia = min(e_p + e_3)
                fila.update({"razon_e3": None if r_3 is None else round(r_3, 3), "segundos_e3": t_3,
                             "delta_producto": round(el_p[1] - referencia, 2),
                             "delta_e3": None if el_3 is None else round(el_3[1] - referencia, 2),
                             "fallos_e3": fallos})
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(fila, flush=True)


if __name__ == "__main__":
    main()
