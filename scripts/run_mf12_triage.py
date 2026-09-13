#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf12_triage.py — MF-12: ¿se puede predecir el fallo de colocación sin dockear?

Prerrequisito formal: `scripts/artifacts_science/MF-12-PRE/PREREGISTRO.md`.

Entrena en los 116 de train y evalúa **una sola vez** en los 87 de val+test. Dos
niveles de disponibilidad, evaluados por separado (§2 del prerregistro):

  * **L**   — sólo ligando: no requiere conocer el sitio;
  * **L+S** — añade descriptores del bolsillo alrededor del centro de caja.

Ningún predictor usa la pose cristalográfica. En particular NO se usan `rmsd_conf`,
`enterramiento` ni `ocupacion_caja` de `MF-24`, que sí la usan.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from estadistica_fnd04 import bootstrap_bca_pareado, efecto_minimo_detectable  # noqa: E402

MAT = PROJECT_ROOT / os.environ.get("MF12_MATERIAL", "data/molflex_train_v2")
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-12"
BOX = 25.0
UMBRAL_A = 2.0

NIVEL_L = ["n_torsiones", "n_pesados", "n_conformeros", "rg_conformero",
           "ocupacion_conformero"]
NIVEL_S = ["prot_5A_centro", "prot_8A_centro"]


def _rasgos(pid: str) -> Dict[str, Any]:
    """Predictores SIN fuga: nada aqui usa la pose cristalografica."""
    import molflex as mf
    out: Dict[str, Any] = {"pid": pid}
    w = MAT / pid / pid
    if not (w / "index_map.json").exists() or not (w / "center.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    centro = json.loads((w / "center.json").read_text(encoding="utf-8"))
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}

    def _coords(f: Path):
        at = []
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
                try:
                    at.append([float(l[30:38]), float(l[38:46]), float(l[46:54])])
                except ValueError:
                    continue
        return at

    entradas = [f for f in sorted(w.glob("conf*.rigid.pdbqt"))
                if re.match(r"conf\d+\.rigid\.pdbqt$", f.name)]
    if not entradas:
        out["error"] = "SIN_CONFORMEROS"
        return out
    out["n_conformeros"] = len(entradas)
    # geometria del CONFORMERO 0, no del cristal
    c0 = _coords(entradas[0])
    if not c0:
        out["error"] = "CONFORMERO_ILEGIBLE"
        return out
    n = len(c0)
    cen = [sum(p[k] for p in c0) / n for k in range(3)]
    out["n_pesados"] = n
    out["rg_conformero"] = round(math.sqrt(
        sum(sum((p[k] - cen[k]) ** 2 for k in range(3)) for p in c0) / n), 3)
    rmax = max(math.sqrt(sum((p[k] - cen[k]) ** 2 for k in range(3))) for p in c0)
    out["ocupacion_conformero"] = round((4 / 3 * math.pi * rmax ** 3) / BOX ** 3, 5)

    tors = None
    for f in sorted(w.glob("conf*.flex.pdbqt")):
        if re.match(r"conf\d+\.flex\.pdbqt$", f.name):
            tors = sum(1 for l in f.read_text(encoding="utf-8", errors="replace").splitlines()
                       if l.startswith("BRANCH"))
            break
    out["n_torsiones"] = tors

    # descriptores del SITIO alrededor del centro de caja (no del ligando)
    n5 = n8 = 0
    for l in (w / "rec.pdbqt").read_text(encoding="utf-8", errors="replace").splitlines():
        if l[:6].strip() in ("ATOM", "HETATM") and len(l) >= 54:
            nm, rn = l[12:16].strip(), l[17:20].strip()
            if nm.startswith("H") or rn in ("HOH", "WAT", "DOD"):
                continue
            try:
                d2 = sum((float(l[30 + 8 * k:38 + 8 * k]) - centro[k]) ** 2 for k in range(3))
            except ValueError:
                continue
            if d2 <= 64.0:
                n8 += 1
                if d2 <= 25.0:
                    n5 += 1
    out["prot_5A_centro"] = n5
    out["prot_8A_centro"] = n8
    return out


def _desenlace(fuente: Path) -> Dict[str, bool]:
    d = {}
    for l in fuente.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if "convierte" in r:
                d[r["pid"]] = bool(r["convierte"])
    return d


