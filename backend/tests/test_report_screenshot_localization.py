"""Regressions from the English MolDex/report screenshots (2026-10-06)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.i18n import localize_payload, reset_request_locale, set_request_locale
from core.i18n_plantillas import traducir
from services.docking.ligand_state_warnings import avisos_estado_ligando
from services.targets.context_localization import physiological_description
from tests.test_pdf_i18n_layer3 import _capturar_pdf
from utils.scientific import audit_scientific_quality

ROOT = Path(__file__).resolve().parents[2]


def screenshot_warnings():
    return audit_scientific_quality(-6.08, 13, 1.4, [], [], [], "ro3", True) + avisos_estado_ligando({
        "cambio_respecto_a_la_entrada": True,
        "smiles_entrada": "CC(=O)Oc1ccccc1C(=O)O",
        "smiles_acoplado": "CC(=O)Oc1ccccc1C(=O)[O-]",
    })


def configure_screenshot(target, result):
    row = next(r for r in json.loads((ROOT / "curated_targets.json").read_text(encoding="utf-8"))
               if r["pdb_id"] == "1J38")
    target.pdb_id, target.chain, target.description = "1J38", "A", row["description"]
    result.scientific_warnings = screenshot_warnings()
    result.shap_values = {"vina_best_score": 1.67, "shell_o_n_4_8": -0.47}
    result.shap_model_id = "d" * 64
    result.shap_output = "delta_pKi"
    result.total_score = 34.98
    result.affinity_score = 52.13
    result.clgnn_score = 0.069
    result.xgb_score = 0.098
    result.target_family = "protease"


def test_moldex_localizes_both_warning_shapes_without_changing_smiles():
    warnings = screenshot_warnings()
    token = set_request_locale("en")
    try:
        result = localize_payload({"scientific_warnings": warnings})["scientific_warnings"]
    finally:
        reset_request_locale(token)
    assert result[0].startswith("Ligand efficiency LE=0.47. With 13 heavy atoms")
    assert "-5.9 kcal/mol" in result[0]
    assert result[1]["mensaje"] == (
        "The docked species differs from the input: CC(=O)Oc1ccccc1C(=O)O → "
        "CC(=O)Oc1ccccc1C(=O)[O-]. Unevaluated alternatives remain a source of chemical uncertainty.")
    assert warnings[0].startswith("Eficiencia de ligando")


def test_scientific_audit_translates_each_regime_and_hotspot_branch():
    messages = set()
    hotspots = [{"name": "A:ARG51", "importance": 1.0}, {"name": "A:HIS337", "importance": 0.95},
                {"name": "A:PHE363", "importance": 0.8}]
    for affinity, atoms, regime, ro3 in [(-20, 80, "bro5", False), (-6.08, 13, "ro3", True),
                                       (-5, 30, "ro5", False), (-12, 20, "ro5", False), (-4, 10, "ro3", True)]:
        for hits in [[], ["A:ARG51"]]:
            messages.update(audit_scientific_quality(
                affinity, atoms, 1.4, [{"affinity": affinity}, {"affinity": affinity + 0.05, "rmsd_lb": 3}],
                hotspots, hits, regime, ro3, "curated_experimental"))
    assert len(messages) >= 10
    for message in messages:
        assert traducir(message, "en") != message, message
        assert traducir(message, "es") == message


@pytest.mark.parametrize("locale", ["en", "es"])
def test_report_renders_screenshot_branches_in_requested_language(monkeypatch, locale):
    labels = []
    footers = []
    from matplotlib.axes import Axes
    from reportlab.pdfgen.canvas import Canvas
    original_label, original_text = Axes.set_xlabel, Canvas.drawString
    original_right_text = Canvas.drawRightString

    def label(self, text, *args, **kwargs):
        labels.append(text)
        return original_label(self, text, *args, **kwargs)

    def draw(self, x, y, text, *args, **kwargs):
        footers.append(text)
        return original_text(self, x, y, text, *args, **kwargs)

    def draw_right(self, x, y, text, *args, **kwargs):
        footers.append(text)
        return original_right_text(self, x, y, text, *args, **kwargs)

    monkeypatch.setattr(Axes, "set_xlabel", label)
    monkeypatch.setattr(Canvas, "drawString", draw)
    monkeypatch.setattr(Canvas, "drawRightString", draw_right)
    pdf, text, _ = _capturar_pdf(monkeypatch, locale, configure_screenshot)
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
    if locale == "en":
        for expected in ("Ligand efficiency LE=0.47", "The docked species differs from the input",
                         "May be involved in the specific maturation", "Model SHA-256: " + "d" * 64,
                         "These contributions do not explain total_score", "Legacy normalized affinity",
                         "52.130 (historical 0–100 scale)", "CL-GNN output", "XGBoost output", "Structural family"):
            assert expected in text
        assert "Affinity contribution (SHAP value)" in labels
        assert any("Page 1 of" in f for f in footers)
        assert any("Status:" in f for f in footers)
        assert not any("Página" in f or "Estado:" in f for f in footers)
        for forbidden in ("Eficiencia de ligando", "La especie acoplada", "Puede estar involucrado",
                          "Estas contribuciones", "escala histórica", "Familia estructural"):
            assert forbidden not in text
    else:
        assert "Puede estar involucrado" in text
        assert "Eficiencia de ligando LE=0.47" in text
        assert "Estas contribuciones" in text
        assert "Contribución a Afinidad (SHAP Value)" in labels
        assert any("Página 1 de" in f for f in footers)


def test_external_context_preserves_original_and_researcher_edits():
    records = json.loads((ROOT / "backend/data/target_contexts_en.json").read_text(encoding="utf-8"))["contexts"]
    record = records["1J38"]
    target = SimpleNamespace(pdb_id="1J38", chain="A", description=record["catalog_description"], is_private=False)
    token = set_request_locale("en")
    try:
        assert physiological_description(target) == record["description"]
        target.description = "Descripción personal: <datos> & notas."
        assert physiological_description(target) == target.description
        target.description = record["catalog_description"]
        target.is_private = True
        assert physiological_description(target) == target.description
        target.is_private = False
        target.chain = "Z"
        assert physiological_description(target) == target.description
    finally:
        reset_request_locale(token)


def test_cached_context_covers_the_catalogue_without_network():
    rows = json.loads((ROOT / "curated_targets.json").read_text(encoding="utf-8"))
    records = json.loads((ROOT / "backend/data/target_contexts_en.json").read_text(encoding="utf-8"))["contexts"]
    assert set(records) == {r["pdb_id"].upper() for r in rows}
    for row in rows:
        record = records[row["pdb_id"].upper()]
        assert record["catalog_description"] == row["description"]
        assert record["chain"] == row["chain"]
        assert record["description"] and record["source_url"].startswith("https://data.rcsb.org/")
        assert len(record["response_sha256"]) == 64
        assert record["kind"] in {"uniprot_function", "structure_title"}
