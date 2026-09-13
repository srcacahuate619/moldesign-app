#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_confirm_cohort.py — construcción de la cohorte confirmatoria D-RC-CONFIRM (FND-05).

ITERACIÓN 3 (revisión independiente): corrige los 2 fallos restantes de la
iteración 2:

  - B1 intra-cohorte: clustering con union-find COMPLETO y cierre transitivo
    sobre el grafo de similitud de cadenas (nodos = complejos; arista si existe
    ALGÚN par de cadenas >= 0.90, incluidas las idénticas sim = 1.0). La
    iteración 2 deduplicaba secuencias con "primer dueño" y perdía las aristas
    entre complejos con cadenas idénticas (grafo incompleto → cap de 3
    violado). El muestreo aplica tope de 3 por componente conexa Y además no
    elige un complejo cuya cadena sea >= 0.90 con otra ya seleccionada (0
    pares directos intra-cohorte).
  - B8 provenance: manifest git_state.commit = commit REAL de HEAD
    (dirty=true, la iteración no se commitea).

ITERACIÓN 4 (documental/operativa, SIN regenerar cohorte): guard de cuarentena
— la etapa 1 excluye del pool los pids de
`artifacts_science/FND-05/denylist_pids.json` vía `confirm_denylist.cargar_denylist`
(defensivo; no-op hoy porque la cohorte no se regenera — una reconstrucción
futura excluye los 112 pids retirados y produce una cohorte nueva por diseño).

ITERACIÓN 2 (revisión independiente): corrigió los bloqueadores B1, B2, B5, B6,
B7 y B8 del diseño D-RC-CONFIRM. Cambios principales respecto de la iteración 1:

  - Receptor POR CADENA (B1): la similitud entre dos complejos es el MÁXIMO del
    coeficiente de solapamiento de k-meros (k=8) sobre todos los pares de cadenas.
    Se excluye si cualquier par de cadenas >= 0.90. El cap intra-cohorte es de 3
    complejos por cluster de cadena de receptor.
  - Cuotas de resto mayor canónicas (B2): floor para todos, remanente repartido
    por fracción descendente (desempate por nombre), piso 1 solo para bins no
    vacíos con floor 0 cuando el total lo permite.
  - Unicidad química (B5): unidad primaria = (scaffold_id, InChIKey14). Tope de 1
    candidato por unidad. Fingerprint de conteo ECFP4 vs TODOS los ligandos de
    desarrollo: Tanimoto >= 0.90 excluye, 0.80–0.89 marca chem_flag. Acíclicos
    con clase `acyclic:<ik14>`; oligosacáridos (>= 3 anillos con O) con clase
    `oligo:<n_rings>:<n_oxygen>`.
  - Metales del pocket (B6): distancia mínima metal–ligando cristalográfico;
    <= 4 Å = pocket (metaloenzima), 4–8 Å = near, > 8 Å = remote (control
    negativo). Los pocket cuentan como metal para el balance; near/remote son
    flags.
  - Dominio químico y QC estructural (B7): MW, n_heavy, n_rings, n_amide y
    estrato (fragment|peptide|lipid|oligo|xl|druglike). QC flags: covalencia
    (átomo de ligando a < 1.8 Å de la proteína → covalent_suspect, excluido del
    gate primario y pasado a revisión manual), altloc y ocupancia < 1 en
    ligandos. Preparación Meeko por ligando con estado meeko_ok/meeko_fail/
    meeko_unavailable.
  - Provenance (B8): el manifest se re-inicializa con el commit REAL de HEAD;
    las dependencias se registran explícitamente; los conteos de receptores usan
    un único denominador nombrado (dev_receptores_complejos / dev_cadenas_totales
    / dev_cadenas_unicas).

Etapas del pipeline (una por exclusión, conteos registrados en metrics.json):

  1. POOL: intersección del índice Fase B enriquecido (`--index`) con los
     complejos con archivos completos en disco (`{pid}_protein.pdb` y
     `{pid}_ligand.sdf` o `.mol2`, ambos no vacíos).
  2. DEV_PIDS: exclusión de todos los pids ya vistos en desarrollo (8 categorías,
     leídas de `--dev-pids`).
  3. QUÍMICA: exclusión por scaffold de ligando, InChIKey de conectividad y
     ECFP4 de conteo (Tanimoto máximo >= 0.90 vs desarrollo; flag 0.80–0.89).
  4. RECEPTOR: exclusión por cadena de receptor (máximo del solapamiento de
     k-meros sobre pares de cadenas >= 0.90 vs TODOS los receptores de
     desarrollo, incluidos los PDB externos de benchmark).
  5. COVALENCIA: covalent_suspect → fuera del gate primario (revisión manual).
  6. BALANCE: muestreo estratificado priorizando el estrato drug-like, con
     cuotas de resto mayor corregidas, tope de 1 por unidad primaria química y
     tope de 3 por cluster de cadena de receptor. Semilla fija (42).

Salidas (en `--out-dir`, que debe ser scripts/artifacts_science/FND-05):

  candidates.jsonl   cohorte propuesta (una línea por complejo, con selected_rank)
  pool_eligible.jsonl pool elegible completo tras las exclusiones
  per_complex.jsonl  alias de pool_eligible para el árbol estándar de artefactos
  failures.jsonl     una línea por complejo excluido, con sus criterios
  metrics.json       conteos por etapa de exclusión y distribución por estrato

Determinismo: mismo input → misma salida byte-idéntica (verificado con dos
ejecuciones comparando sha256 de candidates.jsonl). Solo biblioteca estándar +
RDKit (scaffold, InChIKey, ECFP, descriptores) + numpy (distancias, con fallback
stdlib) + meeko (flag de preparación, degradación elegante).

Uso típico:

  python scripts/build_confirm_cohort.py \\
      --index data/pdbbind/INDEX_faseb_enriched_full_20260813_184439.2020 \\
      --pdbbind data/pdbbind \\
      --dev-pids scripts/artifacts_science/FND-05/dev_seen_pids.json \\
      --dev-receptor-pdbs data/targets data/1f0r_protein.pdb \\
      --refined-index data/pdbbind/INDEX_refined_data.2020 \\
      --out-dir scripts/artifacts_science/FND-05 \\
      --n-target 112 --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import numpy as np

    NUMPY_OK = True
except Exception:  # pragma: no cover - degradación sin numpy
    NUMPY_OK = False

try:
    from rdkit import Chem
    from rdkit import RDLogger
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold

    RDKIT_OK = True
except Exception:  # pragma: no cover - degradación sin RDKit
    RDKIT_OK = False

K_MER = 8
UMBRAL_CADENA = 0.90
TOPE_POR_CLUSTER = 3
TOPE_POR_UNIDAD = 1
METALES = {"ZN", "FE", "MG", "MN", "CA", "CO", "NI", "CU"}
ECFP_RADIO = 2
UMBRAL_ECFP_EXCLUSION = 0.90
UMBRAL_ECFP_FLAG = 0.80
COVALENCIA_A = 1.8
METAL_POCKET_A = 4.0
METAL_NEAR_A = 8.0
RESIDUOS_AGUA = {"HOH", "WAT"}
# Orden de prioridad de estrato cuando el gate primario (drug-like) no alcanza
# n_target: fragmento, péptido, lípido, oligo, xl (orden del maintainer).
ESTRATO_ORDEN = {"fragment": 0, "peptide": 1, "lipid": 2, "oligo": 3, "xl": 4,
                 "druglike": 5}

AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "ASX": "B", "GLX": "Z", "SEC": "U", "PYL": "O",
    "MSE": "M", "HID": "H", "HIE": "H", "HIP": "H", "CYX": "C", "CYM": "C",
}

_AMIDA_SMARTS = None


