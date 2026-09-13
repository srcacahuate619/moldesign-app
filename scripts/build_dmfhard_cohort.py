#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construye la cohorte D-MF-HARD (entregable 6, docs/49 §"D-MF-HARD").

Cohorte de 44 complejos para medir regresiones de MolFlex sin re-docking:
22 difíciles (estrato primario `rot_bonds >= 15`) + 22 controles fáciles
(`rot_bonds <= 4`) emparejados sin reemplazo dentro de cada split por tamaño
de ligando (n_heavy y MW del SDF cristalográfico) con tamaño de receptor
(n residuos del protein.pdb) como desempate.

Reglas del contrato del maintainer (aplicadas literalmente):

- Universo: únicamente los 156 complejos train+val (116+40) de MF-01.
  CERO test histórico y CERO denylist FND-05 (112 pids): verificación dura.
- Estrato primario (hard): `rot_bonds >= 15` -> 22 complejos (17 train,
  5 val), verificado contra el per_complex de MF-01.
- Controles: `rot_bonds <= 4`, 17 en train y 5 en val, SIN reemplazo.
- Matching determinista y estable: los hard se procesan en orden
  (n_heavy desc, MW desc, pid asc); cada uno toma, entre los controles
  libres de su split, el que minimiza (|Δn_heavy|, |ΔMW|, |Δn_residuos|,
  pid) en orden lexicográfico. Ligando primero, receptor como desempate.
- `low_yield` (TÉCNICO): `n_poses_total <= 5` sobre la unión MF-01-UNION.
- `oracle_gap` (SECUNDARIO, dependiente de etiqueta): min-RMSD > 2.0 Å
  computado de `union_labels_*.jsonl`. NUNCA decide membresía, matching ni
  parámetros; solo se reporta como flag.
- `historical_timeout` SOLO desde registros originales hasheados:
  `scripts/artifacts_molflex_v1.json` (los 10 pids del experimento V1,
  documentados por la auditoría `docs/40_MOLFLEX_PROTOCOL.md` como
  "10 de los 74 fallidos" del redock Fase B, todos `vina_timeout_300s`).
  PROHIBIDO inferir timeout porque `n_poses == 0`.
- Determinismo byte a byte: cohort.jsonl y metrics.json idénticos entre
  corridas (sin aleatoriedad, sin dependencia de orden de diccionario).

Verificaciones DURAS (exit 1, sin salidas parciales):

1. Universo == 156 filas, pids únicos, splits 116 train + 40 val.
2. universo ∩ denylist == vacío.
3. Biyección pids(unión) == pids(universo): un pid ajeno al universo 156
   (p. ej. de test histórico) no tiene poses en la unión y hace fallar el
   build sin leer ningún archivo de test.
4. Estrato hard == 22 == 17 train + 5 val; controles 22 == 17 train + 5 val.
5. Matching sin reemplazo: 22 controles distintos, cada par del mismo split.
6. Número de líneas de labels == candidatos en la unión (integridad).

Solo biblioteca estándar de Python (json, hashlib, argparse, os, sys,
pathlib). Sin pip, sin red.

Salidas (--out-dir):
  cohort.jsonl   44 registros ordenados por cohort_id (H-01, C-01, H-02, ...)
  metrics.json   conteos por estrato/split, calidad del matching, cobertura
                 de tamaños, low_yield, oracle_gap (secundario), timeouts
                 históricos, intersecciones denylist/test, hashes de entrada
  failures.jsonl anomalías no fatales (receptor sin tamaño, SDF sin parsear)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_BASE = REPO_ROOT / "scripts" / "artifacts_science"
DATA_ROOT = REPO_ROOT / "data" / "pdbbind"
DENYLIST_PATH = ARTIFACTS_BASE / "FND-05" / "denylist_pids.json"
DEFAULT_PROTOCOL_DOC = REPO_ROOT / "docs" / "40_MOLFLEX_PROTOCOL.md"

