"""LIG-008: una cabeza ausente de ADMET no se interpreta como negativa."""
from __future__ import annotations

import pytest

from chem import blood_viability as bv
from core.models import PhysicochemicalProperties


def _propiedades():
    return PhysicochemicalProperties(
        molecular_weight=180.16, log_p=1.4, tpsa=63.6, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=13, ring_count=2,
        qed=0.9, sa_score=2.0, lipinski_pass=True, veber_pass=True,
    )


@pytest.mark.parametrize(
    "hia,ppb,esperado_hia,esperado_ppb",
    [(None, None, None, None), (None, 70.0, None, "low"),
     (1, None, True, None), (0, 95.0, False, "high")],
)
def test_cabezas_parcialmente_ausentes(monkeypatch, hia, ppb, esperado_hia, esperado_ppb):
    monkeypatch.setattr(bv, "predict_admet_ai", lambda _smi: {
        "Solubility": -3.2, "HIA": hia, "PPB": ppb,
        "BBB_prob": None, "hERG_prob": 0.1,
    })
    monkeypatch.setattr(bv, "predict_tabpfn_custom_toxicity", lambda _p: [])
    resultado = bv.calculate_blood_viability("CC(=O)Oc1ccccc1C(=O)O", _propiedades())
    assert resultado.blood_hia_permeable is esperado_hia
    assert resultado.blood_ppb_category == esperado_ppb
    assert (resultado.blood_viability_score is None) == (hia is None)
