# -*- coding: utf-8 -*-
"""
ruta_c_fase1_5_v05.py — Ruta C, Fase 1.5 (v0.5), docs/42_RUTA_C_PROTOCOLO.md.

Gate G1 FALLO en Fase 1 (v0 top-1 test 0.4043 vs Vina 0.5319). Remedio C6:
reintentar con features de interacción RICAS que ya existen en el repo, ANTES
de tocar el GNN.

Features por registro (4,300 poses, 203 complejos):
  1. Shell atom counts RF-Score style (96): pares receptor(C,N,O,S) x
     ligando(C,N,O,S,F,P,Cl,Br) en cascarones (0,4],(4,8],(8,12] — definicion
     SHELL_FEATURES de rescoring/feature_extractor.py replicada al pie).
  2. ECIF-lite (56): pares (tipo extendido de proteina 8 clases) x
     (elemento de ligando 7 clases) a < 6.0 A. Tipado de proteina idéntico al
     repo (RDKit sobre el PDB de la proteina: aromatico + H explicitos),
     alineado a los atomos del PDBQT por coordenadas (tolerancia 0.01 A);
     fallback heuristico por resname/atomname para atomos sin pareja.
     NOTA HONESTA: la definicion del repo (train_pipeline) es ECIF-lite SIN
     ponderacion por conectividad extendida del ligando (el ECIF original de
     Sanchez-Cruz 2021 si pondera; aqui se replica el contrato del repo).
  3. Codigo poblacional por residuo (63): por cada tipo de residuo (20 aa +
     OTHER): # atomos pesados de ligando a < 4.0 A y < 6.0 A de CUALQUIER
     atomo del receptor de ese tipo (42) + proxy de H-bond: atomos pesados
     N/O del ligando a < 3.5 A de atomos N/O del receptor de ese tipo (21).
  4. Las 9 features baratas de Fase 1. Total = 9 + 96 + 56 + 63 = 224.

Entrenamiento/evaluacion identicos a Fase 1 (XGBRanker rank:pairwise,
relevancia = -rmsd, grupos por complejo, early stopping sobre VAL,
seed 42). Comparacion Vina / v0 / v0.5 sobre el MISMO holdout congelado.
Gate G1: PASS si v0.5 test top-1 > Vina test top-1 (0.5319).

Ablation (R-RC1 a nivel v0.5): segundo modelo SOLO con las 215 features
ricas (sin vina_score ni el resto de features baratas) — ¿las ricas solas
llevan senal de ranking o solo modulan el score de Vina?

Diagnostico honesto: Spearman por-familia vs rmsd en train (por complejo,
promediado), con proyeccion PCA-1 para familias multidimensionales.

Reanudable: data/pose_selector_dataset/features_v05_progress.jsonl guarda
(indice_global -> vector rico de 215) y se reusa en re-ejecuciones.
Artefacto: scripts/artifacts_ruta_c_fase1_5.json (escritura incremental).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402 (leer_ligando, parsear_out_vina)

DATASET_DIR = PROJECT_ROOT / "data" / "pose_selector_dataset"
RECORDS_DIR = DATASET_DIR / "records"
ARTIFACTS_V05 = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1_5.json"
ARTIFACTS_V01 = PROJECT_ROOT / "scripts" / "artifacts_ruta_c_fase1.json"
PROGRESS_FEATURES = DATASET_DIR / "features_v05_progress.jsonl"
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
RUTA_A = PROJECT_ROOT / "tmp" / "ruta_a"
TARGETS = PROJECT_ROOT / "data" / "targets"
UMBRAL_POSITIVA = 2.0

# ─── 9 features baratas de Fase 1 (mismas del dataset) ────────────────────
FEATURES_V0 = ["vina_score", "pose_score_variance", "pose_score_range", "n_heavy",
               "n_contacts_4", "n_contacts_6", "contacts_per_ha_4", "n_clashes",
               "cluster_density"]

# ─── Shell atom counts (definicion del repo, feature_extractor.py) ─────────
PROTEIN_ELEMENTS: tuple = ("C", "N", "O", "S")
LIGAND_ELEMENTS: tuple = ("C", "N", "O", "S", "F", "P", "Cl", "Br")
SHELL_BINS: tuple = ((0, 4), (4, 8), (8, 12))
SHELL_FEATURES = [f"shell_{pe}_{le}_{lo}_{hi}"
                  for pe in PROTEIN_ELEMENTS
                  for le in LIGAND_ELEMENTS
                  for lo, hi in SHELL_BINS]  # 4 x 8 x 3 = 96

# ─── ECIF-lite (definicion del repo) ───────────────────────────────────────
PROT_ECIF_TYPES: tuple = ("C_ali", "C_aro", "N_don", "N_acc",
                          "O_don", "O_acc", "S", "other")
LIG_ECIF_TYPES: tuple = ("C", "N", "O", "S", "F", "Hal", "other")
ECIF_CUTOFF = 6.0
ECIF_FEATURES = [f"ecif_{pt}_{lt}"
                 for pt in PROT_ECIF_TYPES
                 for lt in LIG_ECIF_TYPES]  # 8 x 7 = 56

# ─── Codigo poblacional por residuo ─────────────────────────────────────────
RESIDUOS_21: tuple = ("ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY",
                      "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER",
                      "THR", "TRP", "TYR", "VAL", "OTHER")
POP_FEATURES = ([f"pop_{aa}_4" for aa in RESIDUOS_21]
                + [f"pop_{aa}_6" for aa in RESIDUOS_21]
                + [f"pop_{aa}_hb" for aa in RESIDUOS_21])  # 63

FEATURES_RICH = SHELL_FEATURES + ECIF_FEATURES + POP_FEATURES  # 215
FEATURES_TOTAL = FEATURES_V0 + FEATURES_RICH                     # 224
assert len(SHELL_FEATURES) == 96 and len(ECIF_FEATURES) == 56
assert len(POP_FEATURES) == 63 and len(FEATURES_TOTAL) == 224

PARAMS = {
    "objective": "rank:pairwise",
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "early_stopping_rounds": 50,
    "n_jobs": 4,
    "random_state": 42,
}

# Codigos internos (enteros) para los conteos vectorizados.
_SHELL_PROT_CODE = {e: i for i, e in enumerate(PROTEIN_ELEMENTS)}
_SHELL_LIG_CODE = {e: i for i, e in enumerate(LIGAND_ELEMENTS)}
_ECIF_LIG_CODE = {e: i for i, e in enumerate(LIG_ECIF_TYPES)}
_ECIF_LIG_POR_ELEMENTO = {
    "C": "C", "N": "N", "O": "O", "S": "S", "F": "F",
    "Cl": "Hal", "Br": "Hal", "I": "Hal",
}
_RESCODE = {aa: i for i, aa in enumerate(RESIDUOS_21)}

# Heuristica de tipado ECIF para atomos de receptor sin pareja en el PDB.
_ARO_C_POR_RES: dict = {
    "PHE": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "TYR": {"CG", "CD1", "CD2", "CE1", "CE2", "CZ"},
    "TRP": {"CG", "CD1", "CD2", "CE2", "CE3", "CZ2", "CZ3", "CH2"},
    "HIS": {"CG", "CD2", "CE1"},
}
_N_DON_ATOMNAMES = {"ND2", "NE2", "NZ", "NE", "NH1", "NH2", "NE1"}
_O_DON_ATOMNAMES = {"OG", "OG1", "OH"}

# Mapeo AD4 -> elemento (PDBQT). H se descarta (solo atomos pesados).
AD4_A_ELEMENTO = {
    "C": "C", "A": "C", "G": "C", "N": "N", "NA": "N", "NS": "N",
    "O": "O", "OA": "O", "OS": "O", "S": "S", "SA": "S", "P": "P",
    "F": "F", "Cl": "Cl", "Br": "Br", "I": "I", "Mg": "Mg", "Ca": "Ca",
    "Zn": "Zn", "Fe": "Fe", "Mn": "Mn", "Cu": "Cu", "Co": "Co", "Ni": "Ni",
    "Se": "Se", "B": "B", "Si": "Si", "K": "K", "Na": "Na",
    "H": "H", "HD": "H", "HS": "H", "HO": "H",
}
ELEMENT_RE = re.compile(r"^[A-Z][a-z]?$")

# Ruta del receptor PDBQT por fuente.
def ruta_receptor_pdbqt(pid: str, fuente: str, stem: str) -> Path:
    if fuente == "flexible_redock":
        return PDBBIND / "vina_redock_work" / pid / f"{pid}_rec.pdbqt"
    if fuente == "molflex":
        return WORK_V3 / pid / "rec.pdbqt"
    return RUTA_A / pid / stem / "rec.pdbqt"


# ───────────────────────── utilidades de consola/artefacto ─────────────────

def configurar_salida() -> None:
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


def guardar_artefacto(art: dict, etapa: str) -> None:
    """Escritura incremental (temp + os.replace), patron de Fase 1."""
    art["_ultima_etapa"] = etapa
    tmp = ARTIFACTS_V05.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(art, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, ARTIFACTS_V05)


# ───────────────────────── parsing del receptor PDBQT ──────────────────────

def leer_rec_pdbqt(path: Path):
    """Atomos pesados del receptor PDBQT: coords (N,3) float64, elementos,
    resnames, atomnames. H descartados via columna AD4 (77:79)."""
    coords: list = []
    elems: list = []
    resnames: list = []
    atomnames: list = []
    try:
        lineas = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for l in lineas:
        if not l.startswith(("ATOM", "HETATM")) or len(l) < 79:
            continue
        ad4 = l[77:79].strip()
        elem = AD4_A_ELEMENTO.get(ad4)
        if elem is None:
            ad4 = l[76:78].strip()
            elem = AD4_A_ELEMENTO.get(ad4)
        if elem is None or elem == "H":
            continue
        try:
            coords.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
        except ValueError:
            continue
        elems.append(elem)
        resnames.append(l[17:20].strip() or "XXX")
        atomnames.append(l[12:16].strip())
    if not coords:
        return None
    return (np.array(coords, dtype=np.float64), elems, resnames, atomnames)


def cargar_pdb_rdkit(path: Path):
    """Carga el PDB de la proteina con RDKit (logica de
    rescoring/feature_extractor._load_protein_pdb: sanitizacion relajada,
    fallback sin H). Devuelve el mol o None."""
    from rdkit import Chem
    try:
        mol = Chem.MolFromPDBFile(str(path), removeHs=False, sanitize=False)
        if mol is not None:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            return mol
    except Exception:
        pass
    try:
        mol = Chem.MolFromPDBFile(str(path), removeHs=True, sanitize=False)
        if mol is not None:
            Chem.SanitizeMol(
                mol,
                Chem.SanitizeFlags.SANITIZE_ALL
                ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
            )
            return mol
    except Exception:
        pass
    return None


def tipo_ecif_prot_rdkit(atom) -> int:
    """Replica _assign_prot_ecif_type del repo: C aromatico/alifatico,
    N/O donor/acceptor por hidrogenos, S, other. Devuelve codigo entero."""
    sym = atom.GetSymbol()
    if sym == "C":
        return _ECIF_PROT_CODE["C_aro" if atom.GetIsAromatic() else "C_ali"]
    if sym == "N":
        return _ECIF_PROT_CODE["N_don" if atom.GetTotalNumHs() > 0 else "N_acc"]
    if sym == "O":
        return _ECIF_PROT_CODE["O_don" if atom.GetTotalNumHs() > 0 else "O_acc"]
    if sym == "S":
        return _ECIF_PROT_CODE["S"]
    return _ECIF_PROT_CODE["other"]


_ECIF_PROT_CODE = {t: i for i, t in enumerate(PROT_ECIF_TYPES)}


def tipo_ecif_prot_heuristica(elem: str, resname: str, atomname: str) -> int:
    """Fallback para atomos del PDBQT sin pareja en el PDB: aromaticos por
    anillo de PHE/TYR/TRP/HIS; donors N/O por nombre de atomo (backbone N
    excepto PRO); resto -> alifatico/aceptor."""
    if elem == "C":
        aro = atomname in _ARO_C_POR_RES.get(resname, set())
        return _ECIF_PROT_CODE["C_aro" if aro else "C_ali"]
    if elem == "N":
        es_don = (atomname == "N" and resname != "PRO") or atomname in _N_DON_ATOMNAMES
        return _ECIF_PROT_CODE["N_don" if es_don else "N_acc"]
    if elem == "O":
        return _ECIF_PROT_CODE["O_don" if atomname in _O_DON_ATOMNAMES else "O_acc"]
    if elem == "S":
        return _ECIF_PROT_CODE["S"]
    return _ECIF_PROT_CODE["other"]


def ruta_pdb_proteina(pid: str) -> Path | None:
    p = PDBBIND / pid / f"{pid}_protein.pdb"
    if p.exists():
        return p
    p = TARGETS / f"{pid}.pdb"
    if p.exists():
        return p
    return None


# ───────────────────────── caches de receptor y ligando ─────────────────────

_receptor_cache: dict = {}
_pdb_rdkit_cache: dict = {}
_crystal_cache: dict = {}


def obtener_receptor(pid: str, fuente: str, stem: str):
    """Dict con todo lo necesario por receptor, cacheado por
    (pid, fuente, stem). Devuelve None si el PDBQT es ilegible."""
    key = (pid, fuente, stem)
    if key in _receptor_cache:
        return _receptor_cache[key]
    resultado = None
    rp = ruta_receptor_pdbqt(pid, fuente, stem)
    if rp.exists():
        parsed = leer_rec_pdbqt(rp)
        if parsed is not None:
            coords, elems, resnames, atomnames = parsed
            resultado = _tipar_receptor(pid, coords, elems, resnames, atomnames)
    _receptor_cache[key] = resultado
    return resultado


def _tipar_receptor(pid: str, coords, elems, resnames, atomnames):
    """Tipado ECIF del receptor: RDKit sobre el PDB de la proteina con
    alineacion por coordenadas (misma estructura), fallback heuristico."""
    from scipy.spatial import cKDTree

    ecif_codes = np.empty(len(elems), dtype=np.int8)
    pdb_path = ruta_pdb_proteina(pid)
    mol = None
    if pdb_path is not None:
        if pid not in _pdb_rdkit_cache:
            _pdb_rdkit_cache[pid] = cargar_pdb_rdkit(pdb_path)
        mol = _pdb_rdkit_cache[pid]
    if mol is not None:
        atomos = list(mol.GetAtoms())
        conf = mol.GetConformer()
        pdb_coords = np.array(
            [list(conf.GetAtomPosition(i))
             for i, a in enumerate(atomos) if a.GetAtomicNum() > 1],
            dtype=np.float64)
        pdb_elems = [a.GetSymbol() for a in atomos if a.GetAtomicNum() > 1]
        pdb_codes = np.array(
            [tipo_ecif_prot_rdkit(a) for a in atomos if a.GetAtomicNum() > 1],
            dtype=np.int8)
        tree = cKDTree(pdb_coords)
        d, idx = tree.query(coords, k=1)
        match = (d < 0.01) & (np.array(pdb_elems)[idx] == np.array(elems))
        ecif_codes[match] = pdb_codes[idx[match]]
        pendientes = ~match
    else:
        pendientes = np.ones(len(elems), dtype=bool)
    for i in np.where(pendientes)[0]:
        ecif_codes[i] = tipo_ecif_prot_heuristica(elems[i], resnames[i],
                                                  atomnames[i])
    shell_codes = np.array(
        [_SHELL_PROT_CODE.get(e, -1) for e in elems], dtype=np.int8)
    res_codes = np.array(
        [_RESCODE.get(r, _RESCODE["OTHER"]) for r in resnames], dtype=np.int8)
    es_no = np.array([e in ("N", "O") for e in elems], dtype=bool)
    from scipy.spatial import cKDTree as _T
    tree = _T(coords)
    return {"coords": coords, "shell_codes": shell_codes,
            "ecif_codes": ecif_codes, "res_codes": res_codes,
            "es_no": es_no, "tree": tree, "n_hechos": int(match.sum()) if mol is not None else 0,
            "n_heuristicos": int((~match).sum()) if mol is not None else len(elems)}


def obtener_elementos_ligando(pid: str):
    """Elemento por indice de atomo del cristal (mol_idx), cacheado por pid.
    Devuelve None si el SDF es ilegible."""
    if pid in _crystal_cache:
        return _crystal_cache[pid]
    mol = mf.leer_ligando(str(PDBBIND / pid / f"{pid}_ligand.sdf"))
    if mol is None:
        _crystal_cache[pid] = None
        return None
    _crystal_cache[pid] = [a.GetSymbol() for a in mol.GetAtoms()]
    return _crystal_cache[pid]


def coords_ligando_registro(registro: dict, pid: str):
    """Coords (n_heavy,3) float64 ordenadas por mol_idx + elementos."""
    raw = registro.get("_coords")
    if not raw:
        return None
    idx = sorted(int(k) for k in raw)
    elems_crystal = obtener_elementos_ligando(pid)
    if elems_crystal is None:
        return None
    coords = np.array([raw[str(m)] for m in idx], dtype=np.float64)
    elems = [elems_crystal[m] for m in idx]
    return coords, elems


# ───────────────────────── calculo de features ricas ────────────────────────

def calcular_rich(rec: dict, lig_coords, lig_elems):
    """Shell (96) + ECIF (56) + poblacional (63) para una pose.
    Identico a las definiciones del repo: pares de atomos pesados,
    cascarones [lo,hi), ECIF a < 6.0 A. Todo vectorizado con cKDTree."""
    n_lig = len(lig_coords)
    shell = np.zeros(96, dtype=np.float64)
    ecif = np.zeros(56, dtype=np.float64)
    pop = np.zeros(63, dtype=np.float64)
    if n_lig == 0:
        return shell, ecif, pop

    lig_shell_codes = np.array(
        [_SHELL_LIG_CODE.get(e, -1) for e in lig_elems], dtype=np.int8)
    lig_ecif_codes = np.array(
        [_ECIF_LIG_CODE[_ECIF_LIG_POR_ELEMENTO.get(e, "other")]
         for e in lig_elems], dtype=np.int8)
    lig_es_no = np.array([e in ("N", "O") for e in lig_elems], dtype=bool)

    balls = rec["tree"].query_ball_point(lig_coords, r=12.0)
    lens = np.array([len(b) for b in balls])
    if lens.sum() == 0:
        return shell, ecif, pop
    lig_i = np.repeat(np.arange(n_lig), lens)
    # np.concatenate sobre listas con vacios promueve a float64: forzar
    # enteros explicitamente (guarda contra poses alejadas del receptor).
    rec_j = np.concatenate([np.asarray(b, dtype=np.intp)
                            for b in balls if len(b)])
    d = np.sqrt(((lig_coords[lig_i] - rec["coords"][rec_j]) ** 2).sum(axis=1))

    # Shell: 32 combinaciones de elementos x 3 cascarones. Orden del repo:
    # elemento_prot mayor, elemento_lig medio, cascaron menor
    # (posicion = (pe*8 + le)*3 + k).
    pe = rec["shell_codes"][rec_j]
    le = lig_shell_codes[lig_i]
    valido = (pe >= 0) & (le >= 0)
    pos_base = np.arange(32) * 3
    for k, (lo, hi) in enumerate(SHELL_BINS):
        m = valido & (d >= lo) & (d < hi)
        if m.any():
            combo = pe[m].astype(np.int64) * len(LIGAND_ELEMENTS) + le[m]
            shell[pos_base + k] = np.bincount(combo, minlength=32)

    # ECIF: pares a < 6.0 A por tipos extendidos.
    m6 = d < ECIF_CUTOFF
    if m6.any():
        pt = rec["ecif_codes"][rec_j[m6]].astype(np.int64)
        lt = lig_ecif_codes[lig_i[m6]].astype(np.int64)
        ecif[:] = np.bincount(pt * len(LIG_ECIF_TYPES) + lt, minlength=56)

    # Poblacional: distancia minima por atomo de ligando por tipo de residuo.
    rc = rec["res_codes"][rec_j]
    min_d = np.full((21, n_lig), np.inf)
    for t in range(21):
        sel = rc == t
        if sel.any():
            np.minimum.at(min_d[t], lig_i[sel], d[sel])
    pop[0:21] = (min_d < 4.0).sum(axis=1)
    pop[21:42] = (min_d < 6.0).sum(axis=1)

    # Proxy H-bond: atomo N/O de ligando a < 3.5 A de N/O del receptor,
    # contando atomos de ligando DISTINTOS por tipo de residuo.
    m_hb = (d < 3.5) & lig_es_no[lig_i] & rec["es_no"][rec_j]
    if m_hb.any():
        lig_hb = lig_i[m_hb]
        rc_hb = rc[m_hb]
        for t in range(21):
            sel = rc_hb == t
            if sel.any():
                pop[42 + t] = len(np.unique(lig_hb[sel]))
    return shell, ecif, pop


# ───────────────────────── etapa A: features resumibles ─────────────────────

def cargar_split(nombre: str) -> list[dict]:
    registros: list[dict] = []
    path = DATASET_DIR / f"poses_{nombre}.jsonl"
    for linea in path.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            registros.append(json.loads(linea))
    registros.sort(key=lambda r: (r["pid"], r["source"], r["file_stem"],
                                  r["model_idx"]))
    return registros


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_progreso_features() -> dict:
    """{indice_global: vector_rich(215)}. Si la cabecera no coincide con el
    sha256 actual de los splits, se descarta (dataset congelado)."""
    progreso: dict = {}
    if not PROGRESS_FEATURES.exists():
        return progreso
    cabecera = None
    try:
        with open(PROGRESS_FEATURES, encoding="utf-8") as fh:
            primera = fh.readline()
            if primera.strip():
                cabecera = json.loads(primera)
            if cabecera is None:
                return progreso
            sha_actual = {n: sha256_archivo(DATASET_DIR / f"poses_{n}.jsonl")
                          for n in ("train", "val", "test")}
            if cabecera.get("sha256_splits") != sha_actual:
                print("  [progreso] sha256 de splits distinto: cache invalido")
                return progreso
            for linea in fh:
                if not linea.strip():
                    continue
                reg = json.loads(linea)
                progreso[reg["idx"]] = reg["rich"]
    except Exception:
        return {}
    return progreso


def computar_features_etapa_a(art: dict) -> tuple:
    """Itera los 4,300 registros (orden canonico: train+val+test), calcula
    el vector rico de 215 y lo persiste en el JSONL de progreso."""
    splits = {nombre: cargar_split(nombre)
              for nombre in ("train", "val", "test")}
    orden: list[tuple] = []
    for nombre in ("train", "val", "test"):
        for r in splits[nombre]:
            orden.append((nombre, r))

    progreso = cargar_progreso_features()
    pendientes = [t for t in enumerate(orden) if t[0] not in progreso]
    n_ya = len(orden) - len(pendientes)
    print(f"  registros: {len(orden)} | ya cacheados: {n_ya} | pendientes: {len(pendientes)}")

    if pendientes and not PROGRESS_FEATURES.exists():
        # La cabecera solo se escribe al crear el archivo; si ya existe con
        # cabecera valida, cargar_progreso_features ya la valido.
        sha_actual = {n: sha256_archivo(DATASET_DIR / f"poses_{n}.jsonl")
                      for n in ("train", "val", "test")}
        cabecera = {"version": 1, "n_features_rich": 215,
                    "sha256_splits": sha_actual,
                    "generated_at": ahora_iso()}
        tmp = PROGRESS_FEATURES.with_suffix(".jsonl.tmp")
        tmp.write_text(json.dumps(cabecera) + "\n", encoding="utf-8")
        os.replace(tmp, PROGRESS_FEATURES)

    # Carga de coordenadas por (pid, fuente, file_stem) desde records/*.json.
    cache_registros_pid: dict = {}
    n_sin_coords = 0
    n_tipado_heuristico = 0
    n_tipado_rdkit = 0
    t0 = time.monotonic()
    with open(PROGRESS_FEATURES, "a", encoding="utf-8") as fh:
        for i, (nombre, r) in pendientes:
            pid, fuente, stem = r["pid"], r["source"], r["file_stem"]
            if pid not in cache_registros_pid:
                path = RECORDS_DIR / f"{pid}.json"
                try:
                    datos = json.loads(path.read_text(encoding="utf-8"))
                    cache_registros_pid[pid] = datos.get("registros", {})
                except Exception:
                    cache_registros_pid[pid] = {}
            clave = f"{pid}|{fuente}|{stem}"
            regs = cache_registros_pid[pid].get(clave, [])
            rec_reg = None
            for rr in regs:
                if rr.get("model_idx") == r["model_idx"]:
                    rec_reg = rr
                    break
            rico = [0.0] * 215
            if rec_reg is not None:
                cl = coords_ligando_registro(rec_reg, pid)
                if cl is not None:
                    lig_coords, lig_elems = cl
                    receptor = obtener_receptor(pid, fuente, stem)
                    if receptor is not None:
                        if receptor["n_hechos"] == 0 and receptor["n_heuristicos"] > 0:
                            n_tipado_heuristico += 1
                        else:
                            n_tipado_rdkit += 1
                        shell, ecif, pop = calcular_rich(
                            receptor, lig_coords, lig_elems)
                        rico = list(shell) + list(ecif) + list(pop)
                    else:
                        n_sin_coords += 1
                else:
                    n_sin_coords += 1
            else:
                n_sin_coords += 1
            fh.write(json.dumps({"idx": i, "split": nombre, "pid": pid,
                                 "source": fuente, "file_stem": stem,
                                 "model_idx": r["model_idx"],
                                 "rich": rico}, ensure_ascii=False) + "\n")
            progreso[i] = rico
            if (i + 1) % 500 == 0 or i + 1 == len(orden):
                print(f"  [{i + 1}/{len(orden)}] {time.monotonic() - t0:.0f}s")

    # Relectura ordenada por idx (los ya cacheados + los nuevos).
    progreso = cargar_progreso_features()
    faltantes = [i for i in range(len(orden)) if i not in progreso]
    if faltantes:
        raise RuntimeError(f"{len(faltantes)} registros sin features ricas")
    X_rich = np.array([progreso[i] for i in range(len(orden))],
                      dtype=np.float64)
    print(f"  tipado: rdkit={n_tipado_rdkit} heuristico_solo={n_tipado_heuristico} "
          f"sin_coords={n_sin_coords}")
    return splits, orden, X_rich


# ───────────────────────── matrices y evaluacion (Fase 1) ───────────────────

def preparar_matrices(registros: list[dict], X_rich: np.ndarray,
                      mediana_train: dict | None):
    """X (n, 224) = 9 baratas + 215 ricas. NaN -> mediana del train.
    y = -rmsd, grupos por complejo en orden de filas."""
    X_b = np.array([[r.get(f) for f in FEATURES_V0] for r in registros],
                   dtype=np.float64)
    X = np.hstack([X_b, X_rich])
    if mediana_train is None:
        med = {}
        for i, f in enumerate(FEATURES_V0):
            col = X_b[:, i]
            v = float(np.nanmedian(col)) if np.any(~np.isnan(col)) else 0.0
            med[f] = v if not np.isnan(v) else 0.0
    else:
        med = mediana_train
    for i, f in enumerate(FEATURES_V0):
        col = X[:, i]
        col[np.isnan(col)] = med[f]
    y = -np.array([r["rmsd"] for r in registros], dtype=np.float64)
    grupos: list[int] = []
    pids_orden: list[str] = []
    n = 0
    for r in registros:
        if not pids_orden or r["pid"] != pids_orden[-1]:
            if pids_orden:
                grupos.append(n)
                n = 0
            pids_orden.append(r["pid"])
        n += 1
    if n:
        grupos.append(n)
    return X, y, grupos, pids_orden, med


def evaluar_modelo(modelo, X: np.ndarray, registros: list[dict],
                   pids_orden: list[str]) -> dict:
    """Top-1 por complejo (argmax del score), RMSD mediano y Spearman
    promedio por complejo (>= 2 poses no constantes). Copia de Fase 1."""
    pred = modelo.predict(X)
    por_pid: dict = defaultdict(list)
    for r, p in zip(registros, pred):
        por_pid[r["pid"]].append((r, float(p)))
    from scipy.stats import spearmanr
    top1_ok = 0
    rmsds_sel: list = []
    spearmans_neg: list = []
    n_spearman = 0
    for pid in pids_orden:
        filas = por_pid[pid]
        mejor = max(filas, key=lambda rp: rp[1])[0]
        rmsds_sel.append(mejor["rmsd"])
        if mejor["rmsd"] <= UMBRAL_POSITIVA:
            top1_ok += 1
        if len(filas) >= 2:
            ps = np.array([p for _, p in filas])
            rs = np.array([r["rmsd"] for r, _ in filas])
            if np.std(ps) > 1e-12 and np.std(rs) > 1e-12:
                sp = spearmanr(ps, rs).correlation
                spearmans_neg.append(float(sp) if sp is not None and not np.isnan(sp) else 0.0)
                n_spearman += 1
    n_pids = len(pids_orden)
    return {
        "top1_rate": round(top1_ok / n_pids, 4),
        "mediana_rmsd": round(float(np.median(rmsds_sel)), 3),
        "spearman_pred_vs_rmsd_media": (round(float(np.mean(spearmans_neg)), 4)
                                        if spearmans_neg else None),
        "spearman_pred_vs_relevancia_media": (round(float(-np.mean(spearmans_neg)), 4)
                                              if spearmans_neg else None),
        "n_complejos": n_pids,
        "n_complejos_spearman": n_spearman,
    }


def entrenar_ranker(X_train, y_train, g_train, X_val, y_val, g_val) -> tuple:
    from xgboost import XGBRanker
    metricas = ["auc", "rmse"]
    modelo = None
    for metrica in metricas:
        try:
            modelo = XGBRanker(eval_metric=metrica, **PARAMS)
            modelo.fit(X_train, y_train, group=g_train,
                       eval_set=[(X_val, y_val)], eval_group=[g_val],
                       verbose=False)
            break
        except Exception as e:
            print(f"  metric '{metrica}' fallo: {type(e).__name__}; probando siguiente")
            modelo = None
    if modelo is None:
        raise RuntimeError("ninguna metrica de early-stopping funciono")
    return modelo, metrica


def pca1_proyeccion(X: np.ndarray) -> np.ndarray:
    """Primer componente principal sobre columnas estandarizadas.
    Signo fijado por convencion: el loading de mayor magnitud es positivo."""
    Z = X - X.mean(axis=0)
    std = Z.std(axis=0)
    std[std < 1e-12] = 1.0
    Z = Z / std
    u, s, vt = np.linalg.svd(Z, full_matrices=False)
    v1 = vt[0]
    k = int(np.argmax(np.abs(v1)))
    if v1[k] < 0:
        v1 = -v1
    return Z @ v1


def spearman_por_pid_media(proyeccion: np.ndarray, registros: list[dict],
                           pids_orden: list[str]) -> dict:
    """Spearman(proyeccion, rmsd) por complejo (>= 2 poses), media y
    media del valor absoluto (independiente del signo)."""
    from scipy.stats import spearmanr
    por_pid: dict = defaultdict(list)
    for r, p in zip(registros, proyeccion):
        por_pid[r["pid"]].append((float(r["rmsd"]), float(p)))
    vals: list = []
    for pid in pids_orden:
        filas = por_pid[pid]
        if len(filas) < 2:
            continue
        rs = np.array([a for a, _ in filas])
        ps = np.array([b for _, b in filas])
        if np.std(rs) < 1e-12 or np.std(ps) < 1e-12:
            continue
        sp = spearmanr(ps, rs).correlation
        if sp is not None and not np.isnan(sp):
            vals.append(float(sp))
    if not vals:
        return {"media": None, "media_abs": None, "n_complejos": 0}
    return {"media": round(float(np.mean(vals)), 4),
            "media_abs": round(float(np.mean(np.abs(vals))), 4),
            "n_complejos": len(vals)}


def diagnostico_familias(X_train, registros_train, pids_train) -> dict:
    """Spearman por-familia vs rmsd en TRAIN (media por complejo).
    vina_score directo; familias multidimensionales via PCA-1."""
    cols = {"vina_score": (0, 1), "shells": (9, 105),
            "ecif": (105, 161), "per_residuo": (161, 224)}
    out = {}
    for nombre, rango in cols.items():
        a, b = rango[0], rango[1]
        if b - a == 1:
            proy = X_train[:, a]
            metodo = "valor_directo"
        else:
            proy = pca1_proyeccion(X_train[:, a:b])
            metodo = "pca1"
        res = spearman_por_pid_media(proy, registros_train, pids_train)
        res["metodo"] = metodo
        out[nombre] = res
    return out


# ───────────────────────── flujo principal ──────────────────────────────────

def main() -> None:
    configurar_salida()
    t0 = time.monotonic()
    print("== Ruta C Fase 1.5 (v0.5): features ricas + XGBRanker (docs/42) ==")

    art: dict = {
        "generated_at": ahora_iso(),
        "protocolo": "docs/42_RUTA_C_PROTOCOLO.md",
        "fase": "1.5 (v0.5)",
        "gate_G1_criterio": "v05_top1_test > vina_top1_test (0.5319)",
        "config": {
            "features_v0": FEATURES_V0,
            "n_shell": len(SHELL_FEATURES),
            "n_ecif": len(ECIF_FEATURES),
            "n_poblacional": len(POP_FEATURES),
            "n_total": len(FEATURES_TOTAL),
            "shell_definicion": "replica feature_extractor.py: 4 elem prot x 8 elem lig x 3 cascarones (0,4),(4,8),(8,12)",
            "ecif_definicion": "replica feature_extractor.py ECIF-lite: 8 tipos prot x 7 tipos lig, pares < 6.0 A (SIN ponderacion por conectividad extendida: el repo no la implementa)",
            "poblacional_definicion": "21 tipos de residuo x (lig < 4A, lig < 6A, hbond N/O < 3.5A)",
            "tipado_ecif_receptor": "RDKit sobre PDB de proteina alineado a PDBQT por coordenadas (tol 0.01 A); fallback heuristico resname/atomname",
            "hiperparametros": PARAMS,
            "relevancia": "-rmsd",
            "imputacion_nan": "mediana_train",
        },
    }
    guardar_artefacto(art, "config")

    # ── Etapa A: features ricas (resumible) ──
    splits, orden, X_rich = computar_features_etapa_a(art)
    art["features"] = {
        "n_registros_total": len(orden),
        "duracion_etapa_A_s": round(time.monotonic() - t0, 1),
    }
    guardar_artefacto(art, "features_calculadas")

    # División de X_rich por split (el orden global es train+val+test).
    n_train = len(splits["train"])
    n_val = len(splits["val"])
    X_rich_train = X_rich[:n_train]
    X_rich_val = X_rich[n_train:n_train + n_val]
    X_rich_test = X_rich[n_train + n_val:]

    # ── Matrices ──
    X_train, y_train, g_train, pids_train, med = preparar_matrices(
        splits["train"], X_rich_train, None)
    X_val, y_val, g_val, pids_val, _ = preparar_matrices(
        splits["val"], X_rich_val, med)
    X_test, y_test, g_test, pids_test, _ = preparar_matrices(
        splits["test"], X_rich_test, med)
    print(f"  matrices: train {X_train.shape} | val {X_val.shape} | "
          f"test {X_test.shape}")

    # ── Modelo v0.5 (224 features) ──
    modelo, metrica = entrenar_ranker(X_train, y_train, g_train,
                                      X_val, y_val, g_val)
    art["v05"] = {
        "eval_metric": metrica,
        "best_iteration": int(getattr(modelo, "best_iteration", -1)),
        "best_score": (float(modelo.best_score) if modelo.best_score else None),
        "features": FEATURES_TOTAL,
    }
    art["v05"]["val"] = evaluar_modelo(modelo, X_val, splits["val"], pids_val)
    art["v05"]["test"] = evaluar_modelo(modelo, X_test, splits["test"], pids_test)
    print(f"  v0.5 val:  top1={art['v05']['val']['top1_rate']} "
          f"mediana={art['v05']['val']['mediana_rmsd']}")
    print(f"  v0.5 test: top1={art['v05']['test']['top1_rate']} "
          f"mediana={art['v05']['test']['mediana_rmsd']}")
    guardar_artefacto(art, "v05_entrenado")

    # ── Importancias (gain) ──
    booster = modelo.get_booster()
    scores = booster.get_score(importance_type="gain")
    por_idx = sorted(((int(k[1:]), float(v)) for k, v in scores.items()),
                     key=lambda kv: -kv[1])
    art["v05"]["importancias_top20"] = [
        {"feature": FEATURES_TOTAL[i], "gain": round(g, 2)}
        for i, g in por_idx[:20]]

    # ── Ablación: SOLO features ricas (215, sin vina_score ni baratas) ──
    cols_ricas = list(range(len(FEATURES_V0), len(FEATURES_TOTAL)))
    modelo_r, metrica_r = entrenar_ranker(
        X_train[:, cols_ricas], y_train, g_train,
        X_val[:, cols_ricas], y_val, g_val)
    art["ablacion_solo_ricas"] = {
        "descripcion": "XGBRanker con SOLO las 215 features ricas (shell+ecif+poblacional). R-RC1 a nivel v0.5: si iguala a Vina, la senal rica es independiente; si no, solo modula vina_score.",
        "n_features": len(cols_ricas),
        "eval_metric": metrica_r,
        "best_iteration": int(getattr(modelo_r, "best_iteration", -1)),
        "val": evaluar_modelo(modelo_r, X_val[:, cols_ricas],
                              splits["val"], pids_val),
        "test": evaluar_modelo(modelo_r, X_test[:, cols_ricas],
                               splits["test"], pids_test),
    }
    print(f"  ablacion ricas test: top1={art['ablacion_solo_ricas']['test']['top1_rate']} "
          f"mediana={art['ablacion_solo_ricas']['test']['mediana_rmsd']}")
    guardar_artefacto(art, "ablacion_ricas")

    # ── Diagnóstico por familia en train ──
    art["diagnostico_familias_train"] = diagnostico_familias(
        X_train, splits["train"], pids_train)
    guardar_artefacto(art, "diagnostico_familias")

    # ── Tabla comparativa Vina / v0 / v0.5 ──
    fase1 = {}
    if ARTIFACTS_V01.exists():
        fase1 = json.loads(ARTIFACTS_V01.read_text(encoding="utf-8"))
    tabla = {}
    for split in ("val", "test"):
        tabla[split] = {
            "vina_top1": fase1.get("vina_baseline", {}).get(split, {}).get("top1_rate"),
            "vina_mediana": fase1.get("vina_baseline", {}).get(split, {}).get("mediana_rmsd"),
            "v0_top1": fase1.get("v0", {}).get(split, {}).get("top1_rate"),
            "v0_mediana": fase1.get("v0", {}).get(split, {}).get("mediana_rmsd"),
            "v05_top1": art["v05"][split]["top1_rate"],
            "v05_mediana": art["v05"][split]["mediana_rmsd"],
            "v05_spearman": art["v05"][split]["spearman_pred_vs_rmsd_media"],
        }
    art["comparacion"] = tabla

    vina_test = fase1.get("vina_baseline", {}).get("test", {}).get("top1_rate")
    v05_test = art["v05"]["test"]["top1_rate"]
    pasa = v05_test is not None and vina_test is not None and v05_test > vina_test
    art["gate_G1_v05"] = {
        "vina_top1_test": vina_test,
        "v05_top1_test": v05_test,
        "delta": round(v05_test - vina_test, 4) if v05_test is not None and vina_test is not None else None,
        "resultado": "PASS" if pasa else "FAIL",
    }
    if not pasa:
        art["gate_G1_v05"]["remediacion_protocolo"] = (
            "docs/42 seccion 5 Fase 2: features de interaccion no superan a "
            "Vina en el holdout; el siguiente paso pre-registrado es revisar "
            "el GNN con la leccion aprendida (C6).")
    print(f"  Gate G1 v0.5: {art['gate_G1_v05']['resultado']} "
          f"(v0.5 {v05_test} vs Vina {vina_test})")

    art["caveats_honestos"] = [
        "ECIF sin ponderacion por conectividad extendida: se replica la definicion ECIF-lite del repo (train_pipeline), no el ECIF original de Sanchez-Cruz 2021.",
        "Tipado ECIF del receptor: RDKit sobre el PDB de la proteina (con H explicitos y aromaticidad percibida), alineado al PDBQT por coordenadas; atomos sin pareja usan heuristica resname/atomname.",
        "El codigo poblacional agrega por TIPO de residuo (sin distinguir cadenas ni numeros de residuo), como pide la especificacion v0.5.",
        "Las features ricas usan los atomos pesados del receptor PDBQT (el mismo receptor contra el que se dockeo); las 9 baratas de Fase 1 quedan intactas.",
        "Signo del PCA-1 en el diagnostico por familia es una convencion (loading mayor positivo); la media del |Spearman| es la lectura robusta.",
    ]
    art["duracion_total_s"] = round(time.monotonic() - t0, 1)
    guardar_artefacto(art, "completo")
    print(f"  artefacto: {ARTIFACTS_V05} ({art['duracion_total_s']}s)")


if __name__ == "__main__":
    main()