def configurar_salida() -> None:
    """Fuerza UTF-8 en consola y silencia advertencias de RDKit."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if RDKIT_OK:
        try:
            RDLogger.DisableLog("rdApp.error")
            RDLogger.DisableLog("rdApp.warning")
        except Exception:
            pass


# ─────────────────────────── lectura de datos ─────────────────────────────────


def parse_index(path: Path) -> dict[str, dict]:
    """Índice PDBbind: pid -> {resolution, year, pki}. Formato:
    PDB_ID  resolution  year  binding_data  //  pKi"""
    entries: dict[str, dict] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or "//" not in line:
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            pid = parts[0].lower()
            try:
                resolution = float(parts[1])
                year = int(parts[2])
                pki = float(parts[parts.index("//") + 1])
            except (ValueError, IndexError):
                continue
            entries[pid] = {"resolution": resolution, "year": year, "pki": pki}
    return entries


def cargar_dev_pids(path: Path) -> dict[str, list[str]]:
    """JSON de pids ya vistos: dict {categoria: [pid, ...]}. Normaliza a minúsculas."""
    with open(path, encoding="utf-8") as fh:
        datos = json.load(fh)
    return {
        str(cat): [str(pid).strip().lower() for pid in pids]
        for cat, pids in datos.items()
        if isinstance(pids, list)
    }


def _cargar_denylist_pids() -> set[str]:
    """Pids de la cuarentena materializada FND-05 (denylist); vacío si no aplica.

    Guard de cuarentena (ITERACIÓN 4, defensivo — no-op hoy: la cohorte no se
    regenera). Si el SHA-256 de candidates.jsonl difiere del registrado en la
    denylist, lanza RuntimeError ("cohorte cambiada, denylist obsoleto") para
    que la construcción falle en lugar de reutilizar pids retirados.
    """
    ruta = (Path(__file__).resolve().parent
            / "artifacts_science" / "FND-05" / "denylist_pids.json")
    if not ruta.is_file():
        return set()
    try:
        from confirm_denylist import cargar_denylist  # noqa: F401
    except Exception:
        print("ADVERTENCIA: confirm_denylist no importable; guard desactivado.",
              file=sys.stderr)
        return set()
    denylist = cargar_denylist(ruta)
    return {str(p).strip().lower() for p in denylist.get("pids", [])}


def archivos_completos(pdbbind: Path, pid: str) -> bool:
    """True si el complejo tiene protein.pdb y ligand (sdf o mol2) no vacíos."""
    d = pdbbind / pid
    prot = d / f"{pid}_protein.pdb"
    if not prot.is_file() or prot.stat().st_size == 0:
        return False
    for cand in (f"{pid}_ligand.sdf", f"{pid}_ligand.mol2"):
        p = d / cand
        if p.is_file() and p.stat().st_size > 0:
            return True
    return False


def leer_pdb_texto(pdbbind: Path, pid: str) -> str:
    """Texto del protein.pdb del complejo; '' si no hay archivo."""
    pdb = pdbbind / pid / f"{pid}_protein.pdb"
    if not pdb.is_file():
        return ""
    try:
        return pdb.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def leer_ligando(pdbbind: Path, pid: str):
    """Molécula RDKit del ligando cristalográfico (SDF, fallback MOL2); None si falla."""
    if not RDKIT_OK:
        return None
    sdf = pdbbind / pid / f"{pid}_ligand.sdf"
    try:
        mol = Chem.MolFromMolFile(str(sdf), sanitize=True)
        if mol is not None:
            return mol
    except Exception:
        pass
    try:
        return Chem.MolFromMol2File(str(pdbbind / pid / f"{pid}_ligand.mol2"),
                                    sanitize=True)
    except Exception:
        return None


def sha256_archivo(path: Path) -> str:
    """SHA-256 de un archivo, leyendo por bloques."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ─────────────────────────── secuencias por cadena ────────────────────────────


def secuencias_pdb_texto(texto: str) -> dict[str, str]:
    """Secuencias del receptor POR CADENA, vía SEQRES (fallback: CA de ATOM).

    Devuelve {cadena: secuencia} solo con cadenas no vacías. Esta es la unidad
    de comparación de receptores: la similitud entre dos complejos es el máximo
    del solapamiento de k-meros sobre todos los pares de cadenas.
    """
    lineas = texto.splitlines()
    seqres: dict[str, list[str]] = defaultdict(list)
    for l in lineas:
        if l.startswith("SEQRES"):
            cad = l[11:12].strip() or "?"
            for i in range(19, 70, 4):
                res = l[i:i + 3].strip()
                if res:
                    seqres[cad].append(AA3_TO_1.get(res, "X"))
    if seqres:
        return {c: "".join(seqres[c]) for c in sorted(seqres) if seqres[c]}
    por_cad: dict[str, dict[int, str]] = defaultdict(dict)
    for l in lineas:
        if l.startswith("ATOM") and l[12:16].strip() == "CA":
            cad = l[21:22].strip() or "?"
            try:
                num = int(l[22:26])
            except ValueError:
                continue
            por_cad[cad][num] = AA3_TO_1.get(l[17:20].strip(), "X")
    return {
        c: "".join(por_cad[c][n] for n in sorted(por_cad[c]))
        for c in sorted(por_cad) if por_cad[c]
    }


def cadenas_receptor(pdbbind: Path, pid: str) -> dict[str, str]:
    """Cadenas del receptor del complejo pid; {} si no hay archivo o secuencia."""
    texto = leer_pdb_texto(pdbbind, pid)
    if not texto:
        return {}
    return secuencias_pdb_texto(texto)


def cadenas_archivo_pdb(path: Path) -> dict[str, str]:
    """Cadenas SEQRES de un PDB externo (benchmark); {} si no aplica."""
    try:
        return secuencias_pdb_texto(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def kmers(seq: str, k: int = K_MER) -> set[str]:
    """Conjunto de k-meros de una secuencia (proxy de identidad entre cadenas)."""
    return {seq[i:i + k] for i in range(len(seq) - k + 1)}


def solapamiento_kmers(a: set[str], b: set[str]) -> float:
    """Coeficiente de solapamiento de k-meros (proxy de identidad de secuencia)."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def mejor_par_cadenas(cad_a: dict[str, str], cad_b: dict[str, str]):
    """Máximo del solapamiento de k-meros sobre todos los pares de cadenas.

    Devuelve (sim, par) con par = (cadena_de_a, cadena_de_b) o None.
    """
    mejor = 0.0
    par = None
    for ca, sa in cad_a.items():
        ka = kmers(sa)
        for cb, sb in cad_b.items():
            o = solapamiento_kmers(ka, kmers(sb))
            if o > mejor:
                mejor = o
                par = (ca, cb)
    return mejor, par


