#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs03_param_a_r1.py — RS-03-PARAM-A-R1: energía, serialización y correspondencia atómica.

Mide lo que RS-03-PARAM-A declaró sin calcular (SCI-B-155 y SCI-B-156). Preregistro:
`scripts/artifacts_science/RS-03-PARAM-A-R1/PREREGISTRO.md`. Reconstruye los 116 ligandos como
`run_rs03_param_a.py` (sellado, no se importa: arrastra el runner remoto) y, por ligando:

* cargas NAGL normalizadas, comparadas con las selladas (G1);
* energía de punto único en la geometría del SDF (plataforma Reference) y la misma energía tras
  serializar y deserializar el `System` (G2, G3);
* correspondencia índice a índice RDKit ↔ OpenFF: elemento, carga formal y enlaces (G4), con dos
  controles negativos que el comparador tiene que ver (G5).

Corre dentro del contenedor `moldesign-science` (necesita openff y openmm):
    python scripts/run_rs03_param_a_r1.py --dentro --raiz /work --salida /work/out
y escribe `per_complex.jsonl`, `failures.jsonl` y `metrics.json` en `--salida`. Las funciones de
comparación no dependen de OpenFF y se prueban aparte (`tests/test_rs03_param_a_r1.py`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

EXP_ID = "RS-03-PARAM-A-R1"
NAGL = "openff-gnn-am1bcc-1.0.0.pt"
NAGL_SHA = "7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee"
SAGE = "openff-2.2.1.offxml"
TOL_Q = 1e-5
TOL_E = 1e-6

Atomos = List[Tuple[int, int]]                     # (número atómico, carga formal) por índice
Enlaces = set                                      # {(i, j, orden)} con i < j


def grafo_rdkit(mol) -> Tuple[Atomos, Enlaces]:
    atomos = [(a.GetAtomicNum(), a.GetFormalCharge()) for a in mol.GetAtoms()]
    enlaces = set()
    for b in mol.GetBonds():
        i, j = sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx()))
        enlaces.add((i, j, round(b.GetBondTypeAsDouble(), 1)))
    return atomos, enlaces


def grafo_openff(mol) -> Tuple[Atomos, Enlaces]:
    atomos = [(a.atomic_number, int(a.formal_charge.m)) for a in mol.atoms]
    enlaces = set()
    for b in mol.bonds:
        i, j = sorted((b.atom1_index, b.atom2_index))
        orden = 1.5 if b.is_aromatic else float(b.bond_order)
        enlaces.add((i, j, orden))
    return atomos, enlaces


def diferencias(a: Tuple[Atomos, Enlaces], b: Tuple[Atomos, Enlaces]) -> List[str]:
    """Qué falla en la identidad de índices como correspondencia entre dos grafos."""
    (at_a, en_a), (at_b, en_b) = a, b
    if len(at_a) != len(at_b):
        return [f"n_atomos {len(at_a)} != {len(at_b)}"]
    out = [f"atomo {i}: {x} != {y}" for i, (x, y) in enumerate(zip(at_a, at_b)) if x != y]
    if en_a != en_b:
        out.append(f"enlaces: {len(en_a - en_b)} sólo en el primero, {len(en_b - en_a)} sólo en el segundo")
    return out


def permutar(grafo: Tuple[Atomos, Enlaces], i: int, j: int) -> Tuple[Atomos, Enlaces]:
    """El grafo con los índices i y j intercambiados (lo que haría un mapeo equivocado)."""
    atomos, enlaces = grafo
    p = list(range(len(atomos)))
    p[i], p[j] = j, i
    nuevos = [atomos[p[k]] for k in range(len(atomos))]
    inv = {p[k]: k for k in range(len(p))}
    nuevos_en = {tuple(sorted((inv[x], inv[y]))) + (o,) for x, y, o in enlaces}
    return nuevos, nuevos_en


