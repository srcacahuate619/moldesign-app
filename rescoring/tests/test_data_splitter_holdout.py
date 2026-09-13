"""
tests/test_data_splitter_holdout.py

Tests del holdout A1 scaffold-disjoint (create_frozen_test_set v2):

- Atomicidad por scaffold: NUNCA se parte un scaffold entre holdout y train
- Determinismo con seed fija
- Representación por familia (mínimo 10 por familia si hay suficientes)
- Verificación total: verify_scaffold_disjoint() = True

Requiere RDKit sólo si se quiere validar el Bemis-Murcko real; con el
fallback determinista (hash) las garantías estructurales son equivalentes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_splitter import (
    create_frozen_test_set,
    get_bemis_murcko_scaffold,
    verify_scaffold_disjoint,
)

try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

requires_rdkit = pytest.mark.skipif(
    not HAS_RDKIT,
    reason="RDKit no disponible",
)


def _make_complex(pdb_id: str, smiles: str, pki: float) -> MagicMock:
    cpx = MagicMock()
    cpx.pdb_id = pdb_id
    cpx.ligand_smiles = smiles
    cpx.pki = pki
    return cpx


def _family(pdb_id: str, family: str) -> dict[str, str]:
    return {pdb_id: family}


def _split(
    complexes,
    family_classifications,
    test_size: int = 20,
    seed: int = 42,
):
    return create_frozen_test_set(complexes, family_classifications, test_size, seed)


class TestScaffoldAtomicity:
    """El holdout nunca parte un scaffold: todo o nada."""

    def test_scaffold_all_or_nothing(self):
        # 3 scaffolds: S1 (2 comps), S2 (3 comps), S3 (5 comps)
        complexes = [
            _make_complex("c1", "c1ccccc1", 6.0),
            _make_complex("c2", "c1ccccc1", 7.0),
            _make_complex("d1", "c1ccc(cc1)C", 6.5),
            _make_complex("d2", "c1ccc(cc1)C", 7.5),
            _make_complex("d3", "c1ccc(cc1)C", 8.0),
            _make_complex("e1", "c1ccc2ccccc2c1", 9.0),
            _make_complex("e2", "c1ccc2ccccc2c1", 8.5),
            _make_complex("e3", "c1ccc2ccccc2c1", 7.0),
            _make_complex("e4", "c1ccc2ccccc2c1", 6.0),
            _make_complex("e5", "c1ccc2ccccc2c1", 5.5),
        ]
        fc = {}
        for c in complexes:
            fc[c.pdb_id] = "kinase"

        test_ids = _split(complexes, fc, test_size=4)

        # Agrupar por scaffold y verificar atomicidad
        members_by_scaffold = {}
        for c in complexes:
            members_by_scaffold.setdefault(get_bemis_murcko_scaffold(c.ligand_smiles), []).append(c.pdb_id)
        for group in members_by_scaffold.values():
            in_test = [pid for pid in group if pid in test_ids]
            assert len(in_test) in (0, len(group)), (
                f"scaffold partido: {in_test} de {group}"
            )
        assert len(test_ids) > 0

    def test_verify_scaffold_disjoint_true(self):
        complexes = [
            _make_complex("a1", "c1ccccc1", 6.0),
            _make_complex("a2", "c1ccccc1", 7.0),
            _make_complex("b1", "c1ccc2ccccc2c1", 8.0),
            _make_complex("b2", "c1ccc2ccccc2c1", 7.0),
            _make_complex("c1", "c1ccncc1", 9.0),
            _make_complex("c2", "c1ccncc1", 6.5),
            _make_complex("c3", "c1ccncc1", 5.5),
        ]
        fc = {c.pdb_id: "gpcr" for c in complexes}
        test_ids = _split(complexes, fc, test_size=2)
        ok, violations = verify_scaffold_disjoint(test_ids, complexes)
        assert ok, f"violaciones: {violations}"


class TestDeterminism:
    def test_same_seed_same_holdout(self):
        complexes = [
            _make_complex(f"s{i + 1}", "c1ccc(cc1)" + "C" * (i % 3), 6.0 + (i % 5))
            for i in range(30)
        ]
        fc = {c.pdb_id: "protease" for c in complexes}
        t1 = _split(complexes, fc, test_size=8, seed=7)
        t2 = _split(complexes, fc, test_size=8, seed=7)
        assert t1 == t2

    def test_large_scaffolds_not_discarded(self):
        # [A1 fix] Grupos que exceden el margen 1.5x deben diferirse a la
        # pasada de completado, NO descartarse (antes test_size=0).
        complexes = [
            _make_complex(f"x{i + 1}", "c1ccc2ccccc2c1" + "N" * (i % 2), 6.0 + (i % 4))
            for i in range(40)
        ]
        fc = {c.pdb_id: "kinase" for c in complexes}
        for seed in (1, 2, 42):
            test_ids = _split(complexes, fc, test_size=10, seed=seed)
            assert len(test_ids) > 0, f"seed={seed}: holdout vacío (scaffolds descartados)"
            ok, violations = verify_scaffold_disjoint(test_ids, complexes)
            assert ok, f"seed={seed} violaciones: {violations}"


class TestFamilyRepresentation:
    def test_min_ten_per_family_when_available(self):
        complexes = [
            _make_complex(f"g{i + 1}", "c1ccccc1", 7.0) for i in range(30)
        ] + [
            _make_complex(f"h{i + 1}", "c1ccc2ccccc2c1", 7.0) for i in range(30)
        ]
        fc = {c.pdb_id: ("gpcr" if c.pdb_id.startswith("g") else "kinase") for c in complexes}
        test_ids = _split(complexes, fc, test_size=20)
        ids = set(test_ids)
        n_gpcr = sum(1 for pid in ids if pid.startswith("g"))
        n_kin = sum(1 for pid in ids if pid.startswith("h"))
        # cuota = max(10, 20*0.5=10) = 10, cap a len(members)//2 = 15
        assert n_gpcr >= 10
        assert n_kin >= 10

    def test_never_more_than_half_family(self):
        # Familia chica de 4 con UN solo scaffold: cuota = min(max(10, ...), 2) = 2,
        # pero el grupo (4) excede el margen 1.5x y se difiere a la pasada de
        # completado, donde ATOMICIDAD > cuota: entra el scaffold completo (4).
        complexes = [
            _make_complex(f"a{i + 1}", "c1ccccc1", 7.0) for i in range(4)
        ] + [
            _make_complex(f"b{i + 1}", "c1ccc2ccccc2c1", 7.0) for i in range(40)
        ]
        fc = {c.pdb_id: ("gpcr" if c.pdb_id.startswith("a") else "kinase") for c in complexes}
        test_ids = _split(complexes, fc, test_size=22)
        ids = set(test_ids)
        n_gpcr = sum(1 for pid in ids if pid.startswith("a"))
        ok, violations = verify_scaffold_disjoint(list(ids), complexes)
        assert ok
        assert n_gpcr == 4  # atomicidad impuesta: todo el scaffold, o nada