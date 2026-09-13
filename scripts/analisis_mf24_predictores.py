#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf24_predictores.py — MF-24: ¿qué predice el coste de colocación, sin circularidad?

**Tipo: medición.** Lectura de material ya en disco; sin docking nuevo.

El problema de diseño que este experimento resuelve
---------------------------------------------------
`MF-22` midió que el coste de colocación es **0.741 Å** en el estrato control y
**3.847 Å** en el dominado por colocación. Pero **el estrato COLOCACION se definió como
los complejos que fallan la colocación**, así que esa diferencia está garantizada por
construcción y no explica nada: es la definición vista al revés.

Para romper la circularidad hay que salir de la cohorte estratificada y medir sobre
**los 116 complejos de train**, que no fueron seleccionados por desenlace, usando
predictores calculables **sin mirar el resultado del docking**:

  * `n_pesados` — tamaño del ligando;
  * `n_torsiones` — grados de libertad internos (del PDBQT flexible);
  * `radio_giro` — extensión espacial del ligando cristalográfico;
  * `enterramiento` — átomos pesados de proteína a <4 Å del ligando cristalográfico,
    por átomo de ligando;
  * `ocupacion_caja` — fracción del volumen de la caja de 25 Å que ocupa la esfera
    envolvente del ligando;
  * `n_conformeros` — tamaño del ensemble generado.

Ninguno usa el RMSD de las poses. La variable respuesta sí: **coste de colocación** =
mejor RMSD en marco de pocket − RMSD alineado del confórmero que lo produjo.

