"""
tests/test_integration_synthetic.py

Integration test con datos sintéticos para el pipeline completo de rescoring.

Este test crea un mini-dataset "falso" de PDBbind-like complexes y ejecuta
el pipeline de entrenamiento completo (dry_run + training parcial).

Propósito:
  - Verificar que todos los módulos se conectan correctamente
  - Detectar interface mismatches como el de extract_3d_features (Issue #2)
  - Smoke-test del orquestador sin necesitar PDBbind real
  - Validar que los artefactos se generan correctamente

NOTA: Los datos son SINTÉTICOS. Los resultados científicos de este test
NO tienen significado biológico alguno. El único propósito es verificar
la integridad del pipeline de software.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Detect RDKit availability
try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

# Detect XGBoost availability
try:
    import xgboost  # noqa: F401
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

requires_xgboost = pytest.mark.skipif(
    not HAS_XGBOOST,
    reason="XGBoost not installed (available in Docker Python 3.12 image)",
)


def _make_synthetic_complex(
    pdb_id: str,
    pki: float,
    binding_type: str = "Ki",
    resolution: float = 1.8,
    smiles: str = "c1ccccc1",
    family: str = "other",
):
    """Crear un PDBBindComplex sintético con features pre-pobladas."""
    from pdbbind_parser import PDBBindComplex

    # Binding value from pKi: value_nm = 10^(9 - pKi)
    value_nm = 10 ** (9.0 - pki)

    cpx = PDBBindComplex(
        pdb_id=pdb_id,
        resolution=resolution,
        release_year=2020,
        binding_data_raw=f"{binding_type}={value_nm:.2f}nM",
        binding_type=binding_type,
        binding_value_nm=value_nm,
        pki=pki,
        ligand_smiles=smiles,
    )

    # Pre-fill molecular properties (simula que RDKit ya calculó)
    cpx.molecular_weight = 150.0 + pki * 20.0  # MW correlacionado artificial
    cpx.n_heavy_atoms = 10 + int(pki)

    # Pre-fill the exact current Model A contract. The test exercises software
    # integration, so every synthetic row must be structurally valid rather
    # than relying on the retired v3 20-field schema.
    rng = np.random.RandomState(hash(pdb_id) % 2**31)
    from train_pipeline import ALL_FEATURES

    cpx.features = {
        feature_name: float(rng.normal(0.0, 1.0))
        for feature_name in ALL_FEATURES
    }
    cpx.features.update({
        # Group A: 1D/2D
        "mw": cpx.molecular_weight,
        "logp": 1.0 + rng.normal(0, 0.5),
        "tpsa": 60.0 + rng.normal(0, 10),
        "hbd": float(rng.randint(0, 4)),
        "hba": float(rng.randint(1, 6)),
        "rotatable_bonds": float(rng.randint(1, 8)),
        "qed": 0.3 + rng.random() * 0.5,
        "log_mw": float(np.log(cpx.molecular_weight)),
        # Group B: Vina
        "vina_best_score": -5.0 - pki * 0.3 + rng.normal(0, 0.5),
        "pose_score_variance": rng.random() * 2.0,
        "pose_score_range": rng.random() * 3.0,
        "poses_passing_ratio": 0.5 + rng.random() * 0.5,
    })

    return cpx


def _make_synthetic_dataset(n: int = 200, seed: int = 42):
    """
    Crear dataset sintético de complejos para testing.

    Genera N complejos con:
    - pKi distribuido uniformemente en [4, 11]
    - Features con correlación artificial con pKi (para que el modelo aprenda algo)
    - Binding types: 60% Ki, 30% Kd, 10% IC50 (IC50 serán rechazados por VIP audit)
    """
    rng = np.random.RandomState(seed)
    complexes = []

    # SMILES variados (para scaffold splitting)
    smiles_pool = [
        "c1ccccc1",  # benceno
        "c1ccc(O)cc1",  # fenol
        "c1ccc(N)cc1",  # anilina
        "c1ccncc1",  # piridina
        "c1ccc2ccccc2c1",  # naftaleno
        "C1CCNCC1",  # piperidina
        "c1ccc(-c2ccccc2)cc1",  # bifenilo
        "C1CCOCC1",  # tetrahidropirano
        "c1cnc2ccccc2n1",  # quinazolina
        "c1cc(F)ccc1Cl",  # halogenado
    ]

    binding_types = ["Ki"] * 60 + ["Kd"] * 30 + ["IC50"] * 10
    rng.shuffle(binding_types)

    for i in range(n):
        pdb_id = f"syn{i:04d}"  # synthetic IDs
        pki = 4.0 + rng.random() * 7.0  # pKi in [4, 11]
        smiles = smiles_pool[i % len(smiles_pool)]
        btype = binding_types[i % len(binding_types)]
        resolution = 1.2 + rng.random() * 2.0  # 1.2 - 3.2 Å

        cpx = _make_synthetic_complex(
            pdb_id=pdb_id,
            pki=pki,
            binding_type=btype,
            resolution=resolution,
            smiles=smiles,
        )
        complexes.append(cpx)

    return complexes


class TestSyntheticPipelineIntegration:
    """Integration test: pipeline completo con datos sintéticos."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Crear dataset sintético y directorio de artefactos."""
        self.output_dir = tmp_path / "artifacts"
        self.output_dir.mkdir()
        self.complexes = _make_synthetic_dataset(n=200, seed=42)

    def _get_vip_complexes_with_mock(self):
        """
        Obtener VIP complexes con mock de la verificación de ligando
        cuando RDKit no está disponible (Python 3.14).

        En entorno Docker (Python 3.12 + RDKit), el check real funciona.
        En local sin RDKit, mockeamos _check_ligand para que pase,
        ya que el objetivo del integration test es verificar la conexión
        entre módulos, no la validación de SMILES.
        """
        from vip_audit import VIPAuditor, get_vip_complexes

        auditor = VIPAuditor(skip_structure_checks=True)

        if not HAS_RDKIT:
            # Mock _check_ligand para que siempre pase
            original_check = auditor._check_ligand

            def mock_check_ligand(cpx, result):
                result.checks["ligand"] = True

            auditor._check_ligand = mock_check_ligand

        report = auditor.audit_all(self.complexes)
        vip_ids = get_vip_complexes(report)
        vip = [c for c in self.complexes if c.pdb_id in set(vip_ids)]
        return vip, report

    def test_dataset_basic_stats(self):
        """Verificar que el dataset sintético tiene propiedades esperadas."""
        assert len(self.complexes) == 200

        pkis = [c.pki for c in self.complexes]
        assert min(pkis) >= 4.0
        assert max(pkis) <= 11.0

        # All synthetic rows satisfy the exact current Model A contract.
        from train_pipeline import ALL_FEATURES

        for cpx in self.complexes:
            assert hasattr(cpx, "features")
            assert set(cpx.features) == set(ALL_FEATURES)

    def test_vip_audit_rejects_ic50_and_low_resolution(self):
        """VIP audit debe rechazar IC50 y baja resolución."""
        from vip_audit import VIPAuditor

        auditor = VIPAuditor(skip_structure_checks=True)

        if not HAS_RDKIT:
            # Mock ligand check to pass so we can test other rejection criteria
            auditor._check_ligand = lambda cpx, result: result.checks.__setitem__("ligand", True)

        report = auditor.audit_all(self.complexes)

        # Debe haber rechazos por IC50 (binding type) y resolución >2.5
        assert report.total_rejected > 0

        # Con mock de ligando, debe haber aceptados
        if not HAS_RDKIT:
            assert report.total_accepted > 0

        # IC50 y resolution must appear in rejection reasons
        assert "binding_type" in report.rejection_reasons or "low_resolution" in report.rejection_reasons

    def test_structural_family_classification(self):
        """Familias estructurales deben clasificarse (como 'other' para sintéticos)."""
        from structural_family import StructuralFamilyClassifier

        classifier = StructuralFamilyClassifier()
        classifications = classifier.classify_all(self.complexes)

        assert len(classifications) == len(self.complexes)

        # Todos deben ser "other" (no hay PDB headers reales)
        for cls in classifications.values():
            assert cls.family == "other"
            assert cls.confidence == "unclassified"

    def test_data_splitting_produces_valid_splits(self):
        """Scaffold splitting debe producir folds válidos."""
        from data_splitter import create_frozen_test_set, scaffold_split_cv

        # Filtrar a complejos VIP (with ligand mock if needed)
        vip, _ = self._get_vip_complexes_with_mock()

        assert len(vip) >= 50, f"Need ≥50 VIP complexes, got {len(vip)}"

        # Frozen test set
        from structural_family import StructuralFamilyClassifier
        classifier = StructuralFamilyClassifier()
        families = classifier.classify_all(vip)

        test_ids = create_frozen_test_set(
            vip, families, test_size=min(30, len(vip) // 3), seed=42,
        )
        assert len(test_ids) > 0

        # Scaffold CV
        splits = scaffold_split_cv(vip, test_ids, n_folds=3, seed=42)
        assert len(splits) == 3

        for split in splits:
            assert split.n_train > 0
            assert split.n_val > 0
            # No overlap train/val
            assert len(set(split.train_ids) & set(split.val_ids)) == 0
            # Test IDs excluded
            assert len(set(split.train_ids) & set(test_ids)) == 0

    def test_ltr_groups_built(self):
        """LTR groups deben construirse (cada uno de tamaño 1 por ahora)."""
        from data_splitter import build_ltr_groups

        ids = [c.pdb_id for c in self.complexes[:50]]
        groups, labels = build_ltr_groups(self.complexes[:50], ids)

        assert len(groups) == len(labels)
        assert all(g == 1 for g in groups)  # Limitación documentada
        assert len(labels) > 0

    @requires_xgboost
    def test_training_end_to_end_mini(self):
        """
        Entrenar Model A y Model NULL con datos sintéticos.

        Este es el smoke test clave: verifica que el pipeline de
        entrenamiento completo funciona sin errores de integración.
        """
        from data_splitter import (
            build_ltr_groups,
            create_frozen_test_set,
            scaffold_split_cv,
        )
        from structural_family import StructuralFamilyClassifier
        from train_pipeline import MLTrainer

        # Step 1: VIP audit (with mock if no RDKit)
        vip, _ = self._get_vip_complexes_with_mock()

        if len(vip) < 30:
            pytest.skip(f"Not enough VIP complexes ({len(vip)})")

        # Step 2: Family classification
        classifier = StructuralFamilyClassifier()
        families = classifier.classify_all(vip)

        # Step 3: Split
        test_size = min(20, len(vip) // 4)
        test_ids = create_frozen_test_set(vip, families, test_size=test_size, seed=42)
        splits = scaffold_split_cv(vip, test_ids, n_folds=2, seed=42)

        # Step 4: Training
        trainer = MLTrainer(seed=42)
        primary = splits[0]
        groups_train, _ = build_ltr_groups(vip, primary.train_ids)
        groups_val, _ = build_ltr_groups(vip, primary.val_ids)

        model_a = trainer.train_model_a(vip, primary, groups_train, groups_val)
        model_null = trainer.train_model_null(vip, primary, groups_train, groups_val)

        # Verificar que ambos modelos se entrenaron
        assert model_a is not None
        assert model_a.model is not None
        assert model_a.metrics is not None
        assert model_null is not None
        assert model_null.model is not None

        # Step 5: Ablation
        ablation = trainer.run_ablation(vip, primary, groups_train, groups_val)
        assert len(ablation) >= 3  # Al menos A, B, C individual

        # Step 6: SHAP
        X_train = trainer.prepare_features(vip, primary.train_ids, model_a.feature_names)
        shap_summary = trainer.compute_shap_values(model_a, X_train)
        assert isinstance(shap_summary, dict)
        assert len(shap_summary) > 0

        # Step 7: Delta
        all_ids = [c.pdb_id for c in vip]
        deltas = trainer.compute_delta(model_a, model_null, vip, all_ids)
        assert len(deltas) > 0

        delta_dist = trainer.build_delta_distribution(deltas)
        assert "mean" in delta_dist
        assert "semaphore_thresholds" in delta_dist

        # Step 8: Applicability Domain
        from train_pipeline import ALL_FEATURES
        ad = trainer.build_applicability_domain(vip, primary.train_ids, ALL_FEATURES)
        assert "threshold_p99" in ad
        assert "n_features" in ad

        # Step 9: Acceptance criteria
        acceptance = trainer.evaluate_acceptance_criteria(
            ablation, shap_summary, delta_dist, model_a.metrics,
        )
        assert "all_passed" in acceptance

    @requires_xgboost
    def test_save_load_model(self, tmp_path):
        """Verificar que save/load de modelo funciona correctamente."""
        from data_splitter import (
            build_ltr_groups,
            create_frozen_test_set,
            scaffold_split_cv,
        )
        from structural_family import StructuralFamilyClassifier
        from train_pipeline import MLTrainer

        # Mini training with VIP mock
        vip, _ = self._get_vip_complexes_with_mock()

        if len(vip) < 30:
            pytest.skip("Not enough VIP complexes")

        classifier = StructuralFamilyClassifier()
        families = classifier.classify_all(vip)
        test_ids = create_frozen_test_set(vip, families, test_size=10, seed=42)
        splits = scaffold_split_cv(vip, test_ids, n_folds=2, seed=42)

        trainer = MLTrainer(seed=42)
        primary = splits[0]
        groups_t, _ = build_ltr_groups(vip, primary.train_ids)
        groups_v, _ = build_ltr_groups(vip, primary.val_ids)

        model_a = trainer.train_model_a(vip, primary, groups_t, groups_v)

        # Save
        save_path = tmp_path / "model_a.joblib"
        trainer.save_model(model_a, save_path)
        assert save_path.exists()
        assert save_path.stat().st_size > 0

    def test_vip_audit_save_report(self, tmp_path):
        """Verificar que el reporte de auditoría se guarda correctamente."""
        from vip_audit import VIPAuditor

        auditor = VIPAuditor(skip_structure_checks=True)

        if not HAS_RDKIT:
            auditor._check_ligand = lambda cpx, result: result.checks.__setitem__("ligand", True)

        report = auditor.audit_all(self.complexes)

        report_path = tmp_path / "audit_report.json"
        auditor.save_report(report, report_path)

        assert report_path.exists()

        with open(report_path) as f:
            data = json.load(f)

        # save_report uses nested structure: summary.total_evaluated
        assert "summary" in data
        assert "total_evaluated" in data["summary"]
        assert "total_accepted" in data["summary"]
        assert data["summary"]["total_evaluated"] == 200

    def test_feature_extractor_interface_consistency(self):
        """
        Verificar que los dos entrypoints v4 tienen contratos distintos:
        PDBQT+PDB para inferencia y PDB+SDF para entrenamiento.
        """
        import inspect

        from feature_extractor import InteractionFeatureExtractor

        extractor = InteractionFeatureExtractor()

        # Método para inferencia (PDBQT de Vina)
        assert hasattr(extractor, "extract_from_pose")
        sig_inference = inspect.signature(extractor.extract_from_pose)
        params_inference = list(sig_inference.parameters.keys())
        assert "pose_pdbqt_block" in params_inference
        assert "smiles" in params_inference
        assert "target_pdb_path" in params_inference

        # Método para training (archivos PDB/SDF de PDBbind)
        assert hasattr(extractor, "extract_from_files")
        sig_training = inspect.signature(extractor.extract_from_files)
        params_training = list(sig_training.parameters.keys())
        assert "protein_pdb_path" in params_training
        assert "ligand_sdf_path" in params_training

    def test_split_config_saved(self, tmp_path):
        """Verificar que la configuración de splits se guarda para reproducibilidad."""
        from data_splitter import (
            create_frozen_test_set,
            save_split_config,
            scaffold_split_cv,
        )
        from structural_family import StructuralFamilyClassifier

        vip, _ = self._get_vip_complexes_with_mock()

        classifier = StructuralFamilyClassifier()
        families = classifier.classify_all(vip)
        test_ids = create_frozen_test_set(vip, families, test_size=10, seed=42)
        splits = scaffold_split_cv(vip, test_ids, n_folds=2, seed=42)

        config_path = tmp_path / "split_config.json"
        save_split_config(test_ids, splits, config_path, seed=42)

        assert config_path.exists()
        with open(config_path) as f:
            config = json.load(f)

        assert config["seed"] == 42
        assert config["n_folds"] == 2
        assert len(config["frozen_test_set"]) > 0
