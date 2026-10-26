"""La especie acoplada se lee entera en inglés, en todas sus variantes.

Medido el 2026-10-09 en la auditoría de Preparación traducida (una pasada, como la
sirve `POST /evaluation/dossier/{id}/preparacion`): la especie de CUALQUIER corrida
salía «Microstate closest to the one predicted at pH 7.4, de 4 enumerados», y en las
especies en revisión el párrafo entero quedaba en castellano. La plantilla genérica
«…a pH {n1}» se tragaba el resto de la frase, y ni «La selección es reproducible…»
ni los motivos de revisión tenían traducción.
"""

from __future__ import annotations

import itertools

import pytest

from chem.especie_en_revision import motivos_de_revision
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito

#: Fragmentos que sólo aparecen si una frase se quedó en castellano. Los nombres
#: de clase de la tabla de pKa (`sulfonilurea`, `tetrazol`, `biguanida`) viajan como
#: identificadores, igual que un código, y no se buscan aquí.
CASTELLANO = (
    "enumerados", "empataron", "desempate", "La selección", "selección", "En revisión",
    "tabla de pKa", "Revisa la especie", "candidatos", "carece", "monocatión",
    "Población", "Microestado", "alfabético", "corrida", "piperazina o diamina",
    "N-sulfonil-piperazina", "ácido enólico", "amina protonada", "decisión abierta", "se acoplaba",
)

#: Especies acopladas que disparan cada motivo, y una que no dispara ninguno.
SMILES = {
    "ninguno": "CC(C)Cc1ccc(C(C)C(=O)[O-])cc1",
    "bases_proximas": "O=C([O-])COCC[NH+]1CC[NH+](C(c2ccccc2)c2ccc(Cl)cc2)CC1",
    "sulfonil_piperazina": "CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CC[NH+](C)CC4)ccc3OCC)nc12",
    "acido_enolico": "CN1C(C(=O)Nc2ccccn2)C(=O)c2ccccc2S1(=O)=O",
    "amina_con_atractor": "FC(F)(F)C[NH+](Cc1ccccc1C(F)(F)F)C1CC[NH2+]CC1",
}


def _estado(smiles: str, seleccion: dict, alternativas) -> dict:
    return {
        "smiles_acoplado": smiles,
        "protonacion": {
            "aplicada": True, "motor": "dimorphite-dl", "ph": 7.4, "ph_solicitado": 7.4,
            "aviso_de_ph": None, "alternativas": alternativas, "seleccion": seleccion,
        },
    }


def _selecciones():
    base = {"ph": 7.4, "clases_sin_pka": [], "revision_biguanida": False}
    for empatados, resuelta in itertools.product((1, 3), (True, False)):
        yield "cargas", {**base, "criterio": "cargas_esperadas_ph_7.4", "empatados": empatados,
                         "quimica_resuelta": resuelta}
    yield "sin_centros", {**base, "criterio": "primer_smiles_alfabetico_sin_centros", "empatados": 2,
                          "quimica_resuelta": True}
    yield "sin_pka", {**base, "criterio": "grupo_reconocido_sin_pka", "empatados": 1,
                      "clases_sin_pka": ["sulfonilurea"], "quimica_resuelta": False}
    yield "biguanida", {**base, "criterio": "cargas_esperadas_ph_7.4", "empatados": 1,
                        "quimica_resuelta": False, "revision_biguanida": True}
    yield "cargas_sin_pka", {**base, "criterio": "cargas_esperadas_ph_7.4", "empatados": 1,
                             "clases_sin_pka": ["tetrazol"], "quimica_resuelta": True}
    yield "sin_pka_biguanida", {**base, "criterio": "grupo_reconocido_sin_pka", "empatados": 1,
                                "clases_sin_pka": ["biguanida"], "quimica_resuelta": False,
                                "revision_biguanida": True}


CASOS = [(f"{n}-{m}-alt{a}", s, SMILES[m], a)
         for (n, s), m, a in itertools.product(list(_selecciones()), SMILES, (4, None))]


@pytest.mark.parametrize("nombre, seleccion, smiles, alternativas", CASOS, ids=[c[0] for c in CASOS])
def test_la_especie_se_lee_entera_en_ingles(nombre, seleccion, smiles, alternativas):
    auditoria = traducir_dossier(_auditar(_con_procedencia(**_estado(smiles, seleccion, alternativas))), "en")
    especie = _requisito(auditoria, "ligando.especie")
    texto = " ".join(str(especie.get(k) or "") for k in ("valor", "razon", "etiqueta"))
    restos = [f for f in CASTELLANO if f in texto]
    assert not restos, (restos, texto)


def test_sin_punto_y_coma_tras_punto_en_castellano():
    """«no determinada.; el grupo…» era la puntuación de la descripción con sufijo."""
    for _, seleccion, smiles, alternativas in CASOS:
        especie = _requisito(_auditar(_con_procedencia(**_estado(smiles, seleccion, alternativas))),
                             "ligando.especie")
        texto = f"{especie.get('valor') or ''} {especie.get('razon') or ''}"
        assert ".;" not in texto, texto


def test_los_motivos_de_las_especies_de_prueba_son_los_esperados():
    for motivo, smiles in SMILES.items():
        codigos = [m.codigo for m in motivos_de_revision(smiles)]
        assert codigos == ([] if motivo == "ninguno" else [motivo]), (motivo, codigos)
