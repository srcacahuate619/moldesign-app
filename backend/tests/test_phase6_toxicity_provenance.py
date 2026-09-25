"""LIG-011: el CSV histórico no produce una predicción ni un veto."""
from chem import blood_viability as bv
from core.models import PhysicochemicalProperties


def _properties():
    return PhysicochemicalProperties(
        molecular_weight=180.16, log_p=1.4, tpsa=150.0, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=13, ring_count=2,
        qed=0.9, sa_score=8.0, lipinski_pass=True, veber_pass=True,
    )


def test_csv_sin_procedencia_no_produce_alertas():
    assert bv.predict_tabpfn_custom_toxicity(_properties()) == []
    assert bv._tabpfn_estado == "no_evaluado"


def test_descriptores_heuristicos_no_penalizan_indice_como_toxicidad(monkeypatch):
    monkeypatch.setattr(bv, "predict_admet_ai", lambda _: {
        "Solubility": -3.0, "HIA": 1, "PPB": 70.0, "BBB_prob": None,
        "hERG_prob": 0.0, "hERG": 0,
    })
    result = bv.calculate_blood_viability("CCO", _properties())
    assert result.blood_tabpfn_estado == "no_evaluado"
    assert result.blood_systemic_reactivity == []
    assert result.blood_viability_score == 100.0
