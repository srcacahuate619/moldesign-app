#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_dataset_v2.py — Reconstrucción del conjunto de poses (Ruta C, Fase 0, v2).

Prerrequisito formal: `scripts/artifacts_science/RC-F0-V2-PRE/PREREGISTRO.md` sellado.

Reutiliza **las funciones del constructor original** (`build_pose_selector_dataset`)
para etiquetar: mismo `rmsd_pose_pocket` sin alinear, misma guardia de mapeo
completo, mismos umbrales de contacto, misma densidad de clúster, mismo orden
canónico de claves. Lo único que cambia es de dónde salen las poses.

Fases
-----
1. Etiquetar las poses nuevas de MolFlex (MF-02D train, MF-02E val/test) en un
   directorio de registros **separado** (`records_v2`), sin tocar los de v1.
2. Unir: v1 sin su fuente `molflex` (cuyo receptor ya no existe, PRE §5) + v2.
3. Recalcular `cluster_density` por complejo sobre la unión — no es un append:
   añadir poses cambia el valor de las viejas.
4. Emitir con el split **congelado** de v1 (no se re-divide por scaffold).
5. Evaluar los gates G3–G6 del prerregistro.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_pose_selector_dataset as B  # noqa: E402

DS = PROJECT_ROOT / "data" / "pose_selector_dataset"
RECORDS_V1 = DS / "records"
RECORDS_V2 = DS / "records_v2"
OUT_DIR = DS / "v2"
MATERIAL = {
    "train": PROJECT_ROOT / "data" / "molflex_train_v2",
    "valtest": PROJECT_ROOT / "data" / "molflex_valtest_v2",
}
UMBRAL_A = 2.0
FUENTES_CONSERVADAS_V1 = ("flexible_redock", "ruta_a")


