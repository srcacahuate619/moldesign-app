# -*- coding: utf-8 -*-
"""
rescoring/pose_selector/feature_extractor.py — extractor de las 224 features
raw del selector v0.6 (contrato v0.5, scripts/ruta_c_fase1_5_v05.py).

Contrato de features (orden EXACTO, verificado contra el cache congelado
data/pose_selector_dataset/features_v05_progress.jsonl):
  1. 9 baratas de Fase 1: vina_score, pose_score_variance, pose_score_range,
     n_heavy, n_contacts_4, n_contacts_6, contacts_per_ha_4, n_clashes,
     cluster_density.
  2. Shell atom counts RF-Score style (96): pares receptor(C,N,O,S) x
     ligando(C,N,O,S,F,P,Cl,Br) en cascarones [0,4), [4,8), [8,12).
  3. ECIF-lite (56): pares (tipo extendido de proteina 8 clases) x
     (elemento de ligando 7 clases) a < 6.0 A. SIN ponderacion por
     conectividad extendida (replica el contrato del repo, no el ECIF
     original de Sanchez-Cruz 2021).
  4. Codigo poblacional por residuo (63): por tipo de residuo (20 aa +
     OTHER): atomos pesados de ligando a < 4.0 A y < 6.0 A de CUALQUIER
     atomo del receptor de ese tipo (42) + proxy de H-bond (atomos pesados
     N/O de ligando a < 3.5 A de atomos N/O del receptor, contando atomos
     de ligando DISTINTOS) (21).

Receptor: se parsean los atomos pesados del PDB de la proteina
(target_pdb_path) y el tipado ECIF replica la logica v0.5: RDKit sobre el
mismo PDB (con H explicitos y aromaticidad percibida), alineacion por
coordenadas (tolerancia 0.01 A, mismo elemento); atomos sin pareja en el
mol de RDKit (p. ej. aguas, que RDKit omite) usan la heuristica
resname/atomname. En v0.5 el set de atomos venia del receptor PDBQT del
docking; en produccion solo se dispone del PDB de la proteina, cuyo set de
atomos pesados es identico para los receptores del dataset (verificado en
los pids del test congelado) salvo casos puntuales documentados.

Ligando: atomos pesados del bloque PDBQT (serial, coords, elemento por la
columna AD4). Las features ricas son SUMAS sobre pares, por lo que el orden
de atomos (serial vs mol del cristal) no afecta los conteos; el multiset de
coordenadas+elementos es el mismo que el del extractor v0.5.

Las 3 features no geometricas por-pose (vina_score, pose_score_variance,
pose_score_range) y cluster_density requieren el CONJUNTO de poses: el
selector las rellena (esta funcion deja 0.0 como placeholder).

Dependencias: numpy/scipy/rdkit unicamente (sin meeko, sin torch).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np

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

# Codigos internos (enteros) para los conteos vectorizados.
_SHELL_PROT_CODE = {e: i for i, e in enumerate(PROTEIN_ELEMENTS)}
_SHELL_LIG_CODE = {e: i for i, e in enumerate(LIGAND_ELEMENTS)}
_ECIF_LIG_CODE = {e: i for i, e in enumerate(LIG_ECIF_TYPES)}
_ECIF_LIG_POR_ELEMENTO = {
    "C": "C", "N": "N", "O": "O", "S": "S", "F": "F",
    "Cl": "Hal", "Br": "Hal", "I": "Hal",
}
_ECIF_PROT_CODE = {t: i for i, t in enumerate(PROT_ECIF_TYPES)}
_RESCODE = {aa: i for i, aa in enumerate(RESIDUOS_21)}

# Heuristica de tipado ECIF para atomos de receptor sin pareja en el mol
# de RDKit (identica a la del extractor v0.5).
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


# ───────────────────────── parsing del bloque PDBQT (pose) ─────────────────

def parsear_pose_block(pdbqt_block: str):
    """Atomos pesados de una pose PDBQT: lista [(serial, x, y, z, elemento)].
    Devuelve None si no hay atomos. Si el bloque contiene multiples MODELs
    se usa SOLO el primero (un PoseData.pdbqt_block es una unica pose)."""
    atomos: list = []
    hay_model = False
    en_modelo = False
    modelo_cerrado = False
    for l in pdbqt_block.splitlines():
        if l.startswith("MODEL"):
            hay_model = True
            en_modelo = True
            modelo_cerrado = False
            continue
        if l.startswith("ENDMDL"):
            if en_modelo and atomos:
                modelo_cerrado = True
            en_modelo = False
            continue
        if not l.startswith(("ATOM", "HETATM")):
            continue
        if hay_model and not en_modelo:
            continue
        if len(l) < 55:
            continue
        ad4 = l[77:79].strip()
        elem = AD4_A_ELEMENTO.get(ad4)
        if elem is None:
            ad4 = l[76:78].strip()
            elem = AD4_A_ELEMENTO.get(ad4)
        if elem is None or elem == "H":
            continue
        try:
            serial = int(l[6:11])
            coords = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        except (ValueError, IndexError):
            continue
        atomos.append((serial, coords[0], coords[1], coords[2], elem))
    if not atomos:
        return None
    return atomos


def coords_por_serial(pdbqt_block: str) -> dict:
    """{serial: (x, y, z)} de los atomos pesados del bloque (para el calculo
    de cluster_density con correspondencia por serial)."""
    atomos = parsear_pose_block(pdbqt_block)
    if not atomos:
        return {}
    return {a[0]: (a[1], a[2], a[3]) for a in atomos}


# ───────────────────────── parsing del receptor (PDB) ──────────────────────

def parsear_receptor_pdb(pdb_path: str):
    """Atomos pesados del PDB de la proteina: coords (N,3) float64,
    elementos, resnames, atomnames. H descartados. Si el PDB tiene varios
    modelos (NMR), se usa SOLO el primero."""
    coords: list = []
    elems: list = []
    resnames: list = []
    atomnames: list = []
    try:
        lineas = Path(pdb_path).read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    en_modelo = False
    modelo_cerrado = False
    for l in lineas:
        if l.startswith("MODEL"):
            en_modelo = True
            modelo_cerrado = False
            continue
        if l.startswith("ENDMDL"):
            if en_modelo:
                modelo_cerrado = True
            en_modelo = False
            continue
        if not l.startswith(("ATOM", "HETATM")):
            continue
        if en_modelo is False and modelo_cerrado:
            continue
        if len(l) < 55:
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
        elems.append(sym)
        resnames.append(l[17:20].strip() or "XXX")
        atomnames.append(l[12:16].strip())
    if not coords:
        return None
    return (np.array(coords, dtype=np.float64), elems, resnames, atomnames)


def cargar_pdb_rdkit(path: str):
    """Carga el PDB de la proteina con RDKit (logica de
    rescoring/feature_extractor._load_protein_pdb: sanitizacion relajada,
    fallback sin H). Devuelve el mol o None."""
    from rdkit import Chem
    try:
        mol = Chem.MolFromPDBFile(path, removeHs=False, sanitize=False)
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
        mol = Chem.MolFromPDBFile(path, removeHs=True, sanitize=False)
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


def tipo_ecif_prot_heuristica(elem: str, resname: str, atomname: str) -> int:
    """Fallback para atomos sin pareja en el mol de RDKit: aromaticos por
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


