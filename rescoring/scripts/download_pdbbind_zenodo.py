"""
scripts/download_pdbbind_zenodo.py

Descarga una copia de PDBbind v2020 alojada en Zenodo.

Fuente: https://zenodo.org/records/7014096
  - Chao. (2022). pdbbind-v2020 [Data set]. Zenodo.
  - DOI: 10.5281/zenodo.7014096
  - Licencia: NO VERIFICADA. El registro no muestra una licencia en Rights.
  - Este script no concede derechos de descarga, uso, entrenamiento ni
    redistribucion. El usuario debe obtenerlos del titular correspondiente.
  - Nota: Proteinas re-preparadas con Schrodinger Protein Preparation Wizard

Datasets disponibles:
  - Refined set: 6 archivos (~5.8 GB) — ~5,316 complejos curados de alta calidad
  - Other/General set: 15 archivos (~19.8 GB) — ~14,000+ complejos adicionales
  - Core set: 1 archivo (~35 MB) — 285 complejos benchmark CASF-2016

Por defecto descarga TODO (refined + other = ~25.8 GB, ~50 GB en disco tras extraccion).
Usar --refined-only para descargar solo el refined set (~5.8 GB).

Justificacion cientifica para descargar el dataset completo:
  - Mas datos por familia de proteinas = mejor LTR (Learning to Rank)
  - Scaffold-split CV mas robusto con mas scaffolds
  - El VIP audit ya filtra entries de baja calidad
  - Estado del arte en ML scoring siempre entrena con el dataset completo

Este script:
  1. Descarga cada archivo con verificacion MD5 (resume automatico)
  2. Extrae los archivos al directorio destino
  3. Normaliza la estructura de directorios
  4. Verifica disponibilidad del INDEX file
  5. Reporta estadisticas y problemas

Uso:
  python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind
  python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind --refined-only
  python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind --only-download
  python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind --skip-download

En Windows:
  python rescoring/scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir data/pdbbind

Flujo completo:
  1. python scripts/download_pdbbind_zenodo.py --acknowledge-license --output-dir /data/pdbbind
  2. python scripts/create_pdbbind_index.py --data-dir /data/pdbbind
  3. python scripts/setup_pdbbind.py --data-dir /data/pdbbind
  4. python train_orchestrator.py --data-dir /data/pdbbind

Espacio requerido:
  - Refined only: ~6 GB descarga + ~12 GB extraccion = ~18 GB
  - Full (refined + other): ~26 GB descarga + ~50 GB extraccion = ~76 GB
  - Recomendado: tener al menos 80 GB libres para el dataset completo

LIMITACIONES DOCUMENTADAS:
  - Las proteinas fueron re-preparadas con Schrodinger, no son las originales de PDBbind
  - No incluye el INDEX file oficial de PDBbind (se genera por separado)
  - No redistribuir el dataset ni derivados que reproduzcan su contenido sin
    permiso escrito o una base juridica verificada para la copia concreta.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


# ─── Configuracion de los archivos en Zenodo ───────────────────

ZENODO_RECORD = "7014096"
ZENODO_BASE_URL = f"https://zenodo.org/records/{ZENODO_RECORD}/files"

# ─── Refined Set: ~5,316 complejos curados de alta calidad ─────
REFINED_FILES = [
    {
        "name": "v2020-refined_0.tar.gz",
        "md5": "efa2443b60f95b890892681da959b51f",
        "size_mb": 1200,
    },
    {
        "name": "v2020-refined_1.tar.gz",
        "md5": "73fda885a04ccb8d64ba2a4f74101077",
        "size_mb": 1300,
    },
    {
        "name": "v2020-refined_2.tar.gz",
        "md5": "a39551b8ebf1950c0c03d1f63703a95c",
        "size_mb": 1300,
    },
    {
        "name": "v2020-refined_3.tar.gz",
        "md5": "27015e8a5362367374d517b756b4c53a",
        "size_mb": 1300,
    },
    {
        "name": "v2020-refined_4.tar.gz",
        "md5": "b3d43250cc0d884e2cd498e04396ae64",
        "size_mb": 1300,
    },
    {
        "name": "v2020-refined_5.tar.gz",
        "md5": "3c8ccbd438f1716abeaef8b80ec56ada",
        "size_mb": 425,
    },
]

# ─── Other/General Set: ~14,000+ complejos adicionales ─────────
# Mas diverso en familias de proteinas; menor curado que refined.
# Critico para entrenar ML con suficientes muestras por familia.
OTHER_FILES = [
    {
        "name": "v2020-other-PL_0.tar.gz",
        "md5": "3ce80a8471a44632e95c0225cb7ad0cb",
        "size_mb": 1300,
    },
    {
        "name": "v2020-other-PL_1.tar.gz",
        "md5": "4eb2a7980458f5d47f1a27fa5054f075",
        "size_mb": 1300,
    },
    {
        "name": "v2020-other-PL_2.tar.gz",
        "md5": "fa8027c0a8aaae455589f1ea3731e139",
        "size_mb": 1300,
    },
    {
        "name": "v2020-other-PL_3.tar.gz",
        "md5": "e827f252dea256ae3f35480f1a9ebaac",
        "size_mb": 1300,
    },
    {
        "name": "v2020-other-PL_4.tar.gz",
        "md5": "0692d3ebc45d4d4b96709f711ef2e963",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_5.tar.gz",
        "md5": "0674fbc877cf7e64be0aa617efd8142a",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_6.tar.gz",
        "md5": "d5181764e2b359674b3653271b7ec201",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_7.tar.gz",
        "md5": "8be9e614ec438e0fdd8d0cecfea053fa",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_8.tar.gz",
        "md5": "f1005a85fa4c5ec9389254e9c80ecc3f",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_9.tar.gz",
        "md5": "eb232108e7c5014df82950c50d839388",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_10.tar.gz",
        "md5": "5a950e888451d2e60a34c5a8a02b65ad",
        "size_mb": 1300,
    },
    {
        "name": "v2020-other-PL_11.tar.gz",
        "md5": "3a51089c37db81a5b28424d733f5fc2c",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_12.tar.gz",
        "md5": "574bebfd54e6aed3a326b9d6ce0c3549",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_13.tar.gz",
        "md5": "80432ed7794ebe7dee44b793add6f0cd",
        "size_mb": 1400,
    },
    {
        "name": "v2020-other-PL_14.tar.gz",
        "md5": "1914fa4a523c956e362e649c22d55364",
        "size_mb": 159,
    },
]

# ─── Core Set: 285 complejos benchmark CASF-2016 ──────────────
CORE_SET = {
    "zenodo_record": "7788083",
    "name": "pdbbind2020_core_set.zip",
    "md5": "7f3454af0436cfb86af36a4da5d7041e",
    "size_mb": 35,
    "url": "https://zenodo.org/records/7788083/files/pdbbind2020_core_set.zip",
}


def compute_md5(filepath: Path, chunk_size: int = 8192 * 1024) -> str:
    """Calcular MD5 de un archivo."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, expected_md5: str | None = None) -> bool:
    """
    Descargar un archivo con progreso y verificación MD5.

    Returns:
        True si descarga exitosa y MD5 coincide
    """
    if requests is None:
        print("ERROR: 'requests' no instalado. pip install requests", file=sys.stderr)
        return False

    # Si ya existe y MD5 coincide, skip
    if dest.exists() and expected_md5:
        existing_md5 = compute_md5(dest)
        if existing_md5 == expected_md5:
            print(f"  ✓ Ya existe y MD5 válido: {dest.name}")
            return True
        else:
            print(f"  ⚠ Existe pero MD5 no coincide, re-descargando: {dest.name}")

    print(f"  ↓ Descargando: {url}")
    print(f"    → {dest}")

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        start = time.time()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    elapsed = time.time() - start
                    speed_mbps = downloaded / (1024 * 1024 * max(elapsed, 0.1))
                    print(
                        f"\r    [{pct:5.1f}%] {downloaded / 1e6:.0f}/{total / 1e6:.0f} MB "
                        f"({speed_mbps:.1f} MB/s)",
                        end="",
                        flush=True,
                    )
        print()  # newline

    except Exception as e:
        print(f"\n  ✗ Error descargando {url}: {e}", file=sys.stderr)
        return False

    # Verificar MD5
    if expected_md5:
        actual_md5 = compute_md5(dest)
        if actual_md5 != expected_md5:
            print(
                f"  ✗ MD5 no coincide para {dest.name}:\n"
                f"    esperado: {expected_md5}\n"
                f"    obtenido: {actual_md5}",
                file=sys.stderr,
            )
            return False
        print(f"  ✓ MD5 verificado: {dest.name}")
    else:
        print(f"  ⚠ Sin MD5 para verificar: {dest.name}")

    return True