def split_congelado() -> Dict[str, str]:
    """{pid: split} tal como quedó sellado en v1. No se re-divide."""
    m = {}
    for s in ("train", "val", "test"):
        for l in (DS / f"poses_{s}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                m[json.loads(l)["pid"]] = s
    return m


def dir_material(pid: str) -> Path | None:
    for base in MATERIAL.values():
        w = base / pid / pid
        if (w / "index_map.json").exists():
            return w
    return None


def _etiquetar_pid(pid: str) -> Dict[str, Any]:
    """Etiqueta todas las poses nuevas de un complejo con el código original."""
    B.RECORDS_DIR = RECORDS_V2
    RECORDS_V2.mkdir(parents=True, exist_ok=True)
    w = dir_material(pid)
    if w is None:
        return {"pid": pid, "ok": False, "razon": "sin_material"}
    n_reg = n_mod = 0
    excluidos = 0
    for conf in sorted(w.glob("conf*.out.pdbqt")):
        t = {"pid": pid, "fuente": "molflex", "stem": conf.stem, "out": conf,
             "lig": None, "rec": w / "rec.pdbqt", "index_map": w / "index_map.json"}
        r = B.procesar_trabajo(t, {})
        n_reg += r.get("n_registros", 0)
        n_mod += r.get("n_modelos", 0)
        excluidos += r.get("modelos_excluidos", 0)
        if r["estado"] == "excluido":
            return {"pid": pid, "ok": False, "razon": r.get("razon"),
                    "archivo": conf.name}
    return {"pid": pid, "ok": True, "n_modelos": n_mod, "n_registros": n_reg,
            "modelos_excluidos": excluidos}


def cargar_registros(dirp: Path, fuentes: tuple | None = None) -> Dict[str, list]:
    """{pid: [{'reg':..., 'densa':..., 'idx':...}]} filtrando por fuente."""
    import numpy as np
    todos: Dict[str, list] = {}
    if not dirp.exists():
        return todos
    for f in sorted(dirp.glob("*.json")):
        datos = json.loads(f.read_text(encoding="utf-8"))
        pid = datos.get("pid", f.stem)
        lista = []
        for clave, regs in sorted(datos.get("registros", {}).items()):
            for r in regs:
                if fuentes is not None and r["source"] not in fuentes:
                    continue
                idx = sorted(int(k) for k in r.get("_coords", {}))
                if not idx:
                    continue
                densa = np.full((max(idx) + 1, 3), np.nan)
                for m in idx:
                    densa[m] = r["_coords"][str(m)]
                lista.append({"reg": r, "densa": densa, "idx": idx})
        if lista:
            todos.setdefault(pid, []).extend(lista)
    return todos


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconstruccion del conjunto de poses v2")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--saltar-etiquetado", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    splits = split_congelado()
    pids = sorted(p for p in splits if dir_material(p) is not None)
    if args.limite:
        pids = pids[:args.limite]
    print(f"[v2] complejos con material nuevo: {len(pids)} de {len(splits)}", flush=True)

    # ── Fase 1: etiquetado de poses nuevas ──
    etiquetado: List[Dict[str, Any]] = []
    if not args.saltar_etiquetado:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for i, r in enumerate(ex.map(_etiquetar_pid, pids, chunksize=1), 1):
                etiquetado.append(r)
                if i % 10 == 0 or i == len(pids):
                    reg = sum(x.get("n_registros", 0) for x in etiquetado)
                    print(f"  [fase1 {i}/{len(pids)}] {reg} poses etiquetadas "
                          f"({round(time.time() - t0)}s)", flush=True)
        (OUT_DIR / "etiquetado.json").write_text(
            json.dumps(etiquetado, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
    else:
        etiquetado = json.loads((OUT_DIR / "etiquetado.json").read_text(encoding="utf-8"))
    print(f"[v2] fase 1 lista: {sum(1 for r in etiquetado if r['ok'])}/{len(etiquetado)} complejos", flush=True)

    # ── Fase 2: unión ──
    v1 = cargar_registros(RECORDS_V1, fuentes=FUENTES_CONSERVADAS_V1)
    v2 = cargar_registros(RECORDS_V2)
    union: Dict[str, list] = defaultdict(list)
    for pid, lista in v1.items():
        union[pid].extend(lista)
    for pid, lista in v2.items():
        union[pid].extend(lista)
    n_v1 = sum(len(v) for v in v1.values())
    n_v2 = sum(len(v) for v in v2.values())
    print(f"[v2] union: {n_v1} poses conservadas de v1 + {n_v2} nuevas = "
          f"{n_v1 + n_v2} en {len(union)} complejos", flush=True)

    # ── Fase 3: cluster_density sobre la union (mismo algoritmo del original) ──
    t1 = time.time()
    for pid, lista in union.items():
        for e in lista:
            e["reg"]["cluster_density"] = 0
        for i, ea in enumerate(lista):
            for j in range(i + 1, len(lista)):
                eb = lista[j]
                if B.rmsd_entre_poses(ea["densa"], eb["densa"]) < B.UMBRAL_CLUSTER:
                    ea["reg"]["cluster_density"] += 1
                    eb["reg"]["cluster_density"] += 1
    print(f"[v2] cluster_density recalculada en {round(time.time() - t1)}s", flush=True)

    # ── Fase 4: emision con el split congelado ──
    conteos: Dict[str, Dict[str, int]] = {s: {"poses": 0, "pids": 0} for s in ("train", "val", "test")}
    lineas_por_split: Dict[str, List[str]] = {s: [] for s in conteos}
    for pid in sorted(union):
        s = splits.get(pid)
        if s is None:
            continue
        conteos[s]["pids"] += 1
        for entrada in union[pid]:
            r = dict(entrada["reg"])
            r.pop("_coords", None)
            lineas_por_split[s].append(json.dumps({k: r[k] for k in B.ORDEN_CLAVES},
                                                  ensure_ascii=False))
            conteos[s]["poses"] += 1
    for s, lineas in lineas_por_split.items():
        (OUT_DIR / f"poses_{s}.jsonl").write_text(
            "\n".join(lineas) + "\n", encoding="utf-8", newline="\n")

    # ── Fase 5: gates ──
    def oraculo(path: Path) -> Dict[str, Any]:
        por = defaultdict(list)
        for l in path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                x = json.loads(l)
                por[x["pid"]].append(x["rmsd"])
        cub = sum(1 for v in por.values() if min(v) <= UMBRAL_A)
        return {"complejos": len(por), "cubiertos": cub,
                "cobertura": round(cub / len(por), 4) if por else 0.0}

    orac_v1 = {s: oraculo(DS / f"poses_{s}.jsonl") for s in conteos}
    orac_v2 = {s: oraculo(OUT_DIR / f"poses_{s}.jsonl") for s in conteos}

    # G3: ningun complejo cambia de split
    splits_v2 = {}
    for s in conteos:
        for l in (OUT_DIR / f"poses_{s}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                splits_v2[json.loads(l)["pid"]] = s
    movidos = [p for p, s in splits_v2.items() if splits.get(p) != s]

    # G4: las poses v1 conservadas mantienen etiqueta y features base
    clave = lambda r: (r["pid"], r["source"], r["file_stem"], r["model_idx"])  # noqa: E731
    base_v1 = {}
    for s in conteos:
        for l in (DS / f"poses_{s}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["source"] in FUENTES_CONSERVADAS_V1:
                    base_v1[clave(r)] = r
    discrepancias = []
    faltantes = 0
    campos = ["rmsd", "vina_score", "n_heavy", "n_contacts_4", "n_contacts_6",
              "contacts_per_ha_4", "n_clashes", "pose_score_variance", "pose_score_range"]
    vistos = set()
    for s in conteos:
        for l in (OUT_DIR / f"poses_{s}.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                k = clave(r)
                if k in base_v1:
                    vistos.add(k)
                    o = base_v1[k]
                    dif = {c: (o[c], r[c]) for c in campos if o[c] != r[c]}
                    if dif:
                        discrepancias.append({"clave": list(k), "dif": dif})
    faltantes = len(set(base_v1) - vistos)

    metrics = {
        "experiment_id": "RC-F0-V2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "poses_v1_conservadas": n_v1, "poses_nuevas": n_v2, "poses_total": n_v1 + n_v2,
        "conteos_por_split": conteos,
        "oraculo_v1": orac_v1, "oraculo_v2": orac_v2,
        "etiquetado": {"complejos_ok": sum(1 for r in etiquetado if r["ok"]),
                       "complejos_fallidos": [r for r in etiquetado if not r["ok"]],
                       "modelos_excluidos_por_mapeo": sum(r.get("modelos_excluidos", 0)
                                                          for r in etiquetado)},
        "gates": {
            "G3_split_conservado": {"criterio": "ningun complejo cambia de split",
                                    "movidos": movidos, "pass": not movidos},
            "G4_poses_v1_intactas": {
                "criterio": "toda pose v1 de flexible_redock/ruta_a conserva etiqueta y features base",
                "n_comparadas": len(vistos), "n_faltantes": faltantes,
                "n_discrepancias": len(discrepancias),
                "ejemplos": discrepancias[:5],
                "pass": not discrepancias and faltantes == 0},
            "G5_cobertura": {
                "criterio": "cobertura v2 >= v1 en cada split y >= 0.793 en train",
                "train_v2": orac_v2["train"]["cobertura"],
                "pass": all(orac_v2[s]["cobertura"] >= orac_v1[s]["cobertura"] for s in conteos)
                        and orac_v2["train"]["cobertura"] >= 0.793},
        },
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"
    (OUT_DIR / "metrics_v2.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print(f"\n[v2] decision {metrics['decision']}")
    for s in ("train", "val", "test"):
        print(f"  {s:<6} {conteos[s]['poses']:>6} poses / {conteos[s]['pids']:>3} complejos | "
              f"oraculo {orac_v1[s]['cobertura']:.1%} -> {orac_v2[s]['cobertura']:.1%}")
    for k, g in metrics["gates"].items():
        print(f"  {k}: {'PASS' if g['pass'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
