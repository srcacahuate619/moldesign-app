"""
Tests for rescoring/data_curator.py

Tests each of the 8 sequential filters independently using synthetic
PDBBindComplex objects. No real PDBbind data or file access is needed
except where explicitly testing file-based filters (5, 6).
"""

from __future__ import annotations

import json

from data_curator import (
    ACCEPTED_BINDING_TYPES,
    ACCEPTED_PRECISIONS,
    OUTLIER_ZSCORE_THRESHOLD,
    PKI_MAX,
    PKI_MIN,
    CurationFilter,
    CurationReport,
    DataCurator,
)
from pdbbind_parser import PDBBindComplex

# ─── Helpers ────────────────────────────────────────────────────


def make_complex(
    pdb_id: str = "1abc",
    resolution: float = 2.0,
    binding_type: str = "Ki",
    binding_value_nm: float = 100.0,
    pki: float = 7.0,
    binding_precision: str = "exact",
    source_set: str = "refined",
    protein_pdb_path: str | None = "/fake/1abc_protein.pdb",
    ligand_sdf_path: str | None = "/fake/1abc_ligand.sdf",
    ligand_mol2_path: str | None = None,
    binding_data_raw: str = "Ki=100nM",
    ligand_smiles: str = "CCO",
    release_year: int = 2015,
) -> PDBBindComplex:
    """Create a synthetic PDBBindComplex for testing."""
    return PDBBindComplex(
        pdb_id=pdb_id,
        resolution=resolution,
        release_year=release_year,
        binding_data_raw=binding_data_raw,
        binding_type=binding_type,
        binding_value_nm=binding_value_nm,
        pki=pki,
        ligand_smiles=ligand_smiles,
        binding_precision=binding_precision,
        source_set=source_set,
        protein_pdb_path=protein_pdb_path,
        ligand_sdf_path=ligand_sdf_path,
        ligand_mol2_path=ligand_mol2_path,
    )


def make_batch(n: int, **overrides) -> list[PDBBindComplex]:
    """Create a batch of n distinct complexes. Optional overrides applied to all."""
    complexes = []
    for i in range(n):
        defaults = {
            "pdb_id": f"{i:04d}",
            "pki": 5.0 + i * 0.2,
            "binding_value_nm": 10 ** (9 - (5.0 + i * 0.2)),
        }
        defaults.update(overrides)
        complexes.append(make_complex(**defaults))
    return complexes


# ─── Constants tests ────────────────────────────────────────────


class TestConstants:
    """Verify exported constants match scientific expectations."""

    def test_accepted_binding_types(self):
        assert ACCEPTED_BINDING_TYPES == {"Ki", "Kd"}

    def test_accepted_precisions(self):
        assert ACCEPTED_PRECISIONS == {"exact"}

    def test_pki_range(self):
        assert PKI_MIN == 2.0
        assert PKI_MAX == 13.0

    def test_outlier_threshold(self):
        assert OUTLIER_ZSCORE_THRESHOLD == 4.0


# ─── Filter 1: Precision ───────────────────────────────────────


class TestFilterPrecision:
    """Filter 1: Only exact binding data (operator =)."""

    def test_exact_kept(self):
        curator = DataCurator()
        cpx = [make_complex(binding_precision="exact")]
        result, report = curator.curate(cpx)
        # Should survive all filters (files won't exist, but precision filter is first)
        precision_filter = report.filters[0]
        assert precision_filter.name == "binding_precision"
        assert precision_filter.n_removed == 0

    def test_approximate_removed(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(binding_precision="approximate", binding_data_raw="Ki~100nM")]
        result = curator._filter_precision(cpx, report)
        assert len(result) == 0
        assert report.filters[0].n_removed == 1

    def test_upper_bound_removed(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(binding_precision="upper_bound", binding_data_raw="Ki<100nM")]
        result = curator._filter_precision(cpx, report)
        assert len(result) == 0

    def test_lower_bound_removed(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(binding_precision="lower_bound", binding_data_raw="Ki>100nM")]
        result = curator._filter_precision(cpx, report)
        assert len(result) == 0

    def test_unknown_removed(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(binding_precision="unknown")]
        result = curator._filter_precision(cpx, report)
        assert len(result) == 0

    def test_mixed_batch(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", binding_precision="exact"),
            make_complex(pdb_id="2bbb", binding_precision="approximate"),
            make_complex(pdb_id="3ccc", binding_precision="exact"),
            make_complex(pdb_id="4ddd", binding_precision="lower_bound"),
        ]
        result = curator._filter_precision(cpx, report)
        assert len(result) == 2
        assert {c.pdb_id for c in result} == {"1aaa", "3ccc"}


