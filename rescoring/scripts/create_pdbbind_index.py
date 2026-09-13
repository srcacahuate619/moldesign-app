#!/usr/bin/env python3
"""
scripts/create_pdbbind_index.py

Reconstrucción del INDEX file de PDBbind refined set a partir de
fuentes públicas (RCSB PDB API).

CONTEXTO:
  La descarga de PDBbind desde Zenodo (doi:10.5281/zenodo.7014096) incluye
  los archivos estructurales (proteínas + ligandos) pero puede no incluir
  el INDEX file oficial con las binding affinities experimentales.

  El INDEX file es CRÍTICO para entrenamiento ML porque contiene:
    - PDB ID
    - Resolución cristalográfica (Å)
    - Año de publicación
    - Binding affinity (Ki, Kd, IC50) con unidades
    - pKi calculado (= -log10(Kd_M))

  Este script reconstruye el INDEX desde la API pública de RCSB PDB,
  que incluye datos de binding affinity provenientes de BindingDB y
  PDBbind-CN (con atribución).

FUENTE DE DATOS:
  - RCSB PDB GraphQL API (https://data.rcsb.org/graphql)
  - Campos: rcsb_binding_affinity (tipo, valor, unidad, proveniencia)
  - Campos: rcsb_entry_info (resolución, fecha de depósito)
  - Licencia: CC0 (datos de RCSB PDB son dominio público)

LIMITACIONES DOCUMENTADAS:
  - No todas las entries de PDBbind tienen binding data en RCSB
  - RCSB puede tener datos ligeramente diferentes de los originales de PDBbind
  - La cobertura esperada es ~80-95% del refined set
  - Entries sin binding data se reportan pero se excluyen del INDEX

Uso:
  python scripts/create_pdbbind_index.py --data-dir /data/pdbbind
  python scripts/create_pdbbind_index.py --data-dir /data/pdbbind --batch-size 50
  python scripts/create_pdbbind_index.py --data-dir /data/pdbbind --dry-run

Requerimientos:
  - httpx o requests
  - Conexión a internet (acceso a RCSB PDB API)
  - Directorio con datos PDBbind extraídos (subdirectorios {pdb_id}/)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Intentar importar http client
try:
    import httpx

    def _post_json(url: str, payload: dict, timeout: float = 60.0) -> dict:
        resp = httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

except ImportError:
    try:
        import requests

        def _post_json(url: str, payload: dict, timeout: float = 60.0) -> dict:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()

    except ImportError:
        _post_json = None  # type: ignore


# ─── Configuración ────────────────────────────────────────────────

RCSB_GRAPHQL_URL = "https://data.rcsb.org/graphql"

# Preferencia de tipo de binding data (Ki > Kd > IC50 > EC50)
# Ki es la más relevante para scoring de docking
BINDING_TYPE_PRIORITY = {"Ki": 0, "Kd": 1, "IC50": 2, "EC50": 3}

# Factores de conversión a nanomolar
UNIT_TO_NM = {
    "fm": 1e-6,
    "pm": 1e-3,
    "nm": 1.0,
    "um": 1e3,
    "µm": 1e3,
    "mm": 1e6,
    "m": 1e9,
}

# GraphQL query para obtener binding affinity y metadata
# Nota: deposit_date está en rcsb_accession_info (no rcsb_entry_info)
# resolution_combined devuelve un array [float]
GRAPHQL_QUERY = """
query GetBindingData($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_entry_info {
      resolution_combined
    }
    rcsb_accession_info {
      deposit_date
    }
    rcsb_binding_affinity {
      comp_id
      type
      value
      unit
      provenance_code
    }
  }
}
"""

# Fallback: query simplificada si la anterior falla
GRAPHQL_QUERY_SIMPLE = """
query GetBindingData($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    rcsb_entry_info {
      resolution_combined
    }
    rcsb_binding_affinity {
      type
      value
      unit
    }
  }
}
"""


def discover_pdb_ids(data_dir: Path) -> list[str]:
    """
    Descubrir PDB IDs a partir de los directorios extraídos.

    Busca directorios con nombre de 4 caracteres alfanuméricos
    que contengan al menos un archivo _protein.pdb o _ligand.sdf.
    """
    pdb_ids = []

    for entry in sorted(data_dir.iterdir()):
        if not entry.is_dir():
            continue

        name = entry.name.lower()

        # PDB IDs son exactamente 4 caracteres alfanuméricos
        if len(name) != 4 or not name.isalnum():
            # Podría ser un subdirectorio (e.g., v2020-refined/)
            # Buscar recursivamente un nivel
            if entry.is_dir():
                for sub in entry.iterdir():
                    if sub.is_dir() and len(sub.name) == 4 and sub.name.isalnum():
                        pdb_ids.append(sub.name.lower())
            continue

        # Verificar que tiene archivos de estructura
        has_files = (
            (entry / f"{name}_protein.pdb").exists()
            or (entry / f"{name}_ligand.sdf").exists()
        )

        if has_files:
            pdb_ids.append(name)

    return sorted(set(pdb_ids))


def convert_to_nm(value: float, unit: str) -> float | None:
    """Convertir valor de binding affinity a nanomolar."""
    unit_lower = unit.lower().strip()

    # Intentar mapeo directo
    if unit_lower in UNIT_TO_NM:
        return value * UNIT_TO_NM[unit_lower]

    # Patrones comunes en RCSB
    if "nm" in unit_lower or "nanomol" in unit_lower:
        return value * 1.0
    if "um" in unit_lower or "micromol" in unit_lower:
        return value * 1e3
    if "mm" in unit_lower or "millimol" in unit_lower:
        return value * 1e6
    if "pm" in unit_lower or "picomol" in unit_lower:
        return value * 1e-3
    if "fm" in unit_lower or "femtomol" in unit_lower:
        return value * 1e-6
    if unit_lower == "m" or "mol/l" in unit_lower:
        return value * 1e9

    return None


def value_to_pki(value_nm: float) -> float:
    """Convertir valor en nM a pKi = -log10(Kd_M) = 9 - log10(Kd_nM)."""
    if value_nm <= 0:
        return 0.0
    return round(9.0 - math.log10(value_nm), 4)


def select_best_affinity(affinities: list[dict]) -> dict | None:
    """
    Seleccionar la mejor binding affinity de las disponibles.

    Prioridad: Ki > Kd > IC50 > EC50
    Si hay múltiples del mismo tipo, elegir la de menor valor (más potente).
    """
    if not affinities:
        return None

    # Filtrar las que tienen tipo, valor y unidad
    valid = []
    for aff in affinities:
        atype = aff.get("type", "")
        value = aff.get("value")
        unit = aff.get("unit", "")

        if not atype or value is None or not unit:
            continue

        value_nm = convert_to_nm(float(value), unit)
        if value_nm is None or value_nm <= 0:
            continue

        priority = BINDING_TYPE_PRIORITY.get(atype, 99)
        valid.append({
            "type": atype,
            "value": float(value),
            "unit": unit,
            "value_nm": value_nm,
            "pki": value_to_pki(value_nm),
            "priority": priority,
            "provenance": aff.get("provenance_code", ""),
        })

    if not valid:
        return None

    # Ordenar por prioridad de tipo, luego por potencia (menor nM = más potente)
    valid.sort(key=lambda x: (x["priority"], x["value_nm"]))
    return valid[0]


def fetch_binding_data_batch(
    pdb_ids: list[str],
    timeout: float = 60.0,
) -> dict[str, dict]:
    """
    Fetch binding data para un batch de PDB IDs via RCSB GraphQL.

    Returns:
        dict[pdb_id -> {resolution, year, binding_type, value_nm, pki, raw}]
    """
    results = {}

    # RCSB espera IDs en mayúscula
    ids_upper = [pid.upper() for pid in pdb_ids]

    try:
        payload = {
            "query": GRAPHQL_QUERY,
            "variables": {"ids": ids_upper},
        }
        response = _post_json(RCSB_GRAPHQL_URL, payload, timeout=timeout)
    except Exception:
        # Fallback a query simplificada
        try:
            payload = {
                "query": GRAPHQL_QUERY_SIMPLE,
                "variables": {"ids": ids_upper},
            }
            response = _post_json(RCSB_GRAPHQL_URL, payload, timeout=timeout)
        except Exception as e:
            print(f"  ✗ Error en RCSB API: {e}", file=sys.stderr)
            return results

    entries = (response.get("data") or {}).get("entries") or []

    for entry in entries:
        if entry is None:
            continue

        pdb_id = entry.get("rcsb_id", "").lower()
        if not pdb_id:
            continue

        # Resolución (resolution_combined es un array [float])
        info = entry.get("rcsb_entry_info") or {}
        resolution_raw = info.get("resolution_combined") or []
        resolution = resolution_raw[0] if resolution_raw else 0.0

        # Año de depósito (en rcsb_accession_info)
        accession = entry.get("rcsb_accession_info") or {}
        deposit_date = accession.get("deposit_date", "")
        try:
            year = int(deposit_date[:4]) if deposit_date else 0
        except (ValueError, TypeError):
            year = 0

        # Binding affinity
        affinities = entry.get("rcsb_binding_affinity") or []
        best = select_best_affinity(affinities)

        if best:
            # Formatear binding string como PDBbind INDEX
            unit_str = best["unit"].lower().replace("µ", "u")
            raw_str = f"{best['type']}={best['value']}{unit_str}"

            results[pdb_id] = {
                "resolution": round(resolution, 2),
                "year": year,
                "binding_type": best["type"],
                "value_nm": best["value_nm"],
                "pki": best["pki"],
                "raw": raw_str,
                "provenance": best["provenance"],
            }
        else:
            # Entry sin binding data — registrar solo metadata
            results[pdb_id] = {
                "resolution": round(resolution, 2),
                "year": year,
                "binding_type": None,
                "value_nm": None,
                "pki": None,
                "raw": None,
                "provenance": None,
            }

    return results


def write_index_file(
    data: dict[str, dict],
    output_path: Path,
) -> int:
    """
    Escribir INDEX file en formato PDBbind.

    Formato:
      # Reconstructed PDBbind INDEX from RCSB PDB API
      # PDB_ID  resolution  year  binding_data  pKi
      1a1e  2.40  1997  Ki=13uM  //  4.89

    Returns:
        número de entries escritos (con binding data)
    """
    n_written = 0

    with open(output_path, "w") as f:
        f.write("# PDBbind v2020 refined set — INDEX reconstructed from RCSB PDB API\n")
        f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("# Source: RCSB PDB GraphQL API (https://data.rcsb.org/graphql)\n")
        f.write("# License: CC0 (RCSB PDB data is public domain)\n")
        f.write("#\n")
        f.write("# LIMITACIÓN: Este INDEX fue reconstruido automáticamente y puede\n")
        f.write("# diferir del INDEX oficial de PDBbind. Los valores de binding\n")
        f.write("# affinity provienen de RCSB (fuentes: BindingDB, PDBbind-CN,\n")
        f.write("# literatura). Para máxima fidelidad, usar el INDEX original\n")
        f.write("# de http://www.pdbbind.org.cn/\n")
        f.write("#\n")
        f.write("# Formato: PDB_ID  resolution  year  binding_data  //  pKi\n")
        f.write("#\n")

        for pdb_id in sorted(data.keys()):
            entry = data[pdb_id]

            # Solo escribir entries CON binding data
            if entry["pki"] is None or entry["raw"] is None:
                continue

            line = (
                f"{pdb_id}  "
                f"{entry['resolution']:.2f}  "
                f"{entry['year']}  "
                f"{entry['raw']}  "
                f"//  {entry['pki']:.2f}\n"
            )
            f.write(line)
            n_written += 1

    return n_written


def write_report(
    pdb_ids: list[str],
    data: dict[str, dict],
    output_path: Path,
) -> None:
    """Escribir reporte JSON de la reconstrucción."""
    with_binding = {k: v for k, v in data.items() if v.get("pki") is not None}
    without_binding = {k: v for k, v in data.items() if v.get("pki") is None}
    not_found = [pid for pid in pdb_ids if pid not in data]

    # Estadísticas de binding types
    type_counts = {}
    provenances = {}
    pkis = []
    for v in with_binding.values():
        bt = v.get("binding_type", "unknown")
        type_counts[bt] = type_counts.get(bt, 0) + 1
        prov = v.get("provenance", "unknown")
        provenances[prov] = provenances.get(prov, 0) + 1
        if v["pki"]:
            pkis.append(v["pki"])

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "RCSB PDB GraphQL API",
        "total_pdb_ids_scanned": len(pdb_ids),
        "total_found_in_rcsb": len(data),
        "total_with_binding_data": len(with_binding),
        "total_without_binding_data": len(without_binding),
        "total_not_found_in_rcsb": len(not_found),
        "coverage_pct": round(len(with_binding) / max(len(pdb_ids), 1) * 100, 1),
        "binding_type_counts": type_counts,
        "provenance_counts": provenances,
        "pki_stats": {
            "min": round(min(pkis), 2) if pkis else None,
            "max": round(max(pkis), 2) if pkis else None,
            "mean": round(sum(pkis) / len(pkis), 2) if pkis else None,
            "n": len(pkis),
        },
        "missing_pdb_ids": sorted(not_found)[:50],
        "no_binding_pdb_ids": sorted(without_binding.keys())[:50],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Reconstruir PDBbind INDEX file desde RCSB PDB API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Este script reconstruye el INDEX file de PDBbind usando la API pública
de RCSB PDB. Los datos de binding affinity provienen de BindingDB,
PDBbind-CN y literatura, disponibles via RCSB.

Uso típico después de descargar desde Zenodo:
  1. python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind
  2. python scripts/create_pdbbind_index.py --data-dir /data/pdbbind

El INDEX generado permite ejecutar el pipeline de entrenamiento ML.
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directorio con datos PDBbind extraídos (contiene subdirs {pdb_id}/)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path para el INDEX file (default: data_dir/INDEX_refined_data.2020)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Número de PDB IDs por request a RCSB (default: 50)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay en segundos entre batches (default: 0.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo descubrir PDB IDs sin consultar RCSB",
    )
    parser.add_argument(
        "--report-out",
        type=str,
        default=None,
        help="Path para reporte JSON (default: data_dir/index_reconstruction_report.json)",
    )

    args = parser.parse_args()

    if _post_json is None:
        print(
            "ERROR: Se requiere 'httpx' o 'requests'. Instalar con:\n"
            "  pip install httpx\n"
            "  o: pip install requests",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: Directorio no existe: {data_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else data_dir / "INDEX_refined_data.2020"
    report_path = Path(args.report_out) if args.report_out else data_dir / "index_reconstruction_report.json"

    print("=" * 70)
    print("PDBbind INDEX Reconstruction — RCSB PDB API")
    print("=" * 70)

    # ─── Paso 0: Verificar si INDEX ya existe ───
    existing_index = None
    for candidate in [
        data_dir / "INDEX_refined_data.2020",
        data_dir / "INDEX_refined_data.2019",
        data_dir / "INDEX_refined_data.txt",
        data_dir / "index" / "INDEX_refined_data.2020",
    ]:
        if candidate.exists():
            existing_index = candidate
            break

    if existing_index:
        # Contar entries
        n_entries = 0
        with open(existing_index) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 4 and len(parts[0]) == 4:
                        n_entries += 1

        print(f"\n  ✓ INDEX file ya existe: {existing_index}")
        print(f"    Entries: {n_entries}")
        print("\n  No es necesario reconstruir. Use --output para forzar nueva generación.\n")

        if args.output is None:
            sys.exit(0)
        else:
            print(f"  --output especificado, generando nuevo INDEX en: {output_path}\n")

    # ─── Paso 1: Descubrir PDB IDs ───
    print("\n═══ Paso 1: Descubriendo PDB IDs en datos extraídos ═══")
    pdb_ids = discover_pdb_ids(data_dir)
    print(f"  PDB IDs encontrados: {len(pdb_ids)}")

    if len(pdb_ids) == 0:
        print(
            "\n  ✗ No se encontraron PDB IDs.\n"
            "    ¿Se extrajeron los datos correctamente?\n"
            "    Estructura esperada: data_dir/{pdb_id}/{pdb_id}_protein.pdb\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(pdb_ids) < 100:
        print(f"  ⚠ Solo {len(pdb_ids)} PDB IDs (esperado ~5000). Datos incompletos?")

    print(f"  Primeros 10: {pdb_ids[:10]}")
    print(f"  Últimos  10: {pdb_ids[-10:]}")

    if args.dry_run:
        print(f"\n  --dry-run: {len(pdb_ids)} PDB IDs descubiertos. Sin consultar RCSB.\n")
        sys.exit(0)

    # ─── Paso 2: Consultar RCSB PDB en batches ───
    print(f"\n═══ Paso 2: Consultando RCSB PDB ({len(pdb_ids)} IDs, batch={args.batch_size}) ═══")
    all_data: dict[str, dict] = {}
    n_batches = math.ceil(len(pdb_ids) / args.batch_size)
    start_time = time.time()

    for i in range(0, len(pdb_ids), args.batch_size):
        batch = pdb_ids[i : i + args.batch_size]
        batch_num = i // args.batch_size + 1

        try:
            batch_data = fetch_binding_data_batch(batch)
            all_data.update(batch_data)

            with_binding = sum(1 for v in batch_data.values() if v.get("pki") is not None)
            elapsed = time.time() - start_time
            eta = elapsed / max(batch_num, 1) * (n_batches - batch_num)

            print(
                f"\r  Batch {batch_num}/{n_batches} — "
                f"encontrados: {len(all_data)}, "
                f"con binding: {sum(1 for v in all_data.values() if v.get('pki') is not None)}, "
                f"ETA: {eta:.0f}s   ",
                end="",
                flush=True,
            )

        except Exception as e:
            print(f"\n  ⚠ Error en batch {batch_num}: {e}", file=sys.stderr)

        # Rate limiting — ser amable con RCSB
        if i + args.batch_size < len(pdb_ids):
            time.sleep(args.delay)

    print()  # newline

    # ─── Paso 3: Generar INDEX file ───
    total_with_binding = sum(1 for v in all_data.values() if v.get("pki") is not None)
    total_without = len(all_data) - total_with_binding
    total_not_found = len(pdb_ids) - len(all_data)

    print("\n═══ Paso 3: Generando INDEX file ═══")
    print(f"  PDB IDs escaneados:      {len(pdb_ids)}")
    print(f"  Encontrados en RCSB:     {len(all_data)}")
    print(f"  Con binding data:        {total_with_binding}")
    print(f"  Sin binding data:        {total_without}")
    print(f"  No encontrados en RCSB:  {total_not_found}")
    print(f"  Cobertura:               {total_with_binding / max(len(pdb_ids), 1) * 100:.1f}%")

    n_written = write_index_file(all_data, output_path)
    print(f"\n  INDEX escrito: {output_path}")
    print(f"  Entries con binding data: {n_written}")

    # ─── Paso 4: Reporte ───
    write_report(pdb_ids, all_data, report_path)
    print(f"  Reporte escrito: {report_path}")

    # ─── Evaluación ───
    elapsed_total = time.time() - start_time
    print("\n═══ Resumen ═══")
    print(f"  Duración: {elapsed_total:.0f}s")

    if total_with_binding >= 3000:
        print(f"  ✓ {total_with_binding} entries con binding data — suficiente para entrenamiento ML")
        print("    (PDBbind refined v2020 tiene ~5,316 entries)")
    elif total_with_binding >= 1000:
        print(f"  ⚠ {total_with_binding} entries — funcional pero idealmente >3000")
        print("    Considere usar el INDEX oficial de PDBbind para máxima cobertura")
    else:
        print(f"  ✗ Solo {total_with_binding} entries — insuficiente para entrenamiento robusto")
        print("    Se necesita el INDEX oficial de PDBbind o más datos de BindingDB")

    coverage = total_with_binding / max(len(pdb_ids), 1) * 100
    if coverage < 80:
        print(f"\n  ⚠ Cobertura {coverage:.1f}% — por debajo del 80% recomendado")
        print("    NOTA: Si tiene el INDEX oficial de PDBbind, puede copiarlo a:")
        print(f"    {data_dir / 'INDEX_refined_data.2020'}")

    print("=" * 70)
    sys.exit(0 if total_with_binding >= 1000 else 1)


if __name__ == "__main__":
    main()
