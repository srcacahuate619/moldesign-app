"""¿Bajan la abstención y la energía las moléculas grandes con 16 candidatos por semilla en vez de 8?

Mismas 37 moléculas que `validar_grandes.py` (se leen de `grandes.jsonl`), mismas
semillas y mismo umbral; sólo cambia `conformadores`. Criterio fijado antes de
medir: se pasa a 16 si la abstención baja al menos 5 moléculas de 37 (de 16 a 11
o menos) y el tiempo mediano no pasa de 8 s. Si no, se queda en 8.

    python docs/auditorias/elevacion-abstencion-2026-10-24/candidatos_grandes.py

Escribe `candidatos_grandes.jsonl` junto a este archivo.
"""
from __future__ import annotations

import json
import logging
import pathlib
import statistics
import sys
import time

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[2] / "backend"))
logging.disable(logging.CRITICAL)

from rdkit import RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from chem.elevacion import UMBRAL_ENLACES, modelo_desde_conformador  # noqa: E402


def main() -> None:
    previas = [json.loads(l) for l in open(AQUI / "grandes.jsonl", encoding="utf-8")]
    salida = AQUI / "candidatos_grandes.jsonl"
    with open(salida, "w", encoding="utf-8") as f:
        for d in previas:
            t0 = time.perf_counter()
            modelo = modelo_desde_conformador(d["smiles"], conformadores=16)
            fila = {"smiles": d["smiles"], "pesados": d["pesados"],
                    "razon_8": d["razon_enlaces"], "razon_16": modelo["razon_enlaces"],
                    "segundos_8": d["segundos"], "segundos_16": round(time.perf_counter() - t0, 2),
                    "delta_e_8": d["delta_e_kcal_mol"], "delta_e_16": modelo["conformador"]["delta_e_kcal_mol"]}
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            print(fila["pesados"], fila["razon_8"], "->", fila["razon_16"], fila["segundos_16"], flush=True)
    filas = [json.loads(l) for l in open(salida, encoding="utf-8")]
    for k in (8, 16):
        r = [x[f"razon_{k}"] for x in filas]
        t = [x[f"segundos_{k}"] for x in filas]
        e = [x[f"delta_e_{k}"] for x in filas if x[f"delta_e_{k}"] is not None]
        print(f"{k:>2} candidatos: > {UMBRAL_ENLACES}: {sum(v > UMBRAL_ENLACES for v in r)}/{len(r)}, "
              f"razón mediana {statistics.median(r):.2f}, {statistics.median(t):.1f} s (máx. {max(t):.1f}), "
              f"ΔE mediana {statistics.median(e):.1f}")


if __name__ == "__main__":
    main()
