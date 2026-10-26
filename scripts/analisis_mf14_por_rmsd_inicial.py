#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf14_por_rmsd_inicial.py — la curva de retorno de MF-14 contra el RMSD de partida.

MF-14 perturba la pose del cristal con una traslación de norma nominal r **más** una rotación
aleatoria de hasta 30° alrededor del centroide (`run_mf14_radio_captura.py:_perturbar`), y
agrupa la fracción que vuelve a ≤ 2 Å por r nominal. Pero el RMSD de partida de cada réplica,
que el runner sí guarda (`rmsd_inicial`), no es r: con r = 0,5 Å llega a más de 1,5 Å. Leer
la fila de 0,5 Å como «partiendo prácticamente de la pose correcta» y deducir barreras dentro
de la cuenca a esa distancia no está demostrado (SCI-B-083).

Este script reagrupa las mismas réplicas selladas por su RMSD de partida real, sin acoplar
nada: por estrato, cuántas réplicas hay en cada banda, cuántas vuelven, y cómo se reparte el
RMSD de partida dentro de cada r nominal. No toca los artefactos sellados.

Uso:
    python scripts/analisis_mf14_por_rmsd_inicial.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MF14 = Path("scripts/artifacts_science/MF-14/per_complex.jsonl")
ESTRATOS = ("COLOCACION", "CONTROL")
#: Bandas de RMSD de partida, en Å: [desde, hasta).
BANDAS = ((0.0, 0.75), (0.75, 1.25), (1.25, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, float("inf")))


def _banda(rmsd: float) -> str:
    for lo, hi in BANDAS:
        if lo <= rmsd < hi:
            return f"{lo:g}-{hi:g}"
    raise ValueError(rmsd)


def analizar(raiz: Path) -> Dict[str, Any]:
    filas = [json.loads(l) for l in (raiz / MF14).read_text(encoding="utf-8").splitlines() if l.strip()]
    salida: Dict[str, Any] = {}
    for est in ESTRATOS:
        puntos: List[Dict[str, Any]] = [dict(p, pid=f["pid"]) for f in filas if f.get("estrato") == est
                                        for p in f.get("puntos", []) if "vuelve" in p]
        por_nominal = {}
        for r in sorted({p["r_nominal"] for p in puntos}):
            g = [p for p in puntos if p["r_nominal"] == r]
            ini = sorted(p["rmsd_inicial"] for p in g)
            por_nominal[f"{r:g}"] = {
                "replicas": len(g),
                "fraccion_vuelve": round(sum(p["vuelve"] for p in g) / len(g), 3),
                "rmsd_inicial_mediano": round(median(ini), 3),
                "rmsd_inicial_min": ini[0],
                "rmsd_inicial_max": ini[-1],
            }
        por_banda = {}
        for lo, hi in BANDAS:
            g = [p for p in puntos if lo <= p["rmsd_inicial"] < hi]
            # Las réplicas de un complejo no son independientes: se dice de cuántos complejos salen.
            por_banda[f"{lo:g}-{hi:g}"] = {
                "replicas": len(g),
                "vuelven": sum(p["vuelve"] for p in g),
                "fraccion_vuelve": round(sum(p["vuelve"] for p in g) / len(g), 3) if g else None,
                "complejos": len({p["pid"] for p in g}),
                "complejos_con_algun_fallo": len({p["pid"] for p in g if not p["vuelve"]}),
            }
        salida[est] = {"replicas": len(puntos), "por_r_nominal": por_nominal,
                       "por_rmsd_inicial": por_banda}
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-14 reagrupado por RMSD de partida")
    ap.add_argument("--raiz", type=Path, default=PROJECT_ROOT)
    args = ap.parse_args()
    print(json.dumps(analizar(args.raiz), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