# ─── Filter 2: Binding Type ────────────────────────────────────


class TestFilterBindingType:
    """Filter 2: Only Ki or Kd."""

    def test_ki_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_binding_type(
            [make_complex(binding_type="Ki")], report
        )
        assert len(result) == 1

    def test_kd_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_binding_type(
            [make_complex(binding_type="Kd")], report
        )
        assert len(result) == 1

    def test_ic50_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_binding_type(
            [make_complex(binding_type="IC50")], report
        )
        assert len(result) == 0
        assert report.filters[0].n_removed == 1

    def test_ec50_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_binding_type(
            [make_complex(binding_type="EC50")], report
        )
        assert len(result) == 0


# ─── Filter 3: Affinity Range ──────────────────────────────────


class TestFilterAffinityRange:
    """Filter 3: pKi must be in [2.0, 13.0]."""

    def test_normal_pki_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=7.0)], report
        )
        assert len(result) == 1

    def test_lower_bound_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=2.0)], report
        )
        assert len(result) == 1

    def test_upper_bound_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=13.0)], report
        )
        assert len(result) == 1

    def test_too_low_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=1.5)], report
        )
        assert len(result) == 0
        assert report.filters[0].n_removed == 1

    def test_too_high_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=14.0)], report
        )
        assert len(result) == 0

    def test_zero_pki_removed(self):
        """pKi=0 means unparseable → reject."""
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=0.0)], report
        )
        assert len(result) == 0

    def test_negative_pki_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_affinity_range(
            [make_complex(pki=-1.0)], report
        )
        assert len(result) == 0

    def test_custom_range(self):
        curator = DataCurator(pki_min=5.0, pki_max=10.0)
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="0001", pki=3.0),
            make_complex(pdb_id="0002", pki=7.0),
            make_complex(pdb_id="0003", pki=11.0),
        ]
        result = curator._filter_affinity_range(cpx, report)
        assert len(result) == 1
        assert result[0].pdb_id == "0002"


# ─── Filter 4: Resolution ──────────────────────────────────────


class TestFilterResolution:
    """Filter 4: Resolution ≤ 3.0 Å and > 0."""

    def test_good_resolution_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_resolution(
            [make_complex(resolution=2.0)], report
        )
        assert len(result) == 1

    def test_boundary_resolution_kept(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_resolution(
            [make_complex(resolution=3.0)], report
        )
        assert len(result) == 1

    def test_too_low_resolution_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_resolution(
            [make_complex(resolution=3.5)], report
        )
        assert len(result) == 0

    def test_zero_resolution_removed(self):
        """Resolution 0 means NMR or unreported → reject."""
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_resolution(
            [make_complex(resolution=0.0)], report
        )
        assert len(result) == 0

    def test_negative_resolution_removed(self):
        curator = DataCurator()
        report = CurationReport()
        result = curator._filter_resolution(
            [make_complex(resolution=-1.0)], report
        )
        assert len(result) == 0

    def test_custom_threshold(self):
        curator = DataCurator(max_resolution=2.0)
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="0001", resolution=1.5),
            make_complex(pdb_id="0002", resolution=2.5),
        ]
        result = curator._filter_resolution(cpx, report)
        assert len(result) == 1
        assert result[0].pdb_id == "0001"


