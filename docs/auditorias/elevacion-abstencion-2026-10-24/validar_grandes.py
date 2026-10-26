"""Umbral de abstención en moléculas grandes (> 34 átomos pesados).

El umbral de un enlace se fijó con 167 moléculas de las que sólo tres pasaban de
34 átomos pesados. Aquí se mide con todas las de 35 a 150 que traen los
artefactos versionados de `scripts/artifacts_science` (columnas `*smiles*` de sus
CSV y JSONL; solo lectura; el fragmento mayor de cada SMILES), llamando a
`modelo_desde_conformador` tal como queda en el producto, y además con cada
semilla por separado para ver cuánto cambia la decisión.

    python docs/auditorias/elevacion-abstencion-2026-10-24/validar_grandes.py

Escribe `grandes.jsonl` junto a este archivo.
"""
from __future__ import annotations

import csv
import json
import logging
import pathlib
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "backend"))
logging.disable(logging.CRITICAL)

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from chem.elevacion import SEMILLAS_CRITERIO, UMBRAL_ENLACES, modelo_desde_conformador  # noqa: E402

CIENCIA = RAIZ / "scripts" / "artifacts_science"
SALIDA = pathlib.Path(__file__).resolve().parent / "grandes.jsonl"


def candidatas() -> list[dict]:
    csv.field_size_limit(10**8)
    vistas: dict[str, dict] = {}
    for ruta in sorted(list(CIENCIA.rglob("*.csv")) + list(CIENCIA.rglob("*.jsonl"))):
        if ruta.stat().st_size > 50_000_000:
            continue
        try:
            with open(ruta, encoding="utf-8", errors="ignore") as f:
                filas = list(csv.DictReader(f)) if ruta.suffix == ".csv" else [
                    json.loads(l) for l in f if l.strip().startswith("{")]
        except Exception:  # noqa: BLE001 — un archivo que no es una tabla no aporta
            continue
        for fila in filas:
            if not isinstance(fila, dict):
                continue
            for clave, valor in fila.items():
                if not isinstance(valor, str) or "smiles" not in str(clave).lower() or len(valor) < 30:
                    continue
                mol = Chem.MolFromSmiles(valor)
                if mol is None:
                    continue
                mol = max(Chem.GetMolFrags(mol, asMols=True), key=lambda m: m.GetNumHeavyAtoms())
                if 35 <= mol.GetNumHeavyAtoms() <= 150:
                    can = Chem.MolToSmiles(mol)
                    origen = "/".join(ruta.relative_to(RAIZ).as_posix().split("/")[2:3])
                    vistas.setdefault(can, {"smiles": can, "origen": origen, "pesados": mol.GetNumHeavyAtoms()})
    return sorted(vistas.values(), key=lambda d: (d["pesados"], d["smiles"]))


def main() -> None:
    filas = candidatas()
    with open(SALIDA, "w", encoding="utf-8") as f:
        for d in filas:
            t0 = time.perf_counter()
            modelo = modelo_desde_conformador(d["smiles"])
            segundos = round(time.perf_counter() - t0, 2)
            por_semilla = {str(s): modelo_desde_conformador(d["smiles"], semillas=(s,))["razon_enlaces"]
                           for s in SEMILLAS_CRITERIO}
            fila = {**d, "razon_enlaces": modelo["razon_enlaces"], "fiel": modelo["fiel"],
                    "razon_por_semilla": por_semilla, "segundos": segundos,
                    "candidatos": modelo["conformador"]["candidatos_por_semilla"],
                    "delta_e_kcal_mol": modelo["conformador"]["delta_e_kcal_mol"]}
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(d["pesados"], fila["razon_enlaces"], por_semilla, segundos, flush=True)
    razones = [json.loads(l)["razon_enlaces"] for l in open(SALIDA, encoding="utf-8")]
    print(f"n={len(razones)}  > {UMBRAL_ENLACES}: {sum(r > UMBRAL_ENLACES for r in razones)}")


if __name__ == "__main__":
    main()