def clusters_cadenas(unidades: list[tuple[str, dict[str, str]]]):
    """Clusters de cadena de receptor: union-find completo con cierre transitivo.

    ITERACIÓN 3 (B1 intra-cohorte). Nodos = complejos (posiciones de
    `unidades`); arista entre A y B si existe ALGÚN par de cadenas (cadA, cadB)
    con solapamiento de k-meros >= UMBRAL_CADENA. Las cadenas idénticas
    (sim = 1.0) unen a TODOS sus dueños entre sí: la iteración 2 deduplicaba
    secuencias con "primer dueño" y perdía esas aristas, dejando el grafo
    incompleto (cap de 3 violado dentro de la cohorte). Union-find con path
    compression y union by rank; componentes conexas = clusters de cadena.

    Devuelve (cluster_por_indice, tamanos_desc, vecinos) donde
    cluster_por_indice[pos] = id de componente conexa, tamanos_desc = tamaños
    de componentes en orden descendente y vecinos[pos] = posiciones con arista
    directa >= 0.90 (sin incluirse a sí misma).
    """
    n = len(unidades)
    por_label = {label: i for i, (label, _) in enumerate(unidades)}
    cadena_lista, km_index = _indice_cadenas(unidades)
    owners: list[list[int]] = [
        [por_label[label] for label, _ in ent["sources"]] for ent in cadena_lista
    ]
    vecinos: list[set[int]] = [set() for _ in range(n)]
    padre = list(range(n))
    rango = [0] * n

    def find(x: int) -> int:
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rango[ra] < rango[rb]:
            ra, rb = rb, ra
        padre[rb] = ra
        if rango[ra] == rango[rb]:
            rango[ra] += 1

    # Aristas por cadena idéntica (sim = 1.0): todos los dueños de una misma
    # secuencia comparten una cadena exacta.
    for ows in owners:
        for a in range(len(ows)):
            for b in range(a + 1, len(ows)):
                vecinos[ows[a]].add(ows[b])
                vecinos[ows[b]].add(ows[a])
                union(ows[a], ows[b])

    # Aristas por pares de secuencias distintas >= 0.90: todos los dueños de i
    # con todos los dueños de j (grafo completo de complejos). Se excluyen los
    # pares oa == ob (una sola secuencia de un complejo no es vecina de sí
    # misma; p. ej. un complejo con dos cadenas propias >= 0.90 entre sí no
    # genera self-loop).
    for i, ent in enumerate(cadena_lista):
        tocados: set[int] = set()
        for km in ent["kmers"]:
            tocados |= km_index.get(km, set())
        for j in sorted(tocados):
            if j <= i:
                continue
            if solapamiento_kmers(ent["kmers"],
                                  cadena_lista[j]["kmers"]) >= UMBRAL_CADENA:
                for oa in owners[i]:
                    for ob in owners[j]:
                        if oa == ob:
                            continue
                        vecinos[oa].add(ob)
                        vecinos[ob].add(oa)
                        union(oa, ob)

    componentes: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        componentes[find(i)].append(i)
    cluster_por_indice: dict[int, int] = {}
    cid = 0
    for root in sorted(componentes):
        for i in componentes[root]:
            cluster_por_indice[i] = cid
        cid += 1
    tamanos = sorted((len(v) for v in componentes.values()), reverse=True)
    return cluster_por_indice, tamanos, vecinos


# ─────────────────────────── química del ligando ──────────────────────────────


def _amida_smarts():
    """Patrón SMARTS de enlace amida N-C(=O), cacheado a nivel de módulo."""
    global _AMIDA_SMARTS
    if _AMIDA_SMARTS is None:
        try:
            _AMIDA_SMARTS = Chem.MolFromSmarts("[NX3][CX3](=[OX1])")
        except Exception:
            _AMIDA_SMARTS = False
    return _AMIDA_SMARTS or None


def quimica_ligando(mol) -> dict:
    """Identidad y dominio químico del ligando (B5/B7).

    Computa InChIKey14, clase de scaffold (Murcko, `acyclic:<ik14>` para
    acíclicos y `oligo:<n_rings>:<n_oxygen>` para oligosacáridos heurísticos),
    MW, n_heavy, n_rings, n_amide, anillos con oxígeno y estrato.

    Prioridad de estrato (documentada): fragment > peptide > lipid > oligo > xl
    > druglike.
    """
    out: dict = {"ok": True, "inchikey14": None, "scaffold_class": None,
                 "n_heavy": None, "mw": None, "n_rings": None, "n_amide": None,
                 "rings_with_o": None, "stratum": None}
    try:
        out["inchikey14"] = Chem.MolToInchiKey(mol)[:14]
    except Exception:
        pass
    out["n_heavy"] = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)
    try:
        out["mw"] = round(float(Descriptors.MolWt(mol)), 4)
    except Exception:
        pass
    try:
        out["n_rings"] = int(mol.GetRingInfo().NumRings())
    except Exception:
        pass
    rings_with_o = 0
    o_ring = set()
    try:
        ri = mol.GetRingInfo()
        for ring in ri.AtomRings():
            if any(mol.GetAtomWithIdx(i).GetAtomicNum() == 8 for i in ring):
                rings_with_o += 1
                o_ring.update(i for i in ring
                              if mol.GetAtomWithIdx(i).GetAtomicNum() == 8)
    except Exception:
        pass
    out["rings_with_o"] = rings_with_o
    try:
        pat = _amida_smarts()
        out["n_amide"] = len(mol.GetSubstructMatches(pat)) if pat is not None else 0
    except Exception:
        out["n_amide"] = 0
    # Clase de scaffold (unidad química para la exclusión de desarrollo).
    if rings_with_o >= 3:
        # Heurística de oligosacárido: distinta longitud NO es familia independiente.
        out["scaffold_class"] = f"oligo:{out['n_rings']}:{len(o_ring)}"
    else:
        try:
            scaf = str(MurckoScaffold.MurckoScaffoldSmiles(mol=mol) or "")
        except Exception:
            scaf = None
        if scaf is None:
            out["scaffold_class"] = None
        elif scaf == "":
            out["scaffold_class"] = "acyclic:" + (out["inchikey14"] or "?")
        else:
            out["scaffold_class"] = "m:" + scaf
    out["stratum"] = estrato_ligando(out)
    return out


def estrato_ligando(q: dict) -> str:
    """Estrato químico del ligando según la política del maintainer."""
    mw, heavy = q.get("mw"), q.get("n_heavy")
    if mw is None or heavy is None:
        return "desconocido"
    if mw <= 150.0 or heavy <= 10:
        return "fragment"
    if q.get("n_amide", 0) >= 3:
        return "peptide"
    if q.get("n_rings", 0) == 0 and mw > 150.0:
        return "lipid"
    if q.get("rings_with_o", 0) >= 3:
        return "oligo"
    if mw > 500.0:
        return "xl"
    return "druglike"


def ecfp_conteo(mol):
    """Fingerprint de conteo ECFP4 (Morgan counts) como dict {bit: conteo}."""
    if not RDKIT_OK:
        return None
    try:
        fp = AllChem.GetMorganFingerprint(mol, ECFP_RADIO, useCounts=True)
        return dict(fp.GetNonzeroElements())
    except Exception:
        return None


def tanimoto_conteo(a: dict, b: dict) -> float:
    """Tanimoto sobre fingerprints de conteo: sum(min)/sum(max)."""
    if not a or not b:
        return 0.0
    s_min = 0.0
    s_max = 0.0
    for k, va in a.items():
        vb = b.get(k, 0)
        s_min += min(va, vb)
        s_max += max(va, vb)
    for k, vb in b.items():
        if k not in a:
            s_max += vb
    return s_min / s_max if s_max > 0.0 else 0.0


def unidad_primaria(scaffold_class: str | None, inchikey14: str | None) -> str | None:
    """Unidad primaria química = (scaffold_id, connectivity InChIKey14)."""
    if not scaffold_class or not inchikey14:
        return None
    return hashlib.sha256(
        f"{scaffold_class}|{inchikey14}".encode("utf-8")).hexdigest()[:12]


# ─────────────────────────── metales del pocket (B6) ──────────────────────────


