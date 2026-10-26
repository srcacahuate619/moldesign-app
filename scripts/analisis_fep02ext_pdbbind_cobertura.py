#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep02ext_pdbbind_cobertura.py — un receptor ausente no es un receptor sin huecos (SCI-B-042).

`analisis_fep02ext_huecos_sitio.py` (sellado) lee del padre `huecos_numeracion` con `get(..., 0)`
y `tiene_huecos` con `bool(...)`. Las 1438 filas que FEP-02-PDBBIND marcó `SIN_PDB` no tienen ni
uno ni otro, así que entran en FEP-02-EXT-PDBBIND como `SIN_HUECOS` y la extensión informa
`n_error = 0`. Aquí se reparte de nuevo con el estado del padre.

Uso:
    python scripts/analisis_fep02ext_pdbbind_cobertura.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ART = Path(__file__).resolve().parent / "artifacts_science"


def _jsonl(ruta: Path):
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def reclasificar(ext, padre_por_pid) -> Counter:
    c = Counter()
    for r in ext:
        error_padre = padre_por_pid.get(r["pid"], {}).get("error")
        c["SIN_FUENTE_" + error_padre if error_padre else r.get("clasificacion", "ERROR")] += 1
    return c


def analizar() -> dict:
    padre = {r["pid"]: r for r in _jsonl(ART / "FEP-02-PDBBIND" / "per_complex.jsonl")}
    ext = _jsonl(ART / "FEP-02-EXT-PDBBIND" / "per_complex.jsonl")
    sellado = Counter(r.get("clasificacion", "ERROR") for r in ext)
    nuevo = reclasificar(ext, padre)
    evaluables = sum(v for k, v in nuevo.items() if not k.startswith("SIN_FUENTE"))
    return {"n": len(ext), "sellado": dict(sellado), "con_estado_del_padre": dict(nuevo),
            "evaluables": evaluables,
            "fraccion_sin_huecos_sellada": round(sellado["SIN_HUECOS"] / len(ext), 4),
            "fraccion_sin_huecos_evaluables": round(nuevo["SIN_HUECOS"] / evaluables, 4)}


if __name__ == "__main__":
    print(json.dumps(analizar(), ensure_ascii=False, indent=1))