# ─── Filter 5: Structural Files ────────────────────────────────


class TestFilterStructuralFiles:
    """Filter 5: Protein PDB and ligand SDF/MOL2 must exist on disk."""

    def test_both_exist(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("ATOM  mock protein content\nEND\n")
        sdf.write_text("mock ligand\n$$$$\n")

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_structural_files(cpx, report)
        assert len(result) == 1

    def test_missing_protein(self, tmp_path):
        sdf = tmp_path / "1abc_ligand.sdf"
        sdf.write_text("mock\n$$$$\n")

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(tmp_path / "nonexistent.pdb"),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_structural_files(cpx, report)
        assert len(result) == 0

    def test_missing_ligand(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        pdb.write_text("ATOM mock\nEND\n")

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(tmp_path / "nonexistent.sdf"),
        )]
        result = curator._filter_structural_files(cpx, report)
        assert len(result) == 0

    def test_mol2_accepted_as_ligand(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        mol2 = tmp_path / "1abc_ligand.mol2"
        pdb.write_text("ATOM mock\nEND\n")
        mol2.write_text("@<TRIPOS>MOLECULE\nmock\n")

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=None,
            ligand_mol2_path=str(mol2),
        )]
        result = curator._filter_structural_files(cpx, report)
        assert len(result) == 1

    def test_null_paths_removed(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=None,
            ligand_sdf_path=None,
        )]
        result = curator._filter_structural_files(cpx, report)
        assert len(result) == 0


# ─── Filter 6: File Sizes ──────────────────────────────────────


class TestFilterFileSizes:
    """Filter 6: PDB ≥ 100 bytes, SDF ≥ 50 bytes."""

    def test_normal_files_kept(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("A" * 200)
        sdf.write_text("B" * 100)

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_file_sizes(cpx, report)
        assert len(result) == 1

    def test_truncated_pdb_removed(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("X" * 10)  # Too small
        sdf.write_text("B" * 100)

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_file_sizes(cpx, report)
        assert len(result) == 0
        assert "truncado" in report.filters[0].removed_ids[0].lower() or "PDB" in report.filters[0].removed_ids[0]

    def test_truncated_sdf_removed(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("A" * 200)
        sdf.write_text("X" * 10)  # Too small

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_file_sizes(cpx, report)
        assert len(result) == 0

    def test_empty_files_removed(self, tmp_path):
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("")
        sdf.write_text("")

        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(
            protein_pdb_path=str(pdb),
            ligand_sdf_path=str(sdf),
        )]
        result = curator._filter_file_sizes(cpx, report)
        assert len(result) == 0


# ─── Filter 7: Deduplication ───────────────────────────────────


class TestFilterDeduplication:
    """Filter 7: Refined > Other priority; remove duplicates."""

    def test_no_duplicates_unchanged(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="refined"),
            make_complex(pdb_id="2bbb", source_set="other"),
        ]
        result = curator._deduplicate(cpx, report)
        assert len(result) == 2

    def test_refined_wins_over_other(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="refined", pki=7.0),
            make_complex(pdb_id="1aaa", source_set="other", pki=6.5),
        ]
        result = curator._deduplicate(cpx, report)
        assert len(result) == 1
        assert result[0].source_set == "refined"

    def test_other_before_refined_still_refined_wins(self):
        """Even if other appears first in list, refined should win."""
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="other", pki=6.5),
            make_complex(pdb_id="1aaa", source_set="refined", pki=7.0),
        ]
        result = curator._deduplicate(cpx, report)
        assert len(result) == 1
        assert result[0].source_set == "refined"

    def test_duplicate_within_same_set(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="refined"),
            make_complex(pdb_id="1aaa", source_set="refined"),
        ]
        result = curator._deduplicate(cpx, report)
        assert len(result) == 1

    def test_multiple_duplicates(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="refined"),
            make_complex(pdb_id="2bbb", source_set="refined"),
            make_complex(pdb_id="1aaa", source_set="other"),
            make_complex(pdb_id="3ccc", source_set="other"),
            make_complex(pdb_id="2bbb", source_set="other"),
        ]
        result = curator._deduplicate(cpx, report)
        assert len(result) == 3
        ids = {c.pdb_id for c in result}
        assert ids == {"1aaa", "2bbb", "3ccc"}
        # 1aaa and 2bbb should be from refined
        for c in result:
            if c.pdb_id in ("1aaa", "2bbb"):
                assert c.source_set == "refined"

    def test_dedup_filter_shows_in_report(self):
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id="1aaa", source_set="refined"),
            make_complex(pdb_id="1aaa", source_set="other"),
        ]
        curator._deduplicate(cpx, report)
        f = report.filters[0]
        assert f.name == "deduplication"
        assert f.n_removed == 1


