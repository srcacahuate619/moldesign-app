"""
Tests de los schemas Pydantic (core/models.py).

Cubre:
- BlockchainRecord validación (smiles_hash hex, scores range)
- PhysicochemicalProperties validación (Lipinski consistency)
- DockingResult validación (affinity negativa)
- ScoreBreakdown clamping
- MoleculeRead serialización
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


# ═════════════════════════════════════════════════════════════════════════════
# BlockchainRecord
# ═════════════════════════════════════════════════════════════════════════════


class TestBlockchainRecord:
    """Tests del schema BlockchainRecord."""

    def test_valid_record(self):
        """Un registro válido debe crearse sin error."""
        from core.models import BlockchainRecord
        record = BlockchainRecord(
            smiles_hash="a" * 64,
            total_score=85.5,
            target_pdb_id="7E2Y",
            user_wallet="test@example.com",
            timestamp=datetime(2026, 7, 28, tzinfo=timezone.utc),
        )
        assert record.smiles_hash == "a" * 64
        assert record.total_score == 85.5
        assert record.target_pdb_id == "7E2Y"

    def test_invalid_hash_too_short(self):
        """Hash que no es SHA-256 (menos de 64 chars) debe fallar."""
        from core.models import BlockchainRecord
        with pytest.raises(ValidationError):
            BlockchainRecord(
                smiles_hash="too_short",
                total_score=85.5,
                target_pdb_id="7E2Y",
                user_wallet="test@example.com",
                timestamp=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )

    def test_invalid_hash_not_hex(self):
        """Hash con caracteres no-hexadecimales debe fallar."""
        from core.models import BlockchainRecord
        with pytest.raises(ValidationError):
            BlockchainRecord(
                smiles_hash="z" * 64,  # 'z' no es hex
                total_score=85.5,
                target_pdb_id="7E2Y",
                user_wallet="test@example.com",
                timestamp=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )

    def test_score_out_of_range(self):
        """Score fuera de [0, 100] debe fallar."""
        from core.models import BlockchainRecord
        with pytest.raises(ValidationError):
            BlockchainRecord(
                smiles_hash="a" * 64,
                total_score=150.0,  # > 100
                target_pdb_id="7E2Y",
                user_wallet="test@example.com",
                timestamp=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )
        with pytest.raises(ValidationError):
            BlockchainRecord(
                smiles_hash="a" * 64,
                total_score=-10.0,  # < 0
                target_pdb_id="7E2Y",
                user_wallet="test@example.com",
                timestamp=datetime(2026, 7, 28, tzinfo=timezone.utc),
            )


# ═════════════════════════════════════════════════════════════════════════════
# PhysicochemicalProperties
# ═════════════════════════════════════════════════════════════════════════════


class TestPhysicochemicalProperties:
    """Tests del schema PhysicochemicalProperties."""

    def test_lipinski_pass_consistent(self):
        """lipinski_pass debe ser coherente con MW, logP, HBD, HBA."""
        from core.models import PhysicochemicalProperties
        # Caso Lipinski pass
        props = PhysicochemicalProperties(
            molecular_weight=350.0,
            log_p=3.0,
            tpsa=60.0,
            hbd=2,
            hba=4,
            rotatable_bonds=5,
            heavy_atom_count=25,
            ring_count=3,
            qed=0.7,
            sa_score=3.0,
            lipinski_pass=True,
            veber_pass=True,
        )
        assert props.molecular_weight == 350.0

    def test_lipinski_inconsistent_raises(self):
        """lipinski_pass=False con valores OK debe lanzar ValidationError."""
        from core.models import PhysicochemicalProperties
        with pytest.raises(ValidationError):
            PhysicochemicalProperties(
                molecular_weight=350.0,  # ≤ 500 → OK
                log_p=3.0,               # ≤ 5 → OK
                tpsa=60.0,
                hbd=2,                   # ≤ 5 → OK
                hba=4,                   # ≤ 10 → OK
                rotatable_bonds=5,
                heavy_atom_count=25,
                ring_count=3,
                qed=0.7,
                sa_score=3.0,
                lipinski_pass=False,  # inconsistente!
                veber_pass=True,
            )

    def test_lipinski_actually_fails(self):
        """MW > 500 con lipinski_pass=True debe lanzar error."""
        from core.models import PhysicochemicalProperties
        with pytest.raises(ValidationError):
            PhysicochemicalProperties(
                molecular_weight=600.0,  # > 500 → Lipinski fail
                log_p=3.0,
                tpsa=60.0,
                hbd=2,
                hba=4,
                rotatable_bonds=5,
                heavy_atom_count=25,
                ring_count=3,
                qed=0.7,
                sa_score=3.0,
                lipinski_pass=True,  # inconsistente!
                veber_pass=True,
            )

    def test_boundary_lipinski_mw_500(self):
        """MW exactamente 500 debe ser Lipinski pass."""
        from core.models import PhysicochemicalProperties
        props = PhysicochemicalProperties(
            molecular_weight=500.0,
            log_p=3.0,
            tpsa=60.0,
            hbd=2,
            hba=4,
            rotatable_bonds=5,
            heavy_atom_count=25,
            ring_count=3,
            qed=0.7,
            sa_score=3.0,
            lipinski_pass=True,
            veber_pass=True,
        )
        assert props.lipinski_pass is True


# ═════════════════════════════════════════════════════════════════════════════
# DockingResult
# ═════════════════════════════════════════════════════════════════════════════


class TestDockingResult:
    """Tests del schema DockingResult."""

    def test_negative_affinity_valid(self):
        """Afinidad negativa debe ser válida."""
        from core.models import DockingPose, DockingResult
        result = DockingResult(
            best_affinity=-9.5,
            poses=[
                DockingPose(rank=1, affinity=-9.5, rmsd_lb=0.0, rmsd_ub=0.0),
            ],
        )
        assert result.best_affinity == -9.5

    def test_positive_affinity_raises(self):
        """Afinidad positiva debe lanzar ValidationError."""
        from core.models import DockingPose, DockingResult
        with pytest.raises(ValidationError, match="debe ser negativa"):
            DockingResult(
                best_affinity=5.0,
                poses=[
                    DockingPose(rank=1, affinity=5.0, rmsd_lb=0.0, rmsd_ub=0.0),
                ],
            )

    def test_zero_affinity_allowed(self):
        """Afinidad 0.0 debe permitirse (caso borde de 'sin interacción')."""
        from core.models import DockingPose, DockingResult
        result = DockingResult(
            best_affinity=0.0,
            poses=[
                DockingPose(rank=1, affinity=0.0, rmsd_lb=0.0, rmsd_ub=0.0),
            ],
        )
        assert result.best_affinity == 0.0

    def test_min_one_pose(self):
        """Debe requerir al menos 1 pose."""
        from core.models import DockingResult
        with pytest.raises(ValidationError):
            DockingResult(
                best_affinity=-8.0,
                poses=[],
            )


# ═════════════════════════════════════════════════════════════════════════════
# ScoreBreakdown
# ═════════════════════════════════════════════════════════════════════════════


class TestScoreBreakdown:
    """Tests del schema ScoreBreakdown."""

    def test_valid_breakdown(self):
        """Un breakdown válido debe crearse sin error."""
        from core.models import ScoreBreakdown
        breakdown = ScoreBreakdown(
            affinity_score=75.0,
            adme_score=80.0,
            druglikeness_score=70.0,
            total_score=78.0,
            weight_affinity=0.45,
            weight_adme=0.30,
            weight_druglikeness=0.25,
            strongest_dimension="afinidad (LE)",
            weakest_dimension="propiedades (QED)",
            improvement_hint="Test hint",
        )
        assert breakdown.total_score == 78.0
