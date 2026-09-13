# -*- coding: utf-8 -*-
"""
build_pose_selector_dataset.py — Ruta C, Fase 0 (docs/42_RUTA_C_PROTOCOLO.md).

Construye el dataset etiquetado de poses dockeadas a partir de tres fuentes:
  S1 flexible_redock: data/pdbbind/vina_redock_work/{pid}/{pid}_out.pdbqt
  S2 molflex:         scripts/.work_molflex_v3/{pid}/conf{cid}.out.pdbqt
  S3 ruta_a:          tmp/ruta_a/{pid}/exh{N}/out.pdbqt

Por cada MODEL de cada archivo de poses se emite un registro con:
  - etiqueta: RMSD pocket-frame (SIN alinear) vs cristal, vía
    mf.rmsd_pose_pocket (prohibido rmsd_pesados: GetBestRMS alinea).
  - features v0: vina_score, contactos ligando-receptor (2.2/4.0/6.0 A),
    varianza/rango de scores intra-archivo, densidad de clúster
    intra-complejo (poses vecinas < 2.0 A de la MISMA complejo).

Reanudable: data/pose_selector_dataset/build_progress.json mapea
(pid, fuente, file_stem) → estado. Los registros parciales viven en
data/pose_selector_dataset/records/{pid}.json y se actualizan de forma
atómica (temp + os.replace). La emisión de los JSONL ocurre en una segunda
pasada por complejo (la densidad de clúster requiere todas las poses del
complejo etiquetadas).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402
import provenance_builder as pb  # noqa: E402

WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
RUTA_A = PROJECT_ROOT / "tmp" / "ruta_a"
OUT_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
RECORDS_DIR = OUT_DIR / "records"
PROGRESS_PATH = OUT_DIR / "build_progress.json"
SPLIT_FILES = {
    "train": OUT_DIR / "poses_train.jsonl",
    "val": OUT_DIR / "poses_val.jsonl",
    "test": OUT_DIR / "poses_test.jsonl",
}
SEMILLA = 42
UMBRAL_POSITIVA = 2.0        # A — pose "tipo-cristal"
UMBRAL_CLUSTER = 2.0         # A — vecino de clúster
UMBRALES_CONTACTO = (2.2, 4.0, 6.0)
ELEMENT_RE = re.compile(r"^[A-Z][a-z]?$")
NOMBRE_REC_PREDETERMINADO = "rec.pdbqt"


# ───────────────────────── utilidades de consola/log ───────────────────────

def configurar_salida() -> None:
    """Consola Windows: UTF-8 con reemplazo y silencio de RDKit (kekulize)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.error")
        RDLogger.DisableLog("rdApp.warning")
    except Exception:
        pass


def ahora_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ───────────────────────── enumeración de trabajos ─────────────────────────

def enumerar_trabajos() -> list[dict]:
    """Devuelve la lista de trabajos (pid, fuente, file_stem, rutas)."""
    trabajos: list[dict] = []

    # S1: redock flexible exh=8.
    for out in sorted((mf.PDBBIND / "vina_redock_work").rglob("*_out.pdbqt")):
        pid = out.parent.name
        trabajos.append({
            "pid": pid, "fuente": "flexible_redock", "stem": pid,
            "out": out,
            "lig": out.parent / f"{pid}_lig.pdbqt",
            "rec": out.parent / f"{pid}_rec.pdbqt",
            "index_map": None,
        })

    # S2: MolFlex rígido (solo complejos con index_map.json).
    if WORK_V3.exists():
        for w in sorted(WORK_V3.iterdir()):
            if not w.is_dir():
                continue
            pid = w.name
            index_map = w / "index_map.json"
            if not index_map.exists():
                continue  # exclusión registrada aparte en el manifest
            for conf in sorted(w.glob("conf*.out.pdbqt")):
                trabajos.append({
                    "pid": pid, "fuente": "molflex", "stem": conf.stem,
                    "out": conf, "lig": None, "rec": w / "rec.pdbqt",
                    "index_map": index_map,
                })

    # S3: ruta_a exh1/2/4 (lig.pdbqt trae REMARK INDEX MAP embebido).
    if RUTA_A.exists():
        for pdir in sorted(RUTA_A.iterdir()):
            if not pdir.is_dir():
                continue
            pid = pdir.name
            for exh in sorted(pdir.glob("exh*")):
                out = exh / "out.pdbqt"
                if not out.exists():
                    continue
                trabajos.append({
                    "pid": pid, "fuente": "ruta_a", "stem": exh.name,
                    "out": out, "lig": exh / "lig.pdbqt", "rec": exh / "rec.pdbqt",
                    "index_map": None,
                })
    return trabajos


