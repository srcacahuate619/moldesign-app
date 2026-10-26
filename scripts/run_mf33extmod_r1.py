#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33extmod_r1.py — MF-33-EXT-MOD-R1: el BLOQUE 3 que MF-33-EXT-MOD no ejecutó (SCI-B-131).

Preregistro: `scripts/artifacts_science/MF-33-EXT-MOD-R1/PREREGISTRO.md`. Calcula `torsdof`,
`rot_bonds`, `n_heavy` y `diversidad` para los 68 complejos fuera de la cohorte de 48 con las
funciones del productor sellado de MF-33-DOSIS, y los correlaciona con `beneficio_ensemble` con
`_correlar` del productor sellado de MF-33-EXT-MOD. Los dos se importan; ninguno se modifica.

Uso:
    python scripts/run_mf33extmod_r1.py --datos D:/moldesign-build/data
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, List

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
ART = SCRIPTS / "artifacts_science"
OUT = ART / "MF-33-EXT-MOD-R1"
CUATRO = ["torsdof", "rot_bonds", "diversidad", "n_heavy"]
TOL_DIV = 1e-4


def _modulo(nombre: str, fichero: str):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / fichero)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


DOSIS = _modulo("mf33dosis", "analisis_mf33dosis_cuando_hace_falta_ensemble.py")
MOD = _modulo("mf33extmod", "analisis_mf33ext_moderadores.py")


def _jsonl(p: Path) -> List[Dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def predictores(pid: str, datos: Path) -> Dict:
    """Los cuatro descriptores, exactamente como `MF-33-DOSIS.main` los calcula."""
    import molflex as mf
    from rdkit.Chem import rdMolDescriptors

    w = datos / "molflex_train_v2" / pid / pid
    sdf = datos / "pdbbind" / pid / f"{pid}_ligand.sdf"
    f: Dict = {"pid": pid, "conf0_sha256": _sha(w / "conf0.flex.pdbqt"), "sdf_sha256": _sha(sdf)}
    pesados: set = set()
    lig = w / "conf0.flex.pdbqt"
    if lig.exists():
        txt = lig.read_text(encoding="utf-8", errors="replace")
        f["torsdof"] = DOSIS._torsdof(txt)
        for l in txt.splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 78 and l[77:79].strip().upper() not in ("H", "HD", "HS"):
                try:
                    pesados.add(int(l[6:11]))
                except ValueError:
                    pass
    crystal = mf.leer_ligando(sdf)
    if crystal is not None:
        f["rot_bonds"] = rdMolDescriptors.CalcNumRotatableBonds(crystal)
        f["n_heavy"] = crystal.GetNumHeavyAtoms()
    f["diversidad"] = DOSIS.diversidad_conformeros(w, pesados) if pesados else None
    return f


def reproduccion(calc: Dict[str, Dict], sellado: Dict[str, Dict]) -> List[str]:
    """Diferencias con MF-33-DOSIS en los 48 (G0)."""
    out = []
    for pid, s in sellado.items():
        c = calc[pid]
        for k in ("torsdof", "rot_bonds", "n_heavy"):
            if c.get(k) != s.get(k):
                out.append(f"{pid}.{k}: {c.get(k)} != {s.get(k)}")
        a, b = c.get("diversidad"), s.get("diversidad")
        if (a is None) != (b is None) or (a is not None and abs(a - b) > TOL_DIV):
            out.append(f"{pid}.diversidad: {a} != {b}")
    return out


def decidir(g0: bool, g1: bool, bloque3: Dict) -> str:
    if not (g0 and g1):
        return "INCONCLUSIVE"
    return "GO" if any(bloque3[k].get("significativo_tras_FDR") for k in CUATRO) else "NO_GO"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, required=True)
    args = ap.parse_args(argv)
    t0 = time.time()
    mod = _jsonl(ART / "MF-33-EXT-MOD" / "per_complex.jsonl")
    dosis = {r["pid"]: r for r in _jsonl(ART / "MF-33-DOSIS" / "per_complex.jsonl")}
    calc = {r["pid"]: predictores(r["pid"], args.datos) for r in mod}

    fallos_g0 = reproduccion(calc, dosis)
    fuera = []
    for r in mod:
        if r["en_cohorte_48"]:
            continue
        fila = {**calc[r["pid"]], "estrato": r["estrato"], "n_conformeros": r["n_conformeros"],
                "beneficio_ensemble": r["beneficio_ensemble"]}
        fuera.append(fila)
    completos = sum(1 for f in fuera if all(f.get(k) is not None for k in CUATRO))
    g0, g1 = not fallos_g0, completos >= 65

    bloque3 = MOD._correlar(fuera, MOD.PREDICTORES_PROSPECTIVOS, "beneficio_ensemble")
    barajado = [dict(f) for f in fuera]
    respuestas = [f["beneficio_ensemble"] for f in barajado]
    random.Random(42).shuffle(respuestas)
    for f, v in zip(barajado, respuestas):
        f["beneficio_ensemble"] = v
    control = MOD._correlar(barajado, MOD.PREDICTORES_PROSPECTIVOS, "beneficio_ensemble")

    decision = decidir(g0, g1, bloque3)
    metrics = {
        "experiment_id": "MF-33-EXT-MOD-R1", "n_fuera": len(fuera), "n_completos": completos,
        "gates": {"G0_reproduccion_48": g0, "G1_completitud": g1},
        "fallos_reproduccion": fallos_g0,
        "bloque3": bloque3, "rho_detectable_80": MOD._rho_detectable(len(fuera)),
        "supervivientes_cuatro": [k for k in CUATRO if bloque3[k].get("significativo_tras_FDR")],
        "n_conformeros_sobrevive": bool(bloque3["n_conformeros"].get("significativo_tras_FDR")),
        "control_barajado": control,
        "control_supervivientes": [k for k, v in control.items() if v.get("significativo_tras_FDR")],
        "decision": decision, "duration_seconds": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in fuera)
    (OUT / "failures.jsonl").write_text("".join(json.dumps({"fallo": x}) + "\n" for x in fallos_g0),
                                        encoding="utf-8", newline="\n")
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({k: metrics[k] for k in ("gates", "supervivientes_cuatro", "control_supervivientes",
                                              "rho_detectable_80", "decision")}, ensure_ascii=False))
    for k, v in bloque3.items():
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
