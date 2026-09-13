#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rcf0v2ext_alcance_rigido.py — RC-F0-V2-EXT: ¿cuánto del programa es rígido?

`MF-33` midió que sobre los 33 complejos difíciles el protocolo congelado —docking
**rígido** del ensemble— alcanza **1 de 33**, mientras los **mismos confórmeros** dockeados
flexibles alcanzan **26 de 33**.

Eso plantea inmediatamente una pregunta de alcance que nadie ha respondido: **¿qué
fracción del material sobre el que descansa el programa proviene de ese protocolo?**

Este experimento la responde sin cómputo nuevo. Lee la composición por fuente del conjunto
de poses reconstruido y localiza qué artefactos sellados lo consumen.

Lo que se mide
--------------
  1. **Composición por fuente** del conjunto v2: cuántas poses vienen de `molflex`
     —el generador rígido— y cuántas de fuentes flexibles.
  2. **Consumidores**: qué artefactos sellados hashean o referencian los ficheros de poses,
     es decir qué conclusiones descansan sobre ese material.

Lo que NO se afirma
-------------------
Que las conclusiones de esos artefactos sean incorrectas. `MF-33` midió el hueco de
**cobertura** entre rígido y flexible; los experimentos de selección midieron **precisión
condicional sobre lo cubierto**, que es otra cantidad. Un techo de cobertura más alto
cambia el denominador, no invalida automáticamente una comparación pareada hecha dentro de
él.

Lo que sí se establece es el **alcance**: cuánto habría que rehacer si se decidiera medir
sobre material flexible.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ART = PROJECT_ROOT / "scripts" / "artifacts_science"

# fuentes que producen poses con libertad torsional durante la busqueda
FLEXIBLES = {"flexible_redock", "ruta_a"}
RIGIDAS = {"molflex"}


def main() -> int:
    ap = argparse.ArgumentParser(description="RC-F0-V2-EXT: alcance del protocolo rigido")
    ap.add_argument("--salida", default=str(ART / "RC-F0-V2-EXT"))
    args = ap.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    v2 = json.loads((ART / "RC-F0-V2" / "metrics.json").read_text(encoding="utf-8"))

    def hallar(o, clave):
        if isinstance(o, dict):
            if clave in o:
                return o[clave]
            for v in o.values():
                r = hallar(v, clave)
                if r is not None:
                    return r
        return None

    fuente = hallar(v2, "por_fuente") or {}
    total = sum(fuente.values())
    rig = sum(v for k, v in fuente.items() if k in RIGIDAS)
    flex = sum(v for k, v in fuente.items() if k in FLEXIBLES)
    otras = total - rig - flex

    # ── consumidores: artefactos sellados que hashean los ficheros de poses ──
    marcas = ("poses_train.jsonl", "poses_val.jsonl", "poses_test.jsonl",
              "pose_selector_dataset", "union_labels", "union_candidates")
    consumidores: List[Dict[str, Any]] = []
    for d in sorted(ART.iterdir()):
        m = d / "manifest.json"
        if not d.is_dir() or not m.exists():
            continue
        man = json.loads(m.read_text(encoding="utf-8"))
        if not man.get("sealed"):
            continue
        rutas: List[str] = []
        for k in ("dataset_hashes", "model_hashes", "binary_hashes", "assets_hashes"):
            v = man.get(k)
            if isinstance(v, dict):
                rutas.extend(v.keys())
        tocados = sorted({r for r in rutas if any(s in r for s in marcas)})
        if tocados:
            consumidores.append({"id": man["experiment_id"], "decision": man.get("decision"),
                                 "ficheros": tocados[:6]})

    metrics = {
        "experiment_id": "RC-F0-V2-EXT",
        "tipo": "medicion de alcance, sin computo nuevo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 3),
        "composicion_del_conjunto_v2": {
            "total": total, "por_fuente": fuente,
            "poses_de_protocolo_RIGIDO": rig,
            "poses_de_protocolo_FLEXIBLE": flex,
            "otras": otras,
            "fraccion_rigida": round(rig / total, 4) if total else None},
        "referencia_MF_33": {
            "cobertura_rigido_estrato_dificil": "1/33",
            "cobertura_flexible_mismos_conformeros": "26/33",
            "nota": "medido sobre los 33 de COLOCACION, no sobre los 203"},
        "consumidores_sellados": {
            "n": len(consumidores), "detalle": consumidores},
        "limitacion_declarada": (
            "NO se afirma que las conclusiones de los consumidores sean incorrectas. MF-33 "
            "midio el hueco de COBERTURA entre rigido y flexible; los experimentos de "
            "seleccion midieron PRECISION CONDICIONAL sobre lo cubierto, que es otra "
            "cantidad. Un techo de cobertura mas alto cambia el denominador, no invalida "
            "automaticamente una comparacion pareada hecha dentro de el. Lo que se "
            "establece es el ALCANCE de lo que habria que rehacer si se decidiera medir "
            "sobre material flexible. Ademas, el 1/33 de MF-33 es del estrato dificil: "
            "extrapolarlo a los 203 seria injustificado, porque en CONTROL el rigido "
            "alcanza 15/15."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")
    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for c in consumidores:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    c = metrics["composicion_del_conjunto_v2"]
    print(f"[RC-F0-V2-EXT] {metrics['duration_seconds']}s, sin computo nuevo")
    print(f"  conjunto v2: {c['total']} poses")
    for k, v in sorted(c["por_fuente"].items(), key=lambda x: -x[1]):
        tipo = "RIGIDO" if k in RIGIDAS else "flexible" if k in FLEXIBLES else "?"
        print(f"    {k:18s} {v:6d}  ({tipo})")
    print(f"  FRACCION RIGIDA: {c['fraccion_rigida']}")
    print(f"  artefactos sellados que consumen ese material: {len(consumidores)}")
    for x in consumidores:
        print(f"    {x['id']:16s} {x['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
