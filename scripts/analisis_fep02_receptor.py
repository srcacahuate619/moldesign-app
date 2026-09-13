#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep02_receptor.py — FEP-02: integridad del receptor.

**Tipo: medición.** Auditoría de los PDB en disco. Sin docking.

Qué pide FEP-02
---------------
La cartera H lo define como «chain/assembly, residuos, disulfuros, metales, cofactors y
aguas documentados». Hoy el pipeline no emite ninguno: prepara el receptor con OpenBabel
sobre el PDB completo y sigue.

Tres cosas que esta auditoría busca en concreto
-----------------------------------------------
1. **Huecos de cadena.** `MF-10` falló en 9 complejos con el mismo error de plantilla de
   OpenMM (`residue match NVAL/NILE/NTHR… 1 N atom too many`), y lo diagnostiqué como
   cortes de cadena dejados como términos al vaciar `missingResidues`. **Ese
   diagnóstico nunca se verificó.** Aquí se comprueba contando saltos en la numeración
   de residuos.

2. **Bolsillos entre cadenas.** `19_LIMITATIONS` marca como modo de fallo conocido que
   `_detect_dominant_chain` recorte una sola cadena y destruya un sitio inter-cadena
   (caso de la proteasa del VIH, homodímero). Nadie lo ha contado.

3. **Metales, cofactores y aguas del sitio.** `MF-13` encontró complejos cuyo cristal
   puntúa como si no uniera (`1fkh` a −1.63 kcal/mol), y la primera hipótesis —metales
   ausentes— resultó falsa porque el PDBQT ya los contiene. Aquí se documenta qué hay
   realmente en cada sitio, que es lo que un paquete FEP+ debe declarar.

Limitación declarada
--------------------
Un salto de numeración no siempre es un hueco físico: hay estructuras con numeración no
consecutiva por convención (numeración de quimotripsina, insertions codes). Se cuenta el
salto y se marca como **candidato**, no como defecto confirmado.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
MATS = {"train": PROJECT_ROOT / "data" / "molflex_train_v2",
        "valtest": PROJECT_ROOT / "data" / "molflex_valtest_v2"}
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FEP-02"
AGUAS = {"HOH", "WAT", "DOD"}
METALES = {"ZN", "MG", "MN", "FE", "CA", "CU", "NI", "CO", "CD", "NA", "K", "HG"}
R_SITIO = 6.0


