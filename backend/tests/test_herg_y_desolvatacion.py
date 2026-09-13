"""
Dos declaraciones que faltaban: hERG continuo y receptor desolvatado.

# hERG

    if admet_preds["hERG"] == 1:
        S_tox *= 0.1   # Paro cardíaco casi seguro

Tres problemas. El comentario afirma un desenlace clínico que ese modelo no
predice. El escalón en 0.5 hacía que p=0.49 y p=0.51 —indistinguibles para el
modelo— dieran índices que se diferencian en más del doble. Y el 0.1 es una
constante que nadie calibró.

La cuarta auditoría propuso subirla a 0.5 llamándola «factor calibrado». Sería
igual de arbitraria, con el agravante de que el nombre sugeriría que hay una
calibración detrás. Lo que se hace es usar la probabilidad tal cual, de forma
continua: S_tox = 1 − p.

# Desolvatación

`preparer.py` elimina TODAS las aguas cristalográficas. Es la práctica estándar
en acoplamiento generalista y no se cambia; lo que faltaba era declararlo, para
las dianas donde una o varias aguas puente forman parte del reconocimiento.
"""

import pytest

from chem import blood_viability as bv


class _ModeloFalso:
    def __init__(self, herg: float):
        self._herg = herg

    def predict(self, smiles: str):  # noqa: ARG002
        return {
            "Solubility_AqSolDB": -2.0,
            "PPBR_AZ": 70.0,
            "BBB_Martins": 0.6,
            "HIA_Hou": 0.95,
            "hERG": self._herg,
            "Clearance_Hepatocyte_AZ": 12.0,
            "CYP3A4_Veith": 0.1,
            "CYP2D6_Veith": 0.1,
            "CYP2C9_Veith": 0.1,
            "CYP3A4_Substrate_CarbonMangels": 0.1,
            "CYP2D6_Substrate_CarbonMangels": 0.1,
            "CYP2C9_Substrate_CarbonMangels": 0.1,
        }


def _viabilidad(monkeypatch, herg: float) -> float:
    from core.models import PhysicochemicalProperties as P
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, QED, rdMolDescriptors

    monkeypatch.setattr(bv, "get_admet_model", lambda: _ModeloFalso(herg))
    monkeypatch.setattr(bv, "predict_tabpfn_custom_toxicity", lambda p: [])
    bv._admet_cache.clear()

    smiles = "CN(C)CCOC(c1ccccc1)c1ccccc1"
    m = Chem.MolFromSmiles(smiles)
    props = P(
        molecular_weight=Descriptors.MolWt(m), log_p=Crippen.MolLogP(m),
        tpsa=Descriptors.TPSA(m), hbd=rdMolDescriptors.CalcNumHBD(m),
        hba=rdMolDescriptors.CalcNumHBA(m),
        rotatable_bonds=rdMolDescriptors.CalcNumRotatableBonds(m),
        heavy_atom_count=m.GetNumHeavyAtoms(),
        ring_count=rdMolDescriptors.CalcNumRings(m),
        qed=QED.qed(m), sa_score=2.0, lipinski_pass=True, veber_pass=True,
    )
    return bv.calculate_blood_viability(smiles, props).blood_viability_score


def test_no_hay_escalon_alrededor_del_umbral(monkeypatch):
    """p=0.49 y p=0.51 son indistinguibles para el modelo; el índice también."""
    justo_debajo = _viabilidad(monkeypatch, 0.49)
    justo_encima = _viabilidad(monkeypatch, 0.51)
    assert abs(justo_debajo - justo_encima) < 3.0, (
        "el binarizado daba 100 frente a 46 a los dos lados del umbral"
    )


def test_la_penalizacion_es_monotona(monkeypatch):
    valores = [_viabilidad(monkeypatch, p) for p in (0.02, 0.3, 0.6, 0.95)]
    assert valores == sorted(valores, reverse=True)


def test_una_probabilidad_baja_apenas_penaliza(monkeypatch):
    assert _viabilidad(monkeypatch, 0.02) > 95.0


def test_una_probabilidad_alta_penaliza_de_verdad(monkeypatch):
    assert _viabilidad(monkeypatch, 0.95) < 45.0


def test_el_comentario_ya_no_afirma_un_desenlace_clinico():
    from pathlib import Path

    fuente = (Path(__file__).resolve().parents[1] / "chem" / "blood_viability.py").read_text(
        encoding="utf-8"
    )
    # La frase original iba en la misma línea que la penalización.
    assert "S_tox *= 0.1  # Paro cardíaco casi seguro" not in fuente
    # Y el riesgo se nombra por lo que es.
    assert "QTc" in fuente


def test_se_conserva_la_probabilidad_cruda(monkeypatch):
    monkeypatch.setattr(bv, "get_admet_model", lambda: _ModeloFalso(0.73))
    bv._admet_cache.clear()
    preds = bv.predict_admet_ai("CCO")
    assert preds["hERG_prob"] == pytest.approx(0.73)
    assert preds["hERG"] == 1  # la etiqueta sigue existiendo para las alertas


def test_sin_modelo_la_probabilidad_tambien_es_nula(monkeypatch):
    monkeypatch.setattr(bv, "get_admet_model", lambda: None)
    bv._admet_cache.clear()
    assert bv.predict_admet_ai("CCO")["hERG_prob"] is None


# ── Desolvatación declarada ────────────────────────────────────────────────

def test_el_dossier_declara_que_se_acopla_sin_aguas():
    from services.blockchain.evidence_summary import build_evidence_summary

    class _Eval:
        docking_poses = []
        scientific_warnings = []

    supuestos = build_evidence_summary(_Eval())["assumptions"]
    desolvatacion = [s for s in supuestos if "desolvatada" in s]
    assert desolvatacion, "el dossier no declara que el receptor va sin aguas"
    assert "aguas puente" in desolvatacion[0], (
        "hay que decir POR QUÉ importa, no sólo que se quitaron"
    )


def test_la_declaracion_corresponde_con_lo_que_hace_el_preparador():
    """Si algún día se conservan aguas, esta prueba obliga a revisar el texto."""
    from services.docking.preparer import WATER_RESIDUES

    assert WATER_RESIDUES == {"HOH", "WAT", "DOD"}