@lru_cache(maxsize=8)
def _receptor_cache(pdb_path: str):
    """Receptor parseado + tipado, cacheado por ruta (max 8 complejos)."""
    from scipy.spatial import cKDTree

    parsed = parsear_receptor_pdb(pdb_path)
    if parsed is None:
        return None
    coords, elems, resnames, atomnames = parsed

    ecif_codes = np.empty(len(elems), dtype=np.int8)
    mol = cargar_pdb_rdkit(pdb_path)
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
    tree = cKDTree(coords)
    return {"coords": coords, "shell_codes": shell_codes,
            "ecif_codes": ecif_codes, "res_codes": res_codes,
            "es_no": es_no, "tree": tree,
            "n_hechos": int(match.sum()) if mol is not None else 0,
            "n_heuristicos": int((~match).sum()) if mol is not None else len(elems)}


def obtener_receptor(pdb_path: str):
    """Dict con todo lo necesario por receptor, cacheado por ruta.
    Devuelve None si el PDB es ilegible."""
    try:
        return _receptor_cache(str(pdb_path))
    except Exception:
        return None


# ───────────────────────── calculo de features ricas ────────────────────────

def calcular_rich(rec: dict, lig_coords, lig_elems):
    """Shell (96) + ECIF (56) + poblacional (63) para una pose.
    Identico a las definiciones del repo (extractor v0.5): pares de atomos
    pesados, cascarones [lo,hi), ECIF a < 6.0 A. Todo vectorizado."""
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
    rec_j = np.concatenate([np.asarray(b, dtype=np.intp)
                            for b in balls if len(b)])
    d = np.sqrt(((lig_coords[lig_i] - rec["coords"][rec_j]) ** 2).sum(axis=1))

    pe = rec["shell_codes"][rec_j]
    le = lig_shell_codes[lig_i]
    valido = (pe >= 0) & (le >= 0)
    pos_base = np.arange(32) * 3
    for k, (lo, hi) in enumerate(SHELL_BINS):
        m = valido & (d >= lo) & (d < hi)
        if m.any():
            combo = pe[m].astype(np.int64) * len(LIGAND_ELEMENTS) + le[m]
            shell[pos_base + k] = np.bincount(combo, minlength=32)

    m6 = d < ECIF_CUTOFF
    if m6.any():
        pt = rec["ecif_codes"][rec_j[m6]].astype(np.int64)
        lt = lig_ecif_codes[lig_i[m6]].astype(np.int64)
        ecif[:] = np.bincount(pt * len(LIG_ECIF_TYPES) + lt, minlength=56)

    rc = rec["res_codes"][rec_j]
    min_d = np.full((21, n_lig), np.inf)
    for t in range(21):
        sel = rc == t
        if sel.any():
            np.minimum.at(min_d[t], lig_i[sel], d[sel])
    pop[0:21] = (min_d < 4.0).sum(axis=1)
    pop[21:42] = (min_d < 6.0).sum(axis=1)

    m_hb = (d < 3.5) & lig_es_no[lig_i] & rec["es_no"][rec_j]
    if m_hb.any():
        lig_hb = lig_i[m_hb]
        rc_hb = rc[m_hb]
        for t in range(21):
            sel = rc_hb == t
            if sel.any():
                pop[42 + t] = len(np.unique(lig_hb[sel]))
    return shell, ecif, pop


