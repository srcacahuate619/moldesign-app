"""La especie acoplada se declara en REVISIÓN en las clases que la tabla de pKa no resuelve.

Decisión del propietario (2026-09-28) sobre QA-002/QA-024/QA-S05: sin tocar el
modelo de protonación, el expediente y Preparación dejan de dar por REGISTRADA la
especie de una piperazina o diamina con dos bases a ≤ 3 enlaces, de una
N-sulfonil-piperazina o de un ácido enólico (oxicams, 4-hidroxicumarinas).

Las especies de abajo son las que el producto ACOPLÓ (`smiles_docked` del panel de
la auditoría de GPT 6 Sol, `D:\\moldesign-audits\\qa-sol\\repro\\t3_microstates.jsonl`),
no SMILES escritos a mano: la regla tiene que funcionar sobre la forma protonada.
"""

from __future__ import annotations

import pytest

from chem.especie_en_revision import motivos_de_revision
from services.dossier.model import campos_del_estado_del_ligando
from services.dossier.taxonomy import Estado
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito

#: Especie mal asignada, confirmada con fuente primaria (Sol, T3).
ERRORES_CONFIRMADOS = {
    "sildenafilo": ("CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CC[NH+](C)CC4)ccc3OCC)nc12",
                    "sulfonil_piperazina"),
    "cetirizina": ("O=C([O-])COCC[NH+]1CC[NH+](C(c2ccccc2)c2ccc(Cl)cc2)CC1", "bases_proximas"),
}

#: Especie correcta según fuente primaria: la regla NO puede marcarlas. Incluye
#: dos piperazinas que el producto trata bien (ketoconazol y ciprofloxacino).
CORRECTAS_VERIFICADAS = {
    "albendazol": "CCCSc1ccc2[nH]c(NC(=O)OC)nc2c1",
    "clorfeniramina": "C[NH+](C)CCC(c1ccc(Cl)cc1)c1ccccn1",
    "diclofenaco": "O=C([O-])Cc1ccccc1Nc1c(Cl)cccc1Cl",
    "diflunisal": "O=C([O-])c1cc(-c2ccc(F)cc2F)ccc1O",
    "furosemida": "NS(=O)(=O)c1cc(C(=O)[O-])c(NCc2ccco2)cc1Cl",
    "haloperidol": "OC(CCC[NH+]1CCC(c2ccc(F)cc2)CC1)(c1ccccc1)c1ccc(Cl)cc1",
    "hidroclorotiazida": "NS(=O)(=O)c1cc2c(cc1Cl)NCNS2(=O)=O",
    "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)[O-])cc1",
    "imipramina": "C[NH+](C)CCCN1c2ccccc2CCc2ccccc21",
    "ketoconazol": "CC(=O)N1CCN(c2ccc(OCC3COC(Cn4ccnc4)(c4ccc(Cl)cc4Cl)O3)cc2)CC1",
    "ketoprofeno": "CC(C(=O)[O-])c1cccc(C(=O)c2ccccc2)c1",
    "papaverina": "COc1ccc(Cc2nccc3cc(OC)c(OC)cc23)cc1OC",
    "propranolol": "CC(C)[NH2+]CC(O)COc1cccc2ccccc12",
    "verapamilo": "COc1ccc(CC[NH+](C)CCCC(C#N)(c2ccc(OC)c(OC)c2)C(C)C)cc1OC",
    "ciprofloxacino": "O=C([O-])c1cn(C2CC2)c2cc(F)c(N3CC[NH2+]CC3)cc2c1=O",
    "celecoxib": "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1",
    "losartan": "CCCCc1nc(Cl)c(CO)n1Cc1ccc(-c2ccccc2-c2nn[n-]n2)cc1",
}


@pytest.mark.parametrize("nombre", sorted(ERRORES_CONFIRMADOS))
def test_los_errores_confirmados_se_declaran(nombre):
    smiles, codigo = ERRORES_CONFIRMADOS[nombre]
    assert codigo in [m.codigo for m in motivos_de_revision(smiles)]


