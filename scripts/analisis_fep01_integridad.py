#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep01_integridad.py — FEP-01: integridad química del ligando.

**Tipo: medición.** Auditoría del material en disco. Sin docking.

Qué pide FEP-01
---------------
La cartera H lo define como «estereo, tautómero, protonación, carga y atom mapping
explícitos». Hoy el pipeline **no emite ninguno de los cinco**, y para un paquete que
se entrega a FEP+ cada uno es una causa de fallo silencioso:

  * **estereo indefinido** → la parametrización elige un enantiómero por su cuenta y el
    cálculo de energía libre se hace sobre una molécula que no es la del ensayo;
  * **tautómero ambiguo** → cambia el patrón de donadores/aceptores del ligando;
  * **protonación/carga** → cambia la carga neta del sistema (auditado en `REC-04a`);
  * **atom mapping** → si la correspondencia entre el SDF y el PDBQT no es biyectiva, el
    RMSD y las perturbaciones se calculan sobre átomos distintos.

La decisión silenciosa que motiva esta auditoría
------------------------------------------------
`run_mf10_relax_insitu.construir_sistema` llama a OpenFF así:

    Molecule.from_rdkit(molh, allow_undefined_stereo=True)

Es decir: el pipeline **acepta explícitamente estereoquímica indefinida** y deja que la
biblioteca resuelva. Para relajar una pose es defendible; para exportar a FEP+ no, y
nadie ha medido a cuántos ligandos afecta.

Qué se mide
-----------
Por complejo, sobre los 203 de train + val/test:

  * centros quirales **sin asignar** (`FindMolChiralCenters(includeUnassigned=True)`);
  * enlaces dobles con estereoquímica no especificada;
  * número de tautómeros que RDKit enumera (>1 ⇒ elección no declarada);
  * biyectividad del `index_map` PDBQT↔mol;
  * carga formal (se arrastra de `REC-04a` para tener los cinco campos juntos).

Limitación declarada
--------------------
La enumeración de tautómeros de RDKit es una heurística de transformaciones, no un
cálculo de poblaciones: un conteo >1 señala **ambigüedad no declarada**, no que el
fichero esté mal. Igual que en `REC-04a`, esto dimensiona el hueco; no lo corrige.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
MATS = {"train": PROJECT_ROOT / "data" / "molflex_train_v2",
        "valtest": PROJECT_ROOT / "data" / "molflex_valtest_v2"}
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "FEP-01"
MAX_TAUT = 32


def _analizar(job: Dict[str, str]) -> Dict[str, Any]:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog("rdApp.*")
    pid, split = job["pid"], job["split"]
    out: Dict[str, Any] = {"pid": pid, "split": split}
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    if not sdf.exists():
        out["error"] = "SIN_SDF"
        return out
    mol = Chem.MolFromMolFile(str(sdf))
    if mol is None:
        out["error"] = "SDF_ILEGIBLE"
        return out

    out["n_pesados"] = mol.GetNumHeavyAtoms()
    out["carga_formal"] = int(Chem.GetFormalCharge(mol))

    # ── estereo ──
    try:
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        centros = Chem.FindMolChiralCenters(mol, includeUnassigned=True,
                                            useLegacyImplementation=False)
    except Exception:
        centros = []
    out["n_centros_quirales"] = len(centros)
    out["n_centros_sin_asignar"] = sum(1 for _, v in centros if v == "?")
    dobles = 0
    for b in mol.GetBonds():
        if b.GetBondType() == Chem.BondType.DOUBLE and b.GetStereo() == Chem.BondStereo.STEREONONE:
            a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
            if a1.GetDegree() > 1 and a2.GetDegree() > 1 and not b.IsInRing():
                dobles += 1
    out["n_dobles_sin_estereo"] = dobles
    out["estereo_indefinido"] = bool(out["n_centros_sin_asignar"] > 0 or dobles > 0)

    # ── tautomeros ──
    try:
        enum = rdMolStandardize.TautomerEnumerator()
        enum.SetMaxTautomers(MAX_TAUT)
        taut = enum.Enumerate(mol)
        out["n_tautomeros"] = len(taut)
    except Exception:
        out["n_tautomeros"] = None
    out["tautomero_ambiguo"] = bool(out.get("n_tautomeros") and out["n_tautomeros"] > 1)

    # ── atom mapping PDBQT <-> mol ──
    w = MATS[split] / pid / pid / "index_map.json"
    if w.exists():
        pares = json.loads(w.read_text(encoding="utf-8"))
        seriales = [int(s) for s, _ in pares]
        indices = [int(m) for _, m in pares]
        pes = [i for i, a in enumerate(mol.GetAtoms()) if a.GetAtomicNum() > 1]
        out["mapping_biyectivo"] = bool(len(set(seriales)) == len(seriales) and
                                        len(set(indices)) == len(indices))
        out["mapping_cubre_pesados"] = bool(set(pes).issubset(set(indices)))
    else:
        out["mapping_biyectivo"] = None
        out["mapping_cubre_pesados"] = None

    out["listo_para_fep"] = bool(
        not out["estereo_indefinido"] and not out["tautomero_ambiguo"]
        and out.get("mapping_biyectivo") and out.get("mapping_cubre_pesados"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-01: integridad quimica del ligando")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [{"pid": p.name, "split": s} for s, m in MATS.items()
            for p in sorted(m.iterdir()) if p.is_dir()]
    print(f"[FEP-01] {len(jobs)} complejos, {args.workers} procesos", flush=True)

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
    n = len(ok)
    res = {
        "n_complejos": len(filas), "n_ok": n,
        "estereo": {
            "con_centros_quirales": sum(1 for r in ok if r["n_centros_quirales"] > 0),
            "con_centros_SIN_ASIGNAR": sum(1 for r in ok if r["n_centros_sin_asignar"] > 0),
            "con_dobles_sin_estereo": sum(1 for r in ok if r["n_dobles_sin_estereo"] > 0),
            "estereo_indefinido_total": sum(1 for r in ok if r["estereo_indefinido"]),
        },
        "tautomeros": {
            "ambiguos": sum(1 for r in ok if r["tautomero_ambiguo"]),
            "distribucion": dict(Counter(min(r.get("n_tautomeros") or 0, 10)
                                         for r in ok).most_common()),
        },
        "mapping": {
            "biyectivo": sum(1 for r in ok if r.get("mapping_biyectivo")),
            "cubre_pesados": sum(1 for r in ok if r.get("mapping_cubre_pesados")),
            "sin_index_map": sum(1 for r in ok if r.get("mapping_biyectivo") is None),
        },
        "listos_para_fep": sum(1 for r in ok if r["listo_para_fep"]),
    }
    metrics = {
        "experiment_id": "FEP-01",
        "tipo": "auditoria (sin docking)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "decision_silenciosa_auditada": (
            "run_mf10_relax_insitu.construir_sistema llama a "
            "Molecule.from_rdkit(molh, allow_undefined_stereo=True): el pipeline ACEPTA "
            "estereoquimica indefinida y deja que la biblioteca elija"),
        "resumen": res,
        "limitacion": ("la enumeracion de tautomeros de RDKit es heuristica de "
                       "transformaciones, no calculo de poblaciones: >1 senala AMBIGUEDAD NO "
                       "DECLARADA, no error. Dimensiona el hueco, no lo corrige"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n" + json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