def _analizar(job: Dict[str, str]) -> Dict[str, Any]:
    pid, split = job["pid"], job["split"]
    out: Dict[str, Any] = {"pid": pid, "split": split}
    prot = PDBBIND / pid / f"{pid}_protein.pdb"
    lig = PDBBIND / pid / f"{pid}_ligand.sdf"
    if not prot.exists():
        out["error"] = "SIN_PDB"
        return out

    # coordenadas del ligando cristalografico para definir el sitio
    lig_xyz: List[tuple] = []
    if lig.exists():
        leyendo = False
        for i, l in enumerate(lig.read_text(encoding="utf-8", errors="replace").splitlines()):
            if i == 3:
                try:
                    n_at = int(l[:3])
                except ValueError:
                    n_at = 0
                leyendo = True
                continue
            if leyendo and len(lig_xyz) < n_at:
                p = l.split()
                if len(p) >= 4:
                    try:
                        lig_xyz.append((float(p[0]), float(p[1]), float(p[2])))
                    except ValueError:
                        pass

    cadenas: Dict[str, List[int]] = defaultdict(list)
    cys_sg: List[tuple] = []
    het: Counter = Counter()
    metales_xyz: List[tuple] = []
    aguas_xyz: List[tuple] = []
    cofactores_xyz: List[tuple] = []
    cadenas_sitio = set()

    for l in prot.read_text(encoding="utf-8", errors="replace").splitlines():
        tipo = l[:6].strip()
        if tipo not in ("ATOM", "HETATM") or len(l) < 54:
            continue
        rn = l[17:20].strip()
        nm = l[12:16].strip()
        ch = l[21:22]
        try:
            xyz = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        except ValueError:
            continue
        cerca = any((xyz[0]-q[0])**2 + (xyz[1]-q[1])**2 + (xyz[2]-q[2])**2 <= R_SITIO**2
                    for q in lig_xyz) if lig_xyz else False
        if tipo == "ATOM":
            try:
                ri = int(l[22:26])
            except ValueError:
                continue
            if nm == "CA":
                cadenas[ch].append(ri)
            if rn == "CYS" and nm == "SG":
                cys_sg.append(xyz)
            if cerca:
                cadenas_sitio.add(ch)
        else:
            if rn in AGUAS:
                if cerca:
                    aguas_xyz.append(xyz)
            elif rn in METALES or nm in METALES:
                het[rn] += 1
                if cerca:
                    metales_xyz.append(xyz)
            else:
                het[rn] += 1
                if cerca:
                    cofactores_xyz.append(xyz)

    # huecos de numeracion por cadena
    huecos = 0
    for ch, nums in cadenas.items():
        s = sorted(set(nums))
        huecos += sum(1 for a, b in zip(s, s[1:]) if b - a > 1)
    out["n_cadenas"] = len(cadenas)
    out["n_residuos"] = sum(len(set(v)) for v in cadenas.values())
    out["huecos_numeracion"] = huecos
    out["tiene_huecos"] = bool(huecos > 0)

    # disulfuros: pares SG-SG a <2.5 A
    ss = 0
    for i in range(len(cys_sg)):
        for j in range(i + 1, len(cys_sg)):
            d2 = sum((cys_sg[i][k] - cys_sg[j][k]) ** 2 for k in range(3))
            if d2 <= 6.25:
                ss += 1
    out["n_disulfuros"] = ss

    out["cadenas_en_sitio"] = len(cadenas_sitio)
    out["sitio_entre_cadenas"] = bool(len(cadenas_sitio) > 1)
    out["metales_en_sitio"] = len(metales_xyz)
    out["cofactores_en_sitio"] = len(cofactores_xyz)
    out["aguas_en_sitio"] = len(aguas_xyz)
    out["heteroatomos_totales"] = dict(het.most_common(5))
    out["documentado_para_fep"] = bool(
        not out["tiene_huecos"] and not out["sitio_entre_cadenas"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-02: integridad del receptor")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [{"pid": p.name, "split": s} for s, m in MATS.items()
            for p in sorted(m.iterdir()) if p.is_dir()]
    print(f"[FEP-02] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            if i % 40 == 0:
                print(f"  [{i}/{len(jobs)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    # verificacion del diagnostico de MF-10: los 9 que fallaron por plantilla
    mf10 = ["1b38", "1c4u", "1d3p", "1d9i", "1dgm", "1mu8", "1nm6", "1nw5", "1flr"]
    dic = {r["pid"]: r for r in ok}
    ver = {p: {"huecos": dic[p]["huecos_numeracion"], "cadenas": dic[p]["n_cadenas"]}
           for p in mf10 if p in dic}
    con_huecos = sum(1 for v in ver.values() if v["huecos"] > 0)
    base_huecos = sum(1 for r in ok if r["tiene_huecos"]) / max(1, len(ok))

    res = {
        "n_complejos": len(filas), "n_ok": len(ok),
        "cadenas": {"mediana": int(median(r["n_cadenas"] for r in ok)),
                    "multi_cadena": sum(1 for r in ok if r["n_cadenas"] > 1)},
        "huecos_de_cadena": {
            "complejos_con_huecos": sum(1 for r in ok if r["tiene_huecos"]),
            "fraccion": round(base_huecos, 4),
            "huecos_mediana_cuando_hay": int(median(
                [r["huecos_numeracion"] for r in ok if r["tiene_huecos"]] or [0])),
        },
        "sitio": {
            "entre_cadenas": sum(1 for r in ok if r["sitio_entre_cadenas"]),
            "con_metales": sum(1 for r in ok if r["metales_en_sitio"] > 0),
            "con_cofactores": sum(1 for r in ok if r["cofactores_en_sitio"] > 0),
            "aguas_mediana": int(median(r["aguas_en_sitio"] for r in ok)),
        },
        "disulfuros": {"con_al_menos_uno": sum(1 for r in ok if r["n_disulfuros"] > 0)},
        "documentados_para_fep": sum(1 for r in ok if r["documentado_para_fep"]),
    }
    metrics = {
        "experiment_id": "FEP-02",
        "tipo": "auditoria (sin docking)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "resumen": res,
        "verificacion_diagnostico_MF10": {
            "hipotesis": ("los 9 complejos que fallaron en MF-10 con error de plantilla de "
                          "OpenMM lo hicieron por cortes de cadena dejados como terminos"),
            "detalle": ver,
            "con_huecos": con_huecos, "de": len(ver),
            "tasa_base_en_la_cohorte": round(base_huecos, 4),
        },
        "limitacion": ("un salto de numeracion no siempre es hueco fisico: hay convenciones "
                       "de numeracion no consecutiva. Se marca CANDIDATO, no defecto"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n" + json.dumps(res, ensure_ascii=False, indent=1))
    print("\nVERIFICACION del diagnostico de MF-10 (9 complejos con error de plantilla):")
    for p, v in ver.items():
        print(f"  {p}: huecos={v['huecos']:3}  cadenas={v['cadenas']}")
    print(f"  -> {con_huecos} de {len(ver)} tienen huecos | tasa base en la cohorte: "
          f"{base_huecos:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