UNIVERSE_N = 156
UNIVERSE_TRAIN = 116
UNIVERSE_VAL = 40
HARD_ROT_MIN = 15
CTRL_ROT_MAX = 4
HARD_N = 22
HARD_TRAIN = 17
HARD_VAL = 5
CTRL_N = 22
CTRL_TRAIN = 17
CTRL_VAL = 5
LOW_YIELD_MAX_POSES = 5
ORACLE_GAP_MIN_RMSD = 2.0
UNION_SOURCES = ("flexible_redock", "molflex", "ruta_a")
ORACLE_GAP_ROLE = "SECUNDARIO — no decide membresía"

MASAS_ATOMICAS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "P": 30.974, "S": 32.065, "Cl": 35.45, "Br": 79.904, "I": 126.90,
    "B": 10.81, "Na": 22.99, "Mg": 24.305, "Si": 28.085, "K": 39.098,
    "Ca": 40.078, "Fe": 55.845, "Zn": 65.38, "Se": 78.96, "Cu": 63.546,
    "Mn": 54.938, "Co": 58.933, "Ni": 58.693, "As": 74.922, "Mo": 95.95,
    "V": 50.942, "Ru": 101.07, "Rh": 102.91, "Pd": 106.42, "Ag": 107.87,
    "Cd": 112.41, "Pt": 195.08, "Au": 196.97, "Hg": 200.59,
}


def _reconfigure_stdio():
    """Fuerza UTF-8 en stdout/stderr (Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _sha256_file(path):
    """SHA-256 de un archivo, por bloques."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _escribir_atomico(path, text):
    """Escritura atómica (tmp + os.replace) para no dejar salidas parciales."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(str(tmp), str(path))


def _lineas_jsonl(path):
    """Lee un jsonl devolviendo lista de objetos; aborta con mensaje claro."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: no se pudo leer {path}: {exc}")