def clave_trabajo(t: dict) -> str:
    return f"{t['pid']}|{t['fuente']}|{t['stem']}"


# ───────────────────────── caches por proceso ──────────────────────────────

_cristal: dict[str, object] = {}
_fallo_cristal: set[str] = set()
_mapa_s1: dict[str, tuple] = {}
_rec: dict[str, object] = {}


def obtener_cristal(pid: str):
    """Cristal RDKit (cacheado). None si ilegible (sdf_unreadable)."""
    if pid in _cristal:
        return _cristal[pid]
    if pid in _fallo_cristal:
        return None
    mol = mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))
    if mol is None:
        _fallo_cristal.add(pid)
        return None
    _cristal[pid] = mol
    return mol


def pesados_del_cristal(crystal) -> list[int]:
    """Índices de átomos pesados (Z > 1) del cristal."""
    return [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]


# ───────────────────────── mapas serial → mol ──────────────────────────────
def mapa_para_redock_s1(pid: str):
    """Regenera el PDBQT flexible con meeko y valida firma (serial, elemento)
    contra el lig.pdbqt en disco. Devuelve (mapa, razón_de_fallo). Camino
    probado 2026-08-14: sin mapa dentro del lig.pdbqt de disco, la única forma
    honesta de emparejar seriales es regenerar y comparar."""
    if pid in _mapa_s1:
        return _mapa_s1[pid]
    lig_disco = mf.PDBBIND / "vina_redock_work" / pid / f"{pid}_lig.pdbqt"
    out = mf.PDBBIND / "vina_redock_work" / pid / f"{pid}_out.pdbqt"
    if not out.exists() or not lig_disco.exists():
        _mapa_s1[pid] = (None, "archivos_faltantes")
        return _mapa_s1[pid]
    crystal = obtener_cristal(pid)
    if crystal is None:
        _mapa_s1[pid] = (None, "sdf_ilegible")
        return _mapa_s1[pid]
    try:
        from meeko import MoleculePreparation
        from rdkit import Chem
        mh = Chem.AddHs(crystal)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        _rigid, flex_str, mapa, _err = mf.escribir_pdbqt(setups[0])
        if not flex_str or not mapa:
            _mapa_s1[pid] = (None, "meeko_sin_flex_o_mapa")
            return _mapa_s1[pid]

        def atomos(s):
            return [l for l in s.splitlines() if l.startswith(("ATOM", "HETATM"))]

        def firma(l):
            return (l[6:11].strip(), l[77:79].strip())

        gen = [firma(l) for l in atomos(flex_str)]
        disco = [firma(l) for l in atomos(lig_disco.read_text(encoding="utf-8"))]
        if not gen or gen != disco:
            _mapa_s1[pid] = (None, "firma_no_coincide")
            return _mapa_s1[pid]
        _mapa_s1[pid] = (mapa, None)
        return _mapa_s1[pid]
    except Exception:
        _mapa_s1[pid] = (None, "excepcion_meeko")
        return _mapa_s1[pid]


def mapa_s2(index_map: Path):
    """Lee index_map.json [[serial, mol_idx], ...] → {serial: mol_idx}."""
    try:
        raw = json.loads(index_map.read_text(encoding="utf-8"))
        return {int(s): int(m) for s, m in raw}, None
    except Exception:
        return None, "index_map_ilegible"


