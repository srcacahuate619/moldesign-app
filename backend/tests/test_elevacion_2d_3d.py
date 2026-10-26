"""La elevación 2D → 3D de Moldex y del editor: qué geometría enseña y que no la
deforma.

Lo que se protege, en orden de gravedad:

1. **Nunca un espejo.** El ajuste al dibujo es una rotación propia; una
   reflexión invertiría R/S y el visor enseñaría el enantiómero.
2. **La geometría no se toca.** Moldex gira la pose de la corrida: sus
   distancias interatómicas tienen que ser las del SDF, a escala.
3. **Sin SDF no hay 3D.** La ficha no rellena el hueco con un conformador.
4. **El instante inicial es la miniatura.** `plano` coincide con el dibujo de
   `/chem/render/{id}`, que sale de la misma función.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from rdkit import Chem
from rdkit.Chem import AllChem

from api.dependencies import get_current_user, get_current_user_optional
from chem import router as chem_router
from chem.elevacion import (
    FUENTE_CONFORMADOR,
    FUENTE_POSE,
    ElevacionNoDisponible,
    dibujo_2d,
    modelo_desde_conformador,
    SEMILLAS_CRITERIO,
    UMBRAL_ENLACES,
    _es_fiel,
    modelo_desde_pose,
)
from core.database import get_db
from tests.test_moldex_guarda_corridas import mundo  # noqa: F401  (fixture)

ALANINA_S = "C[C@H](N)C(=O)O"
ALANINA_R = "C[C@@H](N)C(=O)O"


def _xyz_y_arriba(modelo: dict) -> np.ndarray:
    """`xyz` viene en px del lienzo con y hacia abajo; para leer quiralidad se
    vuelve a un marco diestro."""
    return np.array([[x, -y, z] for x, y, z in (a["xyz"] for a in modelo["atomos"])])


def _cip_del_modelo(smiles: str, modelo: dict) -> list[tuple[int, str]]:
    mol = Chem.MolFromSmiles(smiles)
    conf = Chem.Conformer(mol.GetNumAtoms())
    for i, p in enumerate(_xyz_y_arriba(modelo)):
        conf.SetAtomPosition(i, p.tolist())
    sin_estereo = Chem.Mol(mol)
    Chem.RemoveStereochemistry(sin_estereo)
    sin_estereo.RemoveAllConformers()
    sin_estereo.AddConformer(conf, assignId=True)
    Chem.AssignStereochemistryFrom3D(sin_estereo)
    return Chem.FindMolChiralCenters(sin_estereo, useLegacyImplementation=False)


def _sdf_girado(smiles: str, *, protonar: str | None = None, semilla: int = 7) -> tuple[str, np.ndarray]:
    """Una «pose»: un conformador con hidrógenos, girado y desplazado a un
    sitio cualquiera, como lo escribiría Meeko."""
    mol = Chem.AddHs(Chem.MolFromSmiles(protonar or smiles))
    AllChem.EmbedMolecule(mol, randomSeed=semilla)
    rng = np.random.default_rng(semilla)
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    conf = mol.GetConformer()
    pos = conf.GetPositions() @ q.T + np.array([31.0, -4.0, 12.0])
    for i, p in enumerate(pos):
        conf.SetAtomPosition(i, p.tolist())
    mol.SetProp("meeko", '{"free_energy": -6.1}')
    bloque = Chem.MolToMolBlock(mol)
    pesados = np.array([pos[a.GetIdx()] for a in mol.GetAtoms() if a.GetAtomicNum() > 1])
    return f"{bloque}>  <meeko>  (1) \n{mol.GetProp('meeko')}\n\n$$$$\n", pesados


def _distancias(p: np.ndarray) -> np.ndarray:
    return np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)


@pytest.mark.parametrize("smiles, esperado", [(ALANINA_S, "S"), (ALANINA_R, "R")])
def test_el_conformador_conserva_la_quiralidad(smiles, esperado):
    modelo = modelo_desde_conformador(smiles)

    assert modelo["fuente"] == FUENTE_CONFORMADOR
    assert _cip_del_modelo(smiles, modelo) == [(1, esperado)]


@pytest.mark.parametrize("smiles, esperado", [(ALANINA_S, "S"), (ALANINA_R, "R")])
def test_la_pose_conserva_la_quiralidad_y_sus_distancias(smiles, esperado):
    sdf, pesados = _sdf_girado(smiles)

    modelo = modelo_desde_pose(smiles, sdf)

    assert modelo["fuente"] == FUENTE_POSE
    assert _cip_del_modelo(smiles, modelo) == [(1, esperado)]
    # Sólo una escala uniforme separa la geometría mostrada de la del SDF. Se
    # comparan ordenadas: los dos oxígenos del carboxilo pueden corresponderse
    # en cualquier orden.
    origen = np.sort(_distancias(pesados).ravel())
    mostrado = np.sort(_distancias(_xyz_y_arriba(modelo)).ravel())
    escala = mostrado[-1] / origen[-1]
    assert np.allclose(mostrado, origen * escala, rtol=2e-3, atol=0.05)


def test_la_pose_se_lee_aunque_la_especie_acoplada_este_protonada():
    """Dimorphite puede acoplar la amina protonada: cambian carga e H, no el
    grafo de átomos pesados."""
    sdf, _ = _sdf_girado(ALANINA_S, protonar="C[C@H]([NH3+])C(=O)[O-]")

    modelo = modelo_desde_pose(ALANINA_S, sdf)

    assert _cip_del_modelo(ALANINA_S, modelo) == [(1, "S")]
    assert modelo["pose"]["afinidad_kcal_mol"] == pytest.approx(-6.1)


def test_una_pose_de_otra_molecula_no_se_presenta():
    sdf, _ = _sdf_girado("CCN")

    with pytest.raises(ElevacionNoDisponible):
        modelo_desde_pose("CCO", sdf)


def test_una_molecula_rigida_se_levanta_desde_su_dibujo():
    """La cafeína es plana: alineada, su geometría cae casi encima del dibujo."""
    modelo = modelo_desde_conformador("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")

    assert modelo["desajuste_px"] < 8


def test_plano_es_la_posicion_de_cada_atomo_en_la_miniatura():
    """En un enlace C–C, RDKit traza la línea exactamente entre los dos átomos."""
    mol = Chem.MolFromSmiles("CCc1ccccc1")
    dibujo = dibujo_2d(mol)

    trazo = re.search(r"class='bond-0 atom-0 atom-1' d='M ([\d.]+),([\d.]+) L ([\d.]+),([\d.]+)'", dibujo.svg)
    assert trazo, "RDKit cambió el formato de sus trazos"
    x0, y0, x1, y1 = map(float, trazo.groups())
    assert np.allclose(dibujo.lienzo[0], [x0, y0], atol=0.05)
    assert np.allclose(dibujo.lienzo[1], [x1, y1], atol=0.05)


# ── HTTP ──────────────────────────────────────────────────────────────────────


def test_una_pose_que_conserva_la_configuracion_no_se_senala():
    sdf, _ = _sdf_girado(ALANINA_S)

    estereo = modelo_desde_pose(ALANINA_S, sdf)["pose"]["estereo"]

    assert estereo["declarados"] == 1
    assert estereo["conservados"] == 1
    assert estereo["invertidos"] == []


def test_la_pose_del_enantiomero_invierte_el_centro_y_se_senala():
    """Una pose de (R) presentada como la de (S) es la molécula equivocada: el
    visor lo tiene que decir, no enseñarla como la guardada."""
    sdf, _ = _sdf_girado(ALANINA_R)

    estereo = modelo_desde_pose(ALANINA_S, sdf)["pose"]["estereo"]

    assert estereo["conservados"] == 0
    assert estereo["invertidos"] == [{"atomo": 1, "smiles": "S", "pose": "R"}]


def test_un_centro_que_el_smiles_no_declara_no_cuenta_como_inversion():
    sdf, _ = _sdf_girado("CC(N)C(=O)O")

    estereo = modelo_desde_pose("CC(N)C(=O)O", sdf)["pose"]["estereo"]

    assert estereo["declarados"] == 0
    assert estereo["sin_declarar"] == [1]
    assert estereo["invertidos"] == []


def test_la_carga_de_la_especie_acoplada_se_declara():
    """Vina puntúa la especie que se preparó: si la amina llegó protonada, la
    pose lo dice aunque el SMILES guardado sea neutro."""
    sdf, _ = _sdf_girado(ALANINA_S, protonar="C[C@H]([NH3+])C(=O)O")

    especie = modelo_desde_pose(ALANINA_S, sdf)["pose"]["especie"]

    assert especie == {"carga_smiles": 0, "carga_acoplada": 1}


def test_el_criterio_de_abstencion_es_un_enlace_y_tres_semillas():
    """El umbral se fijó antes de medir la cola de la distribución; cambiarlo
    exige volver a medir."""
    assert UMBRAL_ENLACES == 1.0
    assert SEMILLAS_CRITERIO == (1, 2, 3)


def test_una_molecula_rigida_no_se_abstiene_y_declara_su_criterio():
    modelo = modelo_desde_conformador("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")

    assert modelo["fiel"] is True
    assert modelo["razon_enlaces"] is not None
    assert modelo["conformador"]["semillas"] == [1, 2, 3]


def test_sin_enlaces_no_hay_criterio_que_aplicar_y_el_json_no_lleva_nan():
    modelo = modelo_desde_conformador("C")

    assert modelo["enlace_px"] is None
    assert modelo["razon_enlaces"] is None
    assert modelo["fiel"] is True
    json.dumps(modelo, allow_nan=False)


def test_la_abstencion_es_inclusiva_en_el_umbral():
    assert _es_fiel(UMBRAL_ENLACES) is True
    assert _es_fiel(UMBRAL_ENLACES + 0.001) is False
    assert _es_fiel(None) is True


def _app(mundo) -> FastAPI:  # noqa: F811
    async def database():
        async with mundo.factory() as db:
            yield db

    app = FastAPI()
    app.include_router(chem_router.router)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: mundo.owner
    app.dependency_overrides[get_current_user_optional] = lambda: mundo.owner
    return app


@pytest.mark.asyncio
async def test_la_ficha_gira_la_pose_de_su_corrida_y_sin_sdf_no_inventa_otra(mundo, monkeypatch):  # noqa: F811
    sdf_a, _ = _sdf_girado("CCO")
    contenidos = {"poses/run-A.sdf": sdf_a}

    async def leer(ruta, *args, **kwargs):
        if ruta not in contenidos:
            raise FileNotFoundError(ruta)
        return contenidos[ruta]

    monkeypatch.setattr("utils.local_storage.read_text", leer)
    await mundo.evaluar("run-A", 40.0, -6.0)
    await mundo.evaluar("run-B", 55.0, -7.5)

    async with AsyncClient(transport=ASGITransport(app=_app(mundo)), base_url="http://t") as cliente:
        base = f"/chem/elevacion/{mundo.molecule_id}"
        de_a = await cliente.get(base, params={"task_id": "run-A"})
        de_b = await cliente.get(base, params={"task_id": "run-B"})
        render = await cliente.get(f"/chem/render/{mundo.molecule_id}")

    assert de_a.status_code == 200
    cuerpo = de_a.json()
    assert cuerpo["fuente"] == FUENTE_POSE and cuerpo["pose"]["task_id"] == "run-A"
    # El SDF de run-B no existe: 404, y ningún conformador ocupa su lugar.
    assert de_b.status_code == 404
    # El instante inicial de la elevación es la miniatura que ya se veía.
    assert render.text == cuerpo["svg"]


@pytest.mark.asyncio
async def test_el_editor_recibe_un_conformador_declarado(mundo):  # noqa: F811
    async with AsyncClient(transport=ASGITransport(app=_app(mundo)), base_url="http://t") as cliente:
        bueno = await cliente.post("/chem/elevacion", json={"smiles": ALANINA_S})
        malo = await cliente.post("/chem/elevacion", json={"smiles": "C1CC"})

    assert bueno.status_code == 200
    assert bueno.json()["fuente"] == FUENTE_CONFORMADOR
    assert bueno.json()["conformador"]["metodo"] == "ETKDGv3"
    assert malo.status_code == 422


def _pose_barajada(smiles: str, semilla: int) -> tuple[str, np.ndarray]:
    """Una pose con los átomos en otro orden, como la escribe Meeko, y las
    coordenadas de sus átomos pesados en el orden del SMILES."""
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=semilla)
    n = Chem.MolFromSmiles(smiles).GetNumAtoms()  # AddHs añade los H al final
    pesados = mol.GetConformer().GetPositions()[:n].copy()
    orden = list(range(mol.GetNumAtoms()))
    np.random.default_rng(semilla).shuffle(orden)
    barajada = Chem.RenumberAtoms(mol, [int(i) for i in orden])
    return Chem.MolToMolBlock(barajada) + "$$$$\n", pesados


#: Ramas con los mismos elementos y la misma conectividad que sólo distingue el
#: orden de enlace: vinilo y etilo, alquino y etilo, cetona y alcohol, y el C=O y
#: el OH de un carboxilo.
SIMETRIAS_FALSAS = [
    "C#C[C@](C)(O)CC",
    "C=C[C@H](O)CC",
    "CC(=O)C[C@@H](C)CC(O)C",
    "CC(=O)Oc1ccccc1C(=O)O",
]


@pytest.mark.parametrize("smiles", SIMETRIAS_FALSAS)
def test_ramas_que_solo_distingue_el_orden_de_enlace_no_se_confunden(smiles):
    """Casar sólo por conectividad dejaba elegir la rama equivocada si encajaba
    mejor en el dibujo: la misma molécula salía con su centro «invertido» y con
    el doble enlace dibujado entre átomos de la otra rama."""
    for semilla in range(1, 9):
        sdf, pesados = _pose_barajada(smiles, semilla)

        modelo = modelo_desde_pose(smiles, sdf)

        assert modelo["pose"]["estereo"]["invertidos"] == [], semilla
        # Átomo a átomo, no ordenadas: cada átomo del dibujo recibe SU posición.
        origen = _distancias(pesados)
        mostrado = _distancias(_xyz_y_arriba(modelo))
        escala = mostrado.max() / origen.max()
        assert np.allclose(mostrado, origen * escala, rtol=2e-3, atol=0.05), semilla


def test_una_sal_se_levanta_con_el_fragmento_que_se_acoplo():
    """El SMILES guardado conserva el contraión y el validador lo quita antes de
    acoplar. La pose se casa con el fragmento acoplado y el contraión se declara."""
    sal = "OC(=O)C(O)C(O)C(=O)O.CN1CCC[C@H]1c1cccnc1"
    sdf, _ = _sdf_girado("CN1CCC[C@H]1c1cccnc1")

    modelo = modelo_desde_pose(sal, sdf)

    nicotina = list(range(10, 22))  # el tartrato ocupa los diez primeros átomos
    assert [a["elemento"] for a in modelo["atomos"]] == [
        Chem.MolFromSmiles(sal).GetAtomWithIdx(i).GetSymbol() for i in nicotina]
    # El instante inicial sigue siendo la miniatura, que dibuja la sal entera.
    lienzo = dibujo_2d(Chem.MolFromSmiles(sal)).lienzo
    assert np.allclose([a["plano"] for a in modelo["atomos"]], lienzo[nicotina], atol=0.01)
    assert all(0 <= e["a"] < 12 and 0 <= e["b"] < 12 for e in modelo["enlaces"])
    assert modelo["pose"]["contraiones"] == ["O=C(O)C(O)C(O)C(=O)O"]
    assert modelo["pose"]["estereo"]["conservados"] == 1


def test_la_carga_de_una_sal_se_mide_en_el_fragmento_acoplado():
    sdf, _ = _sdf_girado("CC[NH3+]")

    especie = modelo_desde_pose("CC[NH3+].[Cl-]", sdf)["pose"]["especie"]

    assert especie == {"carga_smiles": 1, "carga_acoplada": 1}


def test_sin_contraion_no_se_declara_ninguno():
    sdf, _ = _sdf_girado(ALANINA_S)

    assert modelo_desde_pose(ALANINA_S, sdf)["pose"]["contraiones"] == []
