"""Genera y verifica el inventario documental de catálogo y modelos.

Uso:
    python scripts/generate_runtime_inventory.py --write
    python scripts/generate_runtime_inventory.py --check

El inventario sólo describe archivos declarados: no evalúa ni reinterpreta
métricas científicas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "curated_targets.json"
MANIFEST_PATH = ROOT / "rescoring" / "artifacts" / "model-manifest.json"
OUTPUT_PATH = ROOT / "docs" / "46_RUNTIME_INVENTORY.md"
PDB_ROOTS = (ROOT / "data" / "target_library", ROOT / "data" / "targets")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(value: object) -> str:
    return " ".join(str(value if value is not None else "—").split()).replace("|", "\\|")


def render_inventory() -> str:
    targets = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pdb_ids = {target["pdb_id"].upper() for target in targets}
    # El catálogo se distribuye comprimido (`data/targets/*.pdb.gz`). Los `.pdb`
    # sueltos son descompresiones de trabajo: `data/target_library/` está en
    # .gitignore y no existe en un clon limpio. Contar sólo `*.pdb` hacía que
    # este inventario dependiera de la máquina que lo generaba —y que un clon
    # limpio declarase 0 receptores. La cobertura se deriva de lo distribuido.
    distributed_files = sorted(
        file
        for root in PDB_ROOTS
        if root.is_dir()
        for file in root.rglob("*.pdb.gz")
    )
    distributed_stems = {file.name[: -len(".pdb.gz")].upper() for file in distributed_files}
    represented_ids = pdb_ids & distributed_stems
    families = Counter(target.get("structural_family") or "sin_familia" for target in targets)

    lines = [
        "# 46 — Inventario runtime actual (generado)",
        "",
        "**Estado:** 🟢 Inventario vigente derivado de los artefactos que el repositorio distribuye.",
        "",
        "No contiene una afirmación nueva de validez científica. Las métricas se "
        "transcriben desde el manifiesto v4 y conservan sus estados/notas.",
        "",
        "## Catálogo de receptores", "",
        f"- Entradas en `curated_targets.json`: **{len(targets)}**",
        f"- PDB IDs únicos: **{len(pdb_ids)}**",
        f"- IDs con estructura distribuida en el repositorio (`.pdb.gz` de nombre exacto): **{len(represented_ids)} / {len(pdb_ids)}**",
        f"- Archivos `.pdb.gz` versionados (incluye variantes de cadena y duplicados): **{len(distributed_files)}**",
        f"- SHA-256 del catálogo: `{_sha256(CATALOG_PATH)}`",
        "",
        "### Familias estructurales", "",
        "| Familia | Targets |", "|---|---:|",
        *[f"| `{family}` | {count} |" for family, count in sorted(families.items())],
        "",
        "## Modelos declarados por el manifest v4", "",
        f"- Manifest: `rescoring/artifacts/model-manifest.json` (schema v{manifest.get('manifest_version', '—')})",
        f"- SHA-256 del manifest: `{_sha256(MANIFEST_PATH)}`",
        "",
    ]

    for model_id, model in sorted(manifest.get("models", {}).items()):
        lines.extend(
            [
                f"### `{model_id}`",
                "",
                f"- Archivo: `{_cell(model.get('file'))}`",
                f"- SHA-256: `{_cell(model.get('sha256'))}`",
                f"- Estado científico declarado: `{_cell(model.get('scientific_status'))}`",
                f"- Fecha de entrenamiento: `{_cell(model.get('training_date'))}`",
                f"- Feature schema: {_cell(model.get('feature_schema'))}",
                f"- Nota del manifest: {_cell(model.get('note'))}",
                "",
                "| Métrica declarada | Valor |",
                "|---|---:|",
                *[
                    f"| `{_cell(metric)}` | {_cell(value)} |"
                    for metric, value in sorted(model.get("metrics", {}).items())
                ],
                "",
            ]
        )
    lines.extend(
        [
            "## Mantenimiento", "",
            "- Regenerar: `python scripts/generate_runtime_inventory.py --write`.",
            "- Verificar: `python scripts/generate_runtime_inventory.py --check`.",
            "- Los targets y modelos experimentales no declarados en el manifest no se presentan como runtime de producción.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="escribe el inventario")
    mode.add_argument("--check", action="store_true", help="falla si el inventario está desactualizado")
    args = parser.parse_args()

    expected = render_inventory()
    current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
    if args.check:
        if current != expected:
            print("Inventario runtime desactualizado: ejecuta python scripts/generate_runtime_inventory.py --write")
            return 1
        print("Inventario runtime verificado")
        return 0

    OUTPUT_PATH.write_text(expected, encoding="utf-8")
    print(f"Generado: {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
