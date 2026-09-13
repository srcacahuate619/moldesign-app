# -*- coding: utf-8 -*-
"""audit_split_leakage.py — FND-02: auditoría de duplicados y fuga en splits.

Análisis SOLO-LECTURA del dataset de Ruta C (data/pose_selector_dataset):

  1. Esquema real de los registros JSON por complejo (claves, tipos, ejemplo).
  2. Deduplicación por PDB/receptor: entre splits y dentro del mismo split.
  3. Deduplicación por ligando: InChIKey completo (exactos) y prefijo de 14
     caracteres (casi-duplicados), calculados desde data/pdbbind/{pid}/{pid}_ligand.sdf.
  4. Fuga train<->val/test por criterio: PDB, ligando, scaffold Murcko y
     secuencia del receptor (SEQRES del protein.pdb, coincidencia exacta y
     similitud por k-meros como aproximación a homólogos cercanos).
  5. Distribución de fuentes (molflex/flexible_redock/ruta_a) por split.
  6. Verificación de conteos: 4300 poses / 203 complejos esperados, hashes
     SHA-256 de los JSONL y del holdout test_pids contra el manifest.

Solo biblioteca estándar. Si RDKit está instalado se usa para InChIKey,
SMILES canónico y scaffold Murcko; si no, esos criterios se degradan a
hashes SHA-256 del contenido del SDF y se anota la limitación.

Salidas (directorio del experimento en --artifacts-dir):
  metrics.json       métricas agregadas (claves en inglés)
  per_complex.jsonl  una línea JSON por complejo auditado
  failures.jsonl     una línea JSON por hallazgo (complex_a, complex_b,
                     criterion, split_a, split_b)

Uso:
  python scripts/audit_split_leakage.py \
      --dataset data/pose_selector_dataset \
      --artifacts-dir scripts/artifacts_science [--experiment FND-02]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    RDKIT_OK = True
except Exception:  # pragma: no cover - degradación sin RDKit
    RDKIT_OK = False

SPLIT_NAMES = ("train", "val", "test")
AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "ASX": "B", "GLX": "Z", "SEC": "U", "PYL": "O",
    "MSE": "M", "HID": "H", "HIE": "H", "HIP": "H", "CYX": "C", "CYM": "C",
}


def configurar_salida() -> None:
    """Fuerza UTF-8 en consola y silencia advertencias de RDKit."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if RDKIT_OK:
        try:
            from rdkit import RDLogger

            RDLogger.DisableLog("rdApp.error")
            RDLogger.DisableLog("rdApp.warning")
        except Exception:
            pass


# ───────────────────────── lectura de datos ─────────────────────────────────


def cargar_jsonl(path: Path) -> list[dict]:
    """Lee un JSONL y devuelve la lista de registros."""
    regs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                regs.append(json.loads(line))
    return regs