def extract_tar_gz(tar_path: Path, dest_dir: Path) -> int:
    """
    Extraer un archivo .tar.gz al directorio destino.

    Returns:
        número de archivos extraídos
    """
    print(f"  📦 Extrayendo: {tar_path.name} → {dest_dir}")
    n_extracted = 0

    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            members = tar.getmembers()
            total = len(members)
            for i, member in enumerate(members):
                tar.extract(member, dest_dir, filter="data")
                n_extracted += 1
                if (i + 1) % 500 == 0 or (i + 1) == total:
                    print(f"\r    [{i + 1}/{total}] archivos extraídos", end="", flush=True)
        print()
    except Exception as e:
        print(f"\n  ✗ Error extrayendo {tar_path.name}: {e}", file=sys.stderr)

    return n_extracted


def extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """Extraer un archivo .zip al directorio destino."""
    import zipfile

    print(f"  📦 Extrayendo: {zip_path.name} → {dest_dir}")
    n_extracted = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
            n_extracted = len(z.namelist())
    except Exception as e:
        print(f"\n  ✗ Error extrayendo {zip_path.name}: {e}", file=sys.stderr)
    print(f"    {n_extracted} archivos extraídos")
    return n_extracted


def count_complexes(data_dir: Path) -> dict:
    """Contar complejos extraídos y verificar estructura."""
    stats = {
        "total_dirs": 0,
        "with_protein": 0,
        "with_ligand_sdf": 0,
        "with_ligand_mol2": 0,
        "complete": 0,  # protein + ligand SDF
        "pdb_ids": [],
    }

    for entry in sorted(data_dir.iterdir()):
        if not entry.is_dir():
            continue
        pdb_id = entry.name.lower()
        if len(pdb_id) != 4:
            continue

        stats["total_dirs"] += 1
        stats["pdb_ids"].append(pdb_id)

        has_protein = (entry / f"{pdb_id}_protein.pdb").exists()
        has_sdf = (entry / f"{pdb_id}_ligand.sdf").exists()
        has_mol2 = (entry / f"{pdb_id}_ligand.mol2").exists()

        if has_protein:
            stats["with_protein"] += 1
        if has_sdf:
            stats["with_ligand_sdf"] += 1
        if has_mol2:
            stats["with_ligand_mol2"] += 1
        if has_protein and has_sdf:
            stats["complete"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Descargar PDBbind v2020 (refined + other) desde Zenodo"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/data/pdbbind",
        help="Directorio destino para datos (default: /data/pdbbind)",
    )
    parser.add_argument(
        "--download-dir",
        type=str,
        default=None,
        help="Directorio para archivos descargados (default: output-dir/downloads)",
    )
    parser.add_argument(
        "--refined-only",
        action="store_true",
        help="Solo descargar el refined set (~5.8 GB en lugar de ~25.8 GB)",
    )
    parser.add_argument(
        "--only-download",
        action="store_true",
        help="Solo descargar, no extraer",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="No descargar, solo extraer archivos existentes",
    )
    parser.add_argument(
        "--include-core",
        action="store_true",
        help="También descargar el core set (34.6 MB) como benchmark",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Eliminar archivos tar.gz después de extraer",
    )
    parser.add_argument(
        "--acknowledge-license",
        action="store_true",
        help=(
            "Confirmo que revisé y poseo los derechos necesarios para descargar "
            "y usar esta copia; no implica permiso de redistribución"
        ),
    )
    args = parser.parse_args()

    if not args.acknowledge_license:
        parser.error(
            "licencia no verificada: vuelva a ejecutar con --acknowledge-license "
            "sólo si posee autorización para esta copia de PDBbind v2020"
        )

    output_dir = Path(args.output_dir)
    download_dir = Path(args.download_dir) if args.download_dir else output_dir / "downloads"

    output_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Determinar que conjuntos descargar
    file_sets: list[tuple[str, list[dict]]] = [("refined", REFINED_FILES)]
    if not args.refined_only:
        file_sets.append(("other", OTHER_FILES))

    total_files = sum(len(fs) for _, fs in file_sets)
    total_mb = sum(f["size_mb"] for _, fs in file_sets for f in fs)

    print("=" * 70)
    print("PDBbind v2020 — Download from Zenodo")
    print("=" * 70)
    print(f"  Fuente:    Zenodo record {ZENODO_RECORD}")
    print("  Licencia:  NO VERIFICADA — el registro de Zenodo no declara Rights")
    print("              No redistribuir sin permiso explícito verificable")
    print(f"  Output:    {output_dir}")
    print(f"  Downloads: {download_dir}")
    sets_desc = " + ".join(name for name, _ in file_sets)
    print(f"  Sets:      {sets_desc}")
    print(f"  Archivos:  {total_files} ({total_mb:,} MB total)")
    if not args.refined_only:
        print("  NOTA:      Dataset completo (~50 GB en disco tras extraccion)")
        print("             Usar --refined-only para solo ~12 GB")
    print()

    # ─── Paso 1: Descargar ───
    all_files: list[dict] = []
    if not args.skip_download:
        for set_name, file_list in file_sets:
            print(f"═══ Paso 1: Descargando {set_name} set ({len(file_list)} archivos) ═══")
            success_count = 0
            for finfo in file_list:
                url = f"{ZENODO_BASE_URL}/{finfo['name']}"
                dest = download_dir / finfo["name"]
                ok = download_file(url, dest, finfo["md5"])
                if ok:
                    success_count += 1
                else:
                    print(f"  ✗ FALLO: {finfo['name']}", file=sys.stderr)

            print(f"\n  Resultado {set_name}: {success_count}/{len(file_list)} archivos\n")

            if success_count < len(file_list):
                print("  ⚠ Algunos archivos fallaron. Re-ejecute para reintentar.", file=sys.stderr)
                if success_count == 0 and set_name == "refined":
                    sys.exit(1)

            all_files.extend(file_list)

        # Core set (opcional)
        if args.include_core:
            print("═══ Descargando core set (benchmark) ═══")
            core_dest = download_dir / CORE_SET["name"]
            download_file(CORE_SET["url"], core_dest, CORE_SET["md5"])
    else:
        for _, file_list in file_sets:
            all_files.extend(file_list)

    if args.only_download:
        print("═══ --only-download: extracción omitida ═══")
        sys.exit(0)

    # ─── Paso 2: Extraer ───
    print("═══ Paso 2: Extrayendo archivos ═══")
    total_extracted = 0
    for finfo in all_files:
        tar_path = download_dir / finfo["name"]
        if not tar_path.exists():
            print(f"  ⚠ No encontrado: {tar_path.name}, skip", file=sys.stderr)
            continue
        n = extract_tar_gz(tar_path, output_dir)
        total_extracted += n

    print(f"\n  Total extraído: {total_extracted} archivos\n")

    # Extraer core set si existe
    core_zip = download_dir / CORE_SET["name"]
    if core_zip.exists():
        core_dir = output_dir / "core_set"
        core_dir.mkdir(exist_ok=True)
        extract_zip(core_zip, core_dir)

    # ─── Paso 3: Normalizar estructura ───
    print("═══ Paso 3: Normalizando estructura de directorios ═══")
    normalize_structure(output_dir)

    # ─── Paso 4: Verificar estructura ───
    print("═══ Paso 4: Verificando estructura de datos ═══")
    stats = count_complexes(output_dir)
    print(f"  Directorios de complejos: {stats['total_dirs']}")
    print(f"  Con proteína PDB:        {stats['with_protein']}")
    print(f"  Con ligando SDF:         {stats['with_ligand_sdf']}")
    print(f"  Con ligando MOL2:        {stats['with_ligand_mol2']}")
    print(f"  Completos (PDB+SDF):     {stats['complete']}")

    expected_min = 4000 if args.refined_only else 15000
    if stats["complete"] < expected_min:
        print(f"\n  ⚠ Solo {stats['complete']} complejos completos (esperado >{expected_min})")
        print("    Posibles causas: extracción incompleta, estructura inesperada")
    else:
        print(f"\n  ✓ {stats['complete']} complejos completos — datos listos")

    # ─── Cleanup ───
    if args.cleanup:
        print("\n═══ Limpiando archivos descargados ═══")
        for finfo in all_files:
            tar_path = download_dir / finfo["name"]
            if tar_path.exists():
                tar_path.unlink()
                print(f"  ✗ Eliminado: {tar_path.name}")
        print("  ✓ Cleanup completo")

    # ─── Paso 5: Verificar INDEX files ───
    print("\n═══ Paso 5: Verificando INDEX files ═══")
    index_found_refined = False
    index_found_other = False

    for candidate in [
        output_dir / "INDEX_refined_data.2020",
        output_dir / "INDEX_refined_data.2019",
        output_dir / "INDEX_refined_data.txt",
        output_dir / "index" / "INDEX_refined_data.2020",
    ]:
        if candidate.exists():
            print(f"  ✓ INDEX refined encontrado: {candidate}")
            index_found_refined = True
            break

    if not args.refined_only:
        for candidate in [
            output_dir / "INDEX_general_PL_data.2020",
            output_dir / "INDEX_general_PL.2020",
            output_dir / "INDEX_general_PL_data.txt",
            output_dir / "index" / "INDEX_general_PL_data.2020",
        ]:
            if candidate.exists():
                print(f"  ✓ INDEX other encontrado: {candidate}")
                index_found_other = True
                break

    index_found = index_found_refined and (args.refined_only or index_found_other)

    if not index_found:
        print("  ⚠ INDEX file(s) NO encontrado(s) en los datos extraídos.")
        print("    Esto es esperado para el dataset de Zenodo (solo archivos estructurales).")
        print()
        print("  SIGUIENTE PASO OBLIGATORIO:")
        print(f"    python scripts/create_pdbbind_index.py --data-dir {output_dir}")
        print()
        print("    Esto reconstruirá el INDEX con binding affinities desde RCSB PDB API.")
        print("    Requiere conexión a internet. Duración estimada: ~5-15 minutos.")
    else:
        print("  Los INDEX files están disponibles. Los datos están listos.")

    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"  Complejos completos: {stats['complete']}")
    print(f"  Sets descargados:    {sets_desc}")
    print(f"  INDEX disponible:    {'Sí' if index_found else 'No (ejecutar create_pdbbind_index.py)'}")
    print(f"  Directorio:          {output_dir}")
    if stats['complete'] >= expected_min and index_found:
        print("\n  ✓ DATOS LISTOS — puede proceder con el entrenamiento ML")
        print(f"    python train_orchestrator.py --data-dir {output_dir}")
    elif stats['complete'] >= expected_min:
        print("\n  ⚠ Archivos estructurales listos, falta generar el INDEX")
    else:
        print(f"\n  ⚠ Solo {stats['complete']} complejos completos (esperado >{expected_min})")
    print("=" * 70)