def par_mismo_elemento(grafo: Tuple[Atomos, Enlaces]) -> Optional[Tuple[int, int]]:
    """Dos átomos pesados del mismo elemento cuyo intercambio cambia el grafo, o None."""
    atomos, _ = grafo
    for i in range(len(atomos)):
        for j in range(i + 1, len(atomos)):
            if atomos[i] == atomos[j] and atomos[i][0] > 1 and diferencias(grafo, permutar(grafo, i, j)):
                return i, j
    return None


def par_distinto_elemento(grafo: Tuple[Atomos, Enlaces]) -> Optional[Tuple[int, int]]:
    atomos, _ = grafo
    for j in range(1, len(atomos)):
        if atomos[j][0] != atomos[0][0]:
            return 0, j
    return None


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- contenedor

def _uno(args) -> Dict:
    pid, sdf, sellado = args
    from openff.toolkit import ForceField, Molecule
    from openff.units import unit
    from openmm import Context, LangevinIntegrator, Platform, XmlSerializer
    from openmm import unit as omm
    from rdkit import Chem

    fila: Dict = {"pid": pid, "sdf_sha256": _sha(sdf)}
    fila["sdf_igual_al_sellado"] = fila["sdf_sha256"] == sellado["sdf_sha256"]
    rdmol = Chem.SDMolSupplier(str(sdf), removeHs=False, sanitize=True)[0]
    off = Molecule.from_rdkit(rdmol, allow_undefined_stereo=True)

    # G4 y G5: correspondencia, antes de tocar cargas
    g_rd, g_off = grafo_rdkit(rdmol), grafo_openff(off)
    fila["correspondencia_fallos"] = diferencias(g_rd, g_off)
    controles = {}
    p = par_mismo_elemento(g_off)
    controles["mismo_elemento"] = None if p is None else bool(diferencias(g_rd, permutar(g_off, *p)))
    p = par_distinto_elemento(g_off)
    controles["distinto_elemento"] = None if p is None else bool(diferencias(g_rd, permutar(g_off, *p)))
    fila["controles_detectados"] = controles

    # G1: cargas como el original
    off.assign_partial_charges(partial_charge_method=NAGL)
    q = [float(a.partial_charge.m) for a in off.atoms]
    formal = sum(a.GetFormalCharge() for a in rdmol.GetAtoms())
    d = (formal - sum(q)) / len(q)
    q = [x + d for x in q]
    fila["max_dif_carga_sellada"] = max(abs(a - b) for a, b in zip(q, sellado["charges"]))
    off.partial_charges = unit.Quantity(q, unit.elementary_charge)

    # G2 y G3: energía y serialización
    system = ForceField(SAGE).create_openmm_system(off.to_topology(), charge_from_molecules=[off])
    fila["n_particulas"] = system.getNumParticles()
    fila["n_atomos"] = rdmol.GetNumAtoms()
    pos = rdmol.GetConformer().GetPositions() * 0.1          # Å → nm

    def energia(sis) -> float:
        ctx = Context(sis, LangevinIntegrator(300, 1, 0.001), Platform.getPlatformByName("Reference"))
        ctx.setPositions(pos * omm.nanometer)
        return ctx.getState(getEnergy=True).getPotentialEnergy().value_in_unit(omm.kilojoule_per_mole)

    e = energia(system)
    xml = XmlSerializer.serialize(system)
    e2 = energia(XmlSerializer.deserialize(xml))
    fila.update(energia_kj_mol=e, energia_finita=math.isfinite(e), energia_deserializado_kj_mol=e2,
                dif_serializacion_kj_mol=abs(e2 - e), system_xml_sha256=hashlib.sha256(xml.encode()).hexdigest())
    return fila