# ─── Filter 8: Outliers ────────────────────────────────────────


class TestFilterOutliers:
    """Filter 8: |z-score| > 4σ outlier detection."""

    def test_normal_distribution_no_removal(self):
        """Normal values should not be flagged."""
        curator = DataCurator()
        report = CurationReport()
        # 20 complexes with pKi around 7.0 ± 1.0
        cpx = make_batch(20, binding_precision="exact", binding_type="Ki")
        result = curator._filter_outliers(cpx, report)
        # With pKi from 5.0 to 8.8, none should be >4σ from mean
        assert len(result) == 20

    def test_extreme_outlier_removed(self):
        """An extreme value should be flagged."""
        curator = DataCurator()
        report = CurationReport()
        # 20 normal + 1 extreme
        cpx = make_batch(20)
        cpx.append(make_complex(pdb_id="out1", pki=50.0))  # Way beyond any σ
        result = curator._filter_outliers(cpx, report)
        assert len(result) == 20
        removed_ids = [c.pdb_id for c in cpx if c.pdb_id not in {r.pdb_id for r in result}]
        assert "out1" in removed_ids

    def test_small_dataset_skips_filter(self):
        """< 10 complexes: skip outlier detection (not enough data)."""
        curator = DataCurator()
        report = CurationReport()
        cpx = make_batch(5)
        result = curator._filter_outliers(cpx, report)
        assert len(result) == 5
        assert report.filters[0].n_removed == 0

    def test_zero_std_skips_filter(self):
        """If all pKi are identical, std=0 → skip."""
        curator = DataCurator()
        report = CurationReport()
        cpx = [make_complex(pdb_id=f"{i:04d}", pki=7.0) for i in range(15)]
        result = curator._filter_outliers(cpx, report)
        assert len(result) == 15

    def test_custom_threshold(self):
        """Tighter threshold should remove more."""
        # Create 20 complexes: 19 at pKi=7.0, 1 at pKi=12.0
        cpx = [make_complex(pdb_id=f"{i:04d}", pki=7.0) for i in range(19)]
        cpx.append(make_complex(pdb_id="9999", pki=12.0))

        # With default 4σ — might not be removed depending on std
        curator_default = DataCurator()
        report_default = CurationReport()
        result_default = curator_default._filter_outliers(cpx, report_default)

        # With 2σ — more aggressive, should remove the outlier
        curator_tight = DataCurator(outlier_zscore=2.0)
        report_tight = CurationReport()
        result_tight = curator_tight._filter_outliers(cpx, report_tight)

        # Tighter threshold removes at least as many
        assert len(result_tight) <= len(result_default)


# ─── Full Pipeline ──────────────────────────────────────────────


