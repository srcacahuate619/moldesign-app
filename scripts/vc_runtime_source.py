#!/usr/bin/env python3
"""Fuente versionada y verificada del runtime app-local de Visual C++."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class VcRuntimeSourceError(RuntimeError):
    """La fuente app-local no coincide con su manifiesto versionado."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validated_vc_runtime_dir(root: Path) -> Path:
    """Devuelve la carpeta x64 sólo después de verificar todos sus bytes."""
    base = Path(root).resolve() / "tools" / "vc-runtime"
    manifest_path = base / "vc-runtime-manifest.json"
    if not manifest_path.is_file():
        raise VcRuntimeSourceError(f"Falta el manifiesto del runtime de Visual C++: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("architecture") != "x64" or data.get("deployment") != "app-local":
        raise VcRuntimeSourceError("El manifiesto de Visual C++ no declara x64/app-local")

    declared = data.get("files")
    if not isinstance(declared, dict) or not declared:
        raise VcRuntimeSourceError("El manifiesto de Visual C++ no declara archivos")

    source = base / "x64"
    actual = {p.name for p in source.glob("*.dll") if p.is_file()}
    expected = set(declared)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise VcRuntimeSourceError(
            f"Conjunto de DLLs distinto del manifiesto; faltan={missing}, sobran={extra}"
        )

    for name, metadata in declared.items():
        path = source / name
        size = path.stat().st_size
        if size != int(metadata["bytes"]):
            raise VcRuntimeSourceError(f"Tamaño incorrecto para {name}: {size}")
        digest = _sha256(path)
        if digest.lower() != str(metadata["sha256"]).lower():
            raise VcRuntimeSourceError(f"SHA-256 incorrecto para {name}: {digest}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source = validated_vc_runtime_dir(args.root)
    print(f"Runtime de Visual C++ verificado: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())