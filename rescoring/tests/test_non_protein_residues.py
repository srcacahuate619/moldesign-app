"""
tests/test_non_protein_residues.py

Regression tests for Bucket A.1 - A.3 of docs/19_LIMITATIONS.md:
- ELEMENTS array expanded from 10 to 30 (boron, silicon, selenium, ...)
- AA3_TO_AA1 expanded with PTMs (SEP, TPO, PTR, CSO, PCA, PYL, ...)
- inference.py silent returns now log a WARNING + increment counter

These tests catch the silent-fallthrough regression: if any of the silent
return paths stops being logged in the future, the assertions on
``predictor.silent_failures`` and ``predictor._last_silent_reason`` will
break loudly.
"""

from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from gnn_v2.data import (
    ELEMENTS,
    ELEM_TO_IDX,
    AA3_TO_AA1,
    AMINO_ACIDS,
    AD4_TO_ELEMENT,
)


class TestElementsExpansion:
    """ELEMENTS now covers ~30 medchem-relevant elements (was 10)."""

    def test_at_least_30_elements(self):
        assert len(ELEMENTS) >= 30, (
            f"ELEMENTS was expanded to handle medical-chem elements beyond "
            f"the original 10; current count is {len(ELEMENTS)}"
        )

    def test_boron_present(self):
        assert "B" in ELEMENTS, "Boron (B) must be in ELEMENTS for Bortezomib-class proteasome inhibitors"

    def test_silicon_present(self):
        assert "Si" in ELEMENTS, "Silicon (Si) must be in ELEMENTS for organosilicon probes"

    def test_selenium_present(self):
        assert "Se" in ELEMENTS, "Selenium (Se) must be in ELEMENTS for selenocysteine proteins"

    def test_unknown_bucket_still_present(self):
        """X is the catch-all bucket for elements we don't discretize."""
        assert ELEMENTS[-1] == "X", "X must stay as last-resort unknown bucket"

    def test_ad4_to_element_maps_boron(self):
        assert AD4_TO_ELEMENT.get("B") == "B"

    def test_ad4_to_element_maps_silicon(self):
        assert AD4_TO_ELEMENT.get("Si") == "Si"


class TestAminoAcidExpansion:
    """AA3_TO_AA1 now maps PTMs to their parent AA."""

    def test_sep_map_to_serine(self):
        assert AA3_TO_AA1["SEP"] == "S", "Phosphoserine must map to S"

    def test_tpo_map_to_threonine(self):
        assert AA3_TO_AA1["TPO"] == "T", "Phosphothreonine must map to T"

    def test_ptr_map_to_tyrosine(self):
        assert AA3_TO_AA1["PTR"] == "Y", "Phosphotyrosine must map to Y"

    def test_cso_map_to_cysteine(self):
        assert AA3_TO_AA1["CSO"] == "C", "Hydroxycysteine must map to C"

    def test_pca_map_to_glutamate(self):
        assert AA3_TO_AA1["PCA"] == "E", "Pyroglutamate must map to E"

    def test_pyl_map_to_lysine(self):
        assert AA3_TO_AA1["PYL"] == "K", "Pyrrolysine must map to K"

    def test_selenomethionine_map_to_methionine(self):
        assert AA3_TO_AA1["MSE"] == "M", "Selenomethionine must map to M for MAD phasing proteins"

    def test_dna_codes_present_for_nucleotide_pocket(self):
        """DNA 3-letter codes stay so pocket manager can reach them (the
        feature embedding still falls to UNK_AA_IDX, but at least the
        residue is no longer filtered out of pocket_residues)."""
        for code in ["DA", "DT", "DG", "DC"]:
            assert code in AA3_TO_AA1, f"{code} (DNA nucleotide) must be in AA3_TO_AA1"

    def test_rna_codes_present_for_nucleotide_pocket(self):
        for code in ["RA", "RT", "RG", "RC", "RU"]:
            assert code in AA3_TO_AA1, f"{code} (RNA nucleotide) must be in AA3_TO_AA1"


class TestGNNInferenceSilentReturns:
    """Bucket A.3 - inference.py must log warnings + count silent returns."""

    def test_silent_failures_counter_init(self):
        """GNNv2Predictor MUST carry silent_failures state in __init__."""
        from gnn_v2.inference import GNNv2Predictor
        # Inspect the class signature source rather than instantiating
        # (which loads ~50MB checkpoint and may not be CUDA-friendly)
        import inspect
        src = inspect.getsource(GNNv2Predictor.__init__)
        assert "silent_failures" in src, (
            "GNNv2Predictor.__init__ must initialize self.silent_failures "
            "this is the audit hook added in Bucket A.3"
        )

    def test_silent_failure_marker_exists(self):
        from gnn_v2 import inference
        assert hasattr(inference, "_SilentFailure"), (
            "_SilentFailure exception class must exist for known silent paths"
        )

    def test_record_silent_method_exists(self):
        from gnn_v2.inference import GNNv2Predictor
        assert hasattr(GNNv2Predictor, "_record_silent"), (
            "_record_silent(reason, smiles) must exist to log+count silent returns"
        )

    def test_reset_silent_failures_method_exists(self):
        from gnn_v2.inference import GNNv2Predictor
        assert hasattr(GNNv2Predictor, "reset_silent_failures"), (
            "reset_silent_failures() must exist for per-dataset scope"
        )

    def test_predict_returns_05_on_invalid_smiles(self):
        """End-to-end smoke: invalid SMILES triggers silent fallback path.
        Skipped if there is no model artifact available (e.g. CI without .pth).
        """
        import pytest

        # La guarda existia, pero apuntaba a una ruta absoluta de la maquina del
        # mantenedor: alli siempre existia, asi que nunca saltaba, y el
        # predictor cargaba desde el directorio del repositorio -sin el peso- y
        # moria con FileNotFoundError. Se resuelve contra el repositorio.
        from pesos_ausentes import motivo, pesos_ausentes, se_exigen_pesos

        artefactos = Path(__file__).resolve().parent.parent / "artifacts"
        faltan = pesos_ausentes(artefactos, ["gnn_v3_best.pt"])
        if faltan and not se_exigen_pesos():
            pytest.skip(motivo(faltan, "smoke e2e de fallo silencioso"))

        from gnn_v2.inference import GNNv2Predictor
        p = GNNv2Predictor(device="cpu")
        p.reset_silent_failures()
        # missing pdbqt forces _predict_from_files to raise FileNotFoundError,
        # caught by predict() outer wrapper -> _record_silent("exception_FileNotFoundError").
        fd, pdbqt = tempfile.mkstemp(suffix=".pdbqt")
        os.close(fd)
        os.unlink(pdbqt)
        raiz = Path(__file__).resolve().parent.parent.parent
        prob, std = p.predict(
            "CINVINTMOHNNFI-UHFFFAOYSA-N",  # garbage SMILES
            pdbqt,
            str(raiz / "data" / "3PP0.pdb"),  # era otra ruta absoluta al disco D:
        )
        assert np.isnan(prob), "silent fallback must expose an absent prediction"
        assert np.isnan(std), "silent fallback must expose an absent uncertainty"
        assert p.silent_failures == 1, f"sentinel counter must increment; got {p.silent_failures}"
        assert p._last_silent_reason is not None
