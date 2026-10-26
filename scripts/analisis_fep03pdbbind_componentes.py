#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep03pdbbind_componentes.py — ligandos conectados en una red, no extremos de aristas (SCI-B-008).

`analisis_fep_pdbbind.py` (sellado en FEP-03-PDBBIND) cuenta como «ligandos conectados» de una
diana todos los extremos de sus parejas aptas: dos parejas sueltas A–B y C–D dan 4, aunque no
haya ningún camino de A a D. Una red de FEP relativo necesita un camino entre los ligandos que
compara, así que aquí se cuenta el **mayor componente conexo** de las parejas aptas de cada
diana, con `_componentes` de `analisis_fep_cohorte.py` (el cálculo que ya usaba FEP-03).

Lee `pares/shard_*.jsonl` y `grupos.json` (grupos por diana) del sello.
Uso:
    python scripts/analisis_fep03pdbbind_componentes.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analisis_fep_cohorte import _componentes  # noqa: E402

DIR = Path(__file__).resolve().parent / "artifacts_science" / "FEP-03-PDBBIND"


def por_diana(aptas, grupo_de):
    aristas = defaultdict(list)
    for a, b in aptas:
        aristas[grupo_de[a]].append((a, b))
    filas = []
    for g, ars in aristas.items():
        extremos = {p for e in ars for p in e}
        comps = sorted(_componentes(ars), key=len, reverse=True)
        filas.append({"grupo": g, "extremos": len(extremos), "mayor_componente": len(comps[0]),
                      "n_componentes": len(comps)})
    return filas


def analizar() -> dict:
    grupos = json.loads((DIR / "grupos.json").read_text(encoding="utf-8"))["grupos"]
    multi = [g for g in grupos if len(g) >= 2]
    grupo_de = {p: k for k, g in enumerate(multi) for p in g}
    aptas = []
    for shard in sorted((DIR / "pares").glob("shard_*.jsonl")):
        for linea in shard.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                r = json.loads(linea)
                if r["apta_fep"]:
                    aptas.append((r["pid_a"], r["pid_b"]))
    filas = por_diana(aptas, grupo_de)
    cuenta = lambda campo, u: sum(1 for f in filas if f[campo] >= u)  # noqa: E731
    return {"parejas_aptas": len(aptas), "dianas": len(filas),
            "extremos_ge10": cuenta("extremos", 10), "extremos_ge20": cuenta("extremos", 20),
            "componente_ge10": cuenta("mayor_componente", 10), "componente_ge20": cuenta("mayor_componente", 20),
            "dianas_con_mas_de_un_componente": sum(1 for f in filas if f["n_componentes"] > 1)}


if __name__ == "__main__":
    print(json.dumps(analizar(), ensure_ascii=False, indent=1))
