"""Contracts for the v4 protein-ligand feature extractor.

The Model A contract is 167 fields, of which this module calculates 164 3D
fields. The nine ProLIF counts are retained for transparent API reporting but
are deliberately excluded from the model vector.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feature_extractor import (
    ALL_3D_FEATURES,
    ECIF_FEATURES,
    EXTRACTED_3D_FEATURES,
    INTERACTION_FEATURES,
    SHELL_FEATURES,
    SIZE_NORM_FEATURES,
    InteractionFeatureExtractor,
    zero_all_3d_features,
    zero_extracted_3d_features,
)


class TestInteractionFeatureExtractorInit:
    """Availability is based on the current ProLIF implementation."""

    def test_init_does_not_crash(self):
        assert InteractionFeatureExtractor() is not None

    def test_prolif_availability_is_bool(self):
        extractor = InteractionFeatureExtractor()
        assert isinstance(extractor._prolif_ok, bool)
        assert isinstance(extractor.is_available, bool)


class TestFeatureContracts:
    def test_model_3d_contract_has_155_fields(self):
        assert len(SHELL_FEATURES) == 96
        assert len(ECIF_FEATURES) == 56
        assert len(SIZE_NORM_FEATURES) == 3
        assert len(ALL_3D_FEATURES) == 155
        assert len(ALL_3D_FEATURES) == len(set(ALL_3D_FEATURES))

    def test_extractor_contract_has_visual_interactions(self):
        assert len(INTERACTION_FEATURES) == 9
        assert len(EXTRACTED_3D_FEATURES) == 164
        assert set(INTERACTION_FEATURES).isdisjoint(ALL_3D_FEATURES)
        assert len(EXTRACTED_3D_FEATURES) == len(set(EXTRACTED_3D_FEATURES))

    def test_zero_model_features_are_exact_and_finite(self):
        features = zero_all_3d_features()
        assert list(features) == ALL_3D_FEATURES
        assert set(features.values()) == {0.0}

    def test_zero_extracted_features_are_exact_and_finite(self):
        features = zero_extracted_3d_features()
        assert list(features) == EXTRACTED_3D_FEATURES
        assert set(features.values()) == {0.0}


class TestGracefulDegradation:
    """Unreadable structures must preserve the complete public contract."""

    def test_missing_training_files_return_complete_zero_contract(self, tmp_path):
        extractor = InteractionFeatureExtractor()
        features = extractor.extract_from_files(
            tmp_path / "missing-protein.pdb",
            tmp_path / "missing-ligand.sdf",
        )
        assert list(features) == EXTRACTED_3D_FEATURES
        assert set(features.values()) == {0.0}

    def test_missing_target_pose_returns_complete_zero_contract(self, tmp_path):
        extractor = InteractionFeatureExtractor()
        features = extractor.extract_from_pose(
            "ATOM      1  C1  LIG A   1       0.000   0.000   0.000",
            tmp_path / "missing-target.pdb",
            smiles="CCO",
            skip_prolif=True,
        )
        assert list(features) == EXTRACTED_3D_FEATURES
        assert set(features.values()) == {0.0}
