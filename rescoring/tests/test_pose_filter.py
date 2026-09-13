"""
tests/test_pose_filter.py

Tests unitarios para el filtro geométrico de poses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Agregar el directorio rescoring al path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pose_filter import PoseFilter

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


def _make_pdbqt_line(serial: int, x: float, y: float, z: float, atom_type: str = "C") -> str:
    """
    Generar una línea PDBQT con formato correcto (columnas fijas).

    El parser real lee:
      - cols 0-5: record type (ATOM/HETATM)
      - cols 30-38, 38-46, 46-54: coordenadas x, y, z
      - cols 77+: atom type (H/HD para hidrógenos)
    """
    # Construir exactamente al formato PDB/PDBQT con columnas fijas
    # "ATOM      1  C1  LIG A   1      -22.228  -0.583 -29.375  1.00  0.00    0.000 C"
    name = f" {atom_type}{serial:<2d}"[:4]
    line = f"ATOM  {serial:5d} {name} LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    0.000 {atom_type:>2s}"
    # Asegurar que la columna 77+ tiene el atom type
    # Pad to at least 79 chars, then append atom type
    line = line.ljust(77) + f" {atom_type}"
    return line


def _make_pdbqt_block(coords: list[tuple[float, float, float]], atom_type: str = "C") -> str:
    """Generar un bloque PDBQT sintético con coordenadas dadas."""
    lines = []
    for i, (x, y, z) in enumerate(coords, start=1):
        lines.append(_make_pdbqt_line(i, x, y, z, atom_type))
    lines.append("END")
    return "\n".join(lines)


class FakePose:
    """Pose simulada para tests."""

    def __init__(self, pdbqt_block: str, vina_score: float, rmsd_lb: float = 0.0, rmsd_ub: float = 0.0):
        self.pdbqt_block = pdbqt_block
        self.vina_score = vina_score
        self.rmsd_lb = rmsd_lb
        self.rmsd_ub = rmsd_ub


# Grid center para 7E2Y (default)
GRID_CENTER = (-22.228, -0.583, -29.375)


def _make_pose_at_center(score: float = -8.0) -> FakePose:
    """Crear pose centrada en el grid box."""
    cx, cy, cz = GRID_CENTER
    coords = [
        (cx, cy, cz),
        (cx + 1, cy, cz),
        (cx, cy + 1, cz),
        (cx, cy, cz + 1),
        (cx - 1, cy - 1, cz),
    ]
    return FakePose(_make_pdbqt_block(coords), score)


def _make_pose_far_away(score: float = -5.0) -> FakePose:
    """Crear pose lejos del grid box."""
    coords = [
        (100.0, 100.0, 100.0),
        (101.0, 100.0, 100.0),
        (100.0, 101.0, 100.0),
        (100.0, 100.0, 101.0),
        (99.0, 99.0, 99.0),
    ]
    return FakePose(_make_pdbqt_block(coords), score)


def _make_pose_partially_in_box(score: float = -7.0) -> FakePose:
    """Crear pose parcialmente dentro del grid box (40% dentro)."""
    cx, cy, cz = GRID_CENTER
    # 2 átomos dentro, 3 fuera del box
    coords = [
        (cx, cy, cz),          # dentro
        (cx + 1, cy, cz),      # dentro
        (cx + 50, cy, cz),     # fuera
        (cx, cy + 50, cz),     # fuera
        (cx, cy, cz + 50),     # fuera
    ]
    return FakePose(_make_pdbqt_block(coords), score)


def _pose_filter_for_7e2y() -> PoseFilter:
    """Configure the explicit grid used by the 7E2Y test fixtures."""
    pose_filter = PoseFilter()
    pose_filter.config.grid_center = GRID_CENTER
    return pose_filter


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────


class TestPoseFilter:
    """Tests del filtro geométrico de poses."""

    def test_pose_at_center_passes(self):
        """Una pose centrada en el grid box debe pasar."""
        pf = _pose_filter_for_7e2y()
        result = pf.filter_poses([_make_pose_at_center()])
        assert result["poses_passing"] == 1
        assert len(result["valid_poses"]) == 1

    def test_pose_far_away_fails(self):
        """Una pose lejos del grid box debe fallar check de centroide."""
        pf = _pose_filter_for_7e2y()
        result = pf.filter_poses([_make_pose_far_away()])
        assert result["poses_passing"] == 0
        assert len(result["valid_poses"]) == 0

    def test_mixed_poses(self):
        """Solo las poses válidas pasan."""
        pf = _pose_filter_for_7e2y()
        poses = [
            _make_pose_at_center(-8.0),
            _make_pose_far_away(-5.0),
            _make_pose_at_center(-7.5),
        ]
        result = pf.filter_poses(poses)
        assert result["poses_passing"] == 2
        assert result["total"] == 3
        assert len(result["valid_poses"]) == 2

    def test_partially_in_box_fails(self):
        """Pose con <70% de átomos en el box debe fallar."""
        pf = _pose_filter_for_7e2y()
        result = pf.filter_poses([_make_pose_partially_in_box()])
        assert result["poses_passing"] == 0

    def test_empty_pdbqt_fails(self):
        """PDBQT vacío no debe crashear."""
        pose = FakePose("", -8.0)
        pf = _pose_filter_for_7e2y()
        result = pf.filter_poses([pose])
        assert result["poses_passing"] == 0

    def test_all_nine_poses_pass(self):
        """9 poses válidas → 9 pasan."""
        pf = _pose_filter_for_7e2y()
        poses = [_make_pose_at_center(-8.0 + i * 0.1) for i in range(9)]
        result = pf.filter_poses(poses)
        assert result["poses_passing"] == 9
        assert result["total"] == 9

    def test_details_contain_metrics(self):
        """Cada resultado tiene métricas detalladas."""
        pf = _pose_filter_for_7e2y()
        result = pf.filter_poses([_make_pose_at_center()])
        detail = result["details"][0]
        assert "centroid_distance" in detail
        assert "atoms_in_box_ratio" in detail
        assert "checks" in detail
        assert detail["checks"]["centroid"] is True
        assert detail["checks"]["atoms_in_box"] is True


class TestCoordinateExtraction:
    """Tests de la extracción de coordenadas desde PDBQT."""

    def test_extracts_heavy_atoms(self):
        """Debe extraer coordenadas de átomos pesados."""
        pf = PoseFilter()
        pdbqt = _make_pdbqt_block([(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])
        coords = pf._extract_coordinates(pdbqt)
        assert len(coords) == 2
        assert coords[0] == pytest.approx((1.0, 2.0, 3.0), abs=0.01)

    def test_skips_hydrogen(self):
        """Debe ignorar hidrógenos."""
        pf = PoseFilter()
        carbon_line = _make_pdbqt_line(1, 1.0, 2.0, 3.0, "C")
        hydrogen_line = _make_pdbqt_line(2, 1.5, 2.5, 3.5, "H")
        pdbqt = f"{carbon_line}\n{hydrogen_line}\nEND"
        coords = pf._extract_coordinates(pdbqt)
        assert len(coords) == 1

    def test_empty_block(self):
        """Bloque vacío → lista vacía."""
        pf = PoseFilter()
        coords = pf._extract_coordinates("")
        assert len(coords) == 0
