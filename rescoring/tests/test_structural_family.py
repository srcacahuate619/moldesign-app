"""
tests/test_structural_family.py

Tests para la clasificación de familias estructurales.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structural_family import (
    CURATED_FAMILIES,
    FAMILIES,
    FAMILY_PATTERNS,
    FamilyClassification,
    StructuralFamilyClassifier,
)


class TestCuratedLookup:
    """Tests para lookup en tabla curada."""

    def test_7e2y_is_gpcr(self):
        """7E2Y (5-HT1A) clasifica como GPCR."""
        c = StructuralFamilyClassifier()
        result = c.classify("7e2y")
        assert result.family == "gpcr"
        assert result.confidence == "curated"

    def test_7e2y_case_insensitive(self):
        """PDB ID es case-insensitive."""
        c = StructuralFamilyClassifier()
        result = c.classify("7E2Y")
        assert result.family == "gpcr"

    def test_curated_kinase(self):
        """Kinasa curada se clasifica correctamente."""
        c = StructuralFamilyClassifier()
        result = c.classify("1oiu")
        assert result.family == "kinase"
        assert result.confidence == "curated"

    def test_curated_protease(self):
        """Proteasa curada se clasifica correctamente."""
        c = StructuralFamilyClassifier()
        result = c.classify("1hpv")
        assert result.family == "protease"

    def test_curated_nuclear_receptor(self):
        """Receptor nuclear curado se clasifica correctamente."""
        c = StructuralFamilyClassifier()
        result = c.classify("1err")
        assert result.family == "nuclear_receptor"

    def test_additional_curated(self):
        """Tabla curada adicional funciona."""
        c = StructuralFamilyClassifier(additional_curated={"xxxx": "gpcr"})
        result = c.classify("xxxx")
        assert result.family == "gpcr"
        assert result.confidence == "curated"


class TestHeaderClassification:
    """Tests para clasificación por PDB header."""

    def test_kinase_header(self):
        """Header con 'kinase' → kinase."""
        c = StructuralFamilyClassifier()
        result = c.classify("9xyz", "TYROSINE-PROTEIN KINASE ABL")
        assert result.family == "kinase"
        assert result.confidence == "high"

    def test_protease_header(self):
        """Header con 'protease' → protease."""
        c = StructuralFamilyClassifier()
        result = c.classify("9abc", "HIV-1 PROTEASE COMPLEX")
        assert result.family == "protease"

    def test_gpcr_header(self):
        """Header con '5-HT' receptor → GPCR."""
        c = StructuralFamilyClassifier()
        result = c.classify("9def", "5-HT2A SEROTONIN RECEPTOR")
        assert result.family == "gpcr"

    def test_nuclear_receptor_header(self):
        """Header con 'estrogen receptor' → nuclear_receptor."""
        c = StructuralFamilyClassifier()
        result = c.classify("9ghi", "ESTROGEN RECEPTOR ALPHA")
        assert result.family == "nuclear_receptor"

    def test_dehydrogenase_header(self):
        """Header con 'dehydrogenase' → soluble_enzyme."""
        c = StructuralFamilyClassifier()
        result = c.classify("9jkl", "LACTATE DEHYDROGENASE")
        assert result.family == "soluble_enzyme"

    def test_unknown_header(self):
        """Header sin keywords conocidos → other."""
        c = StructuralFamilyClassifier()
        result = c.classify("9xyz", "SOME UNKNOWN PROTEIN COMPLEX")
        assert result.family == "other"
        assert result.confidence == "unclassified"

    def test_empty_header_unknown_id(self):
        """Sin header ni curación → other."""
        c = StructuralFamilyClassifier()
        result = c.classify("9zzz")
        assert result.family == "other"


class TestClassifyAll:
    """Tests para clasificación masiva."""

    def test_classify_all(self):
        """Clasificar múltiples complejos."""
        c = StructuralFamilyClassifier()
        complexes = [
            MagicMock(pdb_id="7e2y", protein_pdb_path=None),
            MagicMock(pdb_id="1oiu", protein_pdb_path=None),
            MagicMock(pdb_id="9xyz", protein_pdb_path=None),
        ]
        results = c.classify_all(complexes)
        assert len(results) == 3
        assert results["7e2y"].family == "gpcr"
        assert results["1oiu"].family == "kinase"
        assert results["9xyz"].family == "other"


class TestFamilySummary:
    """Tests para resumen estadístico."""

    def test_summary_counts(self):
        """Summary tiene conteos correctos."""
        c = StructuralFamilyClassifier()
        classifications = {
            "a": FamilyClassification(pdb_id="a", family="gpcr", confidence="curated"),
            "b": FamilyClassification(pdb_id="b", family="gpcr", confidence="curated"),
            "c": FamilyClassification(pdb_id="c", family="kinase", confidence="high"),
            "d": FamilyClassification(pdb_id="d", family="other", confidence="unclassified"),
        }
        summary = c.get_family_summary(classifications)
        assert summary["total"] == 4
        assert summary["by_family"]["gpcr"]["count"] == 2
        assert summary["by_family"]["kinase"]["count"] == 1
        assert summary["by_family"]["other"]["count"] == 1

    def test_summary_percentages(self):
        """Summary calcula porcentajes."""
        c = StructuralFamilyClassifier()
        classifications = {
            "a": FamilyClassification(pdb_id="a", family="kinase", confidence="curated"),
            "b": FamilyClassification(pdb_id="b", family="kinase", confidence="curated"),
        }
        summary = c.get_family_summary(classifications)
        assert summary["by_family"]["kinase"]["pct"] == 100.0


class TestConstants:
    """Tests para constantes."""

    def test_families_defined(self):
        """Todas las familias están definidas."""
        assert "gpcr" in FAMILIES
        assert "kinase" in FAMILIES
        assert "protease" in FAMILIES
        assert "nuclear_receptor" in FAMILIES
        assert "soluble_enzyme" in FAMILIES
        assert "other" in FAMILIES

    def test_patterns_cover_main_families(self):
        """Patterns cubren las 5 familias clasificables."""
        for fam in ["gpcr", "kinase", "protease", "nuclear_receptor", "soluble_enzyme"]:
            assert fam in FAMILY_PATTERNS
            assert len(FAMILY_PATTERNS[fam]) > 0

    def test_curated_has_target(self):
        """La tabla fuente conserva el PDB ID canónico en mayúsculas."""
        assert "7E2Y" in CURATED_FAMILIES