def mapa_s3(lig: Path):
    """Parsea las líneas REMARK INDEX MAP del lig.pdbqt de ruta_a. Formato
    verificado empíricamente 2026-08-14: pares (mol_idx 1-based, serial) — el
    mismo orden de meeko (tokens[k]=mol_idx, tokens[k+1]=serial), NO al revés.
    Verificación: la secuencia de elementos pesados del mapa coincide 1:1 con
    la del cristal para los 90 archivos (incl. 1c4u/1ejn con H explícito)."""
    try:
        mapa: dict[int, int] = {}
        for l in lig.read_text(encoding="utf-8").splitlines():
            if l.startswith("REMARK INDEX MAP"):
                toks = l.split()[3:]
                for k in range(0, len(toks) - 1, 2):
                    try:
                        mapa[int(toks[k + 1])] = int(toks[k]) - 1
                    except ValueError:
                        continue
        if not mapa:
            return None, "sin_index_map"
        return mapa, None
    except Exception:
        return None, "index_map_ilegible"


def obtener_mapa(t: dict):
    """Mapa serial→mol para el trabajo, con caché por (pid, fuente, stem)."""
    pid, fuente = t["pid"], t["fuente"]
    if fuente == "flexible_redock":
        return mapa_para_redock_s1(pid)
    if fuente == "molflex":
        if pid not in _mapa_s2_cache:
            _mapa_s2_cache[pid] = mapa_s2(t["index_map"])
        return _mapa_s2_cache[pid]
    key = (pid, t["stem"])
    if key not in _mapa_s3_cache:
        _mapa_s3_cache[key] = mapa_s3(t["lig"])
    return _mapa_s3_cache[key]


_mapa_s2_cache: dict[str, tuple] = {}
_mapa_s3_cache: dict[tuple, tuple] = {}
_rec_cache: dict[tuple, tuple] = {}


# ───────────────────────── receptor (coords pesados) ───────────────────────

def leer_rec_pesados(path: Path):
    """Coords de átomos pesados del receptor PDBQT (columna de elemento
    77:79, con fallback al nombre del átomo). Devuelve ndarray (N, 3)."""
    coords: list[tuple] = []
    try:
        lineas = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for l in lineas:
        if not l.startswith(("ATOM", "HETATM")) or len(l) < 79:
            continue
        sym = l[76:78].strip()
        if not sym or not ELEMENT_RE.match(sym):
            sym = l[77:79].strip()
        if not sym or not ELEMENT_RE.match(sym):
            sym = l[12:16].strip()[:1]
        if not sym or sym == "H":
            continue
        try:
            coords.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
        except ValueError:
            continue
    if not coords:
        return None
    return np.array(coords, dtype=np.float64)


def obtener_rec(t: dict):
    """Coords del receptor + cKDTree, cacheados por (pid, fuente, stem)."""
    key = (t["pid"], t["fuente"], t["stem"] if t["fuente"] == "ruta_a" else "")
    if key in _rec_cache:
        return _rec_cache[key]
    arr = leer_rec_pesados(t["rec"])
    if arr is None:
        _rec_cache[key] = (None, None)
        return _rec_cache[key]
    from scipy.spatial import cKDTree
    tree = cKDTree(arr)
    _rec_cache[key] = (arr, tree)
    return _rec_cache[key]


# ───────────────────────── procesamiento de un trabajo ─────────────────────

def contactos_por_pose(tree, coords_lig: np.ndarray) -> tuple[int, int, int]:
    """(n_clashes<2.2, n_contactos<4.0, n_contactos<6.0) vía query k=1."""
    dists, _ = tree.query(coords_lig, k=1)
    return (int(np.count_nonzero(dists < UMBRALES_CONTACTO[0])),
            int(np.count_nonzero(dists < UMBRALES_CONTACTO[1])),
            int(np.count_nonzero(dists < UMBRALES_CONTACTO[2])))


