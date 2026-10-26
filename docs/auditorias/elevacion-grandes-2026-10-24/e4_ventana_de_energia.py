"""E4 — ventana de energía en la elección del conformador (ver REGISTRO_PREVIO_E4.md).

    python docs/auditorias/elevacion-grandes-2026-10-24/e4_ventana_de_energia.py

Escribe `e4.jsonl` junto a este archivo y, al final, el veredicto.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, Chem, np  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402
from e2_delta_e_xtb import energia_xtb  # noqa: E402

VENTANAS = (None, 3.0, 5.0, 10.0)  # None = el producto, sin ventana


def elegir(por_semilla: list[list[dict]], e_min: float, ventana: float | None) -> tuple[float, dict]:
    """(mediana de los mejores de cada semilla, el enseñado) con la regla del registro."""
    mejores = []
    for candidatos in por_semilla:
        dentro = candidatos if ventana is None else [c for c in candidatos if c["mmff"] <= e_min + ventana]
        mejor = min(dentro, key=lambda c: c["rms"]) if dentro else min(candidatos, key=lambda c: c["mmff"])
        mejores.append(mejor)
    return float(np.median([m["rms"] for m in mejores])), min(mejores, key=lambda c: c["rms"])


def main() -> None:
    conjuntos = [("G37", d) for d in comun.g37()] + [("O167", d) for d in comun.o167()]
    with open(AQUI / "e4.jsonl", "w", encoding="utf-8") as f:
        for conjunto, d in conjuntos:
            mol = Chem.MolFromSmiles(d["smiles"])
            if not AllChem.MMFFHasAllMoleculeParams(Chem.AddHs(mol)):
                f.write(json.dumps({"conjunto": conjunto, "smiles": d["smiles"], "sin_mmff": True}) + "\n")
                continue
            plano = comun.dibujo_2d(Chem.Mol(mol)).plano
            pesos = comun._pesos(mol)
            n = mol.GetNumAtoms()
            L = comun.longitud_media(mol, plano)
            por_semilla = []
            for s in comun.SEMILLAS_CRITERIO:
                h, ids, energias = comun.candidatos(mol, s, comun._candidatos(n))
                por_semilla.append([
                    {"rms": comun._ajuste(comun.pesados(h, c, n), plano, pesos)[1], "mmff": e,
                     "alpb": energia_xtb(h, c, True) if conjunto == "G37" else None}
                    for c, e in zip(ids, energias)])
            todos = [c for s in por_semilla for c in s]
            e_min = min(c["mmff"] for c in todos)
            alpb_min = min((c["alpb"] for c in todos if c["alpb"] is not None), default=None)
            fila = {"conjunto": conjunto, "smiles": d["smiles"], "pesados": n}
            for ventana in VENTANAS:
                mediana, ensenado = elegir(por_semilla, e_min, ventana)
                clave = "producto" if ventana is None else f"v{ventana:g}"
                fila[clave] = {
                    "razon": round(mediana / L, 3),
                    "delta_mmff": round(ensenado["mmff"] - e_min, 2),
                    "delta_alpb": None if alpb_min is None or ensenado["alpb"] is None
                    else round(ensenado["alpb"] - alpb_min, 2),
                }
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(conjunto, n, fila["producto"], fila["v5"], flush=True)
    resumir()


def resumir() -> None:
    filas = [json.loads(l) for l in open(AQUI / "e4.jsonl", encoding="utf-8")]
    print("sin MMFF:", sum(1 for x in filas if x.get("sin_mmff")))
    filas = [x for x in filas if not x.get("sin_mmff")]
    abst = {}
    for conj in ("G37", "O167"):
        sub = [x for x in filas if x["conjunto"] == conj]
        for clave in ("producto", "v3", "v5", "v10"):
            a = sum(x[clave]["razon"] > 1 for x in sub)
            abst[(conj, clave)] = a
            alpb = [x[clave]["delta_alpb"] for x in sub if x[clave]["delta_alpb"] is not None]
            print(f"  {conj} {clave:>8}: se abstienen {a}/{len(sub)}, razón mediana "
                  f"{st.median(x[clave]['razon'] for x in sub):.2f}, ΔE MMFF mediana "
                  f"{st.median(x[clave]['delta_mmff'] for x in sub):.1f}"
                  + (f", ΔE xTB-ALPB mediana {st.median(alpb):.1f}" if alpb else ""))
    sube_o = abst[("O167", "v5")] - abst[("O167", "producto")]
    sube_g = abst[("G37", "v5")] - abst[("G37", "producto")]
    viable = sube_o <= 3 and sube_g <= 4
    print(f"Ventana 5 kcal/mol: la abstención sube {sube_o} en O167 (límite 3) y {sube_g} en G37 (límite 4) -> "
          f"{'VIABLE' if viable else 'NO_GO'}")


if __name__ == "__main__":
    main()
