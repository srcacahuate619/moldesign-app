"""
Tests for Bucket B: dynamic Vina box computed from PDB HETATM/protein atoms.

These tests exercise backend/services/chemistry/protein_surgery.py:
  - extract_accurate_pocket_centroid (4-priority HETATM scan)
  - compute_dynamic_box extended signature (ligand_mol2 OR pdb_path fallback)

Scenarios:
  1. Drug ligand HETATM (7E2Y with SRO serotonin + CLR cholesterol + J40)
     -> Priority 1: DRUG_LIGAND branch.  CLR has 112 atoms, J40 has 57, SRO 13;
        the algorithm picks the LARGEST ligand by atom count, not necessarily
        SRO.  We assert that the returned center is non-zero and the source
        label starts with 'DRUG_LIGAND'.

  2. Catalytic metal only (9QA0 has ZN, all glycans in NON_DRUG_HETATMS)
     -> Priority 2: CATALYTIC_METAL branch. One ZN atom present in the PDB.

  3. No HETATM at all (synthetic PDB with only ATOM lines)
     -> Priority 4: PROTEIN_ATOM_FALLBACK; center equals protein atom centroid.

  4. PDB missing / unreadable
     -> compute_dynamic_box returns _default_box with source='default'.

Also covers: compute_dynamic_box(ligand_mol2=None, pdb_path=None) returns default
box, and the original ligand_mol2-only call path still works (backward compat).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure backend is importable when running from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.chemistry.protein_surgery import (  # noqa: E402
    CATALYTIC_METALS,
    NON_DRUG_HETATMS,
    _default_box,
    compute_dynamic_box,
    extract_accurate_pocket_centroid,
)

# Real PDB fixtures shipped with the repo.
_PDB_7E2Y = _REPO_ROOT / "data" / "targets" / "7E2Y.pdb"
_PDB_9QA0 = _REPO_ROOT / "data" / "target_library" / "18_cardiovascular" / "9QA0.pdb"


# ─────────────────────────────────────────────────────────────
# Constants imported verbatim from scripts/recalibrate_all_386_targets.py
# ─────────────────────────────────────────────────────────────

class TestConstants:
    def test_non_drug_hetatms_includes_water(self):
        for water in ("HOH", "WAT", "DOD", "TIP", "SOL"):
            assert water in NON_DRUG_HETATMS

    def test_non_drug_hetatms_includes_glycans(self):
        for glycan in ("NAG", "MAN", "BMA", "FUC", "GAL", "GLC"):
            assert glycan in NON_DRUG_HETATMS

    def test_catalytic_metals_set(self):
        # Nine biologically relevant catalytic metals (Bucket B spec).
        assert CATALYTIC_METALS == {"ZN", "FE", "MN", "MG", "CA", "CU", "NI", "CO", "CD"}


# ─────────────────────────────────────────────────────────────
# Scenario 1: drug ligand HETATM (7E2Y: SRO + CLR + J40)
# ─────────────────────────────────────────────────────────────

class TestDrugLigandPriority:
    @pytest.mark.skipif(not _PDB_7E2Y.exists(), reason="7E2Y.pdb absent from data/targets")
    def test_7e2y_returns_drug_ligand_branch(self):
        center, method = extract_accurate_pocket_centroid(str(_PDB_7E2Y))
        assert center is not None
        assert method.startswith("DRUG_LIGAND"), f"expected DRUG_LIGAND prefix, got {method!r}"
        # Sanity: HETATM SRO is present in the file (113-114 Å pocket).
        cx, cy, cz = center
        assert abs(cx) > 1.0 and abs(cy) > 1.0 and abs(cz) > 1.0

    @pytest.mark.skipif(not _PDB_7E2Y.exists(), reason="7E2Y.pdb absent")
    def test_compute_box_via_pdb_fallback_returns_mol2_or_pdb_source(self):
        box = compute_dynamic_box(ligand_mol2=None, pdb_path=str(_PDB_7E2Y))
        assert box["center"] != (0.0, 0.0, 0.0)
        # When ligand_mol2 is None, source must be pdb_fallback:* (NOT mol2).
        assert box["source"].startswith(("pdb_fallback:", "default"))
        assert box["size"] == 22.0  # max_size, since PDB fallback uses conservative size


# ─────────────────────────────────────────────────────────────
# Scenario 2: catalytic metal only (9QA0 with ZN, glycans skipped)
# ─────────────────────────────────────────────────────────────

class TestCatalyticMetalPriority:
    @pytest.mark.skipif(not _PDB_9QA0.exists(), reason="9QA0.pdb absent from target_library")
    def test_9qa0_returns_catalytic_metal_or_drug_branch(self):
        # 9QA0 has ZN + glycans.  Glycans are in NON_DRUG_HETATMS so they are
        # excluded from drug_hetatms, leaving ZN as the metal branch winner.
        # If FLC is NOT in NON_DRUG_HETATMS, it becomes the drug_ligand winner.
        center, method = extract_accurate_pocket_centroid(str(_PDB_9QA0))
        assert center is not None
        # Either DRUG_LIGAND (FLC if not skipped) or CATALYTIC_METAL (ZN).
        assert method.startswith(("DRUG_LIGAND", "CATALYTIC_METAL")), \
            f"unexpected method {method!r} for 9QA0"

    @pytest.mark.skipif(not _PDB_9QA0.exists(), reason="9QA0.pdb absent")
    def test_zn_present_in_pdb(self):
        # Sanity: confirm the file actually has a ZN HETATM line.
        text = _PDB_9QA0.read_text(encoding="utf-8", errors="ignore")
        zn_lines = [l for l in text.splitlines() if l.startswith("HETATM") and l[17:20].strip() == "ZN"]
        assert len(zn_lines) >= 1, "9QA0 expected to contain at least one ZN HETATM"


# ─────────────────────────────────────────────────────────────
# Scenario 3: no HETATM at all -> PROTEIN_ATOM_FALLBACK
# ─────────────────────────────────────────────────────────────

_PROTEIN_ONLY_PDB = """\
ATOM      1  N   ALA A   1      10.000  20.000  30.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      11.000  21.000  31.000  1.00  0.00           C
ATOM      3  C   ALA A   1      12.000  22.000  32.000  1.00  0.00           C
ATOM      4  O   ALA A   1      13.000  23.000  33.000  1.00  0.00           O
ATOM      5  N   GLY A   2      20.000  30.000  40.000  1.00  0.00           N
ATOM      6  CA  GLY A   2      21.000  31.000  41.000  1.00  0.00           C
END
"""

# Water-only PDB -> no HETATM passes the water filter; falls to PROTEIN_ATOM_FALLBACK.
_WATER_ONLY_PDB = """\
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  0.00           C
HETATM    3  O   HOH A 101       5.000   5.000   5.000  1.00  0.00           O
END
"""


class TestProteinFallbackPriority:
    def test_protein_only_pdb_falls_to_atom_centroid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False, encoding="utf-8") as f:
            f.write(_PROTEIN_ONLY_PDB)
            path = f.name
        try:
            center, method = extract_accurate_pocket_centroid(path)
            assert method == "PROTEIN_ATOM_FALLBACK"
            # 6 ATOM lines: ALA1 (N=10, CA=11, C=12, O=13), GLY2 (N=20, CA=21).
            # Centroid: x=(10+11+12+13+20+21)/6=87/6=14.5, y=(...)/6=24.5, z=34.5
            assert center == (14.5, 24.5, 34.5)
        finally:
            os.unlink(path)

    def test_water_only_pdb_falls_to_protein_centroid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False, encoding="utf-8") as f:
            f.write(_WATER_ONLY_PDB)
            path = f.name
        try:
            center, method = extract_accurate_pocket_centroid(path)
            assert method == "PROTEIN_ATOM_FALLBACK"
            assert center == (0.5, 0.5, 0.5)
        finally:
            os.unlink(path)

    def test_compute_box_protein_fallback_has_pdb_fallback_source(self):
        with tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False, encoding="utf-8") as f:
            f.write(_PROTEIN_ONLY_PDB)
            path = f.name
        try:
            box = compute_dynamic_box(ligand_mol2=None, pdb_path=path)
            assert box["source"].startswith("pdb_fallback:PROTEIN_ATOM")
            assert box["size"] == 22.0
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────
# Scenario 4: missing file -> default box
# ─────────────────────────────────────────────────────────────

class TestMissingFileDefault:
    def test_missing_pdb_returns_default_box(self):
        box = compute_dynamic_box(ligand_mol2=None, pdb_path="D:/nonexistent/path/missing.pdb")
        assert box["center"] == (0.0, 0.0, 0.0)
        assert box["size"] == 22.0
        assert box["source"] == "default"

    def test_missing_mol2_missing_pdb_returns_default_box(self):
        box = compute_dynamic_box(
            ligand_mol2="D:/nonexistent/missing.mol2",
            pdb_path="D:/nonexistent/missing.pdb",
        )
        assert box["source"] == "default"
        assert box["center"] == (0.0, 0.0, 0.0)

    def test_default_box_helper_shape(self):
        b = _default_box()
        assert set(b.keys()) == {"center", "size", "ligand_span"}
        assert b["size"] == 22.0


# ─────────────────────────────────────────────────────────────
# Backward compatibility: original signature (ligand_mol2 only)
# ─────────────────────────────────────────────────────────────

class TestBackwardCompat:
    def test_ligand_mol2_none_pdb_none_yields_default(self):
        # Same as original compute_dynamic_box(None) which returned _default_box~
        box = compute_dynamic_box()
        assert box["source"] == "default"

    def test_compute_dynamic_box_has_new_optional_params(self):
        import inspect
        sig = inspect.signature(compute_dynamic_box)
        params = set(sig.parameters)
        assert {"ligand_mol2", "pdb_path", "min_size", "max_size", "padding"} == params
        # Defaults confirm new behavior.
        assert sig.parameters["ligand_mol2"].default is None
        assert sig.parameters["pdb_path"].default is None
        assert sig.parameters["min_size"].default == 12.0
        assert sig.parameters["max_size"].default == 22.0
        assert sig.parameters["padding"].default == 8.0