def procesar_trabajo(t: dict, progreso: dict) -> dict:
    """Etiqueta todos los MODELs de un archivo de poses y actualiza el
    archivo de registros del complejo. Devuelve el resumen del trabajo."""
    resumen = {"clave": clave_trabajo(t), "estado": "hecho", "razon": None,
               "n_modelos": 0, "n_registros": 0, "t_s": 0.0}
    t0 = time.monotonic()

    crystal = obtener_cristal(t["pid"])
    if crystal is None:
        resumen.update(estado="excluido", razon="sdf_ilegible")
        return resumen

    mapa, razon = obtener_mapa(t)
    if mapa is None:
        resumen.update(estado="excluido", razon=razon)
        return resumen

    _arr, tree = obtener_rec(t)
    if tree is None:
        resumen.update(estado="excluido", razon="receptor_sin_pesados")
        return resumen

    try:
        texto = t["out"].read_text(encoding="utf-8")
    except Exception:
        resumen.update(estado="excluido", razon="out_ilegible")
        return resumen
    modelos = mf.parsear_out_vina(texto)
    resumen["n_modelos"] = len(modelos)
    if not modelos:
        resumen.update(estado="excluido", razon="sin_modelos")
        return resumen

    idx_pesados = pesados_del_cristal(crystal)
    n_heavy = len(idx_pesados)
    scores = [m[0] for m in modelos]
    sc = [s for s in scores if s is not None]
    if len(sc) >= 2:
        var_score = float(np.var(sc))
        rango_score = float(max(sc) - min(sc))
    elif len(sc) == 1:
        var_score, rango_score = 0.0, 0.0
    else:
        var_score, rango_score = None, None

    registros: list[dict] = []
    n_excluidos_modelo = 0
    for mi, (score, pose) in enumerate(modelos):
        por_mol = mf.coords_pose_a_por_mol(pose, mapa)
        faltan = [i for i in idx_pesados if i not in por_mol]
        if faltan:
            # Guardia conservadora: RMSD parcial sería engañoso.
            n_excluidos_modelo += 1
            continue
        rmsd = mf.rmsd_pose_pocket(crystal, por_mol)
        if rmsd is None:
            n_excluidos_modelo += 1
            continue
        coords_lig = np.array([por_mol[i] for i in idx_pesados], dtype=np.float64)
        n_clash, n_c4, n_c6 = contactos_por_pose(tree, coords_lig)
        registros.append({
            "pid": t["pid"], "source": t["fuente"], "file_stem": t["stem"],
            "model_idx": mi, "vina_score": score,
            "rmsd": round(float(rmsd), 3), "n_heavy": n_heavy,
            "n_contacts_4": n_c4, "n_contacts_6": n_c6,
            "contacts_per_ha_4": round(n_c4 / n_heavy, 4) if n_heavy else None,
            "n_clashes": n_clash,
            "pose_score_variance": (round(var_score, 4) if var_score is not None else None),
            "pose_score_range": (round(rango_score, 4) if rango_score is not None else None),
            "_coords": {str(m): [round(float(x), 3), round(float(y), 3),
                                 round(float(z), 3)]
                        for m, (x, y, z) in por_mol.items()
                        if m in idx_pesados},
        })
    resumen["n_registros"] = len(registros)
    if n_excluidos_modelo:
        resumen["modelos_excluidos"] = n_excluidos_modelo

    actualizar_archivo_pid(t["pid"], clave_trabajo(t), registros)
    resumen["t_s"] = round(time.monotonic() - t0, 2)
    return resumen


def actualizar_archivo_pid(pid: str, clave: str, registros: list[dict]) -> None:
    """Actualiza registros/{pid}.json (temp + os.replace, atómico)."""
    path = RECORDS_DIR / f"{pid}.json"
    datos: dict = {"pid": pid, "registros": {}}
    if path.exists():
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            datos = {"pid": pid, "registros": {}}
    datos.setdefault("registros", {})[clave] = registros
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ───────────────────────── progreso ────────────────────────────────────────

