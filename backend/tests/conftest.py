"""
Fixtures globales para tests.

Estrategia:
- Los tests que requieren RDKit se marcan con @pytest.mark.skip_if_no_rdkit
- Los tests que requieren Solana se mockean completamente
- No se necesita DB real — los tests de lógica pura no tocan la DB
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Activa el guard de core.database: una suite nunca puede caer por accidente
# en ~/MolDesign/data/moldesign_local.db.
os.environ.setdefault("MOLDESIGN_TESTING", "1")

# ── Detectar disponibilidad de RDKit ──────────────────────────────────────────

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Crippen, Descriptors, QED

    _RDKIT_AVAILABLE = True
except ImportError:
    _RDKIT_AVAILABLE = False

rdkit_available = pytest.mark.skipif(
    not _RDKIT_AVAILABLE,
    reason="RDKit no está disponible en este entorno",
)


# ── SMILES de referencia para tests ──────────────────────────────────────────

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"  # aspirina, MW~180, drug-like
ASPIRIN_CANONICAL = "CC(=O)Oc1ccccc1C(=O)O"
ASPIRIN_HASH = "d7b1a5e1a5c5e5b7a1a5c5e5b7a1a5c5e5b7a1a5c5e5b7a1a5c5e5b7a1a5"  # fake for fixture
ETHANOL = "CCO"
ETHANOL_CANONICAL = "CCO"

# Moléculas inválidas
INVALID_SMILES = "CCX"  # X no es un átomo
EMPTY_SMILES = ""
MULTIFRAGMENT = "CCO.Cl"  # etanol + cloro (sal)

# Moléculas para test de scoring
HIGH_AFFINITY = -12.0  # kcal/mol, muy buena
MEDIUM_AFFINITY = -8.0  # kcal/mol, buena
LOW_AFFINITY = -5.0  # kcal/mol, débil
BORDERLINE_AFFINITY = -7.0  # kcal/mol, cerca del threshold


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_settings():
    """Settings mockeadas para tests que necesitan config."""
    with patch("core.config.get_settings") as mock:
        settings = MagicMock()
        settings.strict_science_mode = True
        settings.strict_single_fragment_only = True
        settings.max_total_formal_charge_abs = 2
        settings.max_atom_formal_charge_abs = 2
        settings.mol_max_heavy_atoms = 80
        settings.mol_max_molecular_weight = 800.0
        settings.mol_min_molecular_weight = 100.0
        settings.score_weight_affinity = 0.45
        settings.score_weight_adme = 0.30
        settings.score_weight_druglikeness = 0.25
        settings.solana_rpc_url = "https://api.devnet.solana.com"
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_certifier():
    """Mock completo del SolanaCertifier."""
    with patch("services.blockchain.certifier.SolanaCertifier") as mock_cls:
        instance = MagicMock()
        instance.is_available = True
        instance.certify = AsyncMock(return_value="mock_signature_abc123")
        instance.verify = AsyncMock(
            return_value=MagicMock(
                smiles_hash="abc123def456",
                total_score=85.0,
                target_pdb_id="7E2Y",
                user_wallet="test@example.com",
                timestamp=MagicMock(isoformat=lambda: "2026-07-28T00:00:00"),
            )
        )
        mock_cls.return_value = instance
        yield instance


# ── Helpers ───────────────────────────────────────────────────────────────────


def create_mock_physicochemical_properties(**overrides: Any):
    """Crea un mock de PhysicochemicalProperties con defaults sensibles."""
    from core.models import PhysicochemicalProperties

    defaults = {
        "molecular_weight": 350.0,
        "log_p": 2.5,
        "tpsa": 60.0,
        "hbd": 2,
        "hba": 4,
        "rotatable_bonds": 5,
        "heavy_atom_count": 25,
        "ring_count": 3,
        "qed": 0.7,
        "sa_score": 3.5,
        "sa_reasons": [],
        "lipinski_pass": True,
        "veber_pass": True,
        "ghose_pass": True,
        "egan_pass": True,
        "muegge_pass": True,
        "muegge_score": 5,
        "fsp3": 0.3,
        "is_pains": False,
        "pains_matches": [],
        "blood_viability_score": 75.0,
        "blood_solubility_logs": -4.0,
        "blood_ppb_category": "low",
        "blood_bbb_permeable": True,
        "blood_hia_permeable": True,
        "blood_systemic_reactivity": [],
    }
    defaults.update(overrides)
    return PhysicochemicalProperties(**defaults)
