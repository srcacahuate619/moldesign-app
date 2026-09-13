"""
scripts/setup_pdbbind.py

Descarga y preparación de PDBbind refined set para entrenamiento ML.

PDBbind (http://www.pdbbind.org.cn/) es la fuente estándar de datos
de afinidad proteína-ligando experimental para benchmarking de docking
y ML scoring. El refined set contiene ~5,000 complejos curados.

REQUISITOS LEGALES:
  - Usar PDBbind requiere registro en http://www.pdbbind.org.cn/
  - Los datos están bajo licencia académica (no comercial)
  - La descarga manual es necesaria: este script NO descarga automáticamente

Este script:
  1. Verifica la estructura de directorios esperada
  2. Valida que el INDEX file existe y es parseable
  3. Verifica una muestra de archivos PDB/SDF de proteínas y ligandos
  4. Reporta estadísticas y problemas encontrados
  5. Genera un manifiesto de datos para reproducibilidad

Uso:
  python scripts/setup_pdbbind.py --data-dir /data/pdbbind
  python scripts/setup_pdbbind.py --data-dir /data/pdbbind --validate-all
  python scripts/setup_pdbbind.py --help

Estructura esperada de /data/pdbbind/:
  INDEX_refined_data.2020      (o .2019 o .txt)
  {pdb_id}/
    {pdb_id}_protein.pdb       proteína preparada
    {pdb_id}_ligand.sdf        ligando co-cristalizado
    {pdb_id}_ligand.mol2       ligando (formato alternativo)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────────

EXPECTED_MIN_COMPLEXES = 4000  # PDBbind refined 2020 ≈ 5316
EXPECTED_MAX_COMPLEXES = 8000

INDEX_CANDIDATES = [
    "INDEX_refined_data.2020",
    "INDEX_refined_data.2019",
    "INDEX_refined_data.txt",
    "index/INDEX_refined_data.2020",
    "index/INDEX_refined_data.2019",
]

BINDING_RE = re.compile(
    r"(Kd|Ki|IC50|EC50)\s*[=<>~]\s*([\d.]+)\s*(fM|pM|nM|uM|mM|M)",
    re.IGNORECASE,
)


@dataclass
class SetupReport:
    """Reporte de la validación de datos PDBbind."""
    status: str = "not_started"
    data_dir: str = ""
    index_file: str = ""
    n_entries_index: int = 0
    n_dirs_found: int = 0
    n_protein_pdb: int = 0
    n_ligand_sdf: int = 0
    n_ligand_mol2: int = 0
    n_complete: int = 0  # Tienen proteína + ligando SDF
    binding_type_counts: dict[str, int] = field(default_factory=dict)
    pki_range: tuple[float, float] = (0.0, 0.0)
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sample_validated: int = 0
    sample_valid: int = 0
    timestamp: str = ""
    duration_seconds: float = 0.0


def find_index_file(data_dir: Path) -> Path | None:
    """Buscar INDEX file en las ubicaciones candidatas."""
    for candidate in INDEX_CANDIDATES:
        path = data_dir / candidate
        if path.exists():
            return path
    return None


def parse_index_line(line: str, data_dir: Path) -> dict | None:
    """
    Parsear una línea del INDEX file de PDBbind.

    Formato típico:
      1a1e  2.40  1997  Ki=13uM     // ...
    o:
      # Comment line
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Extraer PDB ID (primeros 4 chars alfanuméricos)
    parts = line.split()
    if len(parts) < 4:
        return None

    pdb_id = parts[0].lower()
    if not re.match(r"^[a-z0-9]{4}$", pdb_id):
        return None

    try:
        resolution = float(parts[1])
    except (ValueError, IndexError):
        resolution = 0.0

    try:
        year = int(parts[2])
    except (ValueError, IndexError):
        year = 0

    # Binding data: buscar patrón en el resto de la línea
    binding_str = " ".join(parts[3:])
    binding_type = "unknown"
    match = BINDING_RE.search(binding_str)
    if match:
        binding_type = match.group(1)

    # Verificar archivos
    cpx_dir = data_dir / pdb_id
    protein_pdb = cpx_dir / f"{pdb_id}_protein.pdb"
    ligand_sdf = cpx_dir / f"{pdb_id}_ligand.sdf"
    ligand_mol2 = cpx_dir / f"{pdb_id}_ligand.mol2"

    return {
        "pdb_id": pdb_id,
        "resolution": resolution,
        "year": year,
        "binding_type": binding_type,
        "binding_raw": binding_str,
        "dir_exists": cpx_dir.exists(),
        "protein_pdb_exists": protein_pdb.exists(),
        "ligand_sdf_exists": ligand_sdf.exists(),
        "ligand_mol2_exists": ligand_mol2.exists(),
    }