def cargar_progreso() -> dict:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "en_progreso", "trabajos": {}, "emision": {},
            "iniciado": ahora_iso()}


def guardar_progreso(prog: dict) -> None:
    tmp = PROGRESS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, PROGRESS_PATH)


# ───────────────────────── segunda pasada: clúster + emisión ───────────────

def rmsd_entre_poses(a: np.ndarray, b: np.ndarray) -> float:
    """RMSD pocket-frame entre dos poses del MISMO complejo (sin alinear):
    sqrt(mean((a-b)^2)) sobre el arreglo denso de coords pesadas. La guardia
    de mapeo completo garantiza la misma malla de índices por complejo; si
    difieren, se comparan solo las posiciones compartidas (no nulas)."""
    if a.shape == b.shape:
        return float(np.sqrt(np.mean((a - b) ** 2)))
    valida = np.isfinite(a) & np.isfinite(b)
    if not valida.any():
        return float("inf")
    diff = a - b
    return float(np.sqrt(np.nanmean(diff[valida] ** 2)))


def cargar_todos_los_registros() -> dict[str, list[dict]]:
    """{pid: [registros...]} con coords densas por registro."""
    todos: dict[str, list[dict]] = {}
    if not RECORDS_DIR.exists():
        return todos
    for f in sorted(RECORDS_DIR.glob("*.json")):
        try:
            datos = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        pid = datos.get("pid", f.stem)
        lista: list[dict] = []
        for clave, regs in sorted(datos.get("registros", {}).items()):
            for r in regs:
                idx = sorted((int(k) for k in r.get("_coords", {})))
                if not idx:
                    continue
                n = max(idx) + 1
                densa = np.full((n, 3), np.nan)
                for m in idx:
                    densa[m] = r["_coords"][str(m)]
                lista.append({"reg": r, "densa": densa, "idx": idx})
        if lista:
            todos[pid] = lista
    return todos


def scaffold_del_pid(pid: str, cache: dict) -> str:
    """Scaffold Murcko del ligando cristalográfico; fallback: pid propio."""
    if pid in cache:
        return cache[pid]
    crystal = obtener_cristal(pid)
    if crystal is not None:
        try:
            # RDKit 2025.09: el submodulo se importa asi; la ruta
            # rdkit.Chem.Scaffolds.MurckoScaffold NO existe como atributo.
            from rdkit.Chem.Scaffolds import MurckoScaffold
            scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=crystal)
            if scaf:
                cache[pid] = str(scaf)
                return cache[pid]
        except Exception:
            pass
    cache[pid] = f"pid:{pid}"
    return cache[pid]


def dividir_complejos(pids: list[str], scaffolds: dict) -> dict[str, list[str]]:
    """Holdout congelado a nivel de grupo de scaffold con greedy (seed 42):
    test ~20% de los pids, val ~25% del resto, train el remanente."""
    rng = random.Random(SEMILLA)
    grupos: dict[str, list[str]] = defaultdict(list)
    for p in pids:
        grupos[scaffolds[p]].append(p)
    pids_ordenados = sorted(pids)
    n_total = len(pids_ordenados)
    objetivo_test = round(0.20 * n_total)

    claves = sorted(grupos.keys())
    rng.shuffle(claves)
    test: list[str] = []
    for k in claves:
        if len(test) >= objetivo_test:
            break
        test.extend(sorted(grupos[k]))
    test_set = set(test)

    restantes = [p for p in pids_ordenados if p not in test_set]
    objetivo_val = round(0.25 * len(restantes))
    claves_rest = sorted({scaffolds[p] for p in restantes})
    rng.shuffle(claves_rest)
    val: list[str] = []
    for k in claves_rest:
        if len(val) >= objetivo_val:
            break
        val.extend(sorted(p for p in grupos[k] if p in restantes and p not in val))
    val_set = set(val)
    train = [p for p in restantes if p not in val_set]
    return {"test": sorted(test), "val": sorted(val), "train": sorted(train)}