# ───────────────────────── entrada principal ───────────────────────────────

def extraer_features_224(pdbqt_block: str, target_pdb_path: str):
    """Features raw 224 de UNA pose contra el PDB de la proteina.

    Devuelve (features, valido):
      features: list[float] de 224 en el orden de FEATURES_TOTAL. Las
        posiciones de vina_score, pose_score_variance, pose_score_range y
        cluster_density van en 0.0 (las rellena el selector con la
        informacion del CONJUNTO de poses); las 5 geometricas restantes
        (n_heavy, n_contacts_4, n_contacts_6, contacts_per_ha_4, n_clashes)
        se calculan aqui.
      valido: bool — False si el bloque o el PDB son ilegibles o si la pose
        no tiene atomos pesados; en ese caso features es todo ceros.
    """
    ceros = [0.0] * len(FEATURES_TOTAL)
    atomos = parsear_pose_block(pdbqt_block)
    if not atomos:
        return ceros, False
    receptor = obtener_receptor(target_pdb_path)
    if receptor is None:
        return ceros, False

    lig_coords = np.array([(a[1], a[2], a[3]) for a in atomos],
                          dtype=np.float64)
    lig_elems = [a[4] for a in atomos]
    shell, ecif, pop = calcular_rich(receptor, lig_coords, lig_elems)

    dists = receptor["tree"].query(lig_coords, k=1)[0]
    n_clash = int(np.count_nonzero(dists < 2.2))
    n_c4 = int(np.count_nonzero(dists < 4.0))
    n_c6 = int(np.count_nonzero(dists < 6.0))
    n_heavy = len(lig_coords)
    cpa4 = round(n_c4 / n_heavy, 4) if n_heavy else None

    d = {
        "n_heavy": n_heavy,
        "n_contacts_4": n_c4,
        "n_contacts_6": n_c6,
        "contacts_per_ha_4": cpa4,
        "n_clashes": n_clash,
    }
    rico = list(shell) + list(ecif) + list(pop)
    orden = {f: i for i, f in enumerate(FEATURES_TOTAL)}
    feats = [0.0] * len(FEATURES_TOTAL)
    for f, v in d.items():
        feats[orden[f]] = float(v)
    for f, v in zip(FEATURES_RICH, rico):
        feats[orden[f]] = float(v)
    return feats, True
