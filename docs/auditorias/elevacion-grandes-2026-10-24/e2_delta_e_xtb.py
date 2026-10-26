"""E2 — ¿la cifra de ΔE de MMFF exagera? (ver REGISTRO_PREVIO.md).

Puntos únicos GFN2-xTB (ALPB agua y fase gas) con el xTB del producto
(`tools/xtb`, los mismos argumentos que `services/xtb/service.py`) sobre cada
candidato MMFF94 del producto.

    python docs/auditorias/elevacion-grandes-2026-10-24/e2_delta_e_xtb.py

Escribe `e2.jsonl` junto a este archivo.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import comun  # noqa: E402
from comun import AQUI, RAIZ, Chem, np  # noqa: E402

HARTREE_A_KCAL = 627.509474
# xTB viaja en `tools/xtb/` (binario no versionado): en un worktree sin él, XTB_DIR apunta al del árbol principal.
XTB = pathlib.Path(os.environ["XTB_DIR"]) if os.environ.get("XTB_DIR") else RAIZ / "tools" / "xtb" / "xtb-6.7.1"


def energia_xtb(con_h: Chem.Mol, cid: int, alpb: bool) -> float | None:
    with tempfile.TemporaryDirectory() as d:
        (pathlib.Path(d) / "m.xyz").write_text(Chem.MolToXYZBlock(con_h, confId=cid))
        orden = [str(XTB / "bin" / "xtb.exe"), "m.xyz", "--gfn", "2", "--sp",
                 "--chrg", str(Chem.GetFormalCharge(con_h))] + (["--alpb", "water"] if alpb else [])
        env = {**os.environ, "XTBHOME": str(XTB / "share" / "xtb"), "OMP_NUM_THREADS": "2", "OMP_STACKSIZE": "1G"}
        r = subprocess.run(orden, cwd=d, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for linea in r.stdout.splitlines():
            if "TOTAL ENERGY" in linea:
                return float(linea.split()[3]) * HARTREE_A_KCAL
    return None


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> None:
    with open(AQUI / "e2.jsonl", "w", encoding="utf-8") as f:
        for d in comun.g37():
            mol = Chem.MolFromSmiles(d["smiles"])
            plano = comun.dibujo_2d(Chem.Mol(mol)).plano
            pesos = comun._pesos(mol)
            n = mol.GetNumAtoms()
            filas = []
            for s in comun.SEMILLAS_CRITERIO:
                h, ids, energias = comun.candidatos(mol, s, comun._candidatos(n))
                for cid, e in zip(ids, energias):
                    filas.append({"rms": comun._ajuste(comun.pesados(h, cid, n), plano, pesos)[1], "mmff": e,
                                  "alpb": energia_xtb(h, cid, True), "gas": energia_xtb(h, cid, False)})
            validas = [x for x in filas if x["alpb"] is not None and x["gas"] is not None]
            elegido = min(validas, key=lambda x: x["rms"])
            fila = {"smiles": d["smiles"], "pesados": n, "candidatos": len(filas), "xtb_fallidos": len(filas) - len(validas)}
            for k in ("mmff", "alpb", "gas"):
                fila[f"delta_{k}"] = round(elegido[k] - min(x[k] for x in validas), 2)
            fila["spearman_mmff_alpb"] = round(spearman([x["mmff"] for x in validas], [x["alpb"] for x in validas]), 3)
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(n, fila, flush=True)


if __name__ == "__main__":
    main()
