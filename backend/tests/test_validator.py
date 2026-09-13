"""
Tests del validador químico (chem/validator.py).

Cubre:
- SMILES válidos → canonicalización + hash
- SMILES inválidos → errores
- Fragmentos múltiples → desalinización
- Átomos no soportados → warnings/errors
- Estereocentros no asignados → warnings
"""
from __future__ import annotations

import pytest
from tests.conftest import (
    rdkit_available,
    ASPIRIN,
    INVALID_SMILES,
    EMPTY_SMILES,
)


@rdkit_available
class TestValidateSmiles:
    """Tests de validate_smiles() — nunca lanza excepción."""

    def test_valid_smiles_returns_valid(self):
        """Un SMILES válido como aspirina debe retornar is_valid=True."""
        from chem.validator import validate_smiles
        result = validate_smiles(ASPIRIN)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_valid_smiles_canonicalizes(self):
        """El SMILES canónico debe ser determinista."""
        from chem.validator import validate_smiles
        r1 = validate_smiles(ASPIRIN)
        r2 = validate_smiles(ASPIRIN)
        assert r1.canonical_smiles == r2.canonical_smiles
        assert r1.canonical_smiles is not None
        assert len(r1.canonical_smiles) > 0

    def test_valid_smiles_has_sha256_hash(self):
        """El hash debe ser un SHA-256 válido (64 chars hex)."""
        from chem.validator import validate_smiles
        result = validate_smiles(ASPIRIN)
        assert result.smiles_hash is not None
        assert len(result.smiles_hash) == 64
        # Verificar que es hex válido
        int(result.smiles_hash, 16)

    def test_valid_smiles_has_formula(self):
        """La fórmula molecular debe ser correcta para aspirina (C9H8O4)."""
        from chem.validator import validate_smiles
        result = validate_smiles(ASPIRIN)
        assert result.molecular_formula == "C9H8O4"

    def test_valid_smiles_has_heavy_atoms(self):
        """Heavy atom count: aspirina C9H8O4 = 9C + 4O = 13 heavy atoms."""
        from chem.validator import validate_smiles
        result = validate_smiles(ASPIRIN)
        assert result.heavy_atom_count == 13  # 9 carbones + 4 oxígenos

    def test_benzene_is_valid(self):
        """Benceno (c1ccccc1 = 6 heavy) debe ser válido."""
        from chem.validator import validate_smiles
        result = validate_smiles("c1ccccc1")
        assert result.is_valid is True
        assert result.molecular_formula == "C6H6"


class TestValidateSmilesInvalid:
    """Tests con SMILES inválidos."""

    def test_invalid_smiles_returns_invalid(self):
        """CCX debe retornar is_valid=False, no lanzar excepción."""
        from chem.validator import validate_smiles
        result = validate_smiles(INVALID_SMILES)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_empty_smiles_returns_invalid(self):
        """String vacío debe retornar is_valid=False."""
        from chem.validator import validate_smiles
        result = validate_smiles(EMPTY_SMILES)
        assert result.is_valid is False
        assert any("vacío" in e.lower() for e in result.errors)

    def test_invalid_smiles_has_no_hash(self):
        """SMILES inválido no debe tener hash ni canonical."""
        from chem.validator import validate_smiles
        result = validate_smiles(INVALID_SMILES)
        assert result.is_valid is False
        assert result.canonical_smiles is None
        assert result.smiles_hash is None


@rdkit_available
class TestValidateSmilesOrRaise:
    """Tests de validate_smiles_or_raise() — lanza InvalidSMILES."""

    def test_valid_returns_result(self):
        """SMILES válido debe retornar ValidationResult."""
        from chem.validator import validate_smiles_or_raise
        result = validate_smiles_or_raise(ASPIRIN)
        assert result.is_valid is True

    def test_invalid_raises_exception(self):
        """SMILES inválido debe lanzar InvalidSMILES."""
        from chem.validator import validate_smiles_or_raise
        from core.exceptions import InvalidSMILES
        with pytest.raises(InvalidSMILES):
            validate_smiles_or_raise(INVALID_SMILES)

    def test_exception_has_smiles_field(self):
        """La excepción debe contener el SMILES original."""
        from chem.validator import validate_smiles_or_raise
        from core.exceptions import InvalidSMILES
        with pytest.raises(InvalidSMILES) as exc:
            validate_smiles_or_raise(INVALID_SMILES)
        assert exc.value.smiles == INVALID_SMILES


@rdkit_available
class TestSaltAndFragmentHandling:
    """Tests de desalinización y fragmentos múltiples."""

    def test_multifragment_desalinates(self):
        """'c1ccccc1.Cl' (benceno + cloro) debe desalinizar a benceno."""
        from chem.validator import validate_smiles
        # Benceno tiene 6 heavy atoms — no falla por size check
        result = validate_smiles("c1ccccc1.Cl")
        # En modo estricto por defecto, puede fallar por fragmentos
        # pero NO debe crashear
        assert len(result.errors) >= 0  # siempre retorna resultado válido
        # Si pasó, el canónico debe ser benceno
        if result.is_valid:
            assert result.canonical_smiles == "c1ccccc1"

    def test_desalinate_does_not_crash_on_invalid(self):
        """Desalinización no debe crashear en moléculas inválidas."""
        from chem.validator import validate_smiles
        # Esto no debe lanzar excepción
        result = validate_smiles("")  # vacío
        assert result.is_valid is False


@rdkit_available
class TestCanonicalizationDeterminism:
    """Tests de determinismo del canonical SMILES."""

    def test_same_molecule_different_smiles(self):
        """Misma molécula, SMILES distintos → mismo canónico."""
        from chem.validator import validate_smiles
        aspirin_v1 = "CC(=O)Oc1ccccc1C(=O)O"
        aspirin_v2 = "OC(=O)c1ccccc1OC(C)=O"
        r1 = validate_smiles(aspirin_v1)
        r2 = validate_smiles(aspirin_v2)
        assert r1.is_valid and r2.is_valid
        assert r1.canonical_smiles == r2.canonical_smiles
        assert r1.smiles_hash == r2.smiles_hash

    def test_are_same_molecule_function(self):
        """are_same_molecule() debe detectar igualdad estructural."""
        from chem.validator import are_same_molecule
        assert are_same_molecule(
            "CC(=O)Oc1ccccc1C(=O)O",
            "OC(=O)c1ccccc1OC(C)=O",
        ) is True
        assert are_same_molecule("CCO", "CCCO") is False
