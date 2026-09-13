"""
tests/test_vip_audit.py

Tests para la auditoría VIP de complejos PDBbind.

Nota: Los tests de Check 1 (ligando) requieren RDKit para validar la lógica
de parsing, elementos y MW. En entornos sin RDKit (e.g. Python 3.14 local)
se saltan y en su lugar se ejecutan tests del fallback.
El entorno de producción (Docker Python 3.12) SÍ tiene RDKit instalado.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vip_audit import (
    ACCEPTED_BINDING_TYPES,
    ALLOWED_ELEMENTS,
    MAX_RESOLUTION_A,
    AuditReport,
    AuditResult,
    VIPAuditor,
    get_vip_complexes,
)

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


def _make_complex(
    pdb_id: str = "test",
    resolution: float = 2.0,
    binding_type: str = "Kd",
    ligand_smiles: str = "c1ccccc1",
    pki: float = 7.0,
    protein_pdb_path: str | None = None,
    ligand_sdf_path: str | None = None,
) -> MagicMock:
    """Helper para crear un mock PDBBindComplex."""
    cpx = MagicMock()
    cpx.pdb_id = pdb_id
    cpx.resolution = resolution
    cpx.binding_type = binding_type
    cpx.ligand_smiles = ligand_smiles
    cpx.pki = pki
    cpx.protein_pdb_path = protein_pdb_path
    cpx.ligand_sdf_path = ligand_sdf_path
    cpx.molecular_weight = 0.0
    cpx.n_heavy_atoms = 0
    cpx.audit_passed = False
    cpx.audit_failures = []
    return cpx


class TestVIPAuditorCheckLigand:
    """Tests para Check 1: Ligando válido (requiere RDKit)."""

    @requires_rdkit
    def test_valid_smiles(self):
        """SMILES válido pasa Check 1."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="c1ccccc1")  # benceno
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is True

    @requires_rdkit
    def test_empty_smiles_no_sdf(self):
        """Sin SMILES ni SDF → falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="", ligand_sdf_path=None)
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is False
        assert any("SMILES" in f or "No SMILES" in f for f in result.failures)

    @requires_rdkit
    def test_invalid_smiles(self):
        """SMILES no parseable → falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="INVALID_XYZ")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is False

    @requires_rdkit
    def test_exotic_atoms(self):
        """Molécula con átomos exóticos (Fe) → falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="[Fe]")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is False
        assert any("exótic" in f.lower() or "átomo" in f.lower() for f in result.failures)

    @requires_rdkit
    def test_very_high_mw(self):
        """MW > 1000 → falla (posible péptido)."""
        auditor = VIPAuditor(skip_structure_checks=True)
        # Un polímero largo con MW > 1000
        cpx = _make_complex(ligand_smiles="C" * 100)  # cadena muy larga
        result = auditor.audit_complex(cpx)
        # Para SMILES "CCC...C" con 100 C's, MW ≈ 1402
        assert result.checks.get("ligand") is False

    @requires_rdkit
    def test_multi_fragment(self):
        """Molécula con múltiples fragmentos → falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="c1ccccc1.O")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is False
        assert any("fragment" in f.lower() for f in result.failures)

    @requires_rdkit
    def test_allowed_elements(self):
        """Molécula con solo elementos permitidos pasa."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="c1cc(F)cc(Cl)c1N")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is True


class TestVIPAuditorCheckResolution:
    """Tests para Check 2: Resolución."""

    def test_good_resolution(self):
        """Resolución de 1.5 Å pasa."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(resolution=1.5)
        result = auditor.audit_complex(cpx)
        assert result.checks.get("resolution") is True

    def test_borderline_resolution(self):
        """Resolución de exactamente 2.5 Å pasa."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(resolution=2.5)
        result = auditor.audit_complex(cpx)
        assert result.checks.get("resolution") is True

    def test_bad_resolution(self):
        """Resolución de 3.0 Å falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(resolution=3.0)
        result = auditor.audit_complex(cpx)
        assert result.checks.get("resolution") is False

    def test_zero_resolution(self):
        """Resolución 0 (no disponible) falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(resolution=0.0)
        result = auditor.audit_complex(cpx)
        assert result.checks.get("resolution") is False


class TestVIPAuditorCheckBindingType:
    """Tests para Check 4: Tipo de binding."""

    def test_kd_passes(self):
        """Kd pasa (constante termodinámica)."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(binding_type="Kd")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("binding_type") is True

    def test_ki_passes(self):
        """Ki pasa (constante termodinámica)."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(binding_type="Ki")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("binding_type") is True

    def test_ic50_fails(self):
        """IC50 falla (depende del ensayo, no es comparable)."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(binding_type="IC50")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("binding_type") is False

    def test_unknown_binding_fails(self):
        """Tipo desconocido falla."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(binding_type="unknown")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("binding_type") is False


class TestVIPAuditorOverall:
    """Tests para auditoría integral."""

    @requires_rdkit
    def test_all_checks_pass(self):
        """Complejo válido pasa todos los checks."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(
            pdb_id="1abc",
            resolution=1.8,
            binding_type="Ki",
            ligand_smiles="c1ccc(NC(=O)c2ccccc2)cc1",  # drug-like
            pki=7.5,
        )
        result = auditor.audit_complex(cpx)
        assert result.passed is True
        assert len(result.failures) == 0

    @requires_rdkit
    def test_multiple_failures(self):
        """Complejo con múltiples problemas reporta todos."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(
            resolution=4.0,
            binding_type="IC50",
            ligand_smiles="[Fe]",  # átomo exótico
        )
        result = auditor.audit_complex(cpx)
        assert result.passed is False
        assert len(result.failures) >= 2  # Al menos ligando + resolución

    @requires_rdkit
    def test_audit_all(self):
        """audit_all procesa múltiples complejos."""
        auditor = VIPAuditor(skip_structure_checks=True)
        complexes = [
            _make_complex(pdb_id="good1", resolution=1.5, binding_type="Ki"),
            _make_complex(pdb_id="good2", resolution=2.0, binding_type="Kd"),
            _make_complex(pdb_id="bad1", resolution=4.0, binding_type="Ki"),
        ]
        report = auditor.audit_all(complexes)
        assert report.total_evaluated == 3
        assert report.total_accepted == 2
        assert report.total_rejected == 1

    @requires_rdkit
    def test_get_vip_complexes(self):
        """get_vip_complexes retorna solo aprobados."""
        auditor = VIPAuditor(skip_structure_checks=True)
        complexes = [
            _make_complex(pdb_id="pass1", resolution=1.5, binding_type="Ki"),
            _make_complex(pdb_id="fail1", resolution=4.0, binding_type="Ki"),
            _make_complex(pdb_id="pass2", resolution=2.0, binding_type="Kd"),
        ]
        report = auditor.audit_all(complexes)
        vip = get_vip_complexes(report)
        assert "pass1" in vip
        assert "pass2" in vip
        assert "fail1" not in vip


class TestVIPAuditorSaveReport:
    """Tests para guardar reporte."""

    def test_save_report(self, tmp_path):
        """Guardar y leer reporte JSON."""
        report = AuditReport()
        report.total_evaluated = 100
        report.total_accepted = 80
        report.total_rejected = 20
        report.timestamp = "2026-04-05T00:00:00Z"
        report.results = [
            AuditResult(pdb_id="test1", passed=True, checks={"ligand": True}),
            AuditResult(pdb_id="test2", passed=False, checks={"ligand": False}, failures=["bad"]),
        ]

        out = tmp_path / "audit_report.json"
        VIPAuditor.save_report(report, out)

        assert out.exists()
        data = json.loads(out.read_text())
        assert data["summary"]["total_evaluated"] == 100
        assert data["summary"]["total_accepted"] == 80
        assert len(data["individual_results"]) == 2


class TestConstants:
    """Tests para constantes."""

    def test_allowed_elements_are_organic(self):
        """Solo elementos orgánicos comunes."""
        assert "C" in ALLOWED_ELEMENTS
        assert "Fe" not in ALLOWED_ELEMENTS
        assert "Pt" not in ALLOWED_ELEMENTS

    def test_accepted_binding_types(self):
        """Solo Ki y Kd aceptados."""
        assert ACCEPTED_BINDING_TYPES == {"Ki", "Kd"}

    def test_max_resolution(self):
        """Resolución máxima es 2.5 Å."""
        assert MAX_RESOLUTION_A == 2.5


class TestVIPAuditorNoRDKit:
    """Tests para el camino de degradación cuando RDKit no está disponible."""

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_ligand_check_reports_rdkit_unavailable(self):
        """Sin RDKit, Check 1 falla explícitamente con mensaje claro."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx = _make_complex(ligand_smiles="c1ccccc1")
        result = auditor.audit_complex(cpx)
        assert result.checks.get("ligand") is False
        assert any("RDKit" in f for f in result.failures)

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_audit_all_rejects_everything_without_rdkit(self):
        """Sin RDKit, ningún complejo pasa la auditoría."""
        auditor = VIPAuditor(skip_structure_checks=True)
        complexes = [
            _make_complex(pdb_id="c1", resolution=1.5, binding_type="Ki"),
            _make_complex(pdb_id="c2", resolution=2.0, binding_type="Kd"),
        ]
        report = auditor.audit_all(complexes)
        assert report.total_accepted == 0
        assert report.total_rejected == 2

    @pytest.mark.skipif(HAS_RDKIT, reason="Solo verifica fallback sin RDKit")
    def test_non_ligand_checks_still_work_without_rdkit(self):
        """Sin RDKit, los checks 2-4 siguen funcionando correctamente."""
        auditor = VIPAuditor(skip_structure_checks=True)
        cpx_good = _make_complex(resolution=1.5, binding_type="Ki")
        cpx_bad = _make_complex(resolution=4.0, binding_type="IC50")

        r_good = auditor.audit_complex(cpx_good)
        r_bad = auditor.audit_complex(cpx_bad)

        assert r_good.checks.get("resolution") is True
        assert r_good.checks.get("binding_type") is True
        assert r_bad.checks.get("resolution") is False
        assert r_bad.checks.get("binding_type") is False
