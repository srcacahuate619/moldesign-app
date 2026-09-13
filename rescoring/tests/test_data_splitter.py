"""
tests/test_data_splitter.py

Tests para la lógica de partición de datos.

Nota: Los tests de scaffold Bemis-Murcko requieren RDKit para extraer
scaffolds reales. En entornos sin RDKit se saltan y se ejecutan tests
de fallback. El entorno Docker de producción SÍ tiene RDKit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_splitter import (
    DataSplit,
    build_ltr_groups,
    create_frozen_test_set,
    get_bemis_murcko_scaffold,
    group_by_scaffold,
    save_split_config,
    scaffold_split_cv,
)
import data_splitter as ds

# --- Detectar RDKit ---
try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

requires_rdkit = pytest.mark.skipif(
    not HAS_RDKIT,
    reason="RDKit no disponible (se ejecuta en Docker con Python 3.12)",
)


def _make_complex(pdb_id: str, smiles: str = "c1ccccc1", pki: float = 7.0) -> MagicMock:
    """Helper para crear mock complejo."""
    cpx = MagicMock()
    cpx.pdb_id = pdb_id
    cpx.ligand_smiles = smiles
    cpx.pki = pki
    return cpx


class TestBemisMurckoScaffold:
    """Tests para extracción de scaffolds (requiere RDKit)."""

    @requires_rdkit
    def test_benzene_scaffold(self):
        """Benceno es su propio scaffold."""
        scaffold = get_bemis_murcko_scaffold("c1ccccc1")
        assert scaffold  # No vacío
        assert "UNPARSEABLE" not in scaffold

    @requires_rdkit
    def test_substituted_benzene(self):
        """Benceno sustituido tiene scaffold = benceno."""
        s1 = get_bemis_murcko_scaffold("c1ccccc1")
        s2 = get_bemis_murcko_scaffold("c1ccc(O)cc1")
        assert s1 == s2  # Mismo scaffold

    @requires_rdkit
    def test_acyclic_gets_unique_scaffold(self):
        """Molécula acíclica recibe scaffold único."""
        scaffold = get_bemis_murcko_scaffold("CCCCCC")
        assert "ACYCLIC" in scaffold

    def test_invalid_smiles_gets_unique(self):
        """SMILES inválido recibe scaffold fallback."""
        scaffold = get_bemis_murcko_scaffold("INVALID")
        assert "UNPARSEABLE" in scaffold or "ERROR" in scaffold

    @requires_rdkit
    def test_different_scaffolds(self):
        """Moléculas con scaffolds diferentes se distinguen."""
        s1 = get_bemis_murcko_scaffold("c1ccccc1")  # benceno
        s2 = get_bemis_murcko_scaffold("c1ccncc1")  # piridina
        # Benceno y piridina tienen scaffolds diferentes
        assert s1 != s2

    def test_deterministic(self):
        """Mismo SMILES → mismo scaffold (reproducibilidad)."""
        s1 = get_bemis_murcko_scaffold("c1ccc(CC2CCCCC2)cc1")
        s2 = get_bemis_murcko_scaffold("c1ccc(CC2CCCCC2)cc1")
        assert s1 == s2


class TestGroupByScaffold:
    """Tests para agrupamiento por scaffold."""

    @requires_rdkit
    def test_same_scaffold_grouped(self):
        """Moléculas con mismo scaffold se agrupan."""
        complexes = [
            _make_complex("a", "c1ccccc1"),
            _make_complex("b", "c1ccc(O)cc1"),  # Mismo scaffold
            _make_complex("c", "c1ccncc1"),       # Diferente scaffold
        ]
        groups = group_by_scaffold(complexes)
        # 'a' y 'b' deben estar en el mismo grupo
        found_together = False
        for ids in groups.values():
            if "a" in ids and "b" in ids:
                found_together = True
        assert found_together

    def test_all_complexes_assigned(self):
        """Todos los complejos aparecen en algún grupo."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(5)]
        groups = group_by_scaffold(complexes)
        all_ids = set()
        for ids in groups.values():
            all_ids.update(ids)
        assert len(all_ids) == 5