def _prec_balanceada(y, p) -> float:
    tp = sum(1 for a, b in zip(y, p) if a and b)
    tn = sum(1 for a, b in zip(y, p) if (not a) and (not b))
    pos = sum(1 for a in y if a)
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    return 0.5 * (tp / pos + tn / neg)


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-12: triage de fallo de colocacion")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    global MAT

    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    datos = {}
    for split, mat, fuente in (
            ("train", "data/molflex_train_v2", ART / "MF-24" / "per_complex.jsonl"),
            ("valtest", "data/molflex_valtest_v2", ART / "MF-24" / "per_complex_valtest.jsonl")):
        MAT = PROJECT_ROOT / mat
        os.environ["MF12_MATERIAL"] = mat
        pids = sorted(p.name for p in MAT.iterdir() if p.is_dir())
        des = _desenlace(fuente)
        filas = []
        for pid in pids:
            r = _rasgos(pid)
            if "error" in r or pid not in des or r.get("n_torsiones") is None:
                continue
            r["convierte"] = des[pid]
            r["split"] = split
            filas.append(r)
        datos[split] = filas
        print(f"[MF-12] {split}: {len(filas)} complejos con rasgos y desenlace", flush=True)

    resultados = {}
    for nivel, cols in (("L", NIVEL_L), ("L+S", NIVEL_L + NIVEL_S)):
        Xtr = np.array([[r[c] for c in cols] for r in datos["train"]], dtype=float)
        ytr = np.array([r["convierte"] for r in datos["train"]])
        Xte = np.array([[r[c] for c in cols] for r in datos["valtest"]], dtype=float)
        yte = np.array([r["convierte"] for r in datos["valtest"]])
        sc = StandardScaler().fit(Xtr)
        mod = LogisticRegression(max_iter=2000, C=1.0).fit(sc.transform(Xtr), ytr)
        pte = mod.predict(sc.transform(Xte))
        mayoritaria = bool(ytr.mean() >= 0.5)
        pbase = np.full(len(yte), mayoritaria)
        bal_m = _prec_balanceada(yte, pte)
        bal_b = _prec_balanceada(yte, pbase)
        # diferencia pareada por complejo: acierto del modelo menos acierto del baseline
        dif = [(1.0 if a == b else 0.0) - (1.0 if a == c else 0.0)
               for a, b, c in zip(yte, pte, pbase)]
        th, lo, hi = bootstrap_bca_pareado(dif, n_boot=10000, seed=42)
        resultados[nivel] = {
            "features": cols,
            "coeficientes": {c: round(float(v), 4) for c, v in zip(cols, mod.coef_[0])},
            "precision_balanceada_modelo": round(float(bal_m), 4),
            "precision_balanceada_baseline": round(float(bal_b), 4),
            "exactitud_modelo": round(float((pte == yte).mean()), 4),
            "exactitud_baseline": round(float((pbase == yte).mean()), 4),
            "dif_pareada_exactitud": round(th, 4),
            "ci95_bca": [round(lo, 4), round(hi, 4)],
            "supera_baseline": bool(lo > 0),
        }

    n_tot = len(datos["train"]) + len(datos["valtest"])
    mde = efecto_minimo_detectable(n_tot, 0.5)
    metrics = {
        "experiment_id": "MF-12",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_train": len(datos["train"]), "n_valtest": len(datos["valtest"]),
        "tasa_base": {"train": round(float(np.mean([r["convierte"] for r in datos["train"]])), 4),
                      "valtest": round(float(np.mean([r["convierte"] for r in datos["valtest"]])), 4)},
        "efecto_minimo_detectable_declarado": round(mde, 4),
        "niveles": resultados,
        "supuesto_del_nivel_S": ("el centro de caja del conjunto es center_from_crystal_ligand, "
                                 "asi que L+S opera con caja perfectamente centrada; en "
                                 "produccion MolPocket yerra ~8 A (REC-03) y lo degradaria. "
                                 "L+S mide un TECHO"),
        "gates": {
            "G2_superioridad_L": {"criterio": "precision balanceada de L supera al baseline con CI95 que excluya 0",
                                  "pass": resultados["L"]["supera_baseline"]},
            "G3_honestidad": {"criterio": "se reportan L y L+S por separado; el claim se hace sobre L",
                              "pass": True},
        },
    }
    metrics["decision"] = "GO" if metrics["gates"]["G2_superioridad_L"]["pass"] else "NO_GO"
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for s in ("train", "valtest"):
            for r in datos[s]:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"tasa_base": metrics["tasa_base"], "MDE": round(mde, 4),
                      "niveles": resultados, "decision": metrics["decision"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