def normalize_structure(data_dir: Path) -> None:
    """
    Normalizar estructura de directorios post-extracción.

    Los tar.gz de Zenodo pueden extraer a un subdirectorio anidado
    (e.g., v2020-refined/XXXX/ en lugar de XXXX/ directamente).
    Si se detecta esto, mover los subdirectorios al nivel correcto.
    """
    import shutil

    # Buscar posibles directiorios contenedores anidados
    # Incluir variantes con sufijo numérico (_0.._9) de Zenodo split archives
    base_candidates = [
        "v2020-refined",
        "refined-set",
        "PDBbind_v2020_refined",
        "v2020-other-PL",
        "other-PL",
        "PDBbind_v2020_other",
        "pdbbind",
    ]
    candidates = []
    for name in base_candidates:
        candidates.append(data_dir / name)
        for i in range(10):
            candidates.append(data_dir / f"{name}_{i}")

    for candidate in candidates:
        if not candidate.is_dir():
            continue

        # Verificar que contiene subdirectorios de 4 caracteres (PDB IDs)
        pdb_dirs = [
            d for d in candidate.iterdir()
            if d.is_dir() and len(d.name) == 4 and d.name.isalnum()
        ]

        if len(pdb_dirs) < 10:
            continue

        print(f"  Detectado directorio anidado: {candidate.name}/ ({len(pdb_dirs)} complejos)")
        print(f"  Moviendo complejos a {data_dir}...")

        moved = 0
        for pdb_dir in pdb_dirs:
            dest = data_dir / pdb_dir.name
            if dest.exists():
                continue
            try:
                shutil.move(str(pdb_dir), str(dest))
                moved += 1
            except Exception as e:
                print(f"    ⚠ Error moviendo {pdb_dir.name}: {e}", file=sys.stderr)

        # Mover también INDEX files si existen
        for f in candidate.iterdir():
            if f.is_file() and (f.name.startswith("INDEX") or f.name.endswith(".txt")):
                dest_f = data_dir / f.name
                if not dest_f.exists():
                    shutil.move(str(f), str(dest_f))
                    print(f"  ✓ INDEX movido: {f.name}")

        print(f"  {moved} directorios movidos")

        # Limpiar directorio vacío
        try:
            if not any(candidate.iterdir()):
                candidate.rmdir()
        except Exception:
            pass


if __name__ == "__main__":
    main()
