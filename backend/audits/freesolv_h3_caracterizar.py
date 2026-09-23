#!/usr/bin/env python3
r"""freesolv_h3_caracterizar.py — lo que H3 enseña además del gate. EXPLORATORIO.

Se escribió **después** de ver la decisión de `MMGBSA-H3-FREESOLV-RADIOS`
(NO_GO) y no la cambia: sólo lee `per_complex.jsonl` y `seleccion.json`
sellados y separa de dónde viene el error. Tres preguntas:

1. ¿La discrepancia GB−PB baja con el radio de Bondi por algo más que por
   escala? (Con radios mayores las dos energías encogen, y el absoluto con ellas.)
2. Con PB en lugar de GB y el mismo término no polar reajustado en las
   moléculas sin halógeno, ¿el radio de Bondi mejora frente al experimento? Si
   tampoco, el NO_GO no es un artefacto de la aproximación GB.
3. ¿Dónde se separa GBn2 de PB? Por número de F y de Cl en la molécula.

Nada de esto es un gate. Un patrón que salga aquí es una hipótesis nueva que
se prerregistra aparte.

    python backend/audits/freesolv_h3_caracterizar.py [--artefactos DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
ARTEFACTOS = RAIZ / "scripts" / "artifacts_science" / "MMGBSA-H3-FREESOLV-RADIOS"
BRI = ("Br", "I", "Br_mixto", "I_mixto")


def _ajuste_no_polar(filas, clave):
    control = [r for r in filas if r["grupo"] == "sin_halogeno"]
    x = np.array([[r["sasa_A2"], 1.0] for r in control])
    y = np.array([r["exp_kcal_mol"] - r[clave] for r in control])
    (gamma, b), *_ = np.linalg.lstsq(x, y, rcond=None)
    return float(gamma), float(b)


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artefactos", type=Path, default=ARTEFACTOS)
    args = ap.parse_args()
    from rdkit import Chem

    filas = [json.loads(linea) for linea in (args.artefactos / "per_complex.jsonl").open(encoding="utf-8")]
    sel = {m["id"]: m for m in json.loads((AQUI / "freesolv_h3" / "seleccion.json").read_text(encoding="utf-8"))["moleculas"]}

    print("1. |GB-PB|/|PB| por brazo (mediana)")
    for g in ("Br", "I", "Br_mixto"):
        s = [r for r in filas if r["grupo"] == g]
        partes = []
        for brazo in "AB":
            rel = np.median([abs(r[f"gb_{brazo}_kcal_mol"] - r[f"pb_{brazo}_kcal_mol"]) / abs(r[f"pb_{brazo}_kcal_mol"])
                             for r in s])
            partes.append(f"{brazo} {rel:.3f}")
        print(f"   {g:9s} n {len(s):2d}  " + "  ".join(partes))

    gamma, b = _ajuste_no_polar(filas, "pb_A_kcal_mol")
    control = [r for r in filas if r["grupo"] == "sin_halogeno"]
    mae_pb = np.mean([abs(r["pb_A_kcal_mol"] + gamma * r["sasa_A2"] + b - r["exp_kcal_mol"]) for r in control])
    mae_gb = np.mean([abs(r["calc_A_kcal_mol"] - r["exp_kcal_mol"]) for r in control])
    print(f"\n2. El mismo modelo con PB (gamma {gamma:.5f} kcal/mol/A2, b {b:.3f}, ajustados en {len(control)} sin halógeno;"
          f" MAE de esas: PB {mae_pb:.2f}, GB {mae_gb:.2f})")
    for grupo in ("Br", "I", "Br_I_todas"):
        s = [r for r in filas if r["grupo"] in BRI] if grupo == "Br_I_todas" else [r for r in filas if r["grupo"] == grupo]
        partes = []
        for brazo in "AB":
            e = np.array([r[f"pb_{brazo}_kcal_mol"] + gamma * r["sasa_A2"] + b - r["exp_kcal_mol"] for r in s])
            partes.append(f"{brazo} MAE {np.mean(np.abs(e)):.2f} sesgo {e.mean():+.2f}")
        print(f"   {grupo:10s} n {len(s):2d}  " + "   ".join(partes))
    bri = [r for r in filas if r["grupo"] in BRI]
    mejora = sum(abs(r["calc_B_kcal_mol"] - r["exp_kcal_mol"]) < abs(r["calc_A_kcal_mol"] - r["exp_kcal_mol"]) for r in bri)
    print(f"   con GB, el brazo B reduce el error en {mejora} de {len(bri)} moléculas con Br o I")

    print("\n3. GB-PB (brazo A) y error del modelo GB, por número de átomos del halógeno")
    for simbolo, grupo in (("F", "F"), ("Cl", "Cl")):
        patron = Chem.MolFromSmarts(f"[{simbolo}]")
        por: dict[int, list] = {}
        for r in (r for r in filas if r["grupo"] == grupo):
            n = len(Chem.MolFromSmiles(sel[r["id"]]["smiles"]).GetSubstructMatches(patron))
            por.setdefault(n if n < 4 else 4, []).append((r["gb_A_kcal_mol"] - r["pb_A_kcal_mol"],
                                                        r["calc_A_kcal_mol"] - r["exp_kcal_mol"]))
        for n in sorted(por):
            a = np.array(por[n])
            print(f"   {grupo:2s} {n}{'+' if n == 4 else ' '}: n {len(a):3d}  GB-PB {a[:, 0].mean():+6.2f}  error del modelo GB {a[:, 1].mean():+6.2f}")
    print("   (el grupo F incluye moléculas con F y ningún otro halógeno; con Br o Cl además van en Br_mixto / otro_halogeno)")
    print("\n   Br_mixto y otro_halogeno, una por una:")
    for r in filas:
        if r["grupo"] in ("Br_mixto", "otro_halogeno"):
            print(f"   {r['id']:16s} {sel[r['id']]['smiles']:32s} exp {r['exp_kcal_mol']:6.2f}  GB {r['gb_A_kcal_mol']:7.2f}"
                  f"  PB {r['pb_A_kcal_mol']:7.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
