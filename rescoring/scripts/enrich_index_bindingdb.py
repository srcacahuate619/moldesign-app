"""
Download BindingDB TSV and extract PDB-linked binding affinities.

Strategy:
1. Download BindingDB_All TSV (all entries with PDB cross-references)
2. Filter entries that have PDB IDs matching our 5,316 complexes
3. Select best affinity per PDB ID (Ki > Kd > IC50 > EC50)
4. Merge with existing RCSB data (865 entries)
5. Write enriched INDEX file with full provenance

BindingDB TSV format reference:
  https://www.bindingdb.org/rwd/bind/chemsearch/marvin/BindingDB-TSV-Format.pdf
  Key columns:
  - PDB ID(s) of Target Chain
  - Ki (nM), Kd (nM), IC50 (nM), EC50 (nM)
  - Ligand InChI, SMILES
  - Target Name
"""
import csv
import io
import json
import math
import re
import sys
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. pip install httpx")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────

BINDINGDB_URL = "https://www.bindingdb.org/rwd/bind/downloads/BindingDB_All_202608_tsv.zip"
BINDINGDB_MD5_URL = "https://www.bindingdb.org/rwd/bind/downloads/BindingDB_All_202608_tsv.md5"

BINDING_TYPE_PRIORITY = {"Ki": 0, "Kd": 1, "IC50": 2, "EC50": 3}

# Columns we need from BindingDB TSV
# (column names from BindingDB format doc)
COL_KI = "Ki (nM)"
COL_KD = "Kd (nM)"
COL_IC50 = "IC50 (nM)"
COL_EC50 = "EC50 (nM)"
COL_PDB_COMPLEX = "PDB ID(s) for Ligand-Target Complex"
COL_PDB_CHAIN_PREFIX = "PDB ID(s) of Target Chain"  # columns 1..50
COL_SMILES = "Ligand SMILES"
COL_INCHI = "Ligand InChI"
COL_TARGET = "Target Name"
COL_BINDINGDB_ID = "BindingDB MonomerID"


def parse_nm_value(raw: str) -> tuple[float | None, str]:
    """
    Parse a BindingDB nM value. Handles: '420', '>10000', '<0.1', '~500'.
    Returns (value_nm, precision) where precision is 'exact', '>', '<', '~'.
    """
    if not raw or raw.strip() == "":
        return None, ""
    
    raw = raw.strip()
    
    # Detect precision qualifier
    precision = "exact"
    if raw.startswith(">"):
        precision = ">"
        raw = raw[1:].strip()
    elif raw.startswith("<"):
        precision = "<"
        raw = raw[1:].strip()
    elif raw.startswith("~"):
        precision = "~"
        raw = raw[1:].strip()
    
    try:
        value = float(raw)
        if value <= 0:
            return None, ""
        return value, precision
    except (ValueError, TypeError):
        return None, ""


def value_to_pki(value_nm: float) -> float:
    """Convert nM to pKi = -log10(Kd_M) = 9 - log10(Kd_nM)."""
    if value_nm <= 0:
        return 0.0
    return round(9.0 - math.log10(value_nm), 4)


def discover_pdb_ids(data_dir: Path) -> set[str]:
    """Find all 4-char alphanumeric PDB ID directories."""
    pdb_ids = set()
    for entry in data_dir.iterdir():
        if entry.is_dir() and len(entry.name) == 4 and entry.name.isalnum():
            pdb_ids.add(entry.name.lower())
    return pdb_ids


