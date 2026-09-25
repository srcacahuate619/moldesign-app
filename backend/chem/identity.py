"""Identidad versionada del ligando, separada del hash legacy de caché."""

from __future__ import annotations

import hashlib
import rdkit

IDENTITY_VERSION = 2


def identity_hash_v2(canonical_smiles: str) -> str:
    """Hash de entrada inequívoco bajo una versión concreta de RDKit.

    `smiles_hash` histórico sigue siendo SHA-256 del SMILES para no cambiar
    rutas y deduplicación anteriores. Este hash nuevo se usa como evidencia de
    identidad; no se calcula retrospectivamente sobre corridas de otra versión.
    """
    payload = (
        f"MolDesign-ligand-input-v{IDENTITY_VERSION}\n"
        f"RDKit={rdkit.__version__}\n"
        f"SMILES={canonical_smiles}\n"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_manifest(canonical_smiles: str) -> dict[str, str | int]:
    return {
        "version": IDENTITY_VERSION,
        "rdkit_version": rdkit.__version__,
        "canonical_smiles": canonical_smiles,
        "sha256": identity_hash_v2(canonical_smiles),
    }
