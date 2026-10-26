"""La vista «Se acoplará» del editor: la especie que entraría en Vina, preparada
con el mismo código que la corrida.

Lo que se protege:

1. **Es la preparación de la corrida, no otra.** El SMILES y la geometría salen
   de `chem.conformer._construir_conformero` con el pH y el modo de tautómero de
   la corrida; si la vista previa preparara por su cuenta, podría enseñar una
   especie que la corrida no acopla.
2. **El dibujo no se mueve.** Cada átomo conserva su sitio en el dibujo escrito,
   así que al alternar sólo cambia lo que la preparación cambió.
3. **Lo que cambia se dice.** Cargas, hidrógenos y órdenes de enlace distintos
   de los escritos se listan átomo a átomo.
"""
from __future__ import annotations

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from rdkit import Chem

from chem import router as chem_router
from chem.conformer import _construir_conformero
from chem.elevacion import FUENTE_ESPECIE, dibujo_2d, modelo_de_la_especie_acoplada

PROPRANOLOL = "CC(C)NCC(O)COc1cccc2ccccc12"
IBUPROFENO = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"
HIDROXIPIRIDINA = "Oc1ccccn1"


def _indice(smiles: str, smarts: str) -> int:
    return Chem.MolFromSmiles(smiles).GetSubstructMatch(Chem.MolFromSmarts(smarts))[0]


def _distancias(p: np.ndarray) -> np.ndarray:
    return np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)


def test_la_amina_se_ve_protonada_en_su_sitio_del_dibujo():
    modelo = modelo_de_la_especie_acoplada(PROPRANOLOL)

    assert modelo["fuente"] == FUENTE_ESPECIE
    n = _indice(PROPRANOLOL, "[NX3;H1]")
    assert modelo["atomos"][n]["carga"] == 1
    assert modelo["atomos"][n]["hidrogenos"] == 2
    assert {"atomo": n, "carga": [0, 1], "hidrogenos": [1, 2]} in modelo["especie_acoplada"]["cambios"]["atomos"]
    lienzo = dibujo_2d(Chem.MolFromSmiles(PROPRANOLOL)).lienzo
    assert np.allclose([a["plano"] for a in modelo["atomos"]], lienzo, atol=0.01)


def test_es_la_especie_y_la_geometria_que_prepara_la_corrida():
    corrida = _construir_conformero(PROPRANOLOL, 7.4, "entrada")
    modelo = modelo_de_la_especie_acoplada(PROPRANOLOL, ph=7.4, tautomero="entrada")

    especie = modelo["especie_acoplada"]
    assert especie["smiles"] == corrida["canonical_smiles"]
    assert especie["sdf_sha256"] == corrida["estado_del_ligando"]["conformero"]["sdf_sha256"]
    # La geometría mostrada es la del SDF de partida, a escala.
    pose = Chem.MolFromMolBlock(corrida["sdf_content"], removeHs=False)
    pesados = Chem.RemoveHs(pose).GetConformer().GetPositions()
    mostrado = np.array([[x, -y, z] for x, y, z in (a["xyz"] for a in modelo["atomos"])])
    origen, vista = np.sort(_distancias(pesados).ravel()), np.sort(_distancias(mostrado).ravel())
    assert np.allclose(vista, origen * vista[-1] / origen[-1], rtol=2e-3, atol=0.05)


def test_el_ph_de_la_corrida_decide_la_especie():
    o = _indice(IBUPROFENO, "[OX2H1]")

    a_74 = modelo_de_la_especie_acoplada(IBUPROFENO, ph=7.4)
    a_2 = modelo_de_la_especie_acoplada(IBUPROFENO, ph=2.0)

    assert a_74["atomos"][o]["carga"] == -1
    assert a_2["atomos"][o]["carga"] == 0
    assert a_74["especie_acoplada"]["ph"] == 7.4
    assert a_2["especie_acoplada"]["ph"] == 2.0


def test_el_modo_de_tautomero_de_la_corrida_decide_los_enlaces():
    entrada = modelo_de_la_especie_acoplada(HIDROXIPIRIDINA, tautomero="entrada")
    canonico = modelo_de_la_especie_acoplada(HIDROXIPIRIDINA, tautomero="canonico")

    assert entrada["especie_acoplada"]["tautomero"]["modo"] == "entrada"
    assert entrada["especie_acoplada"]["cambios"]["enlaces"] == []
    assert canonico["especie_acoplada"]["tautomero"]["modo"] == "canonico"
    # La piridona: el C–O pasa a doble.
    co = {"a": 0, "b": 1}
    assert any({k: e[k] for k in ("a", "b")} == co and e["orden"] == [1.0, 2.0]
               for e in canonico["especie_acoplada"]["cambios"]["enlaces"])


def test_lo_que_no_cambia_no_se_lista_y_los_enlaces_del_dibujo_se_conservan():
    modelo = modelo_de_la_especie_acoplada("c1ccccc1O", ph=7.4)

    assert modelo["especie_acoplada"]["cambios"] == {"atomos": [], "enlaces": []}
    # Mismo Kekulé que el dibujo escrito: alternar no hace saltar los dobles del anillo.
    from chem.elevacion import _enlaces
    assert modelo["enlaces"] == _enlaces(Chem.MolFromSmiles("c1ccccc1O"))


def test_un_centro_sin_declarar_queda_fijado_y_se_dice():
    modelo = modelo_de_la_especie_acoplada("CC(N)CC(=O)O", ph=2.0)

    assert modelo["especie_acoplada"]["estereo"]["sin_declarar"] == [1]


def test_una_sal_se_prepara_sin_el_contraion_y_se_declara():
    modelo = modelo_de_la_especie_acoplada("CC(C)NCC(O)c1ccc(O)c(O)c1.Cl")

    assert modelo["especie_acoplada"]["contraiones"] == ["Cl"]
    assert len(modelo["atomos"]) == 15  # el isoproterenol, sin el cloro


@pytest.mark.asyncio
async def test_el_endpoint_pasa_la_vista_el_ph_y_el_tautomero():
    app = FastAPI()
    app.include_router(chem_router.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cliente:
        acoplada = await cliente.post("/chem/elevacion", json={
            "smiles": IBUPROFENO, "vista": "acoplada", "ph": 2.0, "tautomero": "entrada"})
        escrita = await cliente.post("/chem/elevacion", json={"smiles": IBUPROFENO})
        mala = await cliente.post("/chem/elevacion", json={"smiles": IBUPROFENO, "vista": "otra"})

    assert acoplada.status_code == 200
    assert acoplada.json()["fuente"] == FUENTE_ESPECIE
    assert acoplada.json()["especie_acoplada"]["ph"] == 2.0
    assert escrita.json()["fuente"] == "conformador_calculado"
    assert mala.status_code == 422
