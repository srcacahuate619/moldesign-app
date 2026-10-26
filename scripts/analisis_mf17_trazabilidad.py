#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf17_trazabilidad.py — MF-17 contra sus fuentes selladas (SCI-B-101, SCI-B-102).

`analisis_mf17_sintesis.py` (sellado) lee el r50 de MF-14 de `scratch/mf14_resultados/`, que no
existe ni está hash-vinculado, y busca cada pid de MF-09 en MF-13, MF-14 y MF-15-EXT con
`.get(pid, {})`, sin exigir que las cohortes coincidan. Aquí, sin reescribir nada:

1. se compara, complejo a complejo, el r50 que MF-17 guardó con el de `MF-14/per_complex.jsonl`
   sellado: si coinciden todos, la entrada de scratch era la misma que la sellada;
2. se comprueba que los pids de MF-09 (la tabla base) están en las otras tres fuentes;
3. se informa el N de cada mecanismo dentro de cada grupo (lo que la síntesis no publicaba).

Uso:
    python scripts/analisis_mf17_trazabilidad.py
"""
from __future__ import annotations

import json
from pathlib import Path

ART = Path(__file__).resolve().parent / "artifacts_science"


def _por_pid(exp: str) -> dict:
    ruta = ART / exp / "per_complex.jsonl"
    return {r["pid"]: r for r in (json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip())}


def comparar_r50(mf17: dict, mf14: dict) -> dict:
    iguales, distintos, faltan = 0, [], []
    for pid, f in mf17.items():
        if pid not in mf14:
            faltan.append(pid)
        elif f.get("r50") == mf14[pid].get("r50"):
            iguales += 1
        else:
            distintos.append((pid, f.get("r50"), mf14[pid].get("r50")))
    return {"iguales": iguales, "distintos": distintos, "faltan_en_mf14": faltan}


def analizar() -> dict:
    mf17 = _por_pid("MF-17")
    fuentes = {e: set(_por_pid(e)) for e in ("MF-09", "MF-13", "MF-14", "MF-15-EXT")}
    base_cubierta = {e: len(fuentes["MF-09"] - v) for e, v in fuentes.items() if e != "MF-09"}
    n_por_mecanismo = {}
    for etiq, cond in (("RESUELTO", True), ("FALLA", False)):
        g = [f for f in mf17.values() if f.get("oraculo") is not None and f["cubierto"] is cond]
        n_por_mecanismo[etiq] = {"n": len(g), **{k: sum(1 for f in g if f.get(k) is not None)
                                                 for k in ("rho_embudo", "r50", "ventaja_cristal", "cristal_gana")}}
    return {"r50_contra_mf14_sellado": comparar_r50(mf17, _por_pid("MF-14")),
            "n_por_fuente": {e: len(v) for e, v in fuentes.items()},
            "pids_de_mf09_ausentes_por_fuente": base_cubierta,
            "n_por_mecanismo": n_por_mecanismo}


if __name__ == "__main__":
    print(json.dumps(analizar(), ensure_ascii=False, indent=1))