ORDEN_CLAVES = ["pid", "source", "file_stem", "model_idx", "vina_score", "rmsd",
                "n_heavy", "n_contacts_4", "n_contacts_6", "contacts_per_ha_4",
                "n_clashes", "pose_score_variance", "pose_score_range",
                "cluster_density"]


def emitir_split(prog: dict, todos: dict, division: dict) -> dict:
    """Emite los JSONL por pid (append incremental con progreso). Devuelve
    conteos por split."""
    conteos: dict[str, dict] = {}
    hechas = prog["emision"].get("pids", [])
    hechas_set = set(hechas)
    archivos_ok = all(p.exists() for p in SPLIT_FILES.values())
    if not archivos_ok or not hechas_set:
        # arranque limpio: borrar splits parciales y re-emitir todo
        for p in SPLIT_FILES.values():
            p.unlink(missing_ok=True)
        hechas_set = set()
        hechas = []
        prog["emision"]["pids"] = []
        guardar_progreso(prog)
    splits_de_pid = {pid: s for s, pids in division.items() for pid in pids}

    n_pendientes = 0
    for pid in sorted(todos.keys()):
        if pid in hechas_set or pid not in splits_de_pid:
            continue
        split = splits_de_pid[pid]
        lineas = []
        for entrada in todos[pid]:
            r = dict(entrada["reg"])
            r.pop("_coords", None)
            lineas.append(json.dumps({k: r[k] for k in ORDEN_CLAVES},
                                     ensure_ascii=False))
        with open(SPLIT_FILES[split], "a", encoding="utf-8") as fh:
            fh.write("\n".join(lineas) + "\n")
        hechas.append(pid)
        hechas_set.add(pid)
        conteos.setdefault(split, {"registros": 0, "pids": 0})
        conteos[split]["registros"] += len(lineas)
        conteos[split]["pids"] += 1
        n_pendientes += 1
        if n_pendientes % 50 == 0:
            prog["emision"]["pids"] = hechas
            guardar_progreso(prog)
    prog["emision"]["pids"] = hechas
    prog["emision"]["status"] = "completa"
    guardar_progreso(prog)
    return conteos


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def estadisticas(registros: list[dict]) -> dict:
    rmsds = [r["rmsd"] for r in registros]
    if not rmsds:
        return {}
    pids = sorted({r["pid"] for r in registros})
    por_pid: dict[str, list[float]] = defaultdict(list)
    for r in registros:
        por_pid[r["pid"]].append(r["rmsd"])
    con_positiva = sum(1 for p in pids if min(por_pid[p]) <= UMBRAL_POSITIVA)
    return {
        "registros": len(registros),
        "complejos": len(pids),
        "rmsd_min": round(min(rmsds), 3),
        "rmsd_mediana": round(statistics.median(rmsds), 3),
        "rmsd_max": round(max(rmsds), 3),
        "pct_poses_leq2": round(100.0 * sum(1 for r in rmsds if r <= UMBRAL_POSITIVA) / len(rmsds), 2),
        "complejos_con_positiva": con_positiva,
        "pct_complejos_con_positiva": round(100.0 * con_positiva / len(pids), 2),
    }


