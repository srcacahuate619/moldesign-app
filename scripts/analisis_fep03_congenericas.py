#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep03_congenericas.py — FEP-03: ¿existen series congenéricas en los datos?

**Tipo: medición.** Auditoría del material en disco. Sin docking.

La pregunta, y por qué es la más importante de la cartera H
------------------------------------------------------------
FEP+ no calcula afinidades absolutas: calcula **energías libres relativas entre pares de
ligandos parecidos** que unen **la misma diana**. Una serie congenérica —mismo andamio,
sustituyentes que cambian poco— es el insumo obligatorio.

Si el material de MolDesign no contiene series congenéricas, **la ruta FEP+ no es
aplicable a estos datos**, y el posicionamiento «software de entrada que prepara para
FEP+» necesitaría otro conjunto. Nadie lo ha comprobado.

Qué se mide
-----------
1. **Agrupación por diana**: se extrae la secuencia del receptor (residuos con CA de la
   cadena mayor) y se agrupan los complejos por identidad de secuencia mediante
   k-meros. Dos entradas del PDB de la misma proteína caen en el mismo grupo.
2. **Parejas congenéricas**: dentro de cada grupo con ≥2 miembros, se calcula el
   **MCS** (subestructura común máxima) entre ligandos y el **tamaño de la
   perturbación** = átomos pesados que cambian.
3. **Aptitud para FEP+**: una pareja es utilizable si el MCS cubre una fracción alta de
   ambos ligandos y la perturbación es pequeña. Los umbrales se declaran abajo y no se
   ajustan después de ver los datos.

Umbrales declarados antes de mirar
----------------------------------
  * **cobertura MCS ≥ 0.70** de los átomos pesados del ligando menor;
  * **perturbación ≤ 10** átomos pesados — el rango donde FEP+ suele considerarse fiable.

Limitación declarada
--------------------
La agrupación por k-meros de secuencia es una aproximación: no distingue mutantes
puntuales de la misma proteína (que para FEP+ **sí** serían dianas distintas), y puede
unir isoformas. Y el MCS de RDKit con timeout puede devolver un resultado subóptimo en
ligandos grandes. Ambas cosas sesgan hacia **sobreestimar** el número de parejas, así
que la cifra que salga es una **cota superior**.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
MATS = {"train": PROJECT_ROOT / "data" / "molflex_train_v2",
        "valtest": PROJECT_ROOT / "data" / "molflex_valtest_v2"}
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FEP-03"
K_MER = 8
UMBRAL_SEC = 0.90
COBERTURA_MCS = 0.70
PERTURBACION_MAX = 10
MCS_TIMEOUT = 10

TRES_A_UNO = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E",
    "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F",
    "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _secuencia(pid: str) -> str:
    prot = PDBBIND / pid / f"{pid}_protein.pdb"
    if not prot.exists():
        return ""
    cad: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for l in prot.read_text(encoding="utf-8", errors="replace").splitlines():
        if l[:6].strip() == "ATOM" and len(l) > 26 and l[12:16].strip() == "CA":
            rn = l[17:20].strip()
            if rn in TRES_A_UNO:
                try:
                    cad[l[21:22]].append((int(l[22:26]), TRES_A_UNO[rn]))
                except ValueError:
                    continue
    if not cad:
        return ""
    mayor = max(cad.values(), key=len)
    return "".join(a for _, a in sorted(mayor))


def _kmers(s: str) -> set:
    return {s[i:i + K_MER] for i in range(max(0, len(s) - K_MER + 1))}


def _sec_job(job: Dict[str, str]) -> Dict[str, Any]:
    s = _secuencia(job["pid"])
    return {"pid": job["pid"], "split": job["split"], "len_sec": len(s), "sec": s}


