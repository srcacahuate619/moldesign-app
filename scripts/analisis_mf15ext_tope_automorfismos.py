#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf15ext_tope_automorfismos.py — ¿algún ligando llega al tope de 5000 automorfismos? (SCI-B-094)

`analisis_mf15_ext.py` (sellado) corrige el RMSD por simetría con
`GetSubstructMatches(crystal, crystal, uniquify=False, useChirality=True, maxMatches=5000)`. Si un
ligando tiene más de 5000 automorfismos, el mínimo es sólo sobre los primeros 5000 y la
corrección podría quedarse corta. Aquí se cuenta, para cada complejo de la cohorte de MF-02F,
cuántos devuelve con un tope de 5001: si ninguno llega a 5001, el tope no recortó nada.

Necesita los SDF del cristal de PDBBind (no viajan en el repo). Uso:
    python scripts/analisis_mf15ext_tope_automorfismos.py --datos D:/moldesign-build/data
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ART = Path(__file__).resolve().parent / "artifacts_science"
MAX_AUTOS = 5000


def n_automorfismos(mol, tope: int = MAX_AUTOS + 1) -> int:
    return len(mol.GetSubstructMatches(mol, uniquify=False, useChirality=True, maxMatches=tope))


def pids_de_la_cohorte() -> list:
    c = json.loads((ART / "MF-02F" / "cohorte.json").read_text(encoding="utf-8"))
    if isinstance(c, dict):
        c = c.get("pids") or c.get("cohorte") or [p for v in c.values() if isinstance(v, list) for p in v]
    return sorted({(x["pid"] if isinstance(x, dict) else x) for x in c})


def analizar(datos: Path) -> dict:
    import molflex as mf
    filas, sin_material = [], []
    for pid in pids_de_la_cohorte():
        mol = mf.leer_ligando(datos / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if mol is None:
            sin_material.append(pid)
            continue
        filas.append({"pid": pid, "n_automorfismos": n_automorfismos(mol)})
    filas.sort(key=lambda f: -f["n_automorfismos"])
    return {"n": len(filas), "sin_material": sin_material,
            "en_el_tope": [f["pid"] for f in filas if f["n_automorfismos"] > MAX_AUTOS],
            "maximo": filas[0] if filas else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default=str(Path(__file__).resolve().parents[1] / "data"))
    print(json.dumps(analizar(Path(ap.parse_args().datos)), ensure_ascii=False, indent=1))