class TestFrozenTestSet:
    """Tests para creación del frozen test set (v2 — scaffold-disjoint).

    El scaffold se mapea con una función fake controlada (se evita la
    dependencia de química real): 25 scaffolds de ~40 complejos, integridad
    por scaffold garantizada por el propio contrato A1.
    """

    @staticmethod
    def _fake_scaffold(smiles: str) -> str:
        return f"S{len(smiles)}"

    def _fixture(self, n: int = 1000) -> tuple:
        complexes = [
            MagicMock(
                pdb_id=f"c{i}",
                ligand_smiles="x" * (1 + (i % 25)),
                pki=float(i % 10),
            )
            for i in range(n)
        ]
        families = {
            f"c{i}": MagicMock(family="kinase" if i % 2 == 0 else "protease")
            for i in range(n)
        }
        return complexes, families

    def test_test_set_size(self, monkeypatch):
        """Test set tiene el tamaño solicitado (aprox)."""
        monkeypatch.setattr(ds, "get_bemis_murcko_scaffold", self._fake_scaffold)
        complexes, families = self._fixture()

        test_ids = create_frozen_test_set(complexes, families, test_size=100, seed=42)
        assert len(test_ids) > 50  # Al menos la mitad del solicitado
        assert len(test_ids) <= 200  # No más del doble

    def test_test_set_deterministic(self, monkeypatch):
        """Mismo seed → mismo test set."""
        monkeypatch.setattr(ds, "get_bemis_murcko_scaffold", self._fake_scaffold)
        complexes, families = self._fixture(500)

        ids1 = create_frozen_test_set(complexes, families, test_size=50, seed=42)
        ids2 = create_frozen_test_set(complexes, families, test_size=50, seed=42)
        assert set(ids1) == set(ids2)

    def test_different_seeds_different_sets(self, monkeypatch):
        """Seeds diferentes → test sets diferentes (457: la semilla gobierna
        el lado inicial del intercalado y los desempates)."""
        monkeypatch.setattr(ds, "get_bemis_murcko_scaffold", self._fake_scaffold)
        complexes, families = self._fixture(500)

        ids1 = create_frozen_test_set(complexes, families, test_size=50, seed=42)
        ids2 = create_frozen_test_set(complexes, families, test_size=50, seed=123)
        # No necesariamente disjuntos, pero no idénticos
        assert set(ids1) != set(ids2)


class TestScaffoldSplitCV:
    """Tests para scaffold-split cross-validation."""

    def test_n_folds(self):
        """Genera el número correcto de folds."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(100)]
        test_ids = [f"c{i}" for i in range(90, 100)]

        splits = scaffold_split_cv(complexes, test_ids, n_folds=5, seed=42)
        assert len(splits) == 5

    def test_no_test_overlap(self):
        """IDs de test no aparecen en train ni val."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(100)]
        test_ids = [f"c{i}" for i in range(90, 100)]

        splits = scaffold_split_cv(complexes, test_ids, n_folds=3, seed=42)
        test_set = set(test_ids)

        for split in splits:
            assert test_set.isdisjoint(set(split.train_ids))
            assert test_set.isdisjoint(set(split.val_ids))

    def test_train_val_disjoint(self):
        """Train y val no se solapan dentro del mismo fold."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(100)]
        test_ids = [f"c{i}" for i in range(90, 100)]

        splits = scaffold_split_cv(complexes, test_ids, n_folds=5, seed=42)
        for split in splits:
            assert set(split.train_ids).isdisjoint(set(split.val_ids))

    def test_all_non_test_used(self):
        """Todos los IDs no-test aparecen en train o val de cada fold."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(50)]
        test_ids = [f"c{i}" for i in range(45, 50)]
        non_test = set(f"c{i}" for i in range(45))

        splits = scaffold_split_cv(complexes, test_ids, n_folds=3, seed=42)
        for split in splits:
            used = set(split.train_ids) | set(split.val_ids)
            assert non_test == used

    def test_deterministic(self):
        """Mismo seed → mismos splits."""
        complexes = [_make_complex(f"c{i}", f"c1ccc(C{'C'*i})cc1") for i in range(50)]
        test_ids = [f"c{i}" for i in range(45, 50)]

        splits1 = scaffold_split_cv(complexes, test_ids, n_folds=3, seed=42)
        splits2 = scaffold_split_cv(complexes, test_ids, n_folds=3, seed=42)

        for s1, s2 in zip(splits1, splits2):
            assert set(s1.val_ids) == set(s2.val_ids)