@pytest.mark.parametrize("nombre", sorted(CORRECTAS_VERIFICADAS))
def test_las_especies_correctas_no_se_marcan(nombre):
    assert motivos_de_revision(CORRECTAS_VERIFICADAS[nombre]) == []


@pytest.mark.parametrize("nombre, smiles", [
    ("piroxicam acoplado (ceto)", "CN1C(C(=O)Nc2ccccn2)C(=O)c2ccccc2S1(=O)=O"),
    ("piroxicam enol", "CN1C(C(=O)Nc2ccccn2)=C(O)c2ccccc2S1(=O)=O"),
    ("meloxicam", "Cc1cnc(NC(=O)C2=C(O)c3ccccc3S(=O)(=O)N2C)s1"),
    ("tenoxicam", "CN1C(C(=O)Nc2ccccn2)=C(O)c2sccc2S1(=O)=O"),
    # RDKit aromatiza la pirona: con átomos alifáticos en el patrón no se veía.
    ("warfarina", "CC(=O)CC(c1ccccc1)C1=C(O)c2ccccc2OC1=O"),
    ("4-hidroxicumarina aromática", "Oc1cc(=O)oc2ccccc12"),
])
def test_acidos_enolicos(nombre, smiles):
    assert [m.codigo for m in motivos_de_revision(smiles)] == ["acido_enolico"]


@pytest.mark.parametrize("nombre, smiles", [
    ("cumarina", "O=c1ccc2ccccc2o1"),
    ("umbeliferona: 7-OH, fenol, no vinílogo", "O=c1ccc2ccc(O)cc2o1"),
    ("acetilacetona enol, acíclica", "CC(O)=CC(C)=O"),
    ("1,3-propanodiamina: 4 enlaces", "NCCCN"),
    ("N-metil-N'-arilpiperazina: un solo N básico", "CN1CCN(c2ccccc2)CC1"),
    ("piperidina", "C1CCNCC1"),
])
def test_controles_negativos(nombre, smiles):
    assert motivos_de_revision(smiles) == []


def test_sin_smiles_o_ilegible_no_inventa_motivos():
    assert motivos_de_revision(None) == []
    assert motivos_de_revision("esto no es un smiles") == []


# ── En el expediente y en Preparación ────────────────────────────────────


def _estado(smiles: str) -> dict:
    """`ligand_state` con la forma que persiste la corrida (visto en el panel de Sol)."""
    return {
        "smiles_acoplado": smiles,
        "protonacion": {
            "aplicada": True, "motor": "dimorphite-dl", "ph": 7.4, "ph_solicitado": 7.4,
            "aviso_de_ph": None, "alternativas": 4,
            "seleccion": {"criterio": "cargas_esperadas_ph_7.4", "ph": 7.4, "empatados": 1,
                          "clases_sin_pka": [], "quimica_resuelta": True,
                          "revision_biguanida": False},
        },
    }


def _especie(smiles: str):
    return dict(campos_del_estado_del_ligando(_estado(smiles)))["especie"]


def test_sildenafilo_ya_no_sale_registrado():
    campo = _especie(ERRORES_CONFIRMADOS["sildenafilo"][0])
    assert campo.estado == Estado.REVISAR
    assert "sulfonil" in campo.razon
    assert "energía libre" in campo.razon


def test_una_especie_resuelta_de_otra_clase_sigue_registrada():
    assert _especie(CORRECTAS_VERIFICADAS["ibuprofeno"]).estado == Estado.REGISTRADO


def test_en_preparacion_pide_revision_y_no_bloquea():
    caso = _con_procedencia(**_estado(ERRORES_CONFIRMADOS["cetirizina"][0]))
    auditoria = _auditar(caso)
    especie = _requisito(auditoria, "ligando.especie")
    assert especie["estado"] == "REVISAR"
    assert "ligando.especie" in auditoria["en_revision"]
    assert "ligando.especie" not in auditoria["bloqueantes"]
