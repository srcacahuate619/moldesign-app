#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf15_cobertura_por_radio.py — qué radios de MF-15 se pueden leer, y con quién.

MF-15 y MF-15-EXT resumen la ρ de Spearman (RMSD frente a score) por radio alrededor del
cristal con la mediana de los complejos que tienen al menos 8 poses en ese radio; los demás
dan ρ nula y salen del resumen. La auditoría científica encontró que el texto lee esas
medianas como si cubrieran todos los radios y todos los complejos (SCI-B-088, SCI-B-092):
en el estrato difícil, los radios cortos no tienen complejos medibles, y los que contribuyen
cambian de un radio a otro, así que la secuencia de medianas no es una curva pareada.

Este script lo hace visible desde las salidas selladas, sin recalcular ninguna ρ: por estrato
y radio, cuántos complejos son medibles de cuántos, su mediana, y cuántos complejos son
medibles en todos los radios a la vez. No toca los artefactos sellados.

Uso:
    python scripts/analisis_mf15_cobertura_por_radio.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FUENTES = {
    # experimento: (fichero por complejo, campo con la ρ por radio)
    "MF-15": (Path("scripts/artifacts_science/MF-15/per_complex_train.jsonl"), "spearman_por_radio"),
    # La tabla por radios del paper de MF-15-EXT usa la ρ sin corregir la simetría
    # (0.279 a 4 Å, 0.140 a 6 Å). Los complejos medibles son los mismos con las dos.
    "MF-15-EXT": (Path("scripts/artifacts_science/MF-15-EXT/per_complex.jsonl"), "spearman_ingenuo"),
}
RADIOS = ("2.0", "3.0", "4.0", "6.0", "8.0", "12.0")
ESTRATOS = ("COLOCACION", "CONTROL")


def cobertura(filas: List[Dict[str, Any]], campo: str) -> Dict[str, Any]:
    salida: Dict[str, Any] = {}
    for est in ESTRATOS:
        g = [f for f in filas if f.get("estrato") == est]
        por_radio: Dict[str, Any] = {}
        medibles_por_radio: Dict[str, set] = {}
        for r in RADIOS:
            medibles = {f["pid"]: f[campo][r]["rho"] for f in g
                        if f.get(campo, {}).get(r, {}).get("rho") is not None}
            medibles_por_radio[r] = set(medibles)
            por_radio[r] = {
                "medibles": len(medibles),
                "de": len(g),
                "rho_mediana": round(median(medibles.values()), 4) if medibles else None,
            }
        con_medida = [r for r in RADIOS if medibles_por_radio[r]]
        comunes = set.intersection(*(medibles_por_radio[r] for r in con_medida)) if con_medida else set()
        salida[est] = {
            "complejos": len(g),
            "por_radio": por_radio,
            "radios_sin_complejos_medibles": [r for r in RADIOS if not medibles_por_radio[r]],
            "medibles_en_todos_los_radios_con_medida": len(comunes),
        }
    return salida


def analizar(raiz: Path) -> Dict[str, Any]:
    salida = {}
    for exp, (ruta, campo) in FUENTES.items():
        filas = [json.loads(l) for l in (raiz / ruta).read_text(encoding="utf-8").splitlines() if l.strip()]
        salida[exp] = cobertura(filas, campo)
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-15: cobertura de la ρ por radio")
    ap.add_argument("--raiz", type=Path, default=PROJECT_ROOT)
    args = ap.parse_args()
    print(json.dumps(analizar(args.raiz), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
