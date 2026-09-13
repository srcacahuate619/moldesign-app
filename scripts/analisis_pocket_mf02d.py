#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_pocket_mf02d.py — Métrica correcta sobre el material de MF-02D.

Por qué existe
--------------
MF-02B consumió `rmsd_best_to_crystal` de `molflex.ejecutar_complejo`, que se
calcula con `rmsd_pesados` = `AllChem.GetBestRMS`, y **alinea**. El dataset de
poses etiqueta con `rmsd_pose_pocket`: RMSD en el marco del pocket, **sin
alinear**. El propio repo lo dejó escrito como lección de auditoría el
2026-08-14: GetBestRMS «oculta desplazamientos — una pose movida ~4 A del pocket
puede reportar RMSD ~0», y para poses dockeadas hay que usar la otra.

Comparar el RMSD alineado de MolFlex contra el umbral de 2.0 A del dataset es
apples-to-oranges y sesga a favor: el alineado es siempre <= el de pocket.

Este script recalcula la métrica correcta sobre el material conservado por
MF-02D y produce (a) las métricas corregidas de MF-02D y (b) la base del
corrigendum MF-02B-R1.

Métrica primaria
----------------
**Oráculo de generación en marco de pocket**: mínimo `rmsd_pose_pocket` sobre
TODAS las poses dockeadas (`conf*.out.pdbqt`, todos los MODEL de todos los
conformeros). Es el número que corresponde porque el constructor del dataset
(`build_pose_selector_dataset.py`, fuente S2) consume exactamente ese conjunto,
no el top-K.

Secundaria, para el corrigendum: el mismo RMSD de pocket restringido a los
conformeros que MolFlex entregó como top-K, que es lo que MF-02B midió (pero
alineado).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

POSES_DIR = Path(os.environ.get("MF_POSES_DIR", str(PROJECT_ROOT / "data" / "molflex_train_v2")))
MF02D_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02D"
RESUMEN_DIR = Path(os.environ.get("MF_RESUMEN_DIR", str(MF02D_DIR / "_resumen")))
POSES_TRAIN = PROJECT_ROOT / "data" / "pose_selector_dataset" / "poses_train.jsonl"
UMBRAL_A = 2.0


def _analizar(pid: str) -> Dict[str, Any]:
    import molflex as mf

    w = POSES_DIR / pid / pid
    out: Dict[str, Any] = {"pid": pid}
    if not (w / "index_map.json").exists():
        out["error"] = "SIN_INDEX_MAP"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    raw = json.loads((w / "index_map.json").read_text(encoding="utf-8"))
    serial_a_mol = {int(s): int(m) for s, m in raw}

    top_k_cids: List[int] = []
    resumen = RESUMEN_DIR / f"{pid}.json"
    if resumen.exists():
        try:
            r = json.loads(resumen.read_text(encoding="utf-8"))
            top_k_cids = [p["conf_id"] for p in r.get("top_k_relaxed", [])
                          if p.get("conf_id") is not None]
            out["rmsd_alineado_molflex"] = r.get("rmsd_best_to_crystal")
        except Exception:
            pass

    mejor_gen: Optional[float] = None
    mejor_topk: Optional[float] = None
    n_poses = 0
    por_conf: Dict[int, float] = {}
    for f in sorted(w.glob("conf*.out.pdbqt")):
        try:
            cid = int(f.name[4:f.name.index(".")])
        except ValueError:
            continue
        for _score, atomos in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
            coords = mf.coords_pose_a_por_mol(atomos, serial_a_mol)
            if not coords:
                continue
            n_poses += 1
            rp = mf.rmsd_pose_pocket(crystal, coords)
            if rp is None:
                continue
            if mejor_gen is None or rp < mejor_gen:
                mejor_gen = rp
            if cid not in por_conf or rp < por_conf[cid]:
                por_conf[cid] = rp
            if cid in top_k_cids and (mejor_topk is None or rp < mejor_topk):
                mejor_topk = rp

    out.update({
        "n_poses_dockeadas": n_poses,
        "n_conformeros": len(por_conf),
        "oraculo_generacion_pocket": round(mejor_gen, 3) if mejor_gen is not None else None,
        "oraculo_topk_pocket": round(mejor_topk, 3) if mejor_topk is not None else None,
        "top_k_cids": top_k_cids,
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Metrica en marco de pocket sobre el material de MF-02D")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default=str(MF02D_DIR / "pocket_frame.jsonl"))
    args = ap.parse_args()

    pids = sorted(d.name for d in POSES_DIR.iterdir() if d.is_dir())
    print(f"[pocket] {len(pids)} complejos con material", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, pids, chunksize=1), 1):
            filas.append(r)
            if i % 10 == 0 or i == len(pids):
                print(f"  [{i}/{len(pids)}] ({round(time.time() - t0)}s)", flush=True)

    # Dataset: sus etiquetas ya son de marco de pocket
    por = defaultdict(list)
    for l in POSES_TRAIN.read_text(encoding="utf-8").splitlines():
        if l.strip():
            x = json.loads(l)
            por[x["pid"]].append(x["rmsd"])
    mejor_ds = {p: round(min(v), 3) for p, v in por.items()}

    ok = [f for f in filas if "error" not in f]
    for f in ok:
        base = mejor_ds.get(f["pid"])
        gen = f.get("oraculo_generacion_pocket")
        f["mejor_dataset"] = base
        f["mejor_union"] = round(min([x for x in (base, gen) if x is not None]), 3) \
            if (base is not None or gen is not None) else None
        f["cubierto_antes"] = bool(base is not None and base <= UMBRAL_A)
        f["cubierto_despues"] = bool(f["mejor_union"] is not None and f["mejor_union"] <= UMBRAL_A)
        f["recuperado"] = bool(not f["cubierto_antes"] and f["cubierto_despues"])
        # Lo que MF-02B habria contado con su metrica alineada
        f["contaria_mf02b"] = bool(f.get("rmsd_alineado_molflex") is not None
                                   and f["rmsd_alineado_molflex"] <= UMBRAL_A
                                   and not f["cubierto_antes"])

    Path(args.out).write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
        encoding="utf-8", newline="\n")

    antes = sum(1 for f in ok if f["cubierto_antes"])
    despues = sum(1 for f in ok if f["cubierto_despues"])
    recuperados = [f["pid"] for f in ok if f["recuperado"]]
    inflados = [f["pid"] for f in ok if f["contaria_mf02b"] and not f["recuperado"]]
    print(f"\n[pocket] complejos analizados: {len(ok)}/{len(filas)}")
    print(f"  cobertura del oraculo (marco de pocket): {antes} -> {despues} de {len(ok)}")
    print(f"  recuperados de verdad: {len(recuperados)}")
    print(f"  que MF-02B habria contado y NO se sostienen: {len(inflados)} -> {inflados}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