class TestLTRGroups:
    """Tests para Learning-to-Rank groups."""

    def test_groups_size(self):
        """Cada grupo tiene tamaño 1 (sin UniProt mapping)."""
        complexes = [_make_complex(f"c{i}", pki=float(i)) for i in range(10)]
        pdb_ids = [f"c{i}" for i in range(10)]

        groups, labels = build_ltr_groups(complexes, pdb_ids)
        assert len(groups) == 10
        assert all(g == 1 for g in groups)

    def test_labels_are_pki(self):
        """Labels son pKi."""
        complexes = [_make_complex(f"c{i}", pki=float(i)) for i in range(5)]
        pdb_ids = [f"c{i}" for i in range(5)]

        groups, labels = build_ltr_groups(complexes, pdb_ids)
        assert len(labels) == 5

    def test_labels_aligned(self):
        """Labels se alignan con IDs ordenados."""
        complexes = [
            _make_complex("b", pki=8.0),
            _make_complex("a", pki=5.0),
            _make_complex("c", pki=9.0),
        ]
        pdb_ids = ["a", "b", "c"]
        groups, labels = build_ltr_groups(complexes, pdb_ids)
        # Sorted: a=5.0, b=8.0, c=9.0
        assert labels[0] == 5.0
        assert labels[1] == 8.0
        assert labels[2] == 9.0


class TestDataSplit:
    """Tests para DataSplit."""

    def test_post_init(self):
        """Post-init calcula sizes correctamente."""
        split = DataSplit(
            train_ids=["a", "b", "c"],
            val_ids=["d"],
            test_ids=["e", "f"],
        )
        assert split.n_train == 3
        assert split.n_val == 1
        assert split.n_test == 2


class TestSaveSplitConfig:
    """Tests para guardar configuración de splits."""

    def test_save_and_load(self, tmp_path):
        """Guardar y cargar config JSON."""
        test_ids = ["a", "b"]
        splits = [
            DataSplit(train_ids=["c", "d"], val_ids=["e"], test_ids=test_ids, fold=0),
            DataSplit(train_ids=["c", "e"], val_ids=["d"], test_ids=test_ids, fold=1),
        ]
        out = tmp_path / "split_config.json"
        save_split_config(test_ids, splits, out, seed=42)

        assert out.exists()
        data = json.loads(out.read_text())
        assert data["seed"] == 42
        assert len(data["frozen_test_set"]) == 2
        assert data["n_folds"] == 2


class TestScaffoldNoRDKit:
    """Tests para el fallback de scaffold cuando RDKit no está disponible."""

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_fallback_is_deterministic(self):
        """Sin RDKit, mismo SMILES produce mismo hash (reproducibilidad)."""
        s1 = get_bemis_murcko_scaffold("c1ccccc1")
        s2 = get_bemis_murcko_scaffold("c1ccccc1")
        assert s1 == s2

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_fallback_produces_error_prefix(self):
        """Sin RDKit, scaffolds tienen prefijo ERROR_."""
        scaffold = get_bemis_murcko_scaffold("c1ccccc1")
        assert scaffold.startswith("ERROR_")

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_fallback_different_smiles_differ(self):
        """Sin RDKit, SMILES diferentes producen hashes diferentes."""
        s1 = get_bemis_murcko_scaffold("c1ccccc1")
        s2 = get_bemis_murcko_scaffold("c1ccncc1")
        assert s1 != s2