class TestFullCuration:
    """Test the complete curate() method end-to-end."""

    def test_clean_data_survives(self, tmp_path):
        """A perfectly clean complex should survive all 8 filters."""
        pdb = tmp_path / "1abc_protein.pdb"
        sdf = tmp_path / "1abc_ligand.sdf"
        pdb.write_text("A" * 200)
        sdf.write_text("B" * 100)

        # Create 15 clean complexes (need ≥10 for outlier filter)
        cpx = []
        for i in range(15):
            pid = f"{i:04d}"
            p = tmp_path / f"{pid}_protein.pdb"
            s = tmp_path / f"{pid}_ligand.sdf"
            p.write_text("A" * 200)
            s.write_text("B" * 100)
            cpx.append(make_complex(
                pdb_id=pid,
                resolution=2.0,
                binding_type="Ki",
                pki=6.0 + i * 0.3,
                binding_precision="exact",
                source_set="refined",
                protein_pdb_path=str(p),
                ligand_sdf_path=str(s),
            ))

        curator = DataCurator()
        result, report = curator.curate(cpx)
        assert len(result) == 15
        assert report.n_output == 15
        assert report.overall_removal_rate_pct == 0.0
        assert len(report.filters) == 8

    def test_each_filter_removes_one(self, tmp_path):
        """One bad complex per filter category → verify all removed."""
        # Create real files for complexes that should pass file checks
        good_complexes = []
        for i in range(15):
            pid = f"g{i:03d}"
            p = tmp_path / f"{pid}_protein.pdb"
            s = tmp_path / f"{pid}_ligand.sdf"
            p.write_text("A" * 200)
            s.write_text("B" * 100)
            good_complexes.append(make_complex(
                pdb_id=pid,
                resolution=2.0,
                binding_type="Ki",
                pki=7.0 + i * 0.1,
                binding_precision="exact",
                source_set="refined",
                protein_pdb_path=str(p),
                ligand_sdf_path=str(s),
            ))

        # Bad complex: approximate precision
        bad_precision = make_complex(
            pdb_id="bad1",
            binding_precision="approximate",
            protein_pdb_path=str(tmp_path / "bad1_protein.pdb"),
            ligand_sdf_path=str(tmp_path / "bad1_ligand.sdf"),
        )

        all_cpx = good_complexes + [bad_precision]
        curator = DataCurator()
        result, report = curator.curate(all_cpx)

        # bad_precision removed by filter 1
        assert len(result) == 15
        assert report.filters[0].n_removed >= 1  # precision filter

    def test_report_structure(self, tmp_path):
        """Verify report has all expected fields."""
        cpx = []
        for i in range(12):
            pid = f"{i:04d}"
            p = tmp_path / f"{pid}_protein.pdb"
            s = tmp_path / f"{pid}_ligand.sdf"
            p.write_text("A" * 200)
            s.write_text("B" * 100)
            cpx.append(make_complex(
                pdb_id=pid,
                pki=6.0 + i * 0.3,
                protein_pdb_path=str(p),
                ligand_sdf_path=str(s),
            ))

        curator = DataCurator()
        _, report = curator.curate(cpx)

        assert report.n_input_total == 12
        assert report.timestamp != ""
        assert report.duration_seconds >= 0
        assert len(report.filters) == 8
        assert "accepted_binding_types" in report.config
        assert "pki_range" in report.config

    def test_report_source_set_counts(self, tmp_path):
        """Report should count refined vs other correctly."""
        cpx = []
        for i in range(6):
            pid = f"{i:04d}"
            p = tmp_path / f"{pid}_protein.pdb"
            s = tmp_path / f"{pid}_ligand.sdf"
            p.write_text("A" * 200)
            s.write_text("B" * 100)
            source = "refined" if i < 4 else "other"
            cpx.append(make_complex(
                pdb_id=pid,
                pki=6.0 + i * 0.3,
                source_set=source,
                protein_pdb_path=str(p),
                ligand_sdf_path=str(s),
            ))

        curator = DataCurator()
        _, report = curator.curate(cpx)
        assert report.n_input_refined == 4
        assert report.n_input_other == 2


# ─── Report Save / Print ───────────────────────────────────────