def _fallo_del_build(mensaje):
    """Verificación dura rota: salir 1 sin escribir salidas."""
    print(f"ERROR: {mensaje}", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Carga de entradas
# ---------------------------------------------------------------------------


def cargar_per_complex(path):
    """Carga MF-01/per_complex.jsonl y aplica las verificaciones de universo."""
    rows = _lineas_jsonl(path)
    if len(rows) != UNIVERSE_N:
        _fallo_del_build(
            f"universo != {UNIVERSE_N}: el per_complex tiene {len(rows)} filas"
        )
    pids = [r.get("pid") for r in rows]
    if len(set(pids)) != UNIVERSE_N:
        _fallo_del_build("pids duplicados en el per_complex")
    n_train = sum(1 for r in rows if r.get("split") == "train")
    n_val = sum(1 for r in rows if r.get("split") == "val")
    if (n_train, n_val) != (UNIVERSE_TRAIN, UNIVERSE_VAL):
        _fallo_del_build(
            f"splits del universo != {UNIVERSE_TRAIN}+{UNIVERSE_VAL}: "
            f"{n_train}+{n_val}"
        )
    for r in rows:
        if not isinstance(r.get("rot_bonds"), int):
            _fallo_del_build(f"rot_bonds ausente o no entero en {r}")
    return rows


def cargar_denylist(path):
    """Carga el denylist FND-05 (112 pids) y verifica intersección vacía."""
    data = json.loads(path.read_text(encoding="utf-8"))
    pids = data.get("pids")
    if not isinstance(pids, list) or len(pids) != 112 or len(set(pids)) != 112:
        _fallo_del_build(f"denylist inesperado en {path}")
    return set(pids)


def cargar_union(union_dir):
    """Carga la unión MF-01-UNION y verifica la biyección con el universo.

    Devuelve {pid: {"n_poses": {fuente: n}, "min_rmsd": float|None}}.
    """
    union_dir = Path(union_dir)
    labels = {}
    for split in ("train", "val"):
        labels_path = union_dir / f"union_labels_{split}.jsonl"
        cands_path = union_dir / f"union_candidates_{split}.jsonl"
        if not labels_path.is_file() or not cands_path.is_file():
            _fallo_del_build(f"unión incompleta: faltan archivos en {union_dir}")
        rows = _lineas_jsonl(labels_path)
        with open(cands_path, "r", encoding="utf-8") as fh:
            n_cands = sum(1 for _ in fh)
        if n_cands != len(rows):
            _fallo_del_build(
                f"integridad de la unión rota: labels={len(rows)} != "
                f"candidatos={n_cands} en {split}"
            )
        for d in rows:
            ident = d.get("identity")
            if not ident:
                _fallo_del_build("label sin identity en la unión")
            partes = ident.split("|")
            if len(partes) != 5:
                _fallo_del_build(f"identity mal formada: {ident!r}")
            isplit, pid, fuente, _stem, _idx = partes
            if isplit != split:
                _fallo_del_build(
                    f"label con split inconsistente: {ident!r} en archivo {split}"
                )
            entry = labels.setdefault(
                pid, {"n_poses": {s: 0 for s in UNION_SOURCES}, "min_rmsd": None}
            )
            if fuente not in UNION_SOURCES:
                _fallo_del_build(f"fuente desconocida en identity: {ident!r}")
            entry["n_poses"][fuente] += 1
            rmsd = d.get("rmsd")
            if isinstance(rmsd, (int, float)):
                if entry["min_rmsd"] is None or rmsd < entry["min_rmsd"]:
                    entry["min_rmsd"] = rmsd
    return labels


def cargar_timeouts_historicos(artifacts_dir, protocol_doc):
    """Timeouts históricos SOLO desde registros originales hasheados.

    Fuente autorizada: `scripts/artifacts_molflex_v1.json` (10 pids del
    experimento V1), cuya lectura como "10 de los 74 fallidos" del redock
    Fase B (todos `vina_timeout_300s`) se verifica contra la auditoría
    `docs/40_MOLFLEX_PROTOCOL.md`. No se infiere timeout desde n_poses.
    """
    v1_path = Path(artifacts_dir) / "artifacts_molflex_v1.json"
    if not v1_path.is_file():
        _fallo_del_build(f"registro original ausente: {v1_path}")
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    resultados = v1.get("results")
    if not isinstance(resultados, list) or len(resultados) != 10:
        _fallo_del_build(
            f"artifacts_molflex_v1.json inesperado: n results != 10"
        )
    pids = [str(r.get("pdb_id")) for r in resultados]
    if len(set(pids)) != 10:
        _fallo_del_build("pdb_id duplicados en artifacts_molflex_v1.json")
    if v1.get("n") != 10:
        _fallo_del_build("campo n != 10 en artifacts_molflex_v1.json")
    protocol_path = Path(protocol_doc)
    if not protocol_path.is_file():
        _fallo_del_build(f"auditoría de protocolo ausente: {protocol_path}")
    protocolo = protocol_path.read_text(encoding="utf-8")
    for frase in ("10 de los 74 fallidos", "vina_timeout_300s"):
        if frase not in protocolo:
            _fallo_del_build(
                f"la auditoría {protocol_path} no contiene {frase!r}: "
                "cadena de evidencia rota para historical_timeout"
            )
    fuente = (
        "scripts/artifacts_molflex_v1.json (V1 = 10 de los 74 fallidos del "
        "redock Fase B, todos vina_timeout_300s) + auditoría "
        "docs/40_MOLFLEX_PROTOCOL.md"
    )
    return set(pids), fuente


# ---------------------------------------------------------------------------
# Tamaños de ligando (SDF cristalográfico) y receptor (protein.pdb)
# ---------------------------------------------------------------------------


def tamano_ligando(pid):
    """(n_heavy, MW) del SDF cristalográfico; (None, None) si no parsea."""
    path = DATA_ROOT / pid / f"{pid}_ligand.sdf"
    try:
        lines = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return None, None
    natoms = None
    idx = None
    for i, ln in enumerate(lines):
        if "V2000" in ln:
            campos = ln.split()
            if len(campos) >= 2 and campos[0].isdigit():
                natoms = int(campos[0])
                idx = i
                break
    if natoms is None or idx is None:
        return None, None
    n_heavy = 0
    mw = 0.0
    for j in range(idx + 1, idx + 1 + natoms):
        if j >= len(lines):
            return None, None
        simbolo = lines[j][31:34].strip()
        elemento = "".join(ch for ch in simbolo if ch.isalpha())
        if elemento in ("", "H", "D"):
            continue
        n_heavy += 1
        mw += MASAS_ATOMICAS.get(elemento, 0.0)
    if n_heavy == 0:
        return None, None
    return n_heavy, round(mw, 3)


def tamano_receptor(pid):
    """(n_residuos, n_atomos) del protein.pdb; (None, None) si no parsea."""
    path = DATA_ROOT / pid / f"{pid}_protein.pdb"
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    residuos = set()
    n_atomos = 0
    with fh:
        for ln in fh:
            if ln.startswith("ATOM"):
                n_atomos += 1
                residuos.add((ln[21], ln[22:26].strip(), ln[26]))
    if not residuos:
        return None, None
    return len(residuos), n_atomos


# ---------------------------------------------------------------------------
# Matching determinista
# ---------------------------------------------------------------------------


def match_estable(hards, controles, tamaños):
    """Empareja hards y controles del mismo split, sin reemplazo.

    Procesa los hards en orden (n_heavy desc, MW desc, pid asc) y asigna a
    cada uno el control libre que minimiza la clave lexicográfica
    (|Δn_heavy|, |ΔMW|, |Δn_residuos|, pid). Devuelve lista de pares
    (hard, control) en ese orden de procesamiento.
    """
    def orden_hard(pid):
        nh, mw = tamaños[pid]["ligando"]
        return (-(nh if nh is not None else 0),
                -(mw if mw is not None else 0.0), pid)

    hards_ordenados = sorted(hards, key=orden_hard)
    libres = set(controles)
    pares = []
    for h in hards_ordenados:
        hnh, hmw = tamaños[h]["ligando"]
        hres = tamaños[h]["receptor"][0]
        mejor = None
        mejor_clave = None
        for c in sorted(libres):
            cnh, cmw = tamaños[c]["ligando"]
            cres = tamaños[c]["receptor"][0]
            clave = (
                abs((cnh or 0) - (hnh or 0)),
                abs((cmw or 0.0) - (hmw or 0.0)),
                abs((cres or 0) - (hres or 0)),
                c,
            )
            if mejor_clave is None or clave < mejor_clave:
                mejor_clave = clave
                mejor = c
        libres.remove(mejor)
        pares.append((h, mejor))
    return pares


# ---------------------------------------------------------------------------
# Construcción de registros
# ---------------------------------------------------------------------------


def construir_registros(rows, labels, denylist, timeout_pids, timeout_fuente,
                        tamaños, failures):
    """Selecciona estratos, empareja y construye los 44 registros."""
    por_pid = {r["pid"]: r for r in rows}

    hards = sorted(p for p, r in por_pid.items() if r["rot_bonds"] >= HARD_ROT_MIN)
    n_hard_train = sum(1 for p in hards if por_pid[p]["split"] == "train")
    n_hard_val = sum(1 for p in hards if por_pid[p]["split"] == "val")
    if (len(hards), n_hard_train, n_hard_val) != (HARD_N, HARD_TRAIN, HARD_VAL):
        _fallo_del_build(
            f"estrato hard != {HARD_N} ({HARD_TRAIN}+{HARD_VAL}): "
            f"{len(hards)} ({n_hard_train}+{n_hard_val})"
        )

    pool = {}
    for p, r in por_pid.items():
        if r["rot_bonds"] <= CTRL_ROT_MAX:
            pool.setdefault(r["split"], []).append(p)
    for split, esperado in (("train", CTRL_TRAIN), ("val", CTRL_VAL)):
        if len(pool.get(split, [])) < esperado:
            _fallo_del_build(
                f"pool de controles {split} insuficiente: "
                f"{len(pool.get(split, []))} < {esperado}"
            )
    pool = {s: sorted(ps) for s, ps in pool.items()}

    # Tamaños solo para hards + pool de controles (66 pids).
    for p in sorted(set(hards) | set(pool["train"]) | set(pool["val"])):
        nh, mw = tamano_ligando(p)
        if nh is None:
            failures.append({
                "pid": p,
                "motivo": "ligando_sin_parsear",
                "detalle": "SDF cristalográfico ausente o ilegible; "
                           "excluido del matching si era control",
            })
        nres, natom = tamano_receptor(p)
        if nres is None:
            failures.append({
                "pid": p,
                "motivo": "receptor_sin_tamano",
                "detalle": "protein.pdb ausente o sin registros ATOM; "
                           "receptor_size = null en el registro",
            })
        tamaños[p] = {"ligando": (nh, mw), "receptor": (nres, natom)}

    # Los controles sin ligando parseado no pueden puntuarse en el matching.
    pares = {}
    for split, esperado in (("train", CTRL_TRAIN), ("val", CTRL_VAL)):
        h_split = sorted(p for p in hards if por_pid[p]["split"] == split)
        c_split = [
            p for p in pool[split]
            if tamaños[p]["ligando"][0] is not None
        ]
        if len(c_split) < esperado:
            _fallo_del_build(
                f"controles {split} con SDF parseable insuficientes: "
                f"{len(c_split)} < {esperado}"
            )
        for h, c in match_estable(h_split, c_split, tamaños):
            pares[h] = c

    controles_seleccionados = sorted(pares.values())
    if len(set(controles_seleccionados)) != CTRL_N:
        _fallo_del_build("matching con reemplazo detectado (controles repetidos)")
    if len(pares) != HARD_N:
        _fallo_del_build(f"n pares != {HARD_N}: {len(pares)}")
    for h, c in pares.items():
        if por_pid[h]["split"] != por_pid[c]["split"]:
            _fallo_del_build(f"par de splits distintos: {h}-{c}")
        if por_pid[h]["rot_bonds"] < HARD_ROT_MIN:
            _fallo_del_build(f"hard con rot < {HARD_ROT_MIN}: {h}")
        if por_pid[c]["rot_bonds"] > CTRL_ROT_MAX:
            _fallo_del_build(f"control con rot > {CTRL_ROT_MAX}: {c}")

    seleccion = set(hards) | set(controles_seleccionados)
    if len(seleccion) != 2 * HARD_N:
        _fallo_del_build("cohorte sin 44 pids distintos")
    if seleccion & denylist:
        _fallo_del_build(
            f"cohorte intersecta el denylist: {sorted(seleccion & denylist)}"
        )
    if not seleccion <= set(por_pid):
        _fallo_del_build(
            f"pids fuera del universo 156: {sorted(seleccion - set(por_pid))}"
        )

    registros = []
    for idx, h in enumerate(hards, start=1):
        c = pares[h]
        for cohort_id, p in ((f"H-{idx:02d}", h), (f"C-{idx:02d}", c)):
            r = por_pid[p]
            nh, mw = tamaños[p]["ligando"]
            nres, natom = tamaños[p]["receptor"]
            lab = labels.get(p, {"n_poses": {}, "min_rmsd": None})
            n_poses = {s: lab["n_poses"].get(s, 0) for s in UNION_SOURCES}
            n_total = sum(n_poses.values())
            low_yield = n_total <= LOW_YIELD_MAX_POSES
            min_rmsd = lab.get("min_rmsd")
            oracle_gap = (
                isinstance(min_rmsd, (int, float))
                and min_rmsd > ORACLE_GAP_MIN_RMSD
            )
            es_timeout = p in timeout_pids
            registros.append({
                "cohort_id": cohort_id,
                "pair_id": f"P-{idx:02d}",
                "split": r["split"],
                "pid": p,
                "stratum": "hard" if p == h else "control",
                "rot_bonds": r["rot_bonds"],
                "ligand_size": (
                    {"n_heavy": nh, "mw": mw} if nh is not None else None
                ),
                "receptor_size": (
                    {"n_residues": nres, "n_atoms": natom}
                    if nres is not None else None
                ),
                "receptor_size_note": (
                    None if nres is not None
                    else "protein.pdb sin registros ATOM o ausente"
                ),
                "n_poses_total": n_total,
                "n_poses": n_poses,
                "low_yield": low_yield,
                "historical_timeout": es_timeout,
                "historical_timeout_source": timeout_fuente if es_timeout else None,
                "oracle_gap": oracle_gap,
                "oracle_gap_role": ORACLE_GAP_ROLE,
            })
    return registros, hards, controles_seleccionados, pares


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def _round3(v):
    return round(v, 3)


def _deltas(pares, tamaños):
    dnh = [abs((tamaños[c]["ligando"][0] or 0) - (tamaños[h]["ligando"][0] or 0))
           for h, c in pares]
    dmw = [abs((tamaños[c]["ligando"][1] or 0.0) - (tamaños[h]["ligando"][1] or 0.0))
           for h, c in pares]
    return dnh, dmw


def _resumen_delta(valores):
    if not valores:
        return {"media": None, "rango": [None, None], "suma": 0}
    return {
        "media": _round3(sum(valores) / len(valores)),
        "rango": [_round3(min(valores)), _round3(max(valores))],
        "suma": _round3(sum(valores)),
    }


def construir_metrics(rows, labels, denylist, timeout_pids, timeout_fuente,
                      tamaños, pares, hards, controles, failures,
                      args, hashes_entrada):
    """Agrega las métricas del entregable."""
    por_pid = {r["pid"]: r for r in rows}
    seleccion = hards + controles
    low_yield_pids = []
    oracle_gap_pids = []
    timeout_cohort = []
    for p in seleccion:
        lab = labels.get(p, {})
        n_total = sum(lab.get("n_poses", {}).get(s, 0) for s in UNION_SOURCES)
        if n_total <= LOW_YIELD_MAX_POSES:
            low_yield_pids.append(p)
        min_rmsd = lab.get("min_rmsd")
        if isinstance(min_rmsd, (int, float)) and min_rmsd > ORACLE_GAP_MIN_RMSD:
            oracle_gap_pids.append(p)
        if p in timeout_pids:
            timeout_cohort.append(p)

    dnh, dmw = _deltas(list(pares.items()), tamaños)
    por_split = {}
    for split in ("train", "val"):
        sub = [(h, c) for h, c in pares.items() if por_pid[h]["split"] == split]
        sdnh, sdmw = _deltas(sub, tamaños)
        por_split[split] = {
            "n_pares": len(sub),
            "delta_n_heavy": _resumen_delta(sdnh),
            "delta_mw": _resumen_delta(sdmw),
        }

    n_lig_null = sum(
        1 for p in seleccion if tamaños[p]["ligando"][0] is None
    )
    n_rec_null = sum(
        1 for p in seleccion if tamaños[p]["receptor"][0] is None
    )

    return {
        "experiment": "D-MF-HARD",
        "entregable": 6,
        "universe": {
            "n_total": UNIVERSE_N,
            "n_train": UNIVERSE_TRAIN,
            "n_val": UNIVERSE_VAL,
            "fuente": "scripts/artifacts_science/MF-01/per_complex.jsonl",
        },
        "denylist": {
            "n": 112,
            "interseccion_con_universo": len(denylist & set(por_pid)),
            "interseccion_con_cohorte": len(denylist & set(seleccion)),
            "fuente": "scripts/artifacts_science/FND-05/denylist_pids.json",
        },
        "test_historico": {
            "archivos_leidos": 0,
            "interseccion": 0,
            "nota": (
                "no se lee ningún archivo de test; por construcción todos los "
                "pids seleccionados pertenecen al universo 156 train+val y la "
                "biyección pids(unión)==pids(universo) lo verifica"
            ),
        },
        "strata": {
            "hard": {
                "n": HARD_N, "train": HARD_TRAIN, "val": HARD_VAL,
                "criterio": f"rot_bonds >= {HARD_ROT_MIN}",
                "pids": hards,
            },
            "control": {
                "n": CTRL_N, "train": CTRL_TRAIN, "val": CTRL_VAL,
                "criterio": f"rot_bonds <= {CTRL_ROT_MAX}, emparejados sin "
                             "reemplazo dentro de cada split",
                "pids": controles,
            },
        },
        "matching": {
            "metodo": (
                "greedy estable: hards en orden (n_heavy desc, MW desc, "
                "pid asc); cada hard toma el control libre de su split con "
                "mínimo (|Δn_heavy|, |ΔMW|, |Δn_residuos|, pid) lexicográfico"
            ),
            "sin_reemplazo": True,
            "n_pares": len(pares),
            "delta_n_heavy": _resumen_delta(dnh),
            "delta_mw": _resumen_delta(dmw),
            "por_split": por_split,
        },
        "ligand_size": {
            "cobertura": f"{len(seleccion) - n_lig_null}/{len(seleccion)}",
            "n_null": n_lig_null,
            "fuente": "SDF cristalográfico data/pdbbind/{pid}/{pid}_ligand.sdf",
        },
        "receptor_size": {
            "cobertura": f"{len(seleccion) - n_rec_null}/{len(seleccion)}",
            "n_null": n_rec_null,
            "fuente": "n residuos (ATOM, por cadena+resSeq+iCode) de "
                      "data/pdbbind/{pid}/{pid}_protein.pdb",
        },
        "historical_timeout": {
            "n": len(timeout_cohort),
            "pids": timeout_cohort,
            "fuente": timeout_fuente,
            "prohibicion_aplicada": "no se infirió timeout desde n_poses == 0",
        },
        "low_yield": {
            "n": len(low_yield_pids),
            "pids": low_yield_pids,
            "umbral": f"n_poses_total <= {LOW_YIELD_MAX_POSES} "
                       "(unión MF-01-UNION)",
            "tipo": "indicador TÉCNICO de pocas poses válidas",
        },
        "oracle_gap": {
            "n": len(oracle_gap_pids),
            "pids": oracle_gap_pids,
            "umbral": f"min rmsd > {ORACLE_GAP_MIN_RMSD} Å "
                       "(union_labels_*.jsonl)",
            "rol": "SECUNDARIO — dependiente de etiqueta; no decide "
                    "membresía, matching ni parámetros",
        },
        "anomalias": {
            "n": len(failures),
            "nota": "anomalías no fatales documentadas en failures.jsonl",
        },
        "hashes_entrada": hashes_entrada,
        "determinismo": {
            "nota": "sin aleatoriedad ni dependencia del orden de iteración; "
                     "dos corridas producen cohort.jsonl y metrics.json "
                     "byte-idénticos (verificado externamente con sha256)",
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="build_dmfhard_cohort.py",
        description=(
            "Construye la cohorte D-MF-HARD (entregable 6): 22 hard "
            "(rot_bonds>=15) + 22 controles fáciles emparejados sin "
            "reemplazo, universo 156 train+val, sin test ni denylist."
        ),
    )
    parser.add_argument(
        "--mf01-per-complex", required=True, metavar="JSONL",
        help="scripts/artifacts_science/MF-01/per_complex.jsonl (universo 156)",
    )
    parser.add_argument(
        "--union-dir", required=True, metavar="DIR",
        help="scripts/artifacts_science/MF-01-UNION (union_labels_*.jsonl)",
    )
    parser.add_argument(
        "--out-dir", required=True, metavar="DIR",
        help="directorio de salida de la cohorte",
    )
    parser.add_argument(
        "--artifacts-dir", default=str(REPO_ROOT / "scripts"), metavar="DIR",
        help="directorio con artifacts_molflex_*.json (default: scripts/)",
    )
    parser.add_argument(
        "--protocol-doc", default=str(DEFAULT_PROTOCOL_DOC), metavar="FILE",
        help="docs/40_MOLFLEX_PROTOCOL.md (auditoría original)",
    )
    return parser


def main(argv=None):
    _reconfigure_stdio()
    args = _build_parser().parse_args(argv)

    per_complex_path = Path(args.mf01_per_complex)
    union_dir = Path(args.union_dir)
    out_dir = Path(args.out_dir)

    rows = cargar_per_complex(per_complex_path)
    denylist = cargar_denylist(DENYLIST_PATH)
    universe_pids = {r["pid"] for r in rows}

    if denylist & universe_pids:
        _fallo_del_build(
            "universo intersecta el denylist: "
            f"{sorted(denylist & universe_pids)}"
        )

    labels = cargar_union(union_dir)
    if set(labels) != universe_pids:
        _fallo_del_build(
            "biyección pids(unión) != pids(universo) rota: "
            f"fuera de la unión {sorted(universe_pids - set(labels))}, "
            f"fuera del universo {sorted(set(labels) - universe_pids)}"
        )

    timeout_pids, timeout_fuente = cargar_timeouts_historicos(
        args.artifacts_dir, args.protocol_doc
    )

    tamaños = {}
    failures = []
    registros, hards, controles, pares = construir_registros(
        rows, labels, denylist, timeout_pids, timeout_fuente, tamaños, failures
    )

    hashes_entrada = {
        "mf01_per_complex": _sha256_file(per_complex_path),
        "union_labels_train": _sha256_file(union_dir / "union_labels_train.jsonl"),
        "union_labels_val": _sha256_file(union_dir / "union_labels_val.jsonl"),
        "denylist": _sha256_file(DENYLIST_PATH),
        "artifacts_molflex_v1": _sha256_file(
            Path(args.artifacts_dir) / "artifacts_molflex_v1.json"
        ),
        "protocolo_40": _sha256_file(Path(args.protocol_doc)),
    }

    metrics = construir_metrics(
        rows, labels, denylist, timeout_pids, timeout_fuente,
        tamaños, pares, hards, controles, failures, args, hashes_entrada,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    lineas_cohort = [
        json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n"
        for r in registros
    ]
    lineas_failures = [
        json.dumps(f, ensure_ascii=False, separators=(",", ":")) + "\n"
        for f in failures
    ]
    _escribir_atomico(out_dir / "cohort.jsonl", "".join(lineas_cohort))
    _escribir_atomico(
        out_dir / "metrics.json",
        json.dumps(metrics, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )
    _escribir_atomico(out_dir / "failures.jsonl", "".join(lineas_failures))

    n_timeout = len([r for r in registros if r["historical_timeout"]])
    n_low = len([r for r in registros if r["low_yield"]])
    n_gap = len([r for r in registros if r["oracle_gap"]])
    print(
        f"OK D-MF-HARD: {len(registros)} registros "
        f"({HARD_N} hard + {CTRL_N} controles), {len(pares)} pares "
        f"({HARD_TRAIN}+{HARD_VAL}/{CTRL_TRAIN}+{CTRL_VAL}), "
        f"universo {UNIVERSE_N}, denylist∩cohorte=0, "
        f"historical_timeout={n_timeout}, low_yield={n_low}, "
        f"oracle_gap={n_gap} (secundario), anomalías={len(failures)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
