"""
tests/test_pdbbind_parser.py

Tests para el parser de PDBbind.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdbbind_parser import (
    UNIT_TO_NM,
    PDBBindComplex,
    PDBBindParser,
    parse_binding_string,
)


class TestParseBindingString:
    """Tests para parsing de strings de binding affinity."""

    def test_parse_kd_nm(self):
        """Parsear Kd en nanomolar."""
        btype, value_nm, pki, precision = parse_binding_string("Kd=1.5nM")
        assert btype == "Kd"
        assert abs(value_nm - 1.5) < 0.01
        assert pki > 8  # -log10(1.5e-9) ≈ 8.82
        assert precision == "exact"

    def test_parse_ki_um(self):
        """Parsear Ki en micromolar."""
        btype, value_nm, pki, precision = parse_binding_string("Ki=340uM")
        assert btype == "Ki"
        assert abs(value_nm - 340_000) < 1
        assert pki < 4  # -log10(340e-6) ≈ 3.47
        assert precision == "exact"

    def test_parse_kd_mm(self):
        """Parsear Kd en milimolar."""
        btype, value_nm, pki, precision = parse_binding_string("Kd=0.3mM")
        assert btype == "Kd"
        assert abs(value_nm - 300_000) < 1
        assert precision == "exact"

    def test_parse_ki_pm(self):
        """Parsear Ki en picomolar (alta afinidad)."""
        btype, value_nm, pki, precision = parse_binding_string("Ki=50pM")
        assert btype == "Ki"
        assert abs(value_nm - 0.05) < 0.001
        assert pki > 10  # -log10(50e-12) ≈ 10.3
        assert precision == "exact"

    def test_parse_ic50(self):
        """Parsear IC50 (debe ser reconocido aunque luego la auditoría lo rechace)."""
        btype, value_nm, pki, precision = parse_binding_string("IC50=100nM")
        assert btype == "IC50"
        assert abs(value_nm - 100) < 0.1
        assert precision == "exact"

    def test_parse_tilde_is_approximate(self):
        """Parsear con ~ marca como approximate, NO exact."""
        btype, value_nm, pki, precision = parse_binding_string("Kd~5.6nM")
        assert btype == "Kd"
        assert abs(value_nm - 5.6) < 0.01
        assert precision == "approximate"

    def test_parse_greater_than_is_lower_bound(self):
        """Parsear con > marca como lower_bound."""
        btype, value_nm, pki, precision = parse_binding_string("Ki>100nM")
        assert btype == "Ki"
        assert precision == "lower_bound"

    def test_parse_less_than_is_upper_bound(self):
        """Parsear con < marca como upper_bound."""
        btype, value_nm, pki, precision = parse_binding_string("Kd<1nM")
        assert btype == "Kd"
        assert precision == "upper_bound"

    def test_parse_invalid(self):
        """String no parseable lanza ValueError."""
        with pytest.raises(ValueError, match="No se pudo parsear"):
            parse_binding_string("random text")

    def test_parse_empty(self):
        """String vacío lanza ValueError."""
        with pytest.raises(ValueError):
            parse_binding_string("")

    def test_pki_relationship(self):
        """pKi más alto = mayor afinidad (menor Kd)."""
        _, _, pki_high, _ = parse_binding_string("Kd=1nM")
        _, _, pki_low, _ = parse_binding_string("Kd=1000nM")
        assert pki_high > pki_low

    def test_unit_conversion_consistency(self):
        """1 uM = 1000 nM."""
        _, val_nm, _, _ = parse_binding_string("Kd=1uM")
        assert abs(val_nm - 1000) < 0.1

        _, val_nm2, _, _ = parse_binding_string("Kd=1000nM")
        assert abs(val_nm2 - 1000) < 0.1


class TestPDBBindComplex:
    """Tests para el dataclass PDBBindComplex."""

    def test_basic_creation(self):
        """Crear un complejo con datos mínimos."""
        cpx = PDBBindComplex(
            pdb_id="7e2y",
            resolution=2.0,
            release_year=2021,
            binding_data_raw="Kd=5nM",
            binding_type="Kd",
            binding_value_nm=5.0,
            pki=8.3,
            ligand_smiles="c1ccccc1",
        )
        assert cpx.pdb_id == "7e2y"
        assert cpx.resolution == 2.0
        assert cpx.audit_passed is False  # Default
        assert cpx.audit_failures == []

    def test_audit_fields_default(self):
        """Campos de auditoría tienen valores por defecto correctos."""
        cpx = PDBBindComplex(
            pdb_id="test",
            resolution=1.5,
            release_year=2020,
            binding_data_raw="Ki=10nM",
            binding_type="Ki",
            binding_value_nm=10.0,
            pki=8.0,
            ligand_smiles="CC",
        )
        assert cpx.n_heavy_atoms == 0
        assert cpx.molecular_weight == 0.0
        assert cpx.protein_pdb_path is None


class TestPDBBindParser:
    """Tests para el parser."""

    def test_parser_init_no_args(self):
        """Crear parser sin directorio."""
        p = PDBBindParser()
        assert p.n_complexes == 0

    def test_parser_not_loaded(self):
        """Acceder a complexes sin load() lanza RuntimeError."""
        p = PDBBindParser()
        with pytest.raises(RuntimeError, match="no cargados"):
            _ = p.complexes

    def test_parser_with_nonexistent_dir(self):
        """Directorio inexistente → load retorna 0."""
        p = PDBBindParser("/nonexistent/path/pdbbind")
        n = p.load()
        assert n == 0

    def test_summary_empty(self):
        """Summary de parser vacío."""
        p = PDBBindParser()
        p._loaded = True
        summary = p.summary()
        assert summary["n_complexes"] == 0

    def test_get_by_nonexistent_id(self):
        """Buscar PDB ID que no existe retorna None."""
        p = PDBBindParser()
        p._loaded = True
        assert p.get_by_pdb_id("xxxx") is None


class TestUnitConversions:
    """Tests para factores de conversión."""

    def test_all_units_present(self):
        """Todos los factores de conversión están definidos."""
        expected = {"fm", "pm", "nm", "um", "mm", "m"}
        assert set(UNIT_TO_NM.keys()) == expected

    def test_nm_is_identity(self):
        """nM → nM factor es 1."""
        assert UNIT_TO_NM["nm"] == 1.0

    def test_um_to_nm(self):
        """1 uM = 1000 nM."""
        assert UNIT_TO_NM["um"] == 1e3

    def test_fm_to_nm(self):
        """1 fM = 0.000001 nM."""
        assert UNIT_TO_NM["fm"] == 1e-6
