#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf14_radio_captura.py — MF-14: ¿cuán grande es la cuenca del mínimo nativo?

Prerrequisito formal: `scripts/artifacts_science/MF-14-PRE/PREREGISTRO.md` escrito.
Corre en el contenedor `moldesign-lab` del servidor (Vina 1.2.7, Meeko 0.7.1).

La pregunta
-----------
`MF-13` midió que en ~70% de los complejos difíciles la función de Vina **prefiere**
la pose nativa —el percentil mediano del cristal es 0.0, o sea que puntúa mejor que
todas las poses dockeadas— y que el cristal es un **mínimo local estable** (deriva de
0.32 Å bajo `local_only`). Y sin embargo el buscador nunca llega, con 86 confórmeros,
9 modos, tres cajas y ~751 poses por complejo.

Falta una pieza para que eso tenga sentido mecánico: **¿cuán grande es la cuenca de
atracción de ese mínimo?**

  * Si la cuenca es **ancha** (varios Å), una búsqueda global razonable debería caer
    en ella por azar, y que no ocurra apunta a un defecto del muestreador.
  * Si la cuenca es **estrecha** (~0.5 Å), encontrarla requiere acertar casi
    exactamente, y entonces **ninguna búsqueda global la encuentra por azar**. Eso
    explicaría `MF-08`, `MF-02F`, `MF-09` y `MF-10` con un solo mecanismo: todas
    fallaron porque el objetivo es un pozo estrecho en un paisaje ancho.

Diseño
------
Para cada complejo, se parte de la **pose cristalográfica** y se la perturba con
desplazamientos crecientes; desde cada punto perturbado se ejecuta `vina --local_only`
y se mide si el optimizador **vuelve** a ≤2 Å del cristal.

  * perturbación = traslación aleatoria de magnitud `r` + rotación aleatoria de hasta
    30° alrededor del centroide;
  * `r` recorre {0.5, 1.0, 2.0, 3.0, 4.0} Å, con `REPLICAS` réplicas por radio;
  * se registra el **RMSD inicial real** de cada perturbación, y el análisis se hace
    por RMSD inicial observado, no por el radio nominal.

Métrica: fracción de retorno por radio, y `r50` = radio al que la fracción de retorno
cae por debajo de 0.5. `r50` **es** el radio de captura.

Semilla fija (42) para que las perturbaciones sean reproducibles.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED = 42
UMBRAL_A = 2.0
RADIOS = (0.5, 1.0, 2.0, 3.0, 4.0)
REPLICAS = 6
ANGULO_MAX = 30.0     # grados


def _vina() -> str:
    return os.environ.get("MF14_VINA", "/usr/local/bin/vina")


def _correr(args: List[str], timeout: int) -> Optional[str]:
    try:
        p = subprocess.run([_vina()] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _rot(eje: Tuple[float, float, float], ang: float):
    """Matriz de rotación de Rodrigues."""
    n = math.sqrt(sum(x * x for x in eje)) or 1.0
    x, y, z = (e / n for e in eje)
    c, s, t = math.cos(ang), math.sin(ang), 1 - math.cos(ang)
    return ((t*x*x + c,   t*x*y - s*z, t*x*z + s*y),
            (t*x*y + s*z, t*y*y + c,   t*y*z - s*x),
            (t*x*z - s*y, t*y*z + s*x, t*z*z + c))


def _leer_pdbqt(texto: str):
    """(lineas, indices de lineas de atomo, coords)."""
    L = texto.splitlines()
    idx, xyz = [], []
    for i, l in enumerate(L):
        if l.startswith(("ATOM", "HETATM")):
            idx.append(i)
            xyz.append([float(l[30:38]), float(l[38:46]), float(l[46:54])])
    return L, idx, xyz


def _escribir_pdbqt(L, idx, xyz) -> str:
    out = list(L)
    for k, i in enumerate(idx):
        l = out[i]
        out[i] = "%s%8.3f%8.3f%8.3f%s" % (l[:30], xyz[k][0], xyz[k][1], xyz[k][2], l[54:])
    return "\n".join(out) + "\n"


def _perturbar(xyz, r: float, rng: random.Random):
    cx = [sum(p[k] for p in xyz) / len(xyz) for k in range(3)]
    eje = (rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))
    R = _rot(eje, math.radians(rng.uniform(0, ANGULO_MAX)))
    d = (rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))
    n = math.sqrt(sum(x * x for x in d)) or 1.0
    tras = [x / n * r for x in d]
    nuevo = []
    for p in xyz:
        v = [p[k] - cx[k] for k in range(3)]
        w = [sum(R[i][j] * v[j] for j in range(3)) for i in range(3)]
        nuevo.append([w[i] + cx[i] + tras[i] for i in range(3)])
    return nuevo


def _rmsd(a, b) -> float:
    return math.sqrt(sum((a[i][0]-b[i][0])**2 + (a[i][1]-b[i][1])**2 + (a[i][2]-b[i][2])**2
                         for i in range(len(a))) / len(a))