def dentro(raiz: Path, salida: Path, trabajadores: int) -> int:
    import openff.toolkit
    import openmm
    from openff.nagl_models import validate_nagl_model_path

    t0 = time.time()
    sellados = {}
    for l in (raiz / "sellado_per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            sellados[r["pid"]] = r
    pids = sorted({json.loads(l)["pid"] for l in (raiz / "poses_train.jsonl").read_text(encoding="utf-8").splitlines()
                   if l.strip()})
    nagl_sha = _sha(Path(validate_nagl_model_path(NAGL)))
    tareas = [(p, raiz / "pdbbind" / p / f"{p}_ligand.sdf", sellados[p]) for p in pids]
    filas, fallos = [], []
    with ProcessPoolExecutor(trabajadores) as ex:
        for (p, _, _), fut in zip(tareas, [ex.submit(_uno, t) for t in tareas]):
            try:
                filas.append(fut.result())
            except Exception as exc:                               # se registra, no se oculta
                fallos.append({"pid": p, "error": f"{type(exc).__name__}: {exc}"})
    salida.mkdir(parents=True, exist_ok=True)
    with open(salida / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in filas)
    with open(salida / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(f, ensure_ascii=False) + "\n" for f in fallos)
    metrics = resumir(filas, fallos, len(pids), nagl_sha)
    metrics.update(experiment_id=EXP_ID, duration_seconds=round(time.time() - t0, 1),
                   entorno={"openff_toolkit": openff.toolkit.__version__, "openmm": openmm.__version__,
                            "nagl_model": NAGL, "nagl_sha256": nagl_sha, "sage": SAGE, "trabajadores": trabajadores})
    (salida / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("gates", "decision")}, ensure_ascii=False, indent=1))
    return 0


def resumir(filas: Sequence[Dict], fallos: Sequence[Dict], n: int, nagl_sha: str) -> Dict:
    ok = len(filas) == n and not fallos
    ctrl = [v for f in filas for v in f["controles_detectados"].values() if v is not None]
    sin_par = [f["pid"] for f in filas if f["controles_detectados"]["mismo_elemento"] is None]
    g = {
        "G0_entradas": ok and all(f["sdf_igual_al_sellado"] for f in filas) and nagl_sha == NAGL_SHA,
        "G1_cargas": ok and max(f["max_dif_carga_sellada"] for f in filas) <= TOL_Q,
        "G2_energia_finita": ok and all(f["energia_finita"] for f in filas),
        "G3_serializacion": ok and all(f["dif_serializacion_kj_mol"] <= TOL_E for f in filas),
        "G4_correspondencia": ok and all(not f["correspondencia_fallos"] and f["n_particulas"] == f["n_atomos"]
                                         for f in filas),
        "G5_controles": bool(ctrl) and all(ctrl),
    }
    if not (g["G2_energia_finita"] and g["G3_serializacion"] and g["G4_correspondencia"]):
        decision = "NO_GO"
    elif not (g["G0_entradas"] and g["G1_cargas"] and g["G5_controles"]):
        decision = "INCONCLUSIVE"
    else:
        decision = "GO"
    return {
        "n_total": n, "n_medidos": len(filas), "n_fallos": len(fallos),
        "max_dif_carga_sellada_e": max((f["max_dif_carga_sellada"] for f in filas), default=None),
        "max_dif_serializacion_kj_mol": max((f["dif_serializacion_kj_mol"] for f in filas), default=None),
        "energia_kj_mol_rango": [min((f["energia_kj_mol"] for f in filas), default=None),
                                 max((f["energia_kj_mol"] for f in filas), default=None)],
        "no_finitas": [f["pid"] for f in filas if not f["energia_finita"]],
        "correspondencia_con_fallos": [f["pid"] for f in filas if f["correspondencia_fallos"]],
        "controles_ejecutados": len(ctrl), "controles_detectados": sum(ctrl),
        "sin_par_mismo_elemento": sin_par,
        "gates": g, "decision": decision,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dentro", action="store_true", required=True)
    ap.add_argument("--raiz", type=Path, required=True)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--trabajadores", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()
    raise SystemExit(dentro(a.raiz, a.salida, a.trabajadores))