Limitación declarada
--------------------
Correlacional. Con n≈116 y seis predictores correlacionados entre sí, esto **no
identifica causas**: ordena candidatos para un experimento posterior. No se ajusta
ningún modelo multivariante ni se declara ningún umbral operativo.
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
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# override spawn-safe por variable de entorno: con ProcessPoolExecutor en Windows los
# workers REIMPORTAN el modulo, asi que un `global MAT` en main() no les llega (mismo
# bug que ya se corrigio en analisis_pocket)
MAT = PROJECT_ROOT / os.environ.get("MF24_MATERIAL", "data/molflex_train_v2")
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-24"
BOX = 25.0
UMBRAL_A = 2.0


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < 8:
        return None

    def rangos(v):
        o = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            p = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[o[k]] = p
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def _analizar(pid: str) -> Dict[str, Any]:
    import molflex as mf
    from rdkit import Chem
    from rdkit.Chem import AllChem
    out: Dict[str, Any] = {"pid": pid}
    w = MAT / pid / pid
    if not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    ref_heavy = Chem.RemoveAllHs(Chem.Mol(crystal))
    if ref_heavy.GetNumAtoms() != len(pesados):
        out["error"] = "DESAJUSTE_PESADOS"
        return out
    cf = crystal.GetConformer(0)
    lig = [(cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z)
           for i in pesados]

    # ── predictores, todos independientes del resultado del docking ──
    n = len(lig)
    cen = [sum(p[k] for p in lig) / n for k in range(3)]
    rg = math.sqrt(sum(sum((p[k] - cen[k]) ** 2 for k in range(3)) for p in lig) / n)
    rmax = max(math.sqrt(sum((p[k] - cen[k]) ** 2 for k in range(3))) for p in lig)
    out["n_pesados"] = n
    out["radio_giro"] = round(rg, 3)
    out["ocupacion_caja"] = round((4 / 3 * math.pi * rmax ** 3) / (BOX ** 3), 5)

    tors = None
    for f in sorted(w.glob("conf*.flex.pdbqt")):
        if re.match(r"conf\d+\.flex\.pdbqt$", f.name):
            tors = sum(1 for l in f.read_text(encoding="utf-8", errors="replace").splitlines()
                       if l.startswith("BRANCH"))
            break
    out["n_torsiones"] = tors

    prot = []
    for l in (w / "rec.pdbqt").read_text(encoding="utf-8", errors="replace").splitlines():
        if l[:6].strip() in ("ATOM", "HETATM") and len(l) >= 54:
            nm = l[12:16].strip()
            rn = l[17:20].strip()
            if nm.startswith("H") or rn in ("HOH", "WAT", "DOD"):
                continue
            try:
                prot.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                continue
    cerca = 0
    for p in prot:
        for q in lig:
            if (p[0]-q[0])**2 + (p[1]-q[1])**2 + (p[2]-q[2])**2 <= 16.0:
                cerca += 1
                break
    out["enterramiento"] = round(cerca / n, 3)

    # ── respuesta: coste de colocacion del MEJOR conformero de entrada ──
    entradas = [f for f in sorted(w.glob("conf*.rigid.pdbqt"))
                if re.match(r"conf\d+\.rigid\.pdbqt$", f.name)]
    out["n_conformeros"] = len(entradas)
    mejor_conf, mejor_f = 9e9, None
    for f in entradas:
        at = []
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
                try:
                    at.append([int(l[6:11]), float(l[30:38]), float(l[38:46]),
                               float(l[46:54])])
                except ValueError:
                    continue
        c = mf.coords_pose_a_por_mol(at, s2m)
        if not c or any(i not in c for i in pesados):
            continue
        probe = Chem.Mol(ref_heavy)
        pc = probe.GetConformer(0)
        for k, i in enumerate(pesados):
            x, y, z = c[i]
            pc.SetAtomPosition(k, (float(x), float(y), float(z)))
        try:
            r = float(AllChem.GetBestRMS(probe, ref_heavy, 0, 0))
        except Exception:
            continue
        if r < mejor_conf:
            mejor_conf, mejor_f = r, f
    if mejor_f is None:
        out["error"] = "SIN_CONFORMEROS"
        return out
    out["rmsd_conf"] = round(mejor_conf, 3)
    cid = int(re.match(r"conf(\d+)\.", mejor_f.name).group(1))
    salida = w / f"conf{cid}.out.pdbqt"
    if not salida.exists():
        out["error"] = "SIN_SALIDA"
        return out
    best = None
    for sc, at in mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace")):
        c = mf.coords_pose_a_por_mol(at, s2m)
        if not c:
            continue
        v = mf.rmsd_pose_pocket(crystal, c)
        if v is not None and (best is None or v < best):
            best = v
    if best is None:
        out["error"] = "SIN_POSES"
        return out
    out["rmsd_pose"] = round(best, 3)
    out["colocacion"] = round(best - mejor_conf, 3)
    out["convierte"] = bool(best <= UMBRAL_A)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-24: predictores del coste de colocacion")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--sufijo", default="", help="sufijo para los ficheros de salida")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pids = sorted(p.name for p in MAT.iterdir() if p.is_dir())
    print(f"[MF-24] {len(pids)} complejos de train, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, pids), 1):
            filas.append(r)
            if i % 20 == 0:
                print(f"  [{i}/{len(pids)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / f"per_complex{args.sufijo}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "colocacion" in r and r.get("n_torsiones") is not None]
    preds = ["n_pesados", "n_torsiones", "radio_giro", "enterramiento",
             "ocupacion_caja", "n_conformeros", "rmsd_conf"]
    corr = {}
    for p in preds:
        v = [r[p] for r in ok]
        corr[p] = {"spearman_vs_coste": _spearman(v, [r["colocacion"] for r in ok]),
                   "mediana": round(median(v), 3)}
    conv = [r for r in ok if r["convierte"]]
    noconv = [r for r in ok if not r["convierte"]]
    contraste = {}
    for p in preds:
        contraste[p] = {"convierten": round(median(r[p] for r in conv), 3) if conv else None,
                        "no_convierten": round(median(r[p] for r in noconv), 3) if noconv else None}
    metrics = {
        "experiment_id": "MF-24",
        "tipo": "medicion correlacional sobre los 116 de train (sin seleccion por desenlace)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "por_que_los_116": ("la cohorte de 48 se estratifico POR desenlace de colocacion, asi "
                            "que comparar coste de colocacion entre sus estratos es circular; "
                            "los 116 de train no se seleccionaron por desenlace"),
        "n_complejos": len(filas), "n_ok": len(ok),
        "n_convierten": len(conv), "n_no_convierten": len(noconv),
        "coste_colocacion_mediano": round(median(r["colocacion"] for r in ok), 3) if ok else None,
        "correlaciones": corr,
        "contraste_por_desenlace": contraste,
        "limitacion": ("correlacional, seis predictores correlacionados entre si y n=116: "
                       "ordena candidatos para un experimento posterior, NO identifica causas"),
    }
    (OUT_DIR / f"metrics{args.sufijo}.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(json.dumps({"correlaciones": corr, "contraste": contraste},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