def escribir_manifest(prog: dict, conteos: dict, todos: dict, division: dict,
                      excluidos: dict, t_total: float) -> None:
    por_split: dict[str, list[dict]] = defaultdict(list)
    splits_de_pid = {pid: s for s, pids in division.items() for pid in pids}
    for pid, entradas in todos.items():
        split = splits_de_pid.get(pid)
        if split is None:
            continue
        for e in entradas:
            por_split[split].append(e["reg"])

    fuentes_split: dict[str, dict] = {}
    for split, regs in por_split.items():
        c = defaultdict(int)
        for r in regs:
            c[r["source"]] += 1
        fuentes_split[split] = dict(sorted(c.items()))
    total_fuentes: dict[str, int] = defaultdict(int)
    for c in fuentes_split.values():
        for k, v in c.items():
            total_fuentes[k] += v

    manifest = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "split_method": "scaffold_group_holdout_seed42",
        "semilla": SEMILLA,
        "umbral_pose_positiva_angstrom": UMBRAL_POSITIVA,
        "etiqueta": "rmsd_pocket_frame_sin_alinear",
        "conteos": {s: {"registros": len(por_split[s]),
                        "complejos": len({r["pid"] for r in por_split[s]})}
                    for s in ("train", "val", "test")},
        "por_fuente": dict(fuentes_split),
        "por_fuente_total": total_fuentes,
        "etiquetas": {s: estadisticas(por_split[s])
                      for s in ("train", "val", "test")},
        "excluidos": excluidos,
        "test_pids": division["test"],
        "test_pids_sha256": hashlib.sha256(
            json.dumps(division["test"]).encode("utf-8")).hexdigest(),
        "sha256": {p.name: sha256_archivo(p) for p in SPLIT_FILES.values()},
        "duracion_total_s": round(t_total, 1),
    }
    tmp = OUT_DIR / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, OUT_DIR / "manifest.json")


# ───────────────────────── pasada B (clúster + emisión) ────────────────────

def pasada_b(prog: dict) -> tuple[dict, dict, dict]:
    """Densidad de clúster intra-complejo, división por scaffold y emisión."""
    todos = cargar_todos_los_registros()
    n_pares = 0
    for pid, entradas in todos.items():
        lista = entradas
        n_pares += len(lista) * (len(lista) - 1) // 2
        # inicializar ANTES del doble loop: si se inicializara dentro, cada
        # iteración exterior pisaría los conteos acumulados en iteraciones
        # previas (el registro j de hoy es el i de mañana).
        for e in lista:
            e["reg"]["cluster_density"] = 0
        for i, ea in enumerate(lista):
            for j in range(i + 1, len(lista)):
                eb = lista[j]
                # misma malla de índices pesados: ambos densos completos
                if rmsd_entre_poses(ea["densa"], eb["densa"]) < UMBRAL_CLUSTER:
                    ea["reg"]["cluster_density"] += 1
                    eb["reg"]["cluster_density"] += 1
    print(f"  pasada B: {len(todos)} complejos, {n_pares} pares pose-poso evaluados")

    pids = sorted(todos.keys())
    cache_scaf: dict[str, str] = {}
    scaffolds = {p: scaffold_del_pid(p, cache_scaf) for p in pids}
    n_scaffolds = len({v for v in scaffolds.values()})
    division = dividir_complejos(pids, scaffolds)
    print(f"  scaffolds únicos: {n_scaffolds} | test {len(division['test'])} "
          f"complejos | val {len(division['val'])} | train {len(division['train'])}")

    conteos = emitir_split(prog, todos, division)
    return todos, division, conteos


# ───────────────────────── pasada A (trabajos) ─────────────────────────────