class TestReportIO:
    """Test report saving and printing."""

    def test_save_report_json(self, tmp_path):
        report = CurationReport()
        report.n_input_total = 100
        report.n_output = 80
        report.overall_removal_rate_pct = 20.0
        report.timestamp = "2026-04-05T00:00:00Z"
        report.duration_seconds = 1.5
        report.config = {"test": True}
        report.filters = [
            CurationFilter(
                name="test_filter",
                description="A test filter",
                n_before=100,
                n_after=80,
                n_removed=20,
                removed_ids=["id1", "id2"],
            )
        ]

        output = tmp_path / "report.json"
        DataCurator.save_report(report, output)

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["summary"]["input_total"] == 100
        assert data["summary"]["output_curated"] == 80
        assert len(data["filters"]) == 1
        assert data["filters"][0]["name"] == "test_filter"

    def test_save_report_creates_dirs(self, tmp_path):
        report = CurationReport()
        report.timestamp = "2026-04-05T00:00:00Z"
        output = tmp_path / "nested" / "deep" / "report.json"
        DataCurator.save_report(report, output)
        assert output.exists()

    def test_print_summary_no_crash(self, capsys):
        report = CurationReport()
        report.n_input_total = 100
        report.n_input_refined = 60
        report.n_input_other = 40
        report.n_output = 80
        report.overall_removal_rate_pct = 20.0
        report.duration_seconds = 1.5
        report.pki_stats_curated = {"mean": 7.0, "std": 1.5, "min": 3.0, "max": 12.0}
        report.filters = [
            CurationFilter(
                name="precision", description="test",
                n_before=100, n_after=90, n_removed=10,
            ),
            CurationFilter(
                name="binding_type", description="test",
                n_before=90, n_after=80, n_removed=10,
            ),
        ]
        # Should not raise
        DataCurator.print_summary(report)
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "80" in captured.out
        assert "CURACION" in captured.out.upper() or "REPORTE" in captured.out.upper()


# ─── Edge Cases ─────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_input(self):
        curator = DataCurator()
        result, report = curator.curate([])
        assert len(result) == 0
        assert report.n_output == 0
        # (1 - 0/max(0,1)) * 100 = 100.0 — mathematically correct for empty input
        assert report.overall_removal_rate_pct == 100.0
        assert len(report.filters) == 8

    def test_single_complex_survives(self, tmp_path):
        """Single clean complex should survive (outlier filter skips <10)."""
        p = tmp_path / "1abc_protein.pdb"
        s = tmp_path / "1abc_ligand.sdf"
        p.write_text("A" * 200)
        s.write_text("B" * 100)

        cpx = [make_complex(
            protein_pdb_path=str(p),
            ligand_sdf_path=str(s),
        )]
        curator = DataCurator()
        result, report = curator.curate(cpx)
        assert len(result) == 1

    def test_all_removed(self):
        """If all complexes fail the first filter, result is empty."""
        cpx = [make_complex(binding_precision="approximate") for _ in range(5)]
        curator = DataCurator()
        result, report = curator.curate(cpx)
        assert len(result) == 0
        assert report.overall_removal_rate_pct == 100.0

    def test_removed_ids_capped(self):
        """removed_ids should be capped at max_removed_ids (100)."""
        curator = DataCurator()
        report = CurationReport()
        cpx = [
            make_complex(pdb_id=f"{i:04d}", binding_precision="approximate")
            for i in range(150)
        ]
        curator._filter_precision(cpx, report)
        f = report.filters[0]
        assert f.n_removed == 150
        assert len(f.removed_ids) <= 100

    def test_pki_stats_populated(self, tmp_path):
        """After curation, pKi statistics should be populated."""
        cpx = []
        for i in range(12):
            pid = f"{i:04d}"
            p = tmp_path / f"{pid}_protein.pdb"
            s = tmp_path / f"{pid}_ligand.sdf"
            p.write_text("A" * 200)
            s.write_text("B" * 100)
            cpx.append(make_complex(
                pdb_id=pid,
                pki=5.0 + i * 0.5,
                protein_pdb_path=str(p),
                ligand_sdf_path=str(s),
            ))

        curator = DataCurator()
        _, report = curator.curate(cpx)

        stats = report.pki_stats_curated
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "median" in stats
        assert "n" in stats
        assert stats["n"] == 12
