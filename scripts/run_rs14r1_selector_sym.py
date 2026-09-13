#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs14r1_selector_sym.py — RS-14-R1: RS-14 con las etiquetas de simetría corregidas.

Prerrequisito formal: `scripts/artifacts_science/RS-14-R1-PRE/PREREGISTRO.md` sellado.

Qué cambia respecto a `RS-14`
-----------------------------
**Una sola cosa: la etiqueta.** El RMSD de cada pose pasa de `rmsd` (índice a índice,
sin corregir simetría) a `rmsd_sym` (mínimo sobre automorfismos, igualmente sin
alinear), tomado de `RC-F0-SYM/poses_rmsd_sym.jsonl`.

Todo lo demás queda **congelado y se reutiliza por import**, no por copia: las mismas
233 features, el mismo contrato de transformación de v0.6, los mismos
hiperparámetros, el mismo LOCO con semillas 42/43/44, el mismo nulo por permutación de
200 réplicas y los mismos gates. Si algo más cambiara, la comparación con `RS-14`
mezclaría dos causas.

Por qué es legal bajo la §19.1
------------------------------
La condición 2 de la regla de futilidad exime a un `NO_GO` que **se explique por un
defecto de implementación ya corregido**, y establece que un corrigendum reinicia el
contador **sólo si cambia la decisión**. Re-etiquetar es una corrección de defecto: no
es una arquitectura nueva, ni una pérdida nueva, ni una seed nueva.

Alcance declarado
-----------------
Sólo las poses de fuente `molflex` (32,215 de 34,302; 17,669 de las 18,812 de train)
tienen `rmsd_sym`. Las de `flexible_redock` y `ruta_a` **conservan su RMSD ingenuo**.
Como corregir simetría sólo puede bajar el RMSD, el residuo sesga hacia **menos**
positivas, nunca más: la corrección aplicada es una cota inferior de la real.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_rs14_selector_v2 as base  # noqa: E402

SYM = PROJECT_ROOT / "scripts" / "artifacts_science" / "RC-F0-SYM" / "poses_rmsd_sym.jsonl"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-14-R1"

_ESTADO = {"n_corregidas": 0, "n_sin_sym": 0, "n_total": 0}


def _mapa_sym() -> dict:
    m = {}
    for l in SYM.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if d["split"] == "train":
            m[(d["pid"], d["file_stem"], d["model_idx"])] = d["rmsd_sym"]
    return m


def cargar_sym() -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Idéntico a `base.cargar` salvo que la etiqueta es `rmsd_sym` cuando existe."""
    sym = _mapa_sym()
    rich = {}
    for l in (base.V2 / "features_rich_v2.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            rich[(d["pid"], d["source"], d["file_stem"], d["model_idx"])] = d["rich"]
    filas, rmsds, pids = [], [], []
    for l in (base.V2 / "poses_train.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        k = (r["pid"], r["source"], r["file_stem"], r["model_idx"])
        if k not in rich:
            continue
        fila_base = [r.get(c) if r.get(c) is not None else 0.0 for c in base.BASE_9]
        filas.append(fila_base + rich[k])
        ing = r["rmsd"]
        cor = sym.get((r["pid"], r["file_stem"], r["model_idx"]))
        _ESTADO["n_total"] += 1
        if cor is None:
            _ESTADO["n_sin_sym"] += 1
            cor = ing
        elif cor <= base.UMBRAL_A < ing:
            _ESTADO["n_corregidas"] += 1
        # invariante del contrato: corregir simetria NUNCA sube el RMSD
        assert cor <= ing + 1e-6, f"rmsd_sym > rmsd en {k}: {cor} > {ing}"
        rmsds.append(cor)
        pids.append(r["pid"])
    X = np.asarray(filas, dtype=np.float64)
    return X, np.asarray(rmsds), np.asarray(pids), sorted(set(pids))


def main() -> int:
    ap = argparse.ArgumentParser(description="RS-14-R1: RS-14 con etiquetas de simetria corregidas")
    ap.add_argument("--permutaciones", type=int, default=200)
    ap.add_argument("--semillas", type=int, nargs="*", default=list(base.SEMILLAS))
    ap.add_argument("--limite-complejos", type=int, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # el unico cambio: etiqueta y destino. Todo lo demas se ejecuta tal cual.
    base.cargar = cargar_sym
    base.OUT_DIR = OUT_DIR
    print(f"[RS-14-R1] etiquetas desde {SYM.name}", flush=True)

    argv = ["run_rs14r1", "--permutaciones", str(args.permutaciones),
            "--semillas", *[str(s) for s in args.semillas]]
    if args.limite_complejos:
        argv += ["--limite-complejos", str(args.limite_complejos)]
    old = sys.argv
    sys.argv = argv
    try:
        rc = base.main()
    finally:
        sys.argv = old
    if rc != 0:
        return rc

    # sello de procedencia: quien mira metrics.json debe saber que etiqueta se uso
    mp = OUT_DIR / "metrics.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m["experiment_id"] = "RS-14-R1"
    m["etiquetas"] = {
        "fuente": "RC-F0-SYM/poses_rmsd_sym.jsonl",
        "metrica": "minimo sobre automorfismos del RMSD sin alinear (doc. 49 §5.1)",
        "n_poses": _ESTADO["n_total"],
        "n_sin_rmsd_sym": _ESTADO["n_sin_sym"],
        "n_etiquetas_corregidas_neg_a_pos": _ESTADO["n_corregidas"],
        "nota": ("las poses sin rmsd_sym (flexible_redock, ruta_a) conservan el RMSD "
                 "ingenuo; el residuo sesga hacia MENOS positivas, nunca mas"),
    }
    m["comparacion_con_rs14"] = {
        "unico_cambio": "la etiqueta de RMSD",
        "congelado": ["features 233", "contrato v0.6", "hiperparametros", "LOCO",
                      "semillas 42/43/44", "nulo 200 permutaciones", "gates"],
    }
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n",
                  encoding="utf-8", newline="\n")
    print(f"[RS-14-R1] etiquetas corregidas neg->pos: {_ESTADO['n_corregidas']} "
          f"| poses sin rmsd_sym: {_ESTADO['n_sin_sym']} de {_ESTADO['n_total']}")
    print(f"[RS-14-R1] decision {m.get('decision')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