def sha256_archivo(path: Path) -> str:
    """SHA-256 de un archivo, leyendo por bloques."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_ligando(pid: str, pdbbind: Path):
    """Molécula RDKit del ligando cristalográfico; None si no se puede leer."""
    if not RDKIT_OK:
        return None
    sdf = pdbbind / pid / f"{pid}_ligand.sdf"
    if not sdf.is_file():
        return None
    try:
        return Chem.MolFromMolFile(str(sdf), sanitize=True)
    except Exception:
        return None


def identidad_ligando(pid: str, pdbbind: Path) -> dict:
    """Identidad química del ligando: InChIKey, SMILES y hash del SDF."""
    sdf = pdbbind / pid / f"{pid}_ligand.sdf"
    identidad = {"pid": pid, "inchikey": None, "inchikey14": None,
                 "smiles": None, "sdf_sha256": None}
    if sdf.is_file():
        identidad["sdf_sha256"] = sha256_archivo(sdf)
    mol = leer_ligando(pid, pdbbind)
    if mol is None:
        return identidad
    try:
        key = Chem.MolToInchiKey(mol)
        identidad["inchikey"] = key
        identidad["inchikey14"] = key[:14]
    except Exception:
        pass
    try:
        identidad["smiles"] = Chem.MolToSmiles(mol, isomericSmiles=True)
    except Exception:
        pass
    return identidad


def scaffold_del_ligando(pid: str, pdbbind: Path) -> str | None:
    """Scaffold Murcko del ligando; None si no hay RDKit o falla."""
    if not RDKIT_OK:
        return None
    mol = leer_ligando(pid, pdbbind)
    if mol is None:
        return None
    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
        return str(scaf) if scaf else None
    except Exception:
        return None


def secuencia_receptor(pid: str, pdbbind: Path) -> str:
    """Secuencia del receptor por cadena, vía SEQRES (fallback: CA de ATOM).

    Devuelve "cadena:SEQ|cadena:SEQ|..." para todas las cadenas poliméricas.
    """
    pdb = pdbbind / pid / f"{pid}_protein.pdb"
    if not pdb.is_file():
        return ""
    try:
        lineas = pdb.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    seqres: dict[str, list[str]] = defaultdict(list)
    for l in lineas:
        if l.startswith("SEQRES"):
            cadena = l[11:12].strip() or "?"
            for i in range(19, 70, 4):
                res = l[i:i + 3].strip()
                if res:
                    seqres[cadena].append(AA3_TO_1.get(res, "X"))
    if seqres:
        return "|".join(f"{c}:{''.join(seqres[c])}" for c in sorted(seqres))
    # Fallback: secuencia desde átomos CA (archivos sin SEQRES).
    por_cadena: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for l in lineas:
        if l.startswith("ATOM") and l[12:16].strip() == "CA":
            cadena = l[21:22].strip() or "?"
            try:
                num = int(l[22:26])
            except ValueError:
                continue
            por_cadena[cadena].append((num, AA3_TO_1.get(l[17:20].strip(), "X")))
    partes = []
    for c in sorted(por_cadena):
        partes.append(f"{c}:{''.join(r for _, r in sorted(por_cadena[c]))}")
    return "|".join(partes)


def kmers(seq: str, k: int = 8) -> set[str]:
    """Conjunto de k-meros de una secuencia (para similitud entre receptores)."""
    return {seq[i:i + k] for i in range(len(seq) - k + 1)}


def similitud_secuencias(a: str, b: str, k: int = 8) -> float:
    """Coeficiente de superposición de k-meros (proxy de identidad)."""
    if not a or not b:
        return 0.0
    ka, kb = kmers(a, k), kmers(b, k)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / min(len(ka), len(kb))


# ───────────────────────── agrupación y hallazgos ───────────────────────────


def pares_de_grupo(pids: list[str], split_de: dict, criterion: str,
                   hallazgos: list[dict], solo_cruce: bool) -> int:
    """Emite hallazgos por cada par de complejos que comparte criterio.

    Si solo_cruce=True, solo cuenta pares en splits distintos (fuga).
    Devuelve el número de pares emitidos.
    """
    n = 0
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            sa, sb = split_de[pids[i]], split_de[pids[j]]
            if solo_cruce and sa == sb:
                continue
            hallazgos.append({
                "complex_a": pids[i], "complex_b": pids[j],
                "criterion": criterion, "split_a": sa, "split_b": sb,
            })
            n += 1
    return n


# ───────────────────────── esquema de registros ─────────────────────────────


def esquema_de_registro(records_dir: Path) -> dict:
    """Esquema del primer registro de pose encontrado + ejemplo anonimizado."""
    esquema: dict[str, str] = {}
    ejemplo: dict = {}
    for f in sorted(records_dir.glob("*.json")):
        try:
            datos = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for clave, regs in datos.get("registros", {}).items():
            if not regs:
                continue
            r = regs[0]
            for k, v in r.items():
                tipo = type(v).__name__
                if isinstance(v, list):
                    tipo = f"list[{type(v[0]).__name__ if v else '?'}]"
                esquema[k] = tipo
            ejemplo = dict(r)
            ejemplo["pid"] = "<pid-anonimizado>"
            ejemplo["file_stem"] = "<stem-anonimizado>"
            ejemplo["_coords"] = {"<atom>": [0.0, 0.0, 0.0]}
            return {
                "record_keys": sorted(esquema.keys()),
                "key_types": esquema,
                "example": ejemplo,
                "registros_value_type": (
                    "dict clave 'pid|source|file_stem' -> lista de poses"
                ),
            }
    return {"record_keys": [], "key_types": {}, "example": {}, "registros_value_type": None}


# ───────────────────────── auditoría principal ──────────────────────────────


def auditar(dataset: Path, pdbbind: Path) -> dict:
    """Ejecuta la auditoría completa y devuelve métricas + hallazgos."""
    metrics: dict = {}
    hallazgos: list[dict] = []
    manifest_path = dataset / "manifest.json"
    manif = None
    if manifest_path.is_file():
        try:
            manif = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 1. Esquema de records/{pid}.json.
    records_dir = dataset / "records"
    metrics["records_schema"] = esquema_de_registro(records_dir)

    # 2. Splits desde los JSONL.
    splits: dict[str, list[dict]] = {}
    for nombre in SPLIT_NAMES:
        path = dataset / f"poses_{nombre}.jsonl"
        splits[nombre] = cargar_jsonl(path) if path.is_file() else []

    split_de: dict[str, str] = {}
    pids_por_split: dict[str, set[str]] = defaultdict(set)
    for nombre, regs in splits.items():
        for r in regs:
            pid = r["pid"]
            split_de[pid] = nombre
            pids_por_split[nombre].add(pid)

    # 3. Verificación de conteos y hashes.
    esperado = (manif or {}).get("conteos", {}) if manif else {}
    conteos = {
        s: {"poses": len(splits[s]), "complejos": len(pids_por_split[s])}
        for s in SPLIT_NAMES
    }
    conteos["total"] = {
        "poses": sum(len(splits[s]) for s in SPLIT_NAMES),
        "complejos": len(split_de),
    }
    metrics["conteos"] = conteos
    metrics["conteos_esperados"] = {
        s: {"poses": esperado.get(s, {}).get("registros"),
            "complejos": esperado.get(s, {}).get("complejos")}
        for s in SPLIT_NAMES
    }
    metrics["conteos_coinciden"] = all(
        conteos[s]["poses"] == esperado.get(s, {}).get("registros")
        and conteos[s]["complejos"] == esperado.get(s, {}).get("complejos")
        for s in SPLIT_NAMES
    )
    sha_manif = (manif or {}).get("sha256", {})
    metrics["sha256_jsonl_ok"] = {
        s: sha256_archivo(dataset / f"poses_{s}.jsonl") == sha_manif.get(f"poses_{s}.jsonl")
        for s in SPLIT_NAMES
    }
    test_pids_manif = (manif or {}).get("test_pids", [])
    hash_test_manif = (manif or {}).get("test_pids_sha256")
    hash_test_real = hashlib.sha256(
        json.dumps(sorted(pids_por_split["test"])).encode("utf-8")).hexdigest()
    metrics["test_pids_sha256_ok"] = (
        sorted(pids_por_split["test"]) == sorted(test_pids_manif)
        and hash_test_real == hash_test_manif
    )
    metrics["split_method"] = (manif or {}).get("split_method")

    # 4. Deduplicación por PDB/receptor: un pid en más de un split.
    pids_multi = []
    for nombre in SPLIT_NAMES:
        for otro in SPLIT_NAMES:
            if nombre >= otro:
                continue
            comunes = sorted(pids_por_split[nombre] & pids_por_split[otro])
            for pid in comunes:
                pids_multi.append(pid)
                hallazgos.append({
                    "complex_a": pid, "complex_b": pid, "criterion": "pdb",
                    "split_a": nombre, "split_b": otro,
                })
    metrics["pids_en_multiples_splits"] = sorted(set(pids_multi))
    metrics["duplicate_pdb_pairs"] = [
        h for h in hallazgos if h["criterion"] == "pdb"
    ]

    # 5. Identidad de ligando + scaffold + secuencia por pid.
    ids: dict[str, dict] = {}
    scaffolds: dict[str, str | None] = {}
    secuencias: dict[str, str] = {}
    for pid in sorted(split_de):
        ids[pid] = identidad_ligando(pid, pdbbind)
        scaffolds[pid] = scaffold_del_ligando(pid, pdbbind)
        secuencias[pid] = secuencia_receptor(pid, pdbbind)

    # 6. Duplicados y fuga por ligando (InChIKey completo y prefijo 14).
    por_key: dict[str, list[str]] = defaultdict(list)
    por_key14: dict[str, list[str]] = defaultdict(list)
    por_smiles: dict[str, list[str]] = defaultdict(list)
    for pid, identidad in ids.items():
        if identidad["inchikey"]:
            por_key[identidad["inchikey"]].append(pid)
        if identidad["inchikey14"]:
            por_key14[identidad["inchikey14"]].append(pid)
        if identidad["smiles"]:
            por_smiles[identidad["smiles"]].append(pid)

    grupos_dup = {k: sorted(v) for k, v in por_key.items() if len(v) > 1}
    grupos14_dup = {k: sorted(v) for k, v in por_key14.items() if len(v) > 1}
    grupos_smi = {k: sorted(v) for k, v in por_smiles.items() if len(v) > 1}

    lig_leak = 0
    lig_dup = 0
    for key, pids in grupos_dup.items():
        splits_grupo = {split_de[p] for p in pids}
        if len(splits_grupo) > 1:
            lig_leak += pares_de_grupo(pids, split_de, "ligando_inchikey",
                                       hallazgos, solo_cruce=True)
        lig_dup += pares_de_grupo(pids, split_de, "ligando_inchikey_dup",
                                  hallazgos, solo_cruce=False)
    metrics["duplicate_ligand_groups"] = [
        {"inchikey": k, "pids": v, "splits": sorted({split_de[p] for p in v})}
        for k, v in grupos_dup.items()
    ]
    metrics["ligand_leak_pairs"] = lig_leak

    casi_dup = {k: v for k, v in grupos14_dup.items()
                if len({ids[p]["inchikey"] for p in v if ids[p]["inchikey"]}) > 1}
    casi_leak = 0
    for key, pids in casi_dup.items():
        splits_grupo = {split_de[p] for p in pids}
        if len(splits_grupo) > 1:
            casi_leak += pares_de_grupo(pids, split_de, "ligando_prefijo14",
                                        hallazgos, solo_cruce=True)
    metrics["duplicate_ligand_prefix14_groups"] = [
        {"prefijo": k, "pids": v, "splits": sorted({split_de[p] for p in v})}
        for k, v in casi_dup.items()
    ]
    metrics["ligand_prefix14_leak_pairs"] = casi_leak
    metrics["duplicate_smiles_groups"] = len(grupos_smi)
    metrics["rdkit_available"] = RDKIT_OK

    # 7. Fuga por scaffold Murcko (recomputado de forma independiente).
    por_scaf: dict[str, list[str]] = defaultdict(list)
    for pid, scaf in scaffolds.items():
        if scaf:
            por_scaf[scaf].append(pid)
    scaf_leak = 0
    grupos_scaf_dup = {k: sorted(v) for k, v in por_scaf.items() if len(v) > 1}
    for scaf, pids in grupos_scaf_dup.items():
        splits_grupo = {split_de[p] for p in pids}
        if len(splits_grupo) > 1:
            scaf_leak += pares_de_grupo(pids, split_de, "scaffold",
                                        hallazgos, solo_cruce=True)
    metrics["scaffold_leak_pairs"] = scaf_leak
    metrics["scaffold_groups_total"] = len(por_scaf)
    metrics["scaffold_groups_compartidos"] = len(grupos_scaf_dup)
    metrics["scaffold_groups_spanning_splits"] = [
        {"scaffold": k, "pids": v, "splits": sorted({split_de[p] for p in v})}
        for k, v in grupos_scaf_dup.items()
        if len({split_de[p] for p in v}) > 1
    ]

    # 8. Fuga por secuencia de receptor: coincidencia exacta y homólogos.
    por_seq: dict[str, list[str]] = defaultdict(list)
    for pid, seq in secuencias.items():
        if seq:
            por_seq[seq].append(pid)
    seq_leak = 0
    grupos_seq_dup = {k: sorted(v) for k, v in por_seq.items() if len(v) > 1}
    for seq, pids in grupos_seq_dup.items():
        splits_grupo = {split_de[p] for p in pids}
        if len(splits_grupo) > 1:
            seq_leak += pares_de_grupo(pids, split_de, "secuencia_exacta",
                                       hallazgos, solo_cruce=True)
    metrics["sequence_exact_leak_pairs"] = seq_leak
    metrics["sequence_exact_groups_spanning_splits"] = [
        {"pids": v, "splits": sorted({split_de[p] for p in v})}
        for v in grupos_seq_dup.values()
        if len({split_de[p] for p in v}) > 1
    ]
    # Homólogos cercanos: similitud de k-meros >= umbral.
    pids_con_seq = sorted(p for p in split_de if secuencias.get(p))
    homologos: list[dict] = []
    homologos_leak = 0
    for i in range(len(pids_con_seq)):
        for j in range(i + 1, len(pids_con_seq)):
            a, b = pids_con_seq[i], pids_con_seq[j]
            if secuencias[a] == secuencias[b]:
                continue  # ya cubierto como exacta
            sim = similitud_secuencias(secuencias[a], secuencias[b])
            if sim >= 0.9:
                sa, sb = split_de[a], split_de[b]
                homologos.append({"complex_a": a, "complex_b": b,
                                  "similitud_kmers8": round(sim, 4),
                                  "split_a": sa, "split_b": sb})
                if sa != sb:
                    homologos_leak += 1
    metrics["sequence_near_groups"] = homologos
    metrics["sequence_near_leak_pairs"] = homologos_leak

    # 9. Distribución de fuentes por split.
    fuentes: dict[str, dict[str, int]] = {}
    total_fuentes: Counter = Counter()
    for nombre, regs in splits.items():
        c = Counter(r["source"] for r in regs)
        fuentes[nombre] = dict(sorted(c.items()))
        total_fuentes.update(c)
    metrics["source_distribution"] = fuentes
    metrics["source_distribution_pct"] = {
        nombre: {src: round(100.0 * n / sum(c.values()), 2)
                 for src, n in c.items()}
        for nombre, c in fuentes.items()
    }
    metrics["source_totals"] = dict(total_fuentes)

    # 10. Duplicados de emisión: líneas JSONL idénticas o misma clave pose.
    claves_vistas: set[tuple] = set()
    lineas_vistas: set[str] = set()
    dup_pose_clave = 0
    dup_linea = 0
    for nombre, regs in splits.items():
        for r in regs:
            clave = (r["pid"], r["source"], r["file_stem"], r["model_idx"])
            if clave in claves_vistas:
                dup_pose_clave += 1
            claves_vistas.add(clave)
            linea = json.dumps(r, sort_keys=True, ensure_ascii=False)
            if linea in lineas_vistas:
                dup_linea += 1
            lineas_vistas.add(linea)
    metrics["duplicate_pose_keys"] = dup_pose_clave
    metrics["duplicate_pose_lines"] = dup_linea

    # 11. Duplicados casi idénticos dentro del mismo complejo (poses clonadas
    # entre fuentes/archivos del mismo pid): misma tupla (score, rmsd,
    # contactos, clashes).
    por_pid_tuplas: dict[str, dict[tuple, list[str]]] = defaultdict(
        lambda: defaultdict(list))
    for nombre, regs in splits.items():
        for r in regs:
            t = (r.get("vina_score"), r.get("rmsd"), r.get("n_contacts_4"),
                 r.get("n_contacts_6"), r.get("n_clashes"))
            por_pid_tuplas[r["pid"]][t].append(
                f"{r['source']}|{r['file_stem']}|{r['model_idx']}")
    poses_clonadas = {
        pid: {tuple(t): claves for t, claves in tuplas.items() if len(claves) > 1}
        for pid, tuplas in por_pid_tuplas.items()
    }
    poses_clonadas = {p: v for p, v in poses_clonadas.items() if v}
    metrics["duplicate_pose_tuples_per_pid"] = {
        p: sum(len(c) - 1 for c in v.values()) for p, v in poses_clonadas.items()
    }
    metrics["duplicate_pose_tuples_total"] = sum(
        metrics["duplicate_pose_tuples_per_pid"].values())

    # 12. Cobertura: pids en records/ sin split y viceversa.
    pids_records = {f.stem for f in records_dir.glob("*.json")}
    pids_splits = set(split_de)
    metrics["records_files"] = len(pids_records)
    metrics["pids_en_records_sin_split"] = sorted(pids_records - pids_splits)
    metrics["pids_en_splits_sin_records"] = sorted(pids_splits - pids_records)

    # 13. Excluidos del manifest no deben aparecer en los JSONL.
    excluidos = (manif or {}).get("excluidos", {}).get("complejos", {})
    excluidos_flex = {k.split(":")[1] for k in excluidos
                      if k.startswith("flexible_redock:")}
    viola_exclusion = []
    for nombre, regs in splits.items():
        for r in regs:
            if r["source"] == "flexible_redock" and r["pid"] in excluidos_flex:
                viola_exclusion.append((r["pid"], nombre))
    metrics["excluidos_presentes_en_splits"] = sorted(set(viola_exclusion))

    # 14. Conteos de poses por pid: records vs jsonl.
    rec_conteo: Counter = Counter()
    for f in sorted(records_dir.glob("*.json")):
        try:
            datos = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rec_conteo[datos.get("pid", f.stem)] = sum(
            len(regs) for regs in datos.get("registros", {}).values())
    split_conteo = Counter(r["pid"] for s in SPLIT_NAMES for r in splits[s])
    diffs = {p: (rec_conteo.get(p, 0), split_conteo.get(p, 0))
             for p in set(rec_conteo) | set(split_conteo)
             if rec_conteo.get(p, 0) != split_conteo.get(p, 0)}
    metrics["records_vs_jsonl_diffs"] = diffs
    metrics["total_poses_records"] = sum(rec_conteo.values())
    metrics["total_poses_splits"] = sum(split_conteo.values())

    return metrics, hallazgos


# ───────────────────────── salidas ──────────────────────────────────────────


def escribir_salidas(metrics: dict, hallazgos: list[dict], per_complex: list[dict],
                     exp_dir: Path) -> None:
    """Escribe metrics.json, failures.jsonl y per_complex.jsonl de forma atómica."""
    exp_dir.mkdir(parents=True, exist_ok=True)
    for nombre, texto in (
        ("metrics.json", json.dumps(metrics, indent=2, ensure_ascii=False) + "\n"),
        ("failures.jsonl", "\n".join(json.dumps(h, ensure_ascii=False)
                                     for h in hallazgos) + ("\n" if hallazgos else "")),
        ("per_complex.jsonl", "\n".join(json.dumps(p, ensure_ascii=False)
                                        for p in per_complex) + "\n"),
    ):
        tmp = exp_dir / f"{nombre}.tmp"
        tmp.write_text(texto, encoding="utf-8")
        os.replace(str(tmp), str(exp_dir / nombre))


def main() -> None:
    configurar_salida()
    parser = argparse.ArgumentParser(
        description="Auditoría FND-02 de duplicados y fuga en splits de Ruta C.")
    parser.add_argument("--dataset", required=True,
                        help="ruta de data/pose_selector_dataset")
    parser.add_argument("--artifacts-dir", required=True,
                        help="ruta de scripts/artifacts_science")
    parser.add_argument("--experiment", default="FND-02",
                        help="identificador del experimento (default: FND-02)")
    parser.add_argument("--pdbbind", default=None,
                        help="ruta de data/pdbbind (default: dataset/../pdbbind)")
    args = parser.parse_args()

    dataset = Path(args.dataset)
    pdbbind = Path(args.pdbbind) if args.pdbbind else (dataset.parent / "pdbbind")
    exp_dir = Path(args.artifacts_dir) / args.experiment
    if not dataset.is_dir():
        print(f"ERROR: no existe el dataset: {dataset}", file=sys.stderr)
        sys.exit(1)

    print(f"Auditoría FND-02: dataset={dataset} pdbbind={pdbbind} "
          f"rdkit={'sí' if RDKIT_OK else 'no'}")
    metrics, hallazgos = auditar(dataset, pdbbind)

    # per_complex.jsonl: identidad por complejo para trazabilidad futura.
    split_de = {}
    for s in SPLIT_NAMES:
        for r in cargar_jsonl(dataset / f"poses_{s}.jsonl"):
            split_de.setdefault(r["pid"], s)
    per_complex = []
    for pid in sorted(split_de):
        identidad = identidad_ligando(pid, pdbbind)
        per_complex.append({
            "pid": pid, "split": split_de[pid],
            "inchikey": identidad.get("inchikey"),
            "inchikey14": identidad.get("inchikey14"),
            "smiles": identidad.get("smiles"),
            "scaffold": scaffold_del_ligando(pid, pdbbind),
            "secuencia_sha256": hashlib.sha256(
                secuencia_receptor(pid, pdbbind).encode("utf-8")).hexdigest(),
        })

    escribir_salidas(metrics, hallazgos, per_complex, exp_dir)
    print(f"Hallazgos: {len(hallazgos)}")
    print(f"Métricas: {exp_dir / 'metrics.json'}")
    print(f"Failures: {exp_dir / 'failures.jsonl'}")
    print(f"Per-complex: {exp_dir / 'per_complex.jsonl'}")


if __name__ == "__main__":
    main()
