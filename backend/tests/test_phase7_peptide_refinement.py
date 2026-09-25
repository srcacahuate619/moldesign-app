"""PHYS-012: una pose sin refinamiento no puede presentarse como refinada."""
import pytest


def test_legacy_refinement_abstains_instead_of_returning_input():
    from utils.refinement import refine_receptor_peptide_complex

    with pytest.raises(RuntimeError, match="PEPTIDE_REFINEMENT_NO_VALIDADO"):
        refine_receptor_peptide_complex("RECEPTOR", "PEPTIDE")
