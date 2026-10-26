"""E1 — un dibujo que se ajusta al 3D (ver REGISTRO_PREVIO.md).

    python docs/auditorias/elevacion-grandes-2026-10-24/e1_dibujo_ajustado.py

Escribe `e1.jsonl` y `e1_lamina.svg` junto a este archivo.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, Chem, np  # noqa: E402
from rdkit.Chem import Draw, rdDepictor  # noqa: E402

SOLAPE = 0.4  # fracción de L


def cruces_y_solapes(mol: Chem.Mol, plano: np.ndarray) -> tuple[int, int]:
    L = comun.longitud_media(mol, plano)
    enlazados = {frozenset((e.GetBeginAtomIdx(), e.GetEndAtomIdx())) for e in mol.GetBonds()}
    n = mol.GetNumAtoms()
    solapes = sum(1 for i in range(n) for j in range(i + 1, n)
                  if frozenset((i, j)) not in enlazados and np.linalg.norm(plano[i] - plano[j]) < SOLAPE * L)

    def corta(p1, p2, p3, p4) -> bool:
        def orient(a, b, c):
            return np.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        return (orient(p1, p2, p3) * orient(p1, p2, p4) < 0) and (orient(p3, p4, p1) * orient(p3, p4, p2) < 0)

    enlaces = [(e.GetBeginAtomIdx(), e.GetEndAtomIdx()) for e in mol.GetBonds()]
    cruces = 0
    for k, (a, b) in enumerate(enlaces):
        for c, d in enlaces[k + 1:]:
            if {a, b} & {c, d}:
                continue
            if corta(plano[a], plano[b], plano[c], plano[d]):
                cruces += 1
    return cruces, solapes


def geometrias(mol: Chem.Mol, plano: np.ndarray, pesos: np.ndarray) -> dict[str, np.ndarray]:
    n = mol.GetNumAtoms()
    con_h, ids, _ = comun.candidatos(mol, 1, comun._candidatos(n))
    proxy = comun.pesados(con_h, ids[0], n)
    elegido, mejor = None, None
    for s in comun.SEMILLAS_CRITERIO:
        h, ids_s, _ = comun.candidatos(mol, s, comun._candidatos(n))
        for c in ids_s:
            xyz = comun.pesados(h, c, n)
            rms = comun._ajuste(xyz, plano, pesos)[1]
            if mejor is None or rms < mejor:
                mejor, elegido = rms, xyz
    return {"proxy_de_pose": proxy, "elegido": elegido}


def ajustado(mol: Chem.Mol, xyz: np.ndarray) -> tuple[Chem.Mol, np.ndarray]:
    ref = Chem.Mol(mol)
    ref.RemoveAllConformers()
    conf = Chem.Conformer(mol.GetNumAtoms())
    for i, p in enumerate(xyz):
        conf.SetAtomPosition(i, p.tolist())
    conf.Set3D(True)
    ref.AddConformer(conf, assignId=True)
    dibujada = Chem.Mol(mol)
    rdDepictor.GenerateDepictionMatching3DStructure(dibujada, ref)
    return dibujada, dibujada.GetConformer().GetPositions()[:, :2].copy()


def main() -> None:
    conjuntos = [("G37", d) for d in comun.g37()] + [("O167", d) for d in comun.o167()]
    lamina = []
    with open(AQUI / "e1.jsonl", "w", encoding="utf-8") as f:
        for conjunto, d in conjuntos:
            mol = Chem.MolFromSmiles(d["smiles"])
            normal = Chem.Mol(mol)
            plano = comun.dibujo_2d(normal).plano
            pesos = comun._pesos(mol)
            fila = {"conjunto": conjunto, "smiles": d["smiles"], "pesados": mol.GetNumAtoms(),
                    "normal": dict(zip(("cruces", "solapes"), cruces_y_solapes(mol, plano)))}
            for nombre, xyz in geometrias(mol, plano, pesos).items():
                dibujada, plano_aj = ajustado(mol, xyz)
                c, s = cruces_y_solapes(mol, plano_aj)
                fila[nombre] = {"razon_normal": round(comun.razon(mol, xyz, plano, pesos), 3),
                                "razon_ajustado": round(comun.razon(mol, xyz, plano_aj, pesos), 3),
                                "cruces": c, "solapes": s}
                if conjunto == "G37" and nombre == "proxy_de_pose" and len(lamina) < 24:
                    lamina += [normal, dibujada]
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(conjunto, fila["pesados"], fila["proxy_de_pose"], flush=True)
    svg = Draw.MolsToGridImage(lamina, molsPerRow=4, subImgSize=(320, 260), useSVG=True,
                               legends=[f"{'normal' if i % 2 == 0 else 'ajustado al 3D'} #{i // 2 + 1}"
                                        for i in range(len(lamina))])
    (AQUI / "e1_lamina.svg").write_text(svg if isinstance(svg, str) else svg.data, encoding="utf-8")


if __name__ == "__main__":
    main()