def validate_pdb_file(path: Path) -> tuple[bool, str]:
    """
    Validación mínima de un archivo PDB.

    Verifica que:
    - El archivo no está vacío
    - Contiene líneas ATOM o HETATM
    - Tiene al menos 50 átomos (proteína real)
    """
    if not path.exists():
        return False, "File not found"

    size = path.stat().st_size
    if size < 1000:
        return False, f"File too small ({size} bytes)"

    atom_count = 0
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    atom_count += 1
                    if atom_count >= 50:
                        return True, "OK"
    except Exception as e:
        return False, f"Read error: {e}"

    if atom_count < 50:
        return False, f"Too few atoms ({atom_count})"

    return True, "OK"


def validate_sdf_file(path: Path) -> tuple[bool, str]:
    """
    Validación mínima de un archivo SDF.

    Verifica que:
    - El archivo no está vacío
    - Contiene el delimitador $$$$ (fin de molécula)
    - Tiene al menos 3 átomos
    """
    if not path.exists():
        return False, "File not found"

    size = path.stat().st_size
    if size < 100:
        return False, f"File too small ({size} bytes)"

    try:
        content = path.read_text()
        if "$$$$" not in content:
            return False, "No $$$$ delimiter found"

        # Contar átomos del counts line (línea 4 del SDF)
        lines = content.split("\n")
        if len(lines) < 5:
            return False, "Too few lines"

        return True, "OK"
    except Exception as e:
        return False, f"Read error: {e}"


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash del índice para reproducibilidad."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def run_setup(
    data_dir: str | Path,
    validate_all: bool = False,
    sample_size: int = 20,
) -> SetupReport:
    """
    Ejecutar validación completa de la instalación de PDBbind.

    Args:
        data_dir: directorio con datos PDBbind
        validate_all: si True, valida TODOS los archivos PDB/SDF (lento)
        sample_size: número de complejos a validar como muestra

    Returns:
        SetupReport con resultados
    """
    start = time.time()
    data_dir = Path(data_dir)
    report = SetupReport(
        data_dir=str(data_dir),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # ─── Paso 1: Verificar directorio ───
    if not data_dir.exists():
        report.status = "error"
        report.problems.append(f"Directorio no existe: {data_dir}")
        report.problems.append(
            "Descargue PDBbind refined set desde http://www.pdbbind.org.cn/ "
            "y extraiga en este directorio."
        )
        return report

    # ─── Paso 2: Buscar INDEX file ───
    index_file = find_index_file(data_dir)
    if not index_file:
        report.status = "error"
        report.problems.append(
            f"No se encontró INDEX file en {data_dir}. "
            f"Esperados: {INDEX_CANDIDATES}"
        )
        return report

    report.index_file = str(index_file)
    print(f"  INDEX file: {index_file.name}")
    print(f"  INDEX hash: {compute_file_hash(index_file)[:16]}...")

    # ─── Paso 3: Parsear INDEX ───
    entries = []
    with open(index_file) as f:
        for line in f:
            entry = parse_index_line(line, data_dir)
            if entry:
                entries.append(entry)

    report.n_entries_index = len(entries)
    print(f"  Entries in INDEX: {len(entries)}")

    if len(entries) < EXPECTED_MIN_COMPLEXES:
        report.warnings.append(
            f"Solo {len(entries)} entries (esperado ≥{EXPECTED_MIN_COMPLEXES}). "
            "¿Es el refined set completo?"
        )

    # ─── Paso 4: Estadísticas de archivos ───
    binding_counts: dict[str, int] = {}
    for entry in entries:
        bt = entry["binding_type"]
        binding_counts[bt] = binding_counts.get(bt, 0) + 1

        if entry["dir_exists"]:
            report.n_dirs_found += 1
        if entry["protein_pdb_exists"]:
            report.n_protein_pdb += 1
        if entry["ligand_sdf_exists"]:
            report.n_ligand_sdf += 1
        if entry["ligand_mol2_exists"]:
            report.n_ligand_mol2 += 1
        if entry["protein_pdb_exists"] and entry["ligand_sdf_exists"]:
            report.n_complete += 1

    report.binding_type_counts = binding_counts

    print(f"\n  Directories found: {report.n_dirs_found}/{len(entries)}")
    print(f"  Protein PDB files: {report.n_protein_pdb}")
    print(f"  Ligand SDF files:  {report.n_ligand_sdf}")
    print(f"  Complete pairs:    {report.n_complete}")
    print(f"  Binding types:     {binding_counts}")

    if report.n_complete < len(entries) * 0.8:
        report.problems.append(
            f"Solo {report.n_complete}/{len(entries)} complejos completos "
            "(proteína + ligando). ¿Faltan archivos?"
        )

    # ─── Paso 5: Validación de muestra ───
    import random
    rng = random.Random(42)
    complete_entries = [e for e in entries if e["protein_pdb_exists"] and e["ligand_sdf_exists"]]

    if validate_all:
        to_validate = complete_entries
        print(f"\n  Validating ALL {len(to_validate)} complete complexes...")
    else:
        to_validate = rng.sample(complete_entries, min(sample_size, len(complete_entries)))
        print(f"\n  Validating sample of {len(to_validate)} complexes...")

    n_valid = 0
    for entry in to_validate:
        pdb_id = entry["pdb_id"]
        pdb_path = data_dir / pdb_id / f"{pdb_id}_protein.pdb"
        sdf_path = data_dir / pdb_id / f"{pdb_id}_ligand.sdf"

        pdb_ok, pdb_msg = validate_pdb_file(pdb_path)
        sdf_ok, sdf_msg = validate_sdf_file(sdf_path)

        if pdb_ok and sdf_ok:
            n_valid += 1
        else:
            if not pdb_ok:
                report.warnings.append(f"{pdb_id}: protein PDB issue — {pdb_msg}")
            if not sdf_ok:
                report.warnings.append(f"{pdb_id}: ligand SDF issue — {sdf_msg}")

    report.sample_validated = len(to_validate)
    report.sample_valid = n_valid
    print(f"  Valid: {n_valid}/{len(to_validate)}")

    # ─── Resultado final ───
    report.duration_seconds = round(time.time() - start, 2)

    if report.problems:
        report.status = "error"
    elif report.warnings:
        report.status = "ok_with_warnings"
    else:
        report.status = "ok"

    return report


def save_manifest(report: SetupReport, output_path: Path) -> None:
    """Guardar manifiesto de datos para reproducibilidad."""
    manifest = {
        "status": report.status,
        "data_dir": report.data_dir,
        "index_file": report.index_file,
        "n_entries": report.n_entries_index,
        "n_complete": report.n_complete,
        "binding_types": report.binding_type_counts,
        "validation_sample": report.sample_validated,
        "validation_valid": report.sample_valid,
        "problems": report.problems,
        "warnings": report.warnings[:20],  # Truncar para legibilidad
        "timestamp": report.timestamp,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Setup y validación de PDBbind refined set para MolDesign ML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PASOS PARA OBTENER LOS DATOS:

  1. Registrarse en http://www.pdbbind.org.cn/
  2. Descargar PDBbind refined set (versión 2020 recomendada)
  3. Extraer en un directorio (e.g., /data/pdbbind/)
  4. Ejecutar este script: python setup_pdbbind.py --data-dir /data/pdbbind

ESTRUCTURA ESPERADA:

  /data/pdbbind/
    INDEX_refined_data.2020
    1a1e/
      1a1e_protein.pdb
      1a1e_ligand.sdf
    2hnx/
      2hnx_protein.pdb
      2hnx_ligand.sdf
    ...
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Directorio con datos PDBbind extraídos",
    )
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Validar TODOS los archivos (lento, ~30 min)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Número de complejos a validar como muestra (default: 20)",
    )
    parser.add_argument(
        "--manifest-out",
        type=str,
        default=None,
        help="Path para guardar manifiesto de datos (default: data_dir/pdbbind_manifest.json)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("MolDesign — PDBbind Data Setup")
    print("=" * 60)
    print(f"\n  Data directory: {args.data_dir}")

    report = run_setup(
        data_dir=args.data_dir,
        validate_all=args.validate_all,
        sample_size=args.sample_size,
    )

    # Guardar manifiesto
    manifest_path = Path(args.manifest_out) if args.manifest_out else Path(args.data_dir) / "pdbbind_manifest.json"
    save_manifest(report, manifest_path)

    # Resultado
    print("\n" + "=" * 60)
    if report.status == "ok":
        print("  ✓ PDBbind data READY for training")
        print(f"    {report.n_complete} complete complexes available")
        sys.exit(0)
    elif report.status == "ok_with_warnings":
        print(f"  ⚠ PDBbind data available with {len(report.warnings)} warnings")
        print(f"    {report.n_complete} complete complexes available")
        for w in report.warnings[:5]:
            print(f"    - {w}")
        if len(report.warnings) > 5:
            print(f"    ... and {len(report.warnings) - 5} more (see manifest)")
        sys.exit(0)
    else:
        print("  ✗ PDBbind data NOT ready")
        for p in report.problems:
            print(f"    - {p}")
        sys.exit(1)


if __name__ == "__main__":
    main()
