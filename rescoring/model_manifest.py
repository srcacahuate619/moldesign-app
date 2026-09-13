"""Validation helpers for the versioned rescoring model manifest.

The manifest is a release-integrity record, not a source of scientific
parameters.  It binds each runtime model to the exact bytes and provenance
declared by the release generator.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_VERSION = 4
# `gnn_v2_cl` se anade el 2026-09-04. El checkpoint existia desde julio, con su
# procedencia entera en `docs/CL_GNN_MULTITARGET_RESULTS.md` —708 complejos de
# PDBbind redockeados, 566/142, evaluado en 7 benchmarks held-out— pero no en
# este registro, que es el que la build comprueba. Un modelo que decide parte
# del ranking y no esta aqui no tiene sus bytes ligados a ninguna procedencia.
#
# Su entrada declara los AUC POR FAMILIA y no un numero global, a proposito: la
# transferencia depende de la familia (HIV proteasa 0.949, 5-HT1A 0.850, pero
# CDK2 0.594 y CA2 0.588) y un AUC medio ocultaria justo eso.
# `classifier_binder` se anadio el 2026-09-04. Produce `xgb_score`, y `xgb` es
# el componente de MAS peso del stacking en el artefacto vigente: 0.60 en los
# pesos por defecto -los que reciben todas las familias salvo GPCR- y 0.40 en
# GPCR. Movia el ranking de cada evaluacion y no estaba aqui, asi que sus bytes
# no se ligaban a ninguna procedencia y la build no comprobaba que fueran los
# mismos. Su entrada declara las DOS cohortes -validacion n=108 y holdout
# scaffold-disjoint n=328- porque citar solo la segunda lo haria parecer mejor
# de lo que la validacion sostiene.
REQUIRED_MODEL_KEYS = frozenset({
    "model_a_universal", "pose_selector_v06", "gnn_v2_cl", "classifier_binder",
})


@dataclass(frozen=True)
class ManifestVerification:
    """Result of a non-throwing manifest verification."""

    valid: bool
    version: int | None
    model_keys: tuple[str, ...]
    errors: tuple[str, ...]


def default_artifacts_dir() -> Path:
    return Path(__file__).resolve().parent / "artifacts"


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 checksum for one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Serialize a manifest deterministically for reproducible release checks."""
    return (json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n").encode("utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("El manifiesto debe ser un objeto JSON")
    return payload


def verify_model_manifest(
    manifest_path: Path | None = None,
    artifacts_dir: Path | None = None,
) -> ManifestVerification:
    """Validate version, required models and byte hashes without raising.

    Health endpoints use this function directly, therefore a damaged release
    can become visibly degraded instead of crashing the service at import time.
    Release tooling should additionally use the generator's strict ``--check``
    mode, which compares the full deterministic document against its sources.
    """
    artifacts_dir = artifacts_dir or default_artifacts_dir()
    manifest_path = manifest_path or artifacts_dir / "model-manifest.json"
    errors: list[str] = []
    version: int | None = None
    model_keys: tuple[str, ...] = ()

    try:
        manifest = load_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ManifestVerification(False, None, (), (f"manifest_unreadable:{exc}",))

    raw_version = manifest.get("manifest_version")
    version = raw_version if isinstance(raw_version, int) else None
    if version != MANIFEST_VERSION:
        errors.append(f"manifest_version:{raw_version!r}; expected:{MANIFEST_VERSION}")

    models = manifest.get("models")
    if not isinstance(models, dict):
        errors.append("models debe ser un objeto")
        return ManifestVerification(False, version, (), tuple(errors))

    model_keys = tuple(sorted(models))
    if set(models) != REQUIRED_MODEL_KEYS:
        errors.append(
            "model_keys:" + ",".join(model_keys)
            + "; expected:" + ",".join(sorted(REQUIRED_MODEL_KEYS))
        )

    for model_key, entry in models.items():
        if not isinstance(entry, dict):
            errors.append(f"{model_key}:entrada no es objeto")
            continue

        filename = entry.get("file")
        expected_hash = entry.get("sha256")
        if not isinstance(filename, str) or not filename:
            errors.append(f"{model_key}:file ausente")
            continue
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            errors.append(f"{model_key}:sha256 inválido")
            continue

        artifact_path = artifacts_dir / filename
        if not artifact_path.is_file():
            errors.append(f"{model_key}:artifact ausente:{filename}")
        elif sha256_file(artifact_path) != expected_hash.lower():
            errors.append(f"{model_key}:sha256 no coincide:{filename}")

        metadata_file = entry.get("metadata_file")
        metadata_hash = entry.get("metadata_sha256")
        if (metadata_file is None) != (metadata_hash is None):
            errors.append(f"{model_key}:metadata incompleta")
        elif metadata_file is not None:
            metadata_path = artifacts_dir / str(metadata_file)
            if not metadata_path.is_file():
                errors.append(f"{model_key}:metadata ausente:{metadata_file}")
            elif sha256_file(metadata_path) != str(metadata_hash).lower():
                errors.append(f"{model_key}:metadata sha256 no coincide:{metadata_file}")

    return ManifestVerification(
        valid=not errors,
        version=version,
        model_keys=model_keys,
        errors=tuple(errors),
    )