def pasada_a(prog: dict) -> dict:
    trabajos = enumerar_trabajos()
    por_fuente = defaultdict(int)
    for t in trabajos:
        por_fuente[t["fuente"]] += 1
    print(f"trabajos: {len(trabajos)} ({dict(por_fuente)})")

    excluidos: dict[str, dict] = {
        "complejos": {},
        "modelos_mapeo_incompleto": 0,
        "modelos_sin_etiqueta": 0,
    }
    hechos = prog["trabajos"]
    n_nuevos = 0
    t0_global = time.monotonic()
    for i, t in enumerate(trabajos, 1):
        clave = clave_trabajo(t)
        if clave in hechos:
            continue
        resumen = procesar_trabajo(t, prog)
        hechos[clave] = resumen
        n_nuevos += 1
        if resumen["estado"] == "excluido":
            excluidos["complejos"][f"{t['fuente']}:{t['pid']}:{t['stem']}"] = resumen["razon"]
        if resumen.get("modelos_excluidos"):
            excluidos["modelos_mapeo_incompleto"] += resumen["modelos_excluidos"]
        if i % 50 == 0 or i == len(trabajos):
            guardar_progreso(prog)
            print(f"  [{i}/{len(trabajos)}] {time.monotonic() - t0_global:.0f}s "
                  f"(nuevos: {n_nuevos})")
    print(f"pasada A completa: {n_nuevos} trabajos nuevos, "
          f"{sum(1 for v in hechos.values() if v.get('estado') == 'hecho')} hechos, "
          f"{sum(1 for v in hechos.values() if v.get('estado') == 'excluido')} excluidos")

    # Exclusiones estructurales (sin trabajo asociado).
    if WORK_V3.exists():
        for w in sorted(WORK_V3.iterdir()):
            if w.is_dir() and not (w / "index_map.json").exists():
                excluidos["complejos"][f"molflex:{w.name}"] = "sin_index_map"
    return excluidos


# ───────────────────────── flujo principal ─────────────────────────────────

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Ruta C, Fase 0: dataset pose-selector (docs/42).")
    ap.add_argument("--sidecar-out", metavar="FILE", default=None,
                    help="ruta del sidecar de provenance poses_provenance.jsonl "
                         "(FND-06): emitir junto a un dataset futuro; el dataset "
                         "historico sellado de data/pose_selector_dataset es "
                         "solo lectura")
    args = ap.parse_args()

    configurar_salida()
    t_inicio = time.monotonic()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    prog = cargar_progreso()
    if prog.get("status") == "complete":
        print("Build ya completo (build_progress.json: status=complete).")
        return

    print("== Fase 0: dataset pose-selector (Ruta C, docs/42) ==")
    excluidos = pasada_a(prog)
    guardar_progreso(prog)

    todos, division, conteos = pasada_b(prog)
    escribir_manifest(prog, conteos, todos, division, excluidos,
                      time.monotonic() - t_inicio)

    n_registros = sum(len(entradas) for entradas in todos.values())
    conteos_finales = {}
    for split, path in SPLIT_FILES.items():
        conteos_finales[split] = {
            "registros": sum(1 for _ in path.open(encoding="utf-8")),
        }
    prog["status"] = "complete"
    prog["finalizado"] = ahora_iso()
    prog["n_registros_total"] = n_registros
    prog["n_complejos"] = len(todos)
    prog["trabajos"] = {}
    prog["emision"] = {}
    guardar_progreso(prog)

    # FND-06 (cierre de garantía futura): consumo de los provenance.json de
    # los generadores. La coherencia de clave se valida ANTES de emitir; los
    # errores se reportan con detalle y nunca se emiten. El dataset histórico
    # sellado (OUT_DIR) es solo lectura: el sidecar se escribe únicamente si
    # se pasa --sidecar-out (junto a un dataset futuro).
    registros_prov, errores_prov = pb.construir_sidecar(enumerar_trabajos())
    print(f"provenance: {len(registros_prov)} registros coherentes, "
          f"{len(errores_prov)} errores")
    for detalle in errores_prov:
        print(f"  ERROR provenance: {detalle}")
    if args.sidecar_out:
        n_emitidos = pb.emitir_sidecar(registros_prov, args.sidecar_out)
        print(f"sidecar emitido: {args.sidecar_out} ({n_emitidos} registros)")
    elif registros_prov:
        print("AVISO: sidecar no emitido — el dataset de OUT_DIR está sellado "
              "(solo lectura); usa --sidecar-out junto a un dataset futuro")

    print(f"== Build completo: {n_registros} registros, {len(todos)} complejos, "
          f"{time.monotonic() - t_inicio:.0f}s ==")
    for split in ("train", "val", "test"):
        print(f"  {split}: {conteos_finales[split]['registros']} registros, "
              f"{len(division[split])} complejos")


if __name__ == "__main__":
    main()
