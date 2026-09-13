#!/usr/bin/env python3
"""
scripts/prepare_training_data.py

Script maestro para preparar TODOS los datos necesarios para
entrenar el modelo ML de rescoring.

Ejecuta en secuencia:
  1. Descarga PDBbind v2020 refined set desde Zenodo (~5.8 GB)
  2. Genera/verifica el INDEX file con binding affinities
  3. Valida la integridad de los datos
  4. Reporta estado final

Este script es el ÚNICO punto de entrada necesario para el Perfil 2
(científico que quiere re-entrenar el modelo desde cero).

Uso:
  python scripts/prepare_training_data.py --acknowledge-pdbbind-license
  python scripts/prepare_training_data.py --acknowledge-pdbbind-license --data-dir D:\\data\\pdbbind
  python scripts/prepare_training_data.py --acknowledge-pdbbind-license --skip-download   (si ya descargó)

En Windows:
  python rescoring/scripts/prepare_training_data.py --data-dir data/pdbbind

Después de este script, ejecutar:
  python train_orchestrator.py --data-dir /data/pdbbind

Espacio requerido: ~18 GB (6 GB downloads + 12 GB extraídos)
Tiempo estimado: 30-90 minutos (depende de velocidad de internet)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_step(description: str, command: list[str]) -> bool:
    """Ejecutar un paso y reportar resultado."""
    print(f"\n{'═' * 70}")
    print(f"  {description}")
    print(f"{'═' * 70}\n")

    start = time.time()

    try:
        result = subprocess.run(
            command,
            capture_output=False,
            text=True,
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            print(f"\n  ✓ Completado en {elapsed:.0f}s")
            return True
        else:
            print(f"\n  ✗ Falló (exit code {result.returncode}) en {elapsed:.0f}s")
            return False

    except FileNotFoundError:
        print(f"  ✗ Comando no encontrado: {command[0]}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def check_data_ready(data_dir: Path) -> dict:
    """Verificar rápidamente si los datos están listos."""
    status = {
        "has_complexes": False,
        "n_complexes": 0,
        "has_index": False,
        "index_entries": 0,
    }

    # Contar directorios de complejos
    if data_dir.exists():
        for entry in data_dir.iterdir():
            if entry.is_dir() and len(entry.name) == 4 and entry.name.isalnum():
                protein = entry / f"{entry.name.lower()}_protein.pdb"
                ligand = entry / f"{entry.name.lower()}_ligand.sdf"
                if protein.exists() and ligand.exists():
                    status["n_complexes"] += 1

    status["has_complexes"] = status["n_complexes"] >= 100

    # Verificar INDEX file
    for candidate in [
        "INDEX_refined_data.2020",
        "INDEX_refined_data.2019",
        "INDEX_refined_data.txt",
    ]:
        index_path = data_dir / candidate
        if index_path.exists():
            n_entries = 0
            with open(index_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 4 and len(parts[0]) == 4:
                            n_entries += 1
            status["has_index"] = True
            status["index_entries"] = n_entries
            break

    return status


def main():
    parser = argparse.ArgumentParser(
        description="Preparar todos los datos para entrenar el modelo ML de rescoring",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directorio para datos PDBbind (default: data/pdbbind relativo al proyecto)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Omitir descarga (asumir que ya se descargaron los archivos)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Omitir generación de INDEX (asumir que ya existe)",
    )
    parser.add_argument(
        "--acknowledge-pdbbind-license",
        action="store_true",
        help=(
            "Confirmo que poseo los derechos necesarios para descargar y usar "
            "la copia de PDBbind; no concede permiso de redistribución"
        ),
    )

    args = parser.parse_args()

    if not args.skip_download and not args.acknowledge_pdbbind_license:
        parser.error(
            "--acknowledge-pdbbind-license es obligatorio cuando la preparación "
            "puede descargar PDBbind"
        )
    # Resolver directorio de datos
    scripts_dir = Path(__file__).resolve().parent
    project_root = scripts_dir.parent  # rescoring/
    workspace_root = project_root.parent  # molecular-design/

    if args.data_dir:
        data_dir = Path(args.data_dir).resolve()
    else:
        data_dir = workspace_root / "data" / "pdbbind"

    python = sys.executable

    print("=" * 70)
    print("  MolDesign — Preparación de Datos para ML Rescoring")
    print("=" * 70)
    print(f"  Python:      {python}")
    print(f"  Data dir:    {data_dir}")
    print(f"  Scripts dir: {scripts_dir}")
    print()

    # ─── Verificar estado actual ───
    status = check_data_ready(data_dir)
    print("  Estado actual:")
    print(f"    Complejos: {status['n_complexes']} {'✓' if status['has_complexes'] else '✗'}")
    print(f"    INDEX:     {status['index_entries']} entries {'✓' if status['has_index'] else '✗'}")
    print()

    if status["has_complexes"] and status["has_index"] and status["index_entries"] >= 1000:
        print("  ✓ Los datos ya están listos para entrenamiento.")
        print(f"    Puede ejecutar: python train_orchestrator.py --data-dir {data_dir}")
        print("=" * 70)
        sys.exit(0)

    steps_total = 0
    steps_passed = 0
    start_time = time.time()

    # ─── Paso 1: Descargar desde Zenodo ───
    if not args.skip_download and not status["has_complexes"]:
        download_script = scripts_dir / "download_pdbbind_zenodo.py"
        if not download_script.exists():
            print(f"  ✗ Script de descarga no encontrado: {download_script}")
            sys.exit(1)

        steps_total += 1
        ok = run_step(
            "PASO 1: Descargando PDBbind v2020 refined set desde Zenodo (~5.8 GB)",
            [python, str(download_script), "--acknowledge-license", "--output-dir", str(data_dir)],
        )
        if ok:
            steps_passed += 1
        else:
            print("\n  La descarga falló. Puede reintentar ejecutando este script de nuevo.")
            print("  Los archivos ya descargados no se re-descargarán (checksum).")
            sys.exit(1)
    elif status["has_complexes"]:
        print(f"  → Paso 1 omitido: {status['n_complexes']} complejos ya disponibles")
    else:
        print("  → Paso 1 omitido por --skip-download")

    # Actualizar estado
    status = check_data_ready(data_dir)

    # ─── Paso 2: Generar INDEX file ───
    if not args.skip_index and not status["has_index"]:
        index_script = scripts_dir / "create_pdbbind_index.py"
        if not index_script.exists():
            print(f"  ✗ Script de INDEX no encontrado: {index_script}")
            sys.exit(1)

        steps_total += 1
        ok = run_step(
            "PASO 2: Reconstruyendo INDEX file desde RCSB PDB API",
            [python, str(index_script), "--data-dir", str(data_dir)],
        )
        if ok:
            steps_passed += 1
        else:
            print("\n  La generación del INDEX falló.")
            print("  Posible causa: sin conexión a internet o RCSB API no disponible.")
            print("  Alternativa: copiar INDEX_refined_data.2020 manualmente.")
            sys.exit(1)
    elif status["has_index"]:
        print(f"  → Paso 2 omitido: INDEX ya existe ({status['index_entries']} entries)")
    else:
        print("  → Paso 2 omitido por --skip-index")

    # Actualizar estado
    status = check_data_ready(data_dir)

    # ─── Paso 3: Validar datos ───
    setup_script = scripts_dir / "setup_pdbbind.py"
    if setup_script.exists():
        steps_total += 1
        ok = run_step(
            "PASO 3: Validando integridad de datos",
            [python, str(setup_script), "--data-dir", str(data_dir)],
        )
        if ok:
            steps_passed += 1
        else:
            print("\n  ⚠ Validación reportó problemas. Revise el output anterior.")
            print("  El entrenamiento aún puede ser posible con datos parciales.")

    # ─── Resumen final ───
    elapsed = time.time() - start_time
    status = check_data_ready(data_dir)

    print(f"\n{'=' * 70}")
    print("  RESUMEN FINAL")
    print(f"{'=' * 70}")
    print(f"  Duración total: {elapsed / 60:.1f} minutos")
    print(f"  Pasos: {steps_passed}/{steps_total} exitosos")
    print(f"  Complejos: {status['n_complexes']}")
    print(f"  INDEX entries: {status['index_entries']}")
    print()

    if status["has_complexes"] and status["has_index"] and status["index_entries"] >= 1000:
        print("  ✓ DATOS LISTOS PARA ENTRENAMIENTO")
        print()
        print("  Siguiente paso:")
        print(f"    python train_orchestrator.py --data-dir {data_dir}")
        print(f"{'=' * 70}")
        sys.exit(0)
    else:
        print("  ✗ Datos incompletos. Revise los pasos anteriores.")
        if not status["has_complexes"]:
            print("    - Falta descargar archivos estructurales")
        if not status["has_index"]:
            print("    - Falta generar INDEX file")
        elif status["index_entries"] < 1000:
            print(f"    - INDEX tiene solo {status['index_entries']} entries (mínimo 1000)")
        print(f"{'=' * 70}")
        sys.exit(1)


if __name__ == "__main__":
    main()