def metales_pocket(pdbbind: Path, pid: str) -> dict:
    """Metales HETATM del complejo clasificados por distancia mínima al ligando.

    Distancia mínima metal–ligando cristalográfico (SDF):
      <= 4 Å → `pocket` (metaloenzima candidata; cuenta como metal en el balance)
      4–8 Å → `near` (flag)
      > 8 Å → `remote` (flag, control negativo)

    Devuelve {metales_pocket: [...], detalle: [...], near: [...], remote: [...]}
    donde detalle = [{metal, distancia_min, clase}, ...] en orden de aparición.
    """
    vacio: dict = {"metales_pocket": [], "detalle": [], "near": [], "remote": []}
    texto = leer_pdb_texto(pdbbind, pid)
    if not texto:
        return vacio
    metales: list[tuple[str, float, float, float]] = []
    for l in texto.splitlines():
        if l.startswith("HETATM"):
            el = l[76:78].strip().upper()
            if el in METALES:
                try:
                    x = float(l[30:38])
                    y = float(l[38:46])
                    z = float(l[46:54])
                except ValueError:
                    continue
                metales.append((el, x, y, z))
    if not metales:
        return vacio
    mol = leer_ligando(pdbbind, pid)
    if mol is None:
        detalle = [{"metal": el, "distancia_min": None, "clase": "sin_ligando"}
                   for el, _, _, _ in metales]
        return {**vacio, "detalle": detalle}
    try:
        conf = mol.GetConformer()
        coords = [(float(conf.GetAtomPosition(i).x),
                   float(conf.GetAtomPosition(i).y),
                   float(conf.GetAtomPosition(i).z))
                  for i in range(mol.GetNumAtoms())
                  if mol.GetAtomWithIdx(i).GetAtomicNum() > 1]
    except Exception:
        return {**vacio, "detalle": [
            {"metal": el, "distancia_min": None, "clase": "sin_coordenadas"}
            for el, _, _, _ in metales]}
    if not coords:
        return {**vacio, "detalle": [
            {"metal": el, "distancia_min": None, "clase": "sin_heavy"}
            for el, _, _, _ in metales]}

    def dist_min(x: float, y: float, z: float) -> float:
        if NUMPY_OK:
            arr = np.asarray(coords, dtype=np.float64)
            d = float(np.sqrt(((arr - (x, y, z)) ** 2).sum(axis=1).min()))
        else:  # pragma: no cover - fallback stdlib
            d = min(((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2) ** 0.5
                    for cx, cy, cz in coords)
        return d

    detalle = []
    pocket, near, remote = [], [], []
    for el, x, y, z in metales:
        d = dist_min(x, y, z)
        if d <= METAL_POCKET_A:
            clase = "pocket"
        elif d <= METAL_NEAR_A:
            clase = "near"
        else:
            clase = "remote"
        detalle.append({"metal": el, "distancia_min": round(d, 3), "clase": clase})
        if clase == "pocket":
            pocket.append(el)
        elif clase == "near":
            near.append(el)
        else:
            remote.append(el)
    return {"metales_pocket": pocket, "detalle": detalle,
            "near": near, "remote": remote}


# ─────────────────────────── QC estructural (B7) ──────────────────────────────


def qc_estructural(texto_pdb: str, mol) -> dict:
    """QC estructural del complejo: covalencia, altloc y ocupancia.

    covalencia: átomo de ligando a < COVALENCIA_A (1.8 Å) de cualquier átomo
    PESADO de proteína (registros ATOM con elemento != H; los H de la proteína
    no cuentan para evitar falsos positivos por contactos H···ligando; los
    HETATM no-agua/metales son cofactores y tampoco cuentan). Los átomos de
    proteína se comparan contra los átomos pesados del ligando cristalográfico.
    altloc: cualquier línea ATOM/HETATM con altLoc distinto de blanco/A.
    ocupancia: HETATM (sin aguas ni metales) con ocupancia < 1.0.
    """
    out: dict = {"covalent_suspect": False, "qc_altloc": False,
                 "qc_occupancy_lt1": False, "dist_min_prot_lig": None}
    prot: list[tuple[float, float, float]] = []
    for l in texto_pdb.splitlines():
        if l.startswith("ATOM") or l.startswith("HETATM"):
            alt = l[16:17]
            if alt not in ("", " ", "A"):
                out["qc_altloc"] = True
        if l.startswith("ATOM"):
            el = l[76:78].strip().upper()
            if el == "H":
                continue
            try:
                prot.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                pass
        elif l.startswith("HETATM"):
            res = l[17:20].strip().upper()
            el = l[76:78].strip().upper()
            if res in RESIDUOS_AGUA:
                continue
            if el in METALES:
                continue
            try:
                occ = float(l[54:60])
                if occ < 1.0:
                    out["qc_occupancy_lt1"] = True
            except ValueError:
                pass
    if mol is not None and prot:
        try:
            conf = mol.GetConformer()
            lig = [(float(conf.GetAtomPosition(i).x),
                    float(conf.GetAtomPosition(i).y),
                    float(conf.GetAtomPosition(i).z))
                   for i in range(mol.GetNumAtoms())
                   if mol.GetAtomWithIdx(i).GetAtomicNum() > 1]
        except Exception:
            lig = []
        if lig:
            if NUMPY_OK:
                pa = np.asarray(prot, dtype=np.float64)
                la = np.asarray(lig, dtype=np.float64)
                d = float(np.sqrt(((pa[:, None, :] - la[None, :, :]) ** 2)
                                  .sum(axis=2).min()))
            else:  # pragma: no cover - fallback stdlib
                d = min(((px - lx) ** 2 + (py - ly) ** 2 + (pz - lz) ** 2) ** 0.5
                        for px, py, pz in prot for lx, ly, lz in lig)
            out["dist_min_prot_lig"] = round(d, 3)
            if d < COVALENCIA_A:
                out["covalent_suspect"] = True
    return out


def preparar_meeko(mol):
    """Intento de preparación Meeko por ligando (flag, no exclusión).

    Estados: meeko_ok (con número de setups), meeko_fail (con tipo de error) o
    meeko_unavailable (si el paquete no está instalado).
    """
    try:
        from meeko import MoleculePreparation  # noqa: F401
    except Exception:
        return {"meeko_status": "meeko_unavailable"}
    try:
        mh = Chem.AddHs(mol)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        return {"meeko_status": "meeko_ok", "meeko_n_setups": len(setups)}
    except Exception as exc:
        return {"meeko_status": "meeko_fail", "meeko_error": type(exc).__name__}


# ─────────────────────────── bins de estratificación ───────────────────────────


def bin_resolucion(res: float | None) -> str:
    if res is None:
        return "res_na"
    if res < 2.0:
        return "res_lt2"
    if res <= 2.5:
        return "res_2_2p5"
    return "res_gt2p5"


def bin_rotables(rb: int | None) -> str:
    if rb is None:
        return "rot_na"
    if rb <= 4:
        return "rot_0_4"
    if rb <= 9:
        return "rot_5_9"
    if rb <= 14:
        return "rot_10_14"
    return "rot_15_plus"


def bin_pki(pki: float | None) -> str:
    if pki is None:
        return "pki_na"
    if pki < 6.0:
        return "pki_lt6"
    if pki < 8.0:
        return "pki_6_8"
    return "pki_ge8"


def bin_year(year: int | None) -> str:
    if year is None:
        return "year_na"
    if year <= 2000:
        return "year_le2000"
    if year <= 2010:
        return "year_2001_2010"
    return "year_gt2010"


def cuotas_proporcionales(disponibles: dict[str, int], total: int) -> dict[str, int]:
    """Reparto proporcional canónico con método del resto mayor (B2).

    Algoritmo:
      1. cuota[b] = floor(count_b / n * total) para todos los bins.
      2. Piso 1 SOLO para bins no vacíos con cuota 0, mientras el total lo
         permita (la suma de cuotas no puede exceder total); orden de bins
         alfabético.
      3. Remanente = total - suma(cuotas): se reparte de a +1 (máximo +1 por
         bin) ordenando los bins por parte fraccionaria DESCENDENTE; desempate
         por nombre del bin (regla documentada).

    Si total supera el inventario (suma de disponibles), la cuota puede exceder
    el inventario del bin; el muestreo (`_llenar`) es quien acota la cuota al
    inventario disponible.

    El bug de la iteración 1 (`fracciones[0] = (bin_, fracciones[0][1] - 1)`)
    mantenía la misma parte fraccionaria y el mismo bin ganaba repetidamente.
    """
    n = sum(disponibles.values())
    if n == 0:
        return {}
    bins = sorted(disponibles)
    cuotas: dict[str, int] = {}
    fracciones: dict[str, float] = {}
    for b in bins:
        count = disponibles[b]
        frac = (count / n) * total
        cuotas[b] = math.floor(frac)
        fracciones[b] = frac - cuotas[b]
    suma = sum(cuotas.values())
    for b in bins:
        if disponibles[b] > 0 and cuotas[b] == 0 and suma < total:
            cuotas[b] = 1
            fracciones[b] = 0.0  # ya recibió su piso; no participa del remanente
            suma += 1
    remanente = total - suma
    orden = sorted(bins, key=lambda b: (-fracciones[b], b))
    i = 0
    while remanente > 0 and i < len(orden):
        b = orden[i]
        i += 1
        cuotas[b] += 1
        remanente -= 1
    return cuotas


def expandir_archivos_pdb(rutas: list[str]) -> list[Path]:
    """Convierte una lista de rutas (archivos o directorios) en una lista de .pdb.

    En Windows el filesystem es case-insensitive: rglob('*.pdb') y rglob('*.PDB')
    devuelven los mismos archivos, por lo que se deduplica por ruta resuelta.
    """
    salida: set[Path] = set()
    for raw in rutas:
        p = Path(raw)
        if p.is_file():
            salida.add(p)
        elif p.is_dir():
            for patron in ("*.pdb", "*.PDB"):
                for f in p.rglob(patron):
                    salida.add(f)
    return sorted(salida)


# ─────────────────────────── pipeline principal ───────────────────────────────


def _indice_cadenas(cadenas_unidades: list[tuple[str, dict[str, str]]]):
    """Índice invertido km -> {ids de cadena} para comparación rápida por cadena.

    Recibe una lista de unidades (label, cadenas) y devuelve (cadena_lista,
    km_index) donde cadena_lista[id] = {"kmers": set, "sources": [(label, cad)]}.
    Las secuencias idénticas se deduplican; el primer origen (orden de entrada)
    es el que se reporta en failures.jsonl.
    """
    por_seq: dict[str, dict] = {}
    for label, cads in cadenas_unidades:
        for cad, seq in cads.items():
            if not seq:
                continue
            if seq not in por_seq:
                por_seq[seq] = {"kmers": kmers(seq), "sources": []}
            por_seq[seq]["sources"].append((label, cad))
    cadena_lista: list[dict] = []
    km_index: dict[str, set[int]] = defaultdict(set)
    for seq in sorted(por_seq):
        cid = len(cadena_lista)
        cadena_lista.append(por_seq[seq])
        for km in por_seq[seq]["kmers"]:
            km_index[km].add(cid)
    return cadena_lista, km_index


def _mejores_matches(cads: dict[str, str], cadena_lista: list[dict],
                     km_index: dict[str, set[int]]):
    """Mejor match por cadena candidata contra el índice de cadenas.

    Devuelve [(cadena_candidata, sim, chain_id)], ordenado por (-sim, cadena).
    """
    matches: list[tuple[str, float, int]] = []
    for cad, seq in cads.items():
        ka = kmers(seq)
        tocados: set[int] = set()
        for km in ka:
            tocados |= km_index.get(km, set())
        mejor = 0.0
        mejor_id = -1
        for cid in sorted(tocados):
            o = solapamiento_kmers(ka, cadena_lista[cid]["kmers"])
            if o > mejor:
                mejor = o
                mejor_id = cid
        if mejor >= UMBRAL_CADENA and mejor_id >= 0:
            matches.append((cad, mejor, mejor_id))
    matches.sort(key=lambda t: (-t[1], t[0]))
    return matches


def construir_cohorte(index: Path, pdbbind: Path, dev_pids: dict[str, list[str]],
                      dev_archivos_pdb: list[Path], refined_index: Path | None,
                      n_target: int, seed: int,
                      respetar_denylist: bool = False) -> dict:
    """Ejecuta el pipeline completo y devuelve el resumen para las salidas."""
    metricas: dict = {"pipeline": {}, "rdkit_available": RDKIT_OK,
                      "numpy_available": NUMPY_OK,
                      "k_mer": K_MER, "umbral_cadena": UMBRAL_CADENA,
                      "tope_cluster_cadena": TOPE_POR_CLUSTER,
                      "tope_unidad_primaria": TOPE_POR_UNIDAD,
                      "umbral_ecfp_exclusion": UMBRAL_ECFP_EXCLUSION,
                      "umbral_ecfp_flag": UMBRAL_ECFP_FLAG,
                      "covalencia_a": COVALENCIA_A,
                      "metal_pocket_a": METAL_POCKET_A,
                      "metal_near_a": METAL_NEAR_A,
                      "seed": seed, "n_target": n_target}

    # ── Etapa 1: pool = índice ∩ archivos completos en disco ──
    index_entradas = parse_index(index)
    pids_index = set(index_entradas)
    pool = [pid for pid in sorted(pids_index) if archivos_completos(pdbbind, pid)]
    metricas["pipeline"]["stage_1_pool_index"] = len(pids_index)
    metricas["pipeline"]["stage_1_pool_index_sin_archivos"] = (
        len(pids_index) - len(pool))
    # Guard de cuarentena FND-05 (ITERACIÓN 4, opt-in): la denylist deriva DE la
    # salida de este builder, por lo que excluirla por defecto rompería la
    # autorreproducibilidad de la cohorte. Solo se aplica con --respect-denylist
    # (útil para builders FUTUROS de otros datasets, p. ej. AF-01).
    if respetar_denylist:
        denylist_pids = _cargar_denylist_pids()
        denylist_pool = [pid for pid in pool if pid in denylist_pids]
        pool = [pid for pid in pool if pid not in denylist_pids]
        metricas["pipeline"]["stage_1_denylist_excluidos"] = len(denylist_pool)
    metricas["pipeline"]["stage_1_pool_completo"] = len(pool)

    # ── Etapa 2: exclusión de pids ya vistos en desarrollo ──
    vistos: set[str] = set()
    por_categoria: dict[str, int] = {}
    for cat, pids in sorted(dev_pids.items()):
        vistos.update(pids)
        por_categoria[cat] = len(pids)
    metricas["dev_seen_by_category"] = por_categoria
    metricas["dev_seen_total"] = len(vistos)
    excluidos_pid = [pid for pid in pool if pid in vistos]
    metricas["pipeline"]["stage_2_excluidos_dev_pid"] = len(excluidos_pid)
    restantes = [pid for pid in pool if pid not in vistos]
    metricas["pipeline"]["stage_2_restantes"] = len(restantes)

    # ── Química de desarrollo: scaffold, InChIKey14 y ECFP de conteo ──
    scaffold_dev: set[str] = set()
    ik14_dev: set[str] = set()
    ecfp_dev: list[dict] = []
    ecfp_dev_ik14: set[str] = set()
    lig_dev_ok = 0
    for pid in sorted(vistos):
        mol = leer_ligando(pdbbind, pid)
        if mol is None:
            continue
        lig_dev_ok += 1
        q = quimica_ligando(mol)
        if q.get("scaffold_class"):
            scaffold_dev.add(q["scaffold_class"])
        if q.get("inchikey14"):
            ik = q["inchikey14"]
            ik14_dev.add(ik)
            if ik not in ecfp_dev_ik14:
                fp = ecfp_conteo(mol)
                if fp:
                    ecfp_dev.append(fp)
                    ecfp_dev_ik14.add(ik)
    metricas["dev_ligandos_parseables"] = lig_dev_ok
    metricas["dev_scaffold_clases"] = len(scaffold_dev)
    metricas["dev_ligandos_ecfp"] = len(ecfp_dev)
    ecfp_index: dict[int, set[int]] = defaultdict(set)
    for i, fp in enumerate(ecfp_dev):
        for bit in fp:
            ecfp_index[bit].add(i)

    # ── Receptores de desarrollo POR CADENA (B1) ──
    unidades_dev: list[tuple[str, dict[str, str]]] = []
    n_dev_sec = 0
    cadenas_totales = 0
    for pid in sorted(vistos):
        cads = cadenas_receptor(pdbbind, pid)
        if not cads:
            continue
        n_dev_sec += 1
        cadenas_totales += len(cads)
        unidades_dev.append((pid, cads))
    for p in dev_archivos_pdb:
        cads = cadenas_archivo_pdb(p)
        if not cads:
            continue
        n_dev_sec += 1
        cadenas_totales += len(cads)
        unidades_dev.append((p.name, cads))
    cadena_lista_dev, km_index_dev = _indice_cadenas(unidades_dev)
    metricas["dev_receptores_complejos"] = n_dev_sec
    metricas["dev_cadenas_totales"] = cadenas_totales
    metricas["dev_cadenas_unicas"] = len(cadena_lista_dev)

    # ── Etapas 3–5: química, receptor por cadena y covalencia ──
    if refined_index:
        refined = set(parse_index(refined_index))
    else:
        refined = set()

    excluidos: list[dict] = []
    crit_conteos: Counter = Counter()
    etapa_conteos: Counter = Counter()
    elegibles: list[dict] = []
    n_chem_flag = 0
    cadenas_elegibles: dict[str, dict[str, str]] = {}

    for pid in sorted(restantes):
        e = index_entradas.get(pid, {})
        texto_pdb = leer_pdb_texto(pdbbind, pid)
        mol = leer_ligando(pdbbind, pid)
        q = quimica_ligando(mol) if mol is not None else None
        criterios: list[str] = []
        extra: dict = {}

        # Etapa 3: química del ligando.
        if mol is None:
            criterios.append("ligando_no_parseable")
        else:
            if q.get("scaffold_class") and q["scaffold_class"] in scaffold_dev:
                criterios.append("scaffold_en_desarrollo")
            if q.get("inchikey14") and q["inchikey14"] in ik14_dev:
                criterios.append("ligando_ik14_en_desarrollo")
            fp = ecfp_conteo(mol)
            t_max = 0.0
            if fp and ecfp_dev:
                candidatos_fp: set[int] = set()
                for bit in fp:
                    candidatos_fp |= ecfp_index.get(bit, set())
                for didx in sorted(candidatos_fp):
                    t = tanimoto_conteo(fp, ecfp_dev[didx])
                    if t > t_max:
                        t_max = t
            extra["ecfp_max_tani_dev"] = round(t_max, 4) if fp else None
            if fp and t_max >= UMBRAL_ECFP_EXCLUSION:
                criterios.append("ecfp_tanimoto_ge90")
            elif t_max >= UMBRAL_ECFP_FLAG:
                extra["chem_flag"] = True
                n_chem_flag += 1

        # Etapa 4: receptor por cadena.
        cads = secuencias_pdb_texto(texto_pdb) if texto_pdb else {}
        if not cads:
            criterios.append("receptor_sin_secuencia")
        else:
            matches = _mejores_matches(cads, cadena_lista_dev, km_index_dev)
            if matches:
                cad, sim, cid = matches[0]
                src = cadena_lista_dev[cid]["sources"][0]
                extra["chain_a"] = cad
                extra["chain_b"] = f"{src[0]}:{src[1]}"
                extra["sim"] = round(sim, 4)
                extra["n_cadenas_match"] = len(matches)
                if sim >= 0.9999:
                    criterios.append("receptor_cadena_identica")
                else:
                    criterios.append("receptor_cadena_homologa_90")

        # Etapa 5: covalencia (solo si pasó química y receptor).
        if not criterios:
            qc = qc_estructural(texto_pdb, mol)
            if qc["covalent_suspect"]:
                criterios.append("covalent_suspect")
        else:
            qc = {"covalent_suspect": False, "qc_altloc": False,
                  "qc_occupancy_lt1": False, "dist_min_prot_lig": None}

        registro = {
            "pid": pid,
            "resolution": e.get("resolution"),
            "year": e.get("year"),
            "pki": e.get("pki"),
            "in_refined": pid in refined,
            "n_heavy": q.get("n_heavy") if q else None,
            "mw": q.get("mw") if q else None,
            "n_rings": q.get("n_rings") if q else None,
            "n_amide": q.get("n_amide") if q else None,
            "rings_with_o": q.get("rings_with_o") if q else None,
            "rot_bonds": _rotables(mol) if mol is not None else None,
            "stratum": q.get("stratum") if q else "no_parseable",
            "scaffold_id": (hashlib.sha256(q["scaffold_class"].encode("utf-8")).hexdigest()[:12]
                            if q and q.get("scaffold_class") else None),
            "scaffold_class": q.get("scaffold_class") if q else None,
            "inchikey14": q.get("inchikey14") if q else None,
            "primary_unit": (unidad_primaria(q["scaffold_class"], q["inchikey14"])
                             if q else None),
            "ecfp_max_tani_dev": extra.get("ecfp_max_tani_dev"),
            "chem_flag": bool(extra.get("chem_flag")),
            "qc_altloc": qc["qc_altloc"],
            "qc_occupancy_lt1": qc["qc_occupancy_lt1"],
            "covalent_suspect": qc["covalent_suspect"],
            "dist_min_prot_lig": qc.get("dist_min_prot_lig"),
        }

        if criterios:
            if any(c in {"ligando_no_parseable", "scaffold_en_desarrollo",
                         "ligando_ik14_en_desarrollo", "ecfp_tanimoto_ge90"}
                   for c in criterios):
                etapa = 3
            elif any(c in {"receptor_sin_secuencia", "receptor_cadena_identica",
                           "receptor_cadena_homologa_90"} for c in criterios):
                etapa = 4
            else:
                etapa = 5
            etapa_conteos[etapa] += 1
            for c in criterios:
                crit_conteos[c] += 1
            excluidos.append({"pid": pid, "criteria": criterios,
                              "etapa_exclusion": etapa, **extra, **registro})
        else:
            mp = metales_pocket(pdbbind, pid)
            meeko = preparar_meeko(mol)
            registro.update({
                "metals": mp["metales_pocket"],
                "metal_detail": mp["detalle"],
                "metal_near": mp["near"],
                "metal_remote": mp["remote"],
                "meeko_status": meeko.get("meeko_status"),
                "meeko_error": meeko.get("meeko_error"),
                "meeko_n_setups": meeko.get("meeko_n_setups"),
            })
            cadenas_elegibles[pid] = cads
            elegibles.append(registro)

    metricas["pipeline"]["stage_3_excluidos_quimica"] = etapa_conteos.get(3, 0)
    metricas["pipeline"]["stage_3_restantes"] = len(restantes) - etapa_conteos.get(3, 0)
    metricas["pipeline"]["stage_4_excluidos_receptor_cadena"] = etapa_conteos.get(4, 0)
    metricas["pipeline"]["stage_4_restantes"] = (
        len(restantes) - etapa_conteos.get(3, 0) - etapa_conteos.get(4, 0))
    metricas["pipeline"]["stage_5_excluidos_covalencia"] = etapa_conteos.get(5, 0)
    metricas["pipeline"]["stage_5_restantes"] = len(elegibles)
    metricas["pipeline"]["elegibles"] = len(elegibles)
    metricas["pipeline"]["n_chem_flag_80_89"] = n_chem_flag
    for criterio, n in sorted(crit_conteos.items()):
        metricas["pipeline"][f"criteria_{criterio}"] = n
    metricas["meeko_estados"] = dict(sorted(
        Counter(r.get("meeko_status") for r in elegibles).items()))

    # ── Clusters de cadena de receptor entre elegibles (B1, iteración 3) ──
    # Union-find completo sobre el grafo de similitud de cadenas (arista si
    # existe ALGÚN par de cadenas >= 0.90, incluidas las idénticas sim = 1.0);
    # las componentes conexas definen el cluster y el cap de 3 se aplica por
    # componente durante el muestreo. Además, el muestreo evita pares directos
    # >= 0.90 dentro de la cohorte (vecinos_directos).
    unidades_elig: list[tuple[str, dict[str, str]]] = [
        (r["pid"], cadenas_elegibles[r["pid"]]) for r in elegibles]
    cluster_de_comp, tamanos_clusters, vecinos_idx = clusters_cadenas(
        unidades_elig)
    for i, r in enumerate(elegibles):
        r["receptor_cluster_id"] = cluster_de_comp[i]
    vecinos_directos: dict[str, set[str]] = {
        elegibles[i]["pid"]: {elegibles[j]["pid"] for j in vecinos_idx[i]}
        for i in range(len(elegibles))}
    metricas["receptor_clusters_elegibles"] = len(tamanos_clusters)
    metricas["receptor_cluster_sizes"] = tamanos_clusters

    # ── Etapa 6: muestreo estratificado determinista ──
    metricas["elegibles_distribucion"] = distribucion_estratos(elegibles)
    seleccion, metricas_sel = muestreo_estratificado(
        elegibles, n_target, seed, vecinos_directos)
    metricas["selection"] = metricas_sel
    if seleccion:
        metricas["selection"]["cohorte_distribucion"] = distribucion_estratos(seleccion)

    return {
        "metrics": metricas,
        "candidates": seleccion,
        "pool_eligible": elegibles,
        "failures": excluidos,
    }


def _rotables(mol) -> int | None:
    """Número de enlaces rotables del ligando; None si no computable."""
    try:
        return int(rdMolDescriptors.CalcNumRotatableBonds(mol))
    except Exception:
        return None


def distribucion_estratos(registros: list[dict]) -> dict:
    """Distribución por estrato químico y por bins de balance."""
    return {
        "stratum": dict(sorted(Counter(r.get("stratum") for r in registros).items())),
        "resolution": dict(sorted(Counter(bin_resolucion(r["resolution"]) for r in registros).items())),
        "rot_bonds": dict(sorted(Counter(bin_rotables(r["rot_bonds"]) for r in registros).items())),
        "pki": dict(sorted(Counter(bin_pki(r["pki"]) for r in registros).items())),
        "year": dict(sorted(Counter(bin_year(r["year"]) for r in registros).items())),
        "metals": dict(sorted(Counter("metal" if r.get("metals") else "sin_metal"
                                      for r in registros).items())),
    }


def _llenar(pool: list[dict], target: int, rng: random.Random,
            conteo_cluster: Counter, conteo_unidad: Counter,
            vecinos_directos: dict[str, set[str]], seleccionados_pids: set[str],
            usar_cuotas: bool) -> tuple[list[dict], dict[str, int]]:
    """Llena hasta `target` candidatos del pool respetando las cotas duras.

    Cotas duras (nunca se relajan): tope por cluster de cadena (3), tope de 1
    por unidad primaria química y prohibición de pares directos de cadenas
    >= 0.90 dentro de la cohorte (un complejo es inelegible si comparte una
    cadena >= 0.90 con otro ya seleccionado — garantiza 0 pares directos
    intra-cohorte). Si usar_cuotas=True aplica además cuotas de celda
    (rot x res), cuota de metales pocket y cuotas suaves de pKi/año con
    relajación progresiva. El orden de iteración es determinista: celdas
    ordenadas y barajado rng dentro de cada celda.

    Devuelve (selección, cuotas_celdas) — cuotas_celdas vacío si usar_cuotas
    es False.
    """
    if target <= 0 or not pool:
        return [], {}
    if usar_cuotas:
        celdas: dict[str, list[dict]] = defaultdict(list)
        for r in pool:
            celdas[f"{bin_rotables(r['rot_bonds'])}|{bin_resolucion(r['resolution'])}"].append(r)
        disponibles_celdas = {c: len(regs) for c, regs in celdas.items()}
        cuotas_celdas = cuotas_proporcionales(disponibles_celdas, target)
        for c in list(cuotas_celdas):
            cuotas_celdas[c] = min(cuotas_celdas[c], len(celdas[c]))
        metal_disp = sum(1 for r in pool if r.get("metals"))
        metal_objetivo = round(target * metal_disp / len(pool)) if pool else 0
        cuotas_pki = cuotas_proporcionales(
            dict(Counter(bin_pki(r["pki"]) for r in pool)), target)
        cuotas_year = cuotas_proporcionales(
            dict(Counter(bin_year(r["year"]) for r in pool)), target)
    else:
        celdas = {"fill": list(pool)}
        cuotas_celdas = {"fill": len(pool)}
        metal_objetivo = -1  # sin cota de metales en el relleno
        cuotas_pki = {}
        cuotas_year = {}

    def intentar(tol_metal: int, tol_pki: int, tol_year: int,
                 cuotas_celdas_act: dict[str, int]) -> list[dict]:
        """Un intento de llenado; devuelve la selección lograda (puede ser parcial)."""
        seleccionados: list[dict] = []
        cc: Counter = Counter(conteo_cluster)
        cu: Counter = Counter(conteo_unidad)
        s_pids: set[str] = set(seleccionados_pids)
        conteo_celda: Counter = Counter()
        conteo_metal = 0
        conteo_pki: Counter = Counter()
        conteo_year: Counter = Counter()
        orden_celda = sorted(celdas)
        iters = {c: iter(rng.sample(regs, len(regs))) for c, regs in celdas.items()}
        agotadas: set[str] = set()
        progreso = True
        while progreso and len(seleccionados) < target:
            progreso = False
            for c in orden_celda:
                if c in agotadas or len(seleccionados) >= target:
                    continue
                if conteo_celda[c] >= cuotas_celdas_act.get(c, 0):
                    agotadas.add(c)
                    continue
                it = iters[c]
                tomado = None
                for r in it:
                    if cc[r["receptor_cluster_id"]] >= TOPE_POR_CLUSTER:
                        continue
                    if cu[r["primary_unit"]] >= TOPE_POR_UNIDAD:
                        continue
                    if any(n in s_pids for n in vecinos_directos.get(r["pid"], ())):
                        continue
                    if usar_cuotas and r.get("metals") and conteo_metal >= metal_objetivo + tol_metal:
                        continue
                    if usar_cuotas and not r.get("metals") and conteo_metal < metal_objetivo - tol_metal:
                        continue
                    if usar_cuotas and cuotas_pki:
                        bp = bin_pki(r["pki"])
                        if conteo_pki[bp] >= cuotas_pki.get(bp, 0) + tol_pki:
                            continue
                    if usar_cuotas and cuotas_year:
                        by = bin_year(r["year"])
                        if conteo_year[by] >= cuotas_year.get(by, 0) + tol_year:
                            continue
                    tomado = r
                    break
                if tomado is None:
                    agotadas.add(c)
                    continue
                seleccionados.append(tomado)
                s_pids.add(tomado["pid"])
                cc[tomado["receptor_cluster_id"]] += 1
                cu[tomado["primary_unit"]] += 1
                conteo_celda[c] += 1
                conteo_pki[bin_pki(tomado["pki"])] += 1
                conteo_year[bin_year(tomado["year"])] += 1
                if tomado.get("metals"):
                    conteo_metal += 1
                progreso = True
        return seleccionados

    if usar_cuotas:
        sel = intentar(6, 2, 2, dict(cuotas_celdas))
        if len(sel) < target:
            # Relajación 1: tolerancias amplias de pKi/año, mantener cota de metales.
            sel = intentar(10, 999, 999, dict(cuotas_celdas))
        if len(sel) < target:
            # Relajación 2: reasignar el déficit a celdas con inventario.
            deficit = target - len(sel)
            cuotas2 = dict(cuotas_celdas)
            pendiente = {c: len(celdas[c]) - cuotas_celdas.get(c, 0) for c in celdas}
            for c in sorted(pendiente, key=lambda c: (-pendiente[c], c)):
                if deficit <= 0:
                    break
                extra = min(deficit, max(0, len(celdas[c]) - cuotas_celdas[c]))
                cuotas2[c] += extra
                deficit -= extra
            sel = intentar(10, 999, 999, cuotas2)
    else:
        sel = intentar(0, 0, 0, dict(cuotas_celdas))
    return sel, cuotas_celdas


def muestreo_estratificado(elegibles: list[dict], n_target: int,
                           seed: int,
                           vecinos_directos: dict[str, set[str]] | None = None
                           ) -> tuple[list[dict], dict]:
    """Muestreo balanceado determinista priorizando el estrato drug-like (B5/B7).

    El gate primario se evalúa sobre el estrato drug-like: si el inventario
    drug-like alcanza n_target, toda la cohorte sale de ahí (gate_primary=true).
    Si no alcanza, se completa con estratos no drug-like en el orden documentado
    (fragment, peptide, lipid, oligo, xl) marcados gate_primary=false y
    reportados aparte. Cotas duras: 1 por unidad primaria química, 3 por
    componente conexa de cadenas de receptor y 0 pares directos >= 0.90 dentro
    de la cohorte (un complejo es inelegible si comparte una cadena >= 0.90 con
    otro ya seleccionado). Cuotas de celda (rot x res) con el método del resto
    mayor corregido; restricciones suaves de metales pocket, pKi y año con
    relajación documentada.
    """
    if not elegibles:
        return [], {"selected": 0, "target": n_target}
    vecinos_directos = vecinos_directos or {}
    rng = random.Random(seed)
    druglike = [r for r in elegibles if r["stratum"] == "druglike"]
    otros = [r for r in elegibles if r["stratum"] != "druglike"]
    otros.sort(key=lambda r: (ESTRATO_ORDEN.get(r["stratum"], 99), r["pid"]))
    n_drug = min(n_target, len(druglike))
    cc: Counter = Counter()
    cu: Counter = Counter()
    sel_pids: set[str] = set()
    sel_drug, cuotas_drug = _llenar(druglike, n_drug, rng, cc, cu,
                                    vecinos_directos, sel_pids,
                                    usar_cuotas=True)
    sel_pids.update(r["pid"] for r in sel_drug)
    for r in sel_drug:
        cc[r["receptor_cluster_id"]] += 1
        cu[r["primary_unit"]] += 1
    n_fill = n_target - len(sel_drug)
    if n_fill > 0:
        sel_fill, _ = _llenar(otros, n_fill, rng, cc, cu,
                              vecinos_directos, sel_pids, usar_cuotas=False)
    else:
        sel_fill = []
    seleccion = sel_drug + sel_fill
    for i, r in enumerate(seleccion, start=1):
        r["selected_rank"] = i
        r["gate_primary"] = r["stratum"] == "druglike"
    metal_disp = sum(1 for r in druglike if r.get("metals"))
    metal_objetivo = round(n_drug * metal_disp / len(druglike)) if druglike else 0
    sel_pids_final = {r["pid"] for r in seleccion}
    pares_directos = 0
    for r in seleccion:
        vecinos_r = vecinos_directos.get(r["pid"], set()) - {r["pid"]}
        pares_directos += len(vecinos_r & sel_pids_final)
    pares_directos //= 2
    metricas = {
        "selected": len(seleccion),
        "target": n_target,
        "druglike_selected": len(sel_drug),
        "gate_primario": len(sel_drug),
        "no_druglike_selected": len(sel_fill),
        "metales_pocket_en_cohorte": sum(1 for r in seleccion if r.get("metals")),
        "metal_objetivo": metal_objetivo,
        "pares_cadena_ge90_en_cohorte": pares_directos,
        "clusters_en_cohorte": len({r["receptor_cluster_id"] for r in seleccion}),
        "unidades_primarias_en_cohorte": len({r["primary_unit"] for r in seleccion}),
        "cuotas_celdas_druglike": cuotas_drug,
    }
    return seleccion, metricas


# ─────────────────────────── salidas ───────────────────────────────────────────


def escribir_jsonl(path: Path, registros: list[dict]) -> None:
    """Escribe JSONL atómico (temp + os.replace)."""
    texto = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in registros)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8", newline="\n")
    os.replace(str(tmp), str(path))