def preparar_cristal(ws: Path, pid: str, destino: Path) -> bool:
    import molflex as mf
    from meeko import MoleculePreparation
    from rdkit import Chem
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return False
    mh = Chem.AddHs(crystal, addCoords=True)
    setups = MoleculePreparation().prepare(mh, conformer_id=0)
    rigid, _f, mapa, _e = mf.escribir_pdbqt(setups[0])
    if not rigid:
        return False
    destino.write_text(rigid, encoding="utf-8")
    return True


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "puntos": []}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists():
        out["error"] = "SIN_RECEPTOR_O_CAJA"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    lig0 = tmp / f"{pid}_c.pdbqt"
    try:
        if not preparar_cristal(ws, pid, lig0):
            out["error"] = "PREP_FALLO"
            return out
    except Exception as ex:
        out["error"] = f"PREP:{type(ex).__name__}:{str(ex)[-100:]}"
        return out

    L, idx, xyz0 = _leer_pdbqt(lig0.read_text(encoding="utf-8"))
    rng = random.Random(SEED + abs(hash(pid)) % 100000)
    for r in RADIOS:
        for k in range(REPLICAS):
            xyzp = _perturbar(xyz0, r, rng)
            rmsd_ini = _rmsd(xyz0, xyzp)
            pin = tmp / f"{pid}_p.pdbqt"
            pout = tmp / f"{pid}_po.pdbqt"
            pin.write_text(_escribir_pdbqt(L, idx, xyzp), encoding="utf-8")
            s = _correr(["--receptor", str(rec), "--ligand", str(pin)] + _caja(centro) +
                        ["--seed", str(SEED), "--cpu", "1", "--local_only",
                         "--out", str(pout)], timeout=180)
            fila = {"r_nominal": r, "rmsd_inicial": round(rmsd_ini, 3)}
            if s and pout.exists():
                mods = mf.parsear_out_vina(pout.read_text(encoding="utf-8", errors="replace"))
                if mods:
                    _sc, at = mods[0]
                    fin = [[a[1], a[2], a[3]] for a in at]
                    if len(fin) == len(xyz0):
                        rf = _rmsd(xyz0, fin)
                        fila["rmsd_final"] = round(rf, 3)
                        fila["vuelve"] = bool(rf <= UMBRAL_A)
            out["puntos"].append(fila)
    ok = [p for p in out["puntos"] if "rmsd_final" in p]
    out["n_puntos"] = len(out["puntos"])
    out["n_ok"] = len(ok)
    por_r = {}
    for r in RADIOS:
        g = [p for p in ok if p["r_nominal"] == r]
        if g:
            por_r[str(r)] = {"n": len(g), "vuelven": sum(p["vuelve"] for p in g),
                             "frac": round(sum(p["vuelve"] for p in g) / len(g), 3),
                             "rmsd_final_mediano": round(median(p["rmsd_final"] for p in g), 3)}
    out["por_radio"] = por_r
    # r50: mayor radio con fraccion de retorno >= 0.5
    r50 = None
    for r in RADIOS:
        f = por_r.get(str(r), {}).get("frac")
        if f is not None and f >= 0.5:
            r50 = r
    out["r50"] = r50
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-14: radio de captura del minimo nativo")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-14"
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = [ws / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json",
            ws / "scripts" / "mf13_cohorte.json"]
    ruta = next((c for c in cand if c.exists()), None)
    if ruta is None:
        print("[MF-14] ERROR: falta cohorte.json")
        return 2
    coh = json.loads(ruta.read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-14] {len(jobs)} complejos x {len(RADIOS)} radios x {REPLICAS} replicas "
          f"= {len(jobs)*len(RADIOS)*REPLICAS} corridas", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, (pid, est) in enumerate(jobs, 1):
            filas.append(analizar(ws, pid, est, tmp))
            r = filas[-1]
            print(f"  [{i}/{len(jobs)}] {pid} [{est}] r50={r.get('r50')} "
                  f"ok={r.get('n_ok')}/{r.get('n_puntos')} ({round(time.time()-t0)}s)", flush=True)
            with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in filas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r and r.get("n_ok")]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        curva = {}
        for r in RADIOS:
            tot = sum(r_.get("por_radio", {}).get(str(r), {}).get("n", 0) for r_ in g)
            vue = sum(r_.get("por_radio", {}).get(str(r), {}).get("vuelven", 0) for r_ in g)
            curva[str(r)] = {"n": tot, "vuelven": vue,
                             "frac": round(vue / tot, 4) if tot else None}
        r50s = [r_["r50"] for r_ in g if r_.get("r50") is not None]
        resumen[est] = {"n_complejos": len(g), "curva_retorno": curva,
                        "r50_mediano": median(r50s) if r50s else None,
                        "complejos_sin_r50": sum(1 for r_ in g if r_.get("r50") is None)}
    metrics = {
        "experiment_id": "MF-14",
        "tipo": "medicion con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"radios": list(RADIOS), "replicas": REPLICAS, "angulo_max_grados": ANGULO_MAX,
                   "seed": SEED, "box": BOX},
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "gates": {
            "G1_validez": {"criterio": ">=95% de las perturbaciones producen pose final",
                           "tasa": round(sum(r["n_ok"] for r in ok) /
                                         max(1, sum(r["n_puntos"] for r in ok)), 4)},
            "G2_radio": {"criterio": "r50 mediano de COLOCACION",
                         "r50_mediano": resumen.get("COLOCACION", {}).get("r50_mediano"),
                         "lectura": ("<=1.0 A => cuenca ESTRECHA: ninguna busqueda global la "
                                     "encuentra por azar y eso explica MF-08/MF-02F/MF-09/MF-10. "
                                     ">=3.0 A => cuenca ANCHA: el muestreador deberia caer en "
                                     "ella y el defecto es del muestreador. 1-3 A => intermedio")},
        },
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-14] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