def load_existing_index(index_path: Path) -> dict[str, dict]:
    """Load existing INDEX file entries."""
    entries = {}
    if not index_path.exists():
        return entries
    
    with open(index_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6 and "//" in parts:
                pdb_id = parts[0].lower()
                resolution = float(parts[1])
                year = int(parts[2])
                sep_idx = parts.index("//")
                binding_raw = " ".join(parts[3:sep_idx])
                pki = float(parts[sep_idx + 1])
                entries[pdb_id] = {
                    "resolution": resolution,
                    "year": year,
                    "raw": binding_raw,
                    "pki": pki,
                    "source": "rcsb",
                }
    return entries


def download_bindingdb(output_path: Path) -> Path:
    """Download BindingDB TSV zip with progress."""
    if output_path.exists():
        print(f"  ✓ BindingDB ya descargado: {output_path}")
        return output_path
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print("  ↓ Descargando BindingDB TSV (~525 MB)...")
    print(f"    URL: {BINDINGDB_URL}")
    
    start = time.time()
    with httpx.stream("GET", BINDINGDB_URL, timeout=600, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        
        with open(output_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 / total
                    mb = downloaded / (1024 * 1024)
                    elapsed = time.time() - start
                    speed = mb / elapsed if elapsed > 0 else 0
                    print(f"\r    [{pct:.1f}%] {mb:.0f}/{total/1024/1024:.0f} MB ({speed:.1f} MB/s)", end="", flush=True)
    
    elapsed = time.time() - start
    print(f"\n  ✓ Descargado en {elapsed:.0f}s")
    return output_path


def extract_pdb_bindings(zip_path: Path, target_pdb_ids: set[str]) -> dict[str, list[dict]]:
    """
    Extract binding affinities from BindingDB TSV for target PDB IDs.
    
    Returns: dict[pdb_id -> list of binding entries]
    """
    results = defaultdict(list)
    n_rows = 0
    n_with_pdb = 0
    n_matched = 0
    
    print("  📊 Procesando BindingDB TSV...")
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find the TSV file inside the zip
        tsv_files = [f for f in zf.namelist() if f.endswith(".tsv")]
        if not tsv_files:
            print("  ✗ No TSV file found in zip")
            return results
        
        tsv_name = tsv_files[0]
        print(f"    TSV: {tsv_name}")
        
        with zf.open(tsv_name) as raw:
            # Wrap in text wrapper for csv reader
            text_wrapper = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_wrapper, delimiter="\t")
            
            # Build list of PDB columns to check:
            # 1. "PDB ID(s) for Ligand-Target Complex" (most specific)
            # 2. "PDB ID(s) of Target Chain 1" through 50
            pdb_columns = None  # Will be detected from header
            
            for row in reader:
                n_rows += 1
                
                # Detect PDB columns from first row's keys
                if pdb_columns is None:
                    pdb_columns = [COL_PDB_COMPLEX]
                    for key in row.keys():
                        if key and key.startswith(COL_PDB_CHAIN_PREFIX):
                            pdb_columns.append(key)
                    print(f"    PDB columns detected: {len(pdb_columns)}")
                
                if n_rows % 500000 == 0:
                    print(f"    Procesados: {n_rows:,} filas, {n_matched:,} matches")
                
                # Collect PDB IDs from all PDB columns
                pdb_ids_in_row = set()
                has_any_pdb = False
                for col in pdb_columns:
                    pdb_field = row.get(col, "")
                    if not pdb_field or pdb_field.strip() == "":
                        continue
                    has_any_pdb = True
                    for token in re.split(r"[,;\s]+", pdb_field):
                        token = token.strip().lower()
                        if len(token) == 4 and token.isalnum():
                            pdb_ids_in_row.add(token)
                
                if not has_any_pdb:
                    continue
                
                n_with_pdb += 1
                
                # Check intersection with our targets
                matched = pdb_ids_in_row & target_pdb_ids
                if not matched:
                    continue
                
                n_matched += 1
                
                # Extract binding values
                for pdb_id in matched:
                    entry = {"pdb_id": pdb_id}
                    
                    # Try each binding type
                    for col_name, btype in [
                        (COL_KI, "Ki"),
                        (COL_KD, "Kd"),
                        (COL_IC50, "IC50"),
                        (COL_EC50, "EC50"),
                    ]:
                        val_str = row.get(col_name, "")
                        value_nm, precision = parse_nm_value(val_str)
                        if value_nm is not None:
                            entry[btype] = {
                                "value_nm": value_nm,
                                "precision": precision,
                                "pki": value_to_pki(value_nm),
                            }
                    
                    # Only add if at least one binding value
                    if any(bt in entry for bt in BINDING_TYPE_PRIORITY):
                        entry["target_name"] = row.get(COL_TARGET, "")
                        entry["smiles"] = row.get(COL_SMILES, "")
                        entry["bindingdb_id"] = row.get(COL_BINDINGDB_ID, "")
                        results[pdb_id].append(entry)
    
    print(f"    Total filas: {n_rows:,}")
    print(f"    Con PDB ID: {n_with_pdb:,}")
    print(f"    Matches con nuestros complejos: {n_matched:,}")
    print(f"    PDB IDs únicos con binding: {len(results)}")
    
    return dict(results)


def select_best_binding(entries: list[dict]) -> dict | None:
    """
    Select best binding entry following priority: Ki > Kd > IC50 > EC50.
    Prefer exact values over inequalities.
    """
    candidates = []
    
    for entry in entries:
        for btype in ["Ki", "Kd", "IC50", "EC50"]:
            if btype in entry:
                bd = entry[btype]
                precision_rank = 0 if bd["precision"] == "exact" else 1
                priority = BINDING_TYPE_PRIORITY[btype]
                candidates.append({
                    "type": btype,
                    "value_nm": bd["value_nm"],
                    "precision": bd["precision"],
                    "pki": bd["pki"],
                    "priority": priority,
                    "precision_rank": precision_rank,
                    "target_name": entry.get("target_name", ""),
                    "smiles": entry.get("smiles", ""),
                })
    
    if not candidates:
        return None
    
    # Sort: exact first, then by type priority, then by potency
    candidates.sort(key=lambda x: (x["precision_rank"], x["priority"], x["value_nm"]))
    return candidates[0]


def fetch_rcsb_metadata(pdb_ids: list[str], batch_size: int = 50) -> dict[str, dict]:
    """Fetch resolution and year from RCSB for PDB IDs without it."""
    
    query = """
    query GetMetadata($ids: [String!]!) {
      entries(entry_ids: $ids) {
        rcsb_id
        rcsb_entry_info {
          resolution_combined
        }
        rcsb_accession_info {
          deposit_date
        }
      }
    }
    """
    
    results = {}
    total = len(pdb_ids)
    
    for i in range(0, total, batch_size):
        batch = pdb_ids[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        try:
            ids_upper = [pid.upper() for pid in batch]
            resp = httpx.post(
                "https://data.rcsb.org/graphql",
                json={"query": query, "variables": {"ids": ids_upper}},
                timeout=30,
            )
            data = (resp.json().get("data") or {}).get("entries") or []
            
            for entry in data:
                if entry is None:
                    continue
                pdb_id = entry.get("rcsb_id", "").lower()
                if not pdb_id:
                    continue
                
                info = entry.get("rcsb_entry_info") or {}
                res_raw = info.get("resolution_combined") or []
                resolution = res_raw[0] if res_raw else 0.0
                
                accession = entry.get("rcsb_accession_info") or {}
                deposit_date = accession.get("deposit_date", "")
                try:
                    year = int(deposit_date[:4]) if deposit_date else 0
                except (ValueError, TypeError):
                    year = 0
                
                results[pdb_id] = {
                    "resolution": round(resolution, 2),
                    "year": year,
                }
            
            if batch_num % 20 == 0 or batch_num == total_batches:
                print(f"    Metadata batch {batch_num}/{total_batches} — {len(results)} entries")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"    ⚠ Metadata batch {batch_num} error: {e}")
    
    return results


def write_enriched_index(
    entries: dict[str, dict],
    output_path: Path,
    report_path: Path,
):
    """Write enriched INDEX file and detailed report."""
    
    n_written = 0
    source_counts = defaultdict(int)
    type_counts = defaultdict(int)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# PDBbind v2020 refined set — Enriched INDEX\n")
        f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("# Sources: RCSB PDB GraphQL API + BindingDB bulk TSV\n")
        f.write("# License: CC0 (RCSB) + CC-BY-SA 3.0 (BindingDB)\n")
        f.write("#\n")
        f.write("# LIMITACIÓN: INDEX reconstruido de fuentes públicas.\n")
        f.write("# Los valores pueden diferir del INDEX oficial de PDBbind.\n")
        f.write("# Para máxima fidelidad, usar INDEX de pdbbind.org.cn\n")
        f.write("#\n")
        f.write("# Formato: PDB_ID  resolution  year  binding_data  //  pKi\n")
        f.write("#\n")
        
        for pdb_id in sorted(entries.keys()):
            entry = entries[pdb_id]
            if entry.get("pki") is None or entry.get("raw") is None:
                continue
            
            line = (
                f"{pdb_id}  "
                f"{entry.get('resolution', 0.0):.2f}  "
                f"{entry.get('year', 0)}  "
                f"{entry['raw']}  "
                f"//  {entry['pki']:.2f}\n"
            )
            f.write(line)
            n_written += 1
            source_counts[entry.get("source", "unknown")] += 1
            
            # Extract binding type from raw string
            btype = entry["raw"].split("=")[0] if "=" in entry["raw"] else "unknown"
            type_counts[btype] += 1
    
    print(f"\n  ✓ INDEX escrito: {output_path}")
    print(f"    Entries con binding data: {n_written}")
    print(f"    Por fuente: {dict(source_counts)}")
    print(f"    Por tipo: {dict(type_counts)}")
    
    # Write detailed report
    pki_values = [e["pki"] for e in entries.values() if e.get("pki") is not None]
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": ["RCSB PDB GraphQL API", "BindingDB All TSV (April 2026)"],
        "total_pdb_ids_in_dataset": 0,  # filled by caller
        "total_with_binding_data": n_written,
        "source_counts": dict(source_counts),
        "binding_type_counts": dict(type_counts),
        "pki_stats": {
            "min": round(min(pki_values), 2) if pki_values else None,
            "max": round(max(pki_values), 2) if pki_values else None,
            "mean": round(sum(pki_values) / len(pki_values), 2) if pki_values else None,
            "n": len(pki_values),
        },
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"    Reporte: {report_path}")
    
    return n_written, report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enrich PDBbind INDEX with BindingDB data"
    )
    parser.add_argument("--data-dir", required=True, help="PDBbind data directory")
    parser.add_argument("--output", default=None, help="Output INDEX file path")
    parser.add_argument("--skip-download", action="store_true", help="Skip BindingDB download")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    downloads_dir = data_dir / "downloads"
    
    print("=" * 70)
    print("  PDBbind INDEX Enrichment — Multi-Source")
    print("=" * 70)
    
    # Step 1: Discover PDB IDs
    print("\n═══ Paso 1: Descubriendo PDB IDs ═══")
    target_ids = discover_pdb_ids(data_dir)
    print(f"  PDB IDs en dataset: {len(target_ids)}")
    
    # Step 2: Load existing INDEX (from RCSB)
    print("\n═══ Paso 2: Cargando INDEX existente (RCSB) ═══")
    existing_index = data_dir / "INDEX_refined_data.2020"
    entries = load_existing_index(existing_index)
    print(f"  Entries existentes (RCSB): {len(entries)}")
    
    # Step 3: Download BindingDB
    if not args.skip_download:
        print("\n═══ Paso 3: Descargando BindingDB ═══")
        zip_path = downloads_dir / "BindingDB_All_202608_tsv.zip"
        download_bindingdb(zip_path)
    else:
        zip_path = downloads_dir / "BindingDB_All_202608_tsv.zip"
        if not zip_path.exists():
            print("  ✗ BindingDB zip no encontrado y --skip-download activo")
            sys.exit(1)
    
    # Step 4: Extract PDB-linked bindings
    print("\n═══ Paso 4: Extrayendo bindings de BindingDB ═══")
    missing_ids = target_ids - set(entries.keys())
    print(f"  PDB IDs sin binding data: {len(missing_ids)}")
    print(f"  Buscando en BindingDB para TODOS los {len(target_ids)} IDs...")
    
    bdb_bindings = extract_pdb_bindings(zip_path, target_ids)
    
    # Step 5: Merge data
    print("\n═══ Paso 5: Fusionando datos ═══")
    new_from_bdb = 0
    upgraded = 0
    
    for pdb_id, bdb_entries in bdb_bindings.items():
        best = select_best_binding(bdb_entries)
        if best is None:
            continue
        
        # Format raw string
        precision_prefix = ""
        if best["precision"] == ">":
            precision_prefix = ">"
        elif best["precision"] == "<":
            precision_prefix = "<"
        elif best["precision"] == "~":
            precision_prefix = "~"
        
        raw_str = f"{best['type']}={precision_prefix}{best['value_nm']}nM"
        
        if pdb_id not in entries:
            # New entry from BindingDB
            entries[pdb_id] = {
                "resolution": 0.0,  # will be filled from RCSB metadata
                "year": 0,
                "raw": raw_str,
                "pki": best["pki"],
                "source": "bindingdb",
                "precision": best["precision"],
            }
            new_from_bdb += 1
        else:
            # Entry exists from RCSB — check if BindingDB has better data
            existing = entries[pdb_id]
            existing_prio = BINDING_TYPE_PRIORITY.get(
                existing["raw"].split("=")[0] if "=" in existing.get("raw", "") else "", 99
            )
            new_prio = BINDING_TYPE_PRIORITY.get(best["type"], 99)
            
            # Upgrade if: BindingDB has higher priority type, OR exact vs inexact
            if (new_prio < existing_prio) or (
                new_prio == existing_prio 
                and best["precision"] == "exact"
                and existing.get("precision", "exact") != "exact"
            ):
                entries[pdb_id]["raw"] = raw_str
                entries[pdb_id]["pki"] = best["pki"]
                entries[pdb_id]["source"] = "bindingdb+rcsb"
                entries[pdb_id]["precision"] = best["precision"]
                upgraded += 1
    
    print(f"  Nuevos de BindingDB: {new_from_bdb}")
    print(f"  Mejorados: {upgraded}")
    print(f"  Total con binding: {sum(1 for e in entries.values() if e.get('pki') is not None)}")
    
    # Step 6: Fetch RCSB metadata for new entries
    print("\n═══ Paso 6: Obteniendo metadata de RCSB ═══")
    needs_metadata = [
        pid for pid, e in entries.items()
        if e.get("resolution", 0) == 0.0 and e.get("pki") is not None
    ]
    print(f"  Entries sin metadata: {len(needs_metadata)}")
    
    if needs_metadata:
        metadata = fetch_rcsb_metadata(needs_metadata)
        for pid, meta in metadata.items():
            if pid in entries:
                entries[pid]["resolution"] = meta["resolution"]
                entries[pid]["year"] = meta["year"]
        print(f"  Metadata obtenida: {len(metadata)}")
    
    # Step 7: Write enriched INDEX
    print("\n═══ Paso 7: Escribiendo INDEX enriquecido ═══")
    output_path = Path(args.output) if args.output else data_dir / "INDEX_refined_data.2020"
    report_path = data_dir / "index_enrichment_report.json"
    
    n_written, report = write_enriched_index(entries, output_path, report_path)
    report["total_pdb_ids_in_dataset"] = len(target_ids)
    report["coverage_pct"] = round(n_written * 100 / len(target_ids), 1) if target_ids else 0
    
    # Rewrite report with coverage
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Summary
    print(f"\n{'=' * 70}")
    print("  RESUMEN DE ENRIQUECIMIENTO")
    print(f"{'=' * 70}")
    print(f"  PDB IDs en dataset:     {len(target_ids)}")
    print(f"  Con binding data:       {n_written}")
    print(f"  Cobertura:              {report['coverage_pct']}%")
    print("  Por fuente:")
    for src, count in report["source_counts"].items():
        print(f"    {src}: {count}")
    print(f"  pKi stats: {report['pki_stats']}")
    
    if report["coverage_pct"] >= 80:
        print("\n  ✓ Cobertura suficiente para entrenamiento robusto")
    elif report["coverage_pct"] >= 50:
        print("\n  ⚠ Cobertura moderada — suficiente para entrenamiento inicial")
    else:
        print("\n  ⚠ Cobertura baja — considerar INDEX oficial de PDBbind")
    
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
