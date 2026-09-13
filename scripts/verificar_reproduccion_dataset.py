#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verificar_reproduccion_dataset.py — Gate de reproducción del dataset de poses.

Antes de añadir una sola pose nueva al conjunto, hay que demostrar que se
reproduce **exactamente** el conjunto sellado a partir de sus propios registros
intermedios (`data/pose_selector_dataset/records/`, que conservan las coordenadas
por pose).

Reproduce las tres etapas finales del constructor original sin re-ejecutar nada
de docking:
  1. densidad de clúster intra-complejo (pares a < 2.0 A, RMSD pocket-frame),
  2. división por grupo de scaffold Murcko con semilla 42,
  3. emisión de los JSONL por split en el orden canónico.

y compara el resultado contra `poses_{train,val,test}.jsonl` línea a línea.

Si esto no da idéntico, cualquier reconstrucción posterior es indefendible: no
sabríamos si una diferencia viene de las poses nuevas o de haber entendido mal
el contrato.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_pose_selector_dataset as B  # noqa: E402


def sha256_texto(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def reconstruir() -> Dict[str, List[str]]:
    """Devuelve {split: [lineas_json]} reproduciendo el contrato original."""
    todos = B.cargar_todos_los_registros()
    print(f"[repro] registros cargados: {len(todos)} complejos, "
          f"{sum(len(v) for v in todos.values())} poses", flush=True)

    # 1. densidad de clúster (idéntica al original: inicializar ANTES del doble loop)
    for pid, lista in todos.items():
        for e in lista:
            e["reg"]["cluster_density"] = 0
        for i, ea in enumerate(lista):
            for j in range(i + 1, len(lista)):
                eb = lista[j]
                if B.rmsd_entre_poses(ea["densa"], eb["densa"]) < B.UMBRAL_CLUSTER:
                    ea["reg"]["cluster_density"] += 1
                    eb["reg"]["cluster_density"] += 1

    # 2. división por scaffold
    pids = sorted(todos.keys())
    cache: Dict[str, str] = {}
    scaffolds = {p: B.scaffold_del_pid(p, cache) for p in pids}
    division = B.dividir_complejos(pids, scaffolds)
    print(f"[repro] split reproducido: train {len(division['train'])} | "
          f"val {len(division['val'])} | test {len(division['test'])}", flush=True)

    # 3. emisión en el orden canónico
    splits_de_pid = {pid: s for s, ps in division.items() for pid in ps}
    salida: Dict[str, List[str]] = {"train": [], "val": [], "test": []}
    for pid in sorted(todos.keys()):
        split = splits_de_pid.get(pid)
        if split is None:
            continue
        for entrada in todos[pid]:
            r = dict(entrada["reg"])
            r.pop("_coords", None)
            salida[split].append(json.dumps({k: r[k] for k in B.ORDEN_CLAVES},
                                            ensure_ascii=False))
    return salida


def main() -> int:
    reconstruido = reconstruir()
    ok_global = True
    resumen: Dict[str, Any] = {}
    for split, path in B.SPLIT_FILES.items():
        original = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        nuevo = reconstruido[split]
        iguales = original == nuevo
        # diagnóstico por si difieren
        detalle: Dict[str, Any] = {"n_original": len(original), "n_reproducido": len(nuevo),
                                   "identico": iguales}
        if not iguales:
            ok_global = False
            set_o, set_n = set(original), set(nuevo)
            detalle["solo_en_original"] = len(set_o - set_n)
            detalle["solo_en_reproducido"] = len(set_n - set_o)
            detalle["mismo_conjunto_distinto_orden"] = set_o == set_n
            difs = [(i, o, n) for i, (o, n) in enumerate(zip(original, nuevo)) if o != n]
            detalle["primera_diferencia"] = (
                {"linea": difs[0][0], "original": difs[0][1][:200],
                 "reproducido": difs[0][2][:200]} if difs else None)
        detalle["sha256_original"] = sha256_texto("\n".join(original))
        detalle["sha256_reproducido"] = sha256_texto("\n".join(nuevo))
        resumen[split] = detalle
        estado = "IDENTICO" if iguales else "DIFIERE"
        print(f"  {split:<6} {len(original):>5} lineas | {estado}")
        if not iguales:
            print(f"         solo_original={detalle['solo_en_original']} "
                  f"solo_reproducido={detalle['solo_en_reproducido']} "
                  f"mismo_conjunto={detalle['mismo_conjunto_distinto_orden']}")
            if detalle["primera_diferencia"]:
                print(f"         linea {detalle['primera_diferencia']['linea']}:")
                print(f"           orig: {detalle['primera_diferencia']['original']}")
                print(f"           repr: {detalle['primera_diferencia']['reproducido']}")

    print(f"\n[repro] GATE DE REPRODUCCION: {'PASS' if ok_global else 'FAIL'}")
    salida = PROJECT_ROOT / "scripts" / "artifacts_science" / "_repro_dataset.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({"pass": ok_global, "splits": resumen},
                                 ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8", newline="\n")
    return 0 if ok_global else 1


if __name__ == "__main__":
    sys.exit(main())
