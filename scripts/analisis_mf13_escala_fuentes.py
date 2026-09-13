#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf13_escala_fuentes.py — MF-13-ESCALA: ¿arrastra MF-13 el mismo desajuste?

Sin computo nuevo. Lee datos ya sellados.

Por que existe
--------------
`MF-29-EMP-COR` midio que comparar un PDBQT rigido (`TORSDOF 0`) contra scores de un
PDBQT flexible no es valido: Vina divide la afinidad por `(1 + w_rot * N_rot)` y el rigido
no paga esa penalizacion, de modo que puntua mejor para la misma pose. El salto de escala
resulto de 1.055 kcal/mol medianos.

`MF-13` puntuo el cristal como PDBQT **rigido** y lo comparo contra `score_top1_dock`, que
sale del conjunto v2. Al cerrar `MF-29-EMP-COR` se registro la **sospecha** de que `MF-13`
arrastraba el mismo desajuste, y que su diagnostico -«~70% busqueda, ~30% puntuacion»,
citado en todo el programa- podia ser un artefacto. Este analisis la comprueba en vez de
dejarla escrita.

Que se mide
-----------
1. De que **fuente** sale el `top-1` de cada complejo, que es el numero que `MF-13` uso.
   `RC-F0-V2-EXT` ya clasifico las fuentes del conjunto v2 por protocolo: `molflex` es
   **rigido** -docka `conf{cid}.rigid.pdbqt`, ver `molflex.docking_conformero`- mientras que
   `flexible_redock` y `ruta_a` son **flexibles**.
2. El gate G2 de `MF-13` -fraccion de COLOCACION donde el cristal relajado gana al mejor
   dock- recalculado **restringiendo el mejor dock a poses de fuente rigida**, que es la
   comparacion a escala homogenea con su cristal rigido.

Si el gate no se mueve, `MF-13` no tiene el desajuste y la sospecha se retira.

Limites
-------
1. **No relee `MF-13` ni lo toca.** `MF-13` esta sellado. Esto comprueba si su comparacion
   era homogenea, no cambia su lectura -y si el gate no se mueve, no hay nada que cambiar-.
2. No dice nada sobre la **magnitud** de la ventaja del cristal, solo sobre el conteo del
   gate, que es lo que decidia.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Clasificacion de RC-F0-V2-EXT, y confirmada en molflex.docking_conformero:
# `rig = w / f"conf{cid}.rigid.pdbqt"` es lo que se pasa a --ligand para la fuente molflex.
FUENTES_RIGIDAS = {"molflex"}


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-13-ESCALA: homogeneidad de escala del gate de MF-13")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-13-ESCALA"
    out_dir.mkdir(parents=True, exist_ok=True)

    por: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    ruta = ws / "data" / "pose_selector_dataset" / "v2" / "poses_train.jsonl"
    for l in ruta.read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            por[d["pid"]].append(d)

    m13 = {r["pid"]: r for r in
           (json.loads(l) for l in
            (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip())}

    fuente_del_top1 = Counter()
    filas: List[Dict[str, Any]] = []
    for pid, r in m13.items():
        v = por.get(pid, [])
        if not v:
            continue
        top = min(v, key=lambda x: x["vina_score"])
        fuente_del_top1[top["source"]] += 1
        rig = [d for d in v if d["source"] in FUENTES_RIGIDAS]
        top_rig = min((d["vina_score"] for d in rig), default=None)
        cl = r.get("score_cristal_local")
        filas.append({
            "pid": pid, "estrato": r["estrato"],
            "score_cristal_local_rigido": cl,
            "top1_todas_fuentes": round(top["vina_score"], 3),
            "fuente_del_top1": top["source"],
            "top1_solo_rigidas": round(top_rig, 3) if top_rig is not None else None,
            "cristal_gana_todas": bool(cl is not None and cl < top["vina_score"]),
            "cristal_gana_solo_rigidas": (bool(cl is not None and top_rig is not None
                                               and cl < top_rig)
                                          if top_rig is not None else None),
        })

    def _gate(campo: str, estrato: str = "COLOCACION"):
        g = [f for f in filas if f["estrato"] == estrato and f[campo] is not None]
        n_gana = sum(1 for f in g if f[campo])
        return n_gana, len(g), (round(n_gana / len(g), 4) if g else None)

    ga, na, fa = _gate("cristal_gana_todas")
    gr, nr, fr = _gate("cristal_gana_solo_rigidas")

    def _lectura(f):
        if f is None:
            return None
        return "BUSQUEDA" if f >= 0.70 else ("PUNTUACION" if f <= 0.30 else "MIXTO")

    mezclados = [f["pid"] for f in filas
                 if f["estrato"] == "COLOCACION" and f["fuente_del_top1"] not in FUENTES_RIGIDAS]

    out = {
        "analisis_id": "MF-13-ESCALA",
        "tipo": "comprobacion de homogeneidad de escala, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pregunta": "el gate de MF-13 comparaba su cristal RIGIDO contra poses de que protocolo",
        "fuentes_rigidas": sorted(FUENTES_RIGIDAS),
        "n_complejos": len(filas),
        "fuente_del_top1": dict(fuente_del_top1),
        "gate_G2_colocacion": {
            "definicion": "fraccion de COLOCACION donde el cristal relajado gana al mejor dock",
            "umbrales_de_MF13": ">=0.70 BUSQUEDA, <=0.30 PUNTUACION, intermedio MIXTO",
            "como_se_midio_todas_las_fuentes": {"n_gana": ga, "de": na, "fraccion": fa,
                                                "lectura": _lectura(fa)},
            "a_escala_homogenea_solo_rigidas": {"n_gana": gr, "de": nr, "fraccion": fr,
                                                "lectura": _lectura(fr)},
            "el_gate_se_mueve": bool(fa != fr),
        },
        "colocacion_con_top1_de_fuente_flexible": {"n": len(mezclados), "pids": sorted(mezclados)},
        "conclusion": None,
        "limites_declarados": [
            "no relee MF-13 ni lo toca; MF-13 esta sellado",
            "solo comprueba el conteo del gate, no la magnitud de la ventaja del cristal",
        ],
        "per_complex": filas,
    }
    out["conclusion"] = (
        "MF-13 NO arrastra el desajuste de escala: en la gran mayoria de complejos su top-1 "
        "viene de molflex, que docka el PDBQT rigido, la misma escala que su cristal rigido. "
        "Restringir el mejor dock a poses rigidas deja el gate identico."
        if fa == fr else
        "El gate de MF-13 SI se mueve al homogeneizar la escala: exige corrigendum propio."
    )
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    print(f"[MF-13-ESCALA] top-1 por fuente: {dict(fuente_del_top1)}")
    print(f"[MF-13-ESCALA] gate G2 todas={ga}/{na}={fa} ({_lectura(fa)})  "
          f"solo_rigidas={gr}/{nr}={fr} ({_lectura(fr)})  se_mueve={fa != fr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