def main() -> int:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFMCS
    RDLogger.DisableLog("rdApp.*")
    ap = argparse.ArgumentParser(description="FEP-03: series congenericas")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = [{"pid": p.name, "split": s} for s, m in MATS.items()
            for p in sorted(m.iterdir()) if p.is_dir()]
    print(f"[FEP-03] {len(jobs)} complejos | agrupando por secuencia", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        secs = list(ex.map(_sec_job, jobs))
    secs = [s for s in secs if s["len_sec"] >= 30]
    print(f"  {len(secs)} con secuencia utilizable ({round(time.time()-t0)}s)", flush=True)

    # agrupacion por identidad de k-meros (union-find simple)
    km = {s["pid"]: _kmers(s["sec"]) for s in secs}
    padre = {s["pid"]: s["pid"] for s in secs}

    def find(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    pids = [s["pid"] for s in secs]
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            a, b = km[pids[i]], km[pids[j]]
            if not a or not b:
                continue
            inter = len(a & b)
            jac = inter / min(len(a), len(b))
            if jac >= UMBRAL_SEC:
                ra, rb = find(pids[i]), find(pids[j])
                if ra != rb:
                    padre[ra] = rb
    grupos: Dict[str, List[str]] = defaultdict(list)
    for p in pids:
        grupos[find(p)].append(p)
    multi = {k: v for k, v in grupos.items() if len(v) >= 2}
    print(f"  {len(grupos)} dianas distintas | {len(multi)} con >=2 complejos "
          f"({sum(len(v) for v in multi.values())} complejos)", flush=True)

    # MCS por pareja dentro de cada grupo
    mols: Dict[str, Any] = {}
    for p in pids:
        m = Chem.MolFromMolFile(str(PDBBIND / p / f"{p}_ligand.sdf"))
        if m is not None:
            # RemoveAllHs: MolFromMolFile retiene un H en algunos ficheros y FindMCS lo
            # cuenta como atomo, mientras GetNumHeavyAtoms no -> cobertura >1 y
            # perturbacion negativa, ambas imposibles. Se compara solo sobre pesados.
            mols[p] = Chem.RemoveAllHs(m)
    parejas: List[Dict[str, Any]] = []
    for _, miembros in multi.items():
        ms = [p for p in miembros if p in mols]
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = mols[ms[i]], mols[ms[j]]
                na, nb = a.GetNumAtoms(), b.GetNumAtoms()
                try:
                    r = rdFMCS.FindMCS([a, b], timeout=MCS_TIMEOUT,
                                       ringMatchesRingOnly=True, completeRingsOnly=True)
                    ncomun = r.numAtoms
                except Exception:
                    ncomun = 0
                menor = min(na, nb)
                cob = ncomun / menor if menor else 0.0
                pert = (na - ncomun) + (nb - ncomun)
                parejas.append({
                    "pid_a": ms[i], "pid_b": ms[j], "n_a": na, "n_b": nb,
                    "mcs": ncomun, "cobertura_mcs": round(cob, 3), "perturbacion": pert,
                    "apta_fep": bool(cob >= COBERTURA_MCS and pert <= PERTURBACION_MAX),
                })

    aptas = [p for p in parejas if p["apta_fep"]]
    dianas_con_serie = len({find(p["pid_a"]) for p in aptas})
    res = {
        "n_complejos": len(secs),
        "n_dianas_distintas": len(grupos),
        "dianas_con_2_o_mas": len(multi),
        "complejos_en_dianas_multiples": sum(len(v) for v in multi.values()),
        "tamano_grupo_max": max((len(v) for v in grupos.values()), default=0),
        "n_parejas_evaluadas": len(parejas),
        "n_parejas_aptas_fep": len(aptas),
        "dianas_con_serie_congenerica": dianas_con_serie,
        "cobertura_mcs_mediana": round(median([p["cobertura_mcs"] for p in parejas]), 3)
        if parejas else None,
        "perturbacion_mediana": int(median([p["perturbacion"] for p in parejas]))
        if parejas else None,
    }
    metrics = {
        "experiment_id": "FEP-03",
        "tipo": "auditoria (sin docking)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "umbrales_declarados": {"identidad_secuencia_kmer": UMBRAL_SEC,
                                "cobertura_mcs": COBERTURA_MCS,
                                "perturbacion_max_atomos": PERTURBACION_MAX},
        "resumen": res,
        "limitacion": ("la agrupacion por k-meros no distingue mutantes puntuales (que para "
                       "FEP+ SI serian dianas distintas) y puede unir isoformas; el MCS con "
                       "timeout puede ser suboptimo. Ambos sesgos SOBREESTIMAN las parejas: "
                       "la cifra es una COTA SUPERIOR"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(OUT_DIR / "parejas.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for p in sorted(parejas, key=lambda x: -x["cobertura_mcs"]):
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print("\n" + json.dumps(res, ensure_ascii=False, indent=1))
    if aptas:
        print("\nmejores parejas congenericas:")
        for p in sorted(aptas, key=lambda x: (-x["cobertura_mcs"], x["perturbacion"]))[:10]:
            print("  %s <-> %s  MCS=%d/%d cobertura=%.2f perturbacion=%d" % (
                p["pid_a"], p["pid_b"], p["mcs"], min(p["n_a"], p["n_b"]),
                p["cobertura_mcs"], p["perturbacion"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