def escribir_json(path: Path, datos: dict) -> None:
    """Escribe JSON atómico con salto de línea final."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(str(tmp), str(path))


def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(
        description="Construye la cohorte confirmatoria D-RC-CONFIRM (FND-05).")
    parser.add_argument("--index", required=True,
                        help="índice Fase B enriquecido (formato PDBbind)")
    parser.add_argument("--pdbbind", required=True, help="directorio data/pdbbind")
    parser.add_argument("--dev-pids", required=True,
                        help="JSON con pids ya vistos en desarrollo, por categoría")
    parser.add_argument("--dev-receptor-pdbs", nargs="*", default=[],
                        help="PDB externos de desarrollo (archivos o directorios); repetible")
    parser.add_argument("--refined-index", default=None,
                        help="índice refined para marcar in_refined (opcional)")
    parser.add_argument("--out-dir", required=True,
                        help="directorio de salida (scripts/artifacts_science/FND-05)")
    parser.add_argument("--n-target", type=int, default=112,
                        help="tamaño objetivo de la cohorte (default: 112)")
    parser.add_argument("--seed", type=int, default=42,
                        help="semilla preregistrada del muestreo (default: 42)")
    parser.add_argument("--respect-denylist", action="store_true",
                        help="excluye del pool los pids de la denylist FND-05 "
                             "(para builders futuros; OFF por defecto para "
                             "preservar la autorreproducibilidad de la cohorte)")
    args = parser.parse_args()

    index = Path(args.index)
    pdbbind = Path(args.pdbbind)
    out_dir = Path(args.out_dir)
    dev_pids = cargar_dev_pids(Path(args.dev_pids))
    archivos_dev = expandir_archivos_pdb(args.dev_receptor_pdbs)
    if not index.is_file():
        print(f"ERROR: índice no encontrado: {index}", file=sys.stderr)
        sys.exit(1)
    if not pdbbind.is_dir():
        print(f"ERROR: pdbbind no encontrado: {pdbbind}", file=sys.stderr)
        sys.exit(1)
    if not dev_pids:
        print("ERROR: --dev-pids no contiene categorías con pids.", file=sys.stderr)
        sys.exit(1)

    print(f"build_confirm_cohort: index={index.name} n_target={args.n_target} "
          f"seed={args.seed} rdkit={'sí' if RDKIT_OK else 'no'} "
          f"numpy={'sí' if NUMPY_OK else 'no'}")
    resultado = construir_cohorte(index, pdbbind, dev_pids, archivos_dev,
                                  Path(args.refined_index) if args.refined_index else None,
                                  args.n_target, args.seed,
                                  respetar_denylist=args.respect_denylist)
    out_dir.mkdir(parents=True, exist_ok=True)
    escribir_jsonl(out_dir / "candidates.jsonl", resultado["candidates"])
    escribir_jsonl(out_dir / "pool_eligible.jsonl", resultado["pool_eligible"])
    escribir_jsonl(out_dir / "per_complex.jsonl", resultado["pool_eligible"])
    escribir_jsonl(out_dir / "failures.jsonl", resultado["failures"])
    escribir_json(out_dir / "metrics.json", resultado["metrics"])
    print(f"Pool: {resultado['metrics']['pipeline'].get('stage_1_pool_completo')} "
          f"| denylist excluidos: {resultado['metrics']['pipeline'].get('stage_1_denylist_excluidos')} "
          f"| excluidos dev: {resultado['metrics']['pipeline'].get('stage_2_excluidos_dev_pid')} "
          f"| excluidos química: {resultado['metrics']['pipeline'].get('stage_3_excluidos_quimica')} "
          f"| excluidos receptor-cadena: {resultado['metrics']['pipeline'].get('stage_4_excluidos_receptor_cadena')} "
          f"| excluidos covalencia: {resultado['metrics']['pipeline'].get('stage_5_excluidos_covalencia')} "
          f"| elegibles: {resultado['metrics']['pipeline'].get('elegibles')} "
          f"| cohorte: {len(resultado['candidates'])}")
    print(f"Salidas escritas en {out_dir}")


if __name__ == "__main__":
    main()
