"""El visor del editor sitúa en los átomos lo que los detectores del producto ya
saben de la molécula, y dice lo que su geometría implica para Vina.

Lo que se protege:

1. **Los mismos detectores que el resto del producto.** Ojivas covalentes,
   PAINS y especie en revisión salen de `chem/ojivas_covalentes.py`,
   `chem/pains.py` y `chem/especie_en_revision.py`; el visor sólo añade dónde.
2. **En el átomo correcto.** Los índices son los del modelo (el dibujo escrito),
   también en la vista «Se acoplará», donde se detecta sobre la especie
   preparada y se traduce con la correspondencia.
3. **La geometría se declara.** Plana o no, macrociclos que Meeko abre, ΔE del
   conformador elegido, y si la abstención todavía es provisional.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from rdkit import Chem

from chem import router as chem_router
from chem.especie_en_revision import motivos_de_revision
from chem.elevacion import (
    SEMILLAS_CRITERIO,
    modelo_de_la_especie_acoplada,
    modelo_desde_conformador,
)
from chem.ojivas_covalentes import ojivas


def _detectados(modelo: dict, tipo: str) -> list[dict]:
    return [d for d in modelo["detectores"] if d["tipo"] == tipo]


def test_una_acrilamida_se_marca_en_sus_atomos():
    modelo = modelo_desde_conformador("C=CC(=O)NCc1ccccc1")

    ojiva, = _detectados(modelo, "ojiva")
    assert ojiva["nombre"] == "acrilamida (aceptor de Michael)"
    assert ojiva["atomos"] == [0, 1, 2, 3, 4]


def test_los_nombres_de_ojiva_son_los_de_preparacion():
    smiles = "C=CC(=O)NCc1ccc(CCl)cc1C1OC1"

    nombres = {d["nombre"] for d in _detectados(modelo_desde_conformador(smiles), "ojiva")}

    assert nombres == set(ojivas(smiles))


def test_un_pains_se_marca_con_sus_atomos():
    rodanina = "S=C1SC(=Cc2ccccc2)C(=O)N1"

    pains = _detectados(modelo_desde_conformador(rodanina), "pains")

    assert pains
    assert set(pains[0]["atomos"]) <= set(range(Chem.MolFromSmiles(rodanina).GetNumAtoms()))
    assert {0, 1} & set(pains[0]["atomos"])  # el tiocarbonilo de la rodanina


def test_la_especie_en_revision_dice_el_mismo_motivo_y_donde():
    smiles = "CS(=O)(=O)N1CCN(C)CC1"

    revision = _detectados(modelo_desde_conformador(smiles), "especie_en_revision")

    assert [d["codigo"] for d in revision] == [m.codigo for m in motivos_de_revision(smiles)]
    assert revision[0]["codigo"] == "sulfonil_piperazina"
    assert set(revision[0]["atomos"]) >= {1, 4, 7}  # S, N sulfonilado, N distal


def test_en_la_vista_acoplada_se_detecta_sobre_la_especie_preparada_y_en_su_atomo():
    """La amina con un CF3 en β sólo está «en revisión» protonada: la vista escrita
    (neutra) no la marca y la acoplada sí, sobre los átomos del dibujo escrito."""
    smiles = "FC(F)(F)CNCc1ccccc1"

    escrita = _detectados(modelo_desde_conformador(smiles), "especie_en_revision")
    acoplada = _detectados(modelo_de_la_especie_acoplada(smiles), "especie_en_revision")

    assert escrita == []
    assert [d["codigo"] for d in acoplada] == ["amina_con_atractor"]
    assert set(acoplada[0]["atomos"]) >= {1, 4, 5}  # C del CF3, CH2 y N


def test_sin_hallazgos_la_lista_esta_vacia():
    assert modelo_desde_conformador("CCO")["detectores"] == []


def test_la_cafeina_se_declara_plana_y_el_ibuprofeno_no():
    cafeina = modelo_desde_conformador("Cn1cnc2n(C)c(=O)n(C)c(=O)c12")["geometria"]
    ibuprofeno = modelo_desde_conformador("CC(C)Cc1ccc(C(C)C(=O)O)cc1")["geometria"]

    assert cafeina["plana"] is True
    assert cafeina["espesor_A"] < 0.1
    assert ibuprofeno["plana"] is False


def test_un_macrociclo_se_declara_y_un_anillo_pequeno_no():
    assert modelo_desde_conformador("OC1CCCCCCCCCCC1")["geometria"]["macrociclos"] == [12]
    assert modelo_desde_conformador("OC1CCCCC1")["geometria"]["macrociclos"] == []


def test_el_conformador_declara_su_energia_sobre_el_mas_bajo_encontrado():
    modelo = modelo_desde_conformador("CCCCOCCN")

    conformador = modelo["conformador"]
    assert conformador["campo_de_fuerza"] == "MMFF94"
    assert conformador["delta_e_kcal_mol"] >= 0
    # Con un único candidato, el elegido es el más bajo.
    unico = modelo_desde_conformador("CCCCOCCN", conformadores=1, semillas=(1,))
    assert unico["conformador"]["delta_e_kcal_mol"] == 0


def test_con_una_sola_semilla_la_abstencion_es_provisional():
    assert modelo_desde_conformador("CCO", semillas=(1,))["abstencion_provisional"] is True
    assert modelo_desde_conformador("CCO")["abstencion_provisional"] is False


@pytest.mark.asyncio
async def test_la_peticion_rapida_usa_una_semilla_y_lo_dice():
    app = FastAPI()
    app.include_router(chem_router.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cliente:
        rapida = await cliente.post("/chem/elevacion", json={"smiles": "CCO", "rapida": True})
        completa = await cliente.post("/chem/elevacion", json={"smiles": "CCO"})

    assert rapida.json()["conformador"]["semillas"] == [SEMILLAS_CRITERIO[0]]
    assert rapida.json()["abstencion_provisional"] is True
    assert completa.json()["conformador"]["semillas"] == list(SEMILLAS_CRITERIO)


def _pose(smiles: str) -> str:
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=3)
    return Chem.MolToMolBlock(mol) + "$$$$\n"


def test_una_pose_con_el_doble_enlace_al_reves_se_senala():
    from chem.elevacion import modelo_desde_pose

    estereo = modelo_desde_pose("C/C=C/C(=O)O", _pose("C/C=C\C(=O)O"))["pose"]["estereo"]

    assert estereo["dobles_declarados"] == 1
    assert estereo["dobles_invertidos"] == [{"enlace": [1, 2], "smiles": "E", "pose": "Z"}]


def test_una_pose_que_conserva_el_doble_enlace_no_se_senala():
    from chem.elevacion import modelo_desde_pose

    estereo = modelo_desde_pose("C/C=C/C(=O)O", _pose("C/C=C/C(=O)O"))["pose"]["estereo"]

    assert estereo["dobles_declarados"] == 1
    assert estereo["dobles_invertidos"] == []


def test_moldex_lee_la_afinidad_y_la_validez_fisica_de_la_corrida():
    """Se LEE lo que la corrida guardó (como `pose_selection`): recalcularlo
    abriría la puerta a dos respuestas sobre la misma pose."""
    from types import SimpleNamespace

    from chem.elevacion import evidencia_de_la_corrida

    corrida = SimpleNamespace(
        affinity_kcal=-7.9,
        docking_poses=[{"rank": 2, "affinity": -7.1}, {"rank": 1, "affinity": -7.9}],
        structural_evidence={"poses": [
            {"rank": 1, "status": "failed", "label": "NO PASA", "engine": "posebusters",
             "checks_que_fallan": ["internal_steric_clash"]},
            {"rank": 2, "status": "passed", "label": "PASA", "engine": "posebusters", "checks_que_fallan": []},
        ]},
    )

    evidencia = evidencia_de_la_corrida(corrida)

    assert evidencia["afinidad_kcal_mol"] == -7.9
    assert evidencia["validez_fisica"] == {"status": "failed", "label": "NO PASA", "motor": "posebusters",
                                           "comprobaciones_que_fallan": ["internal_steric_clash"]}


def test_una_corrida_sin_evidencia_fisica_no_la_inventa():
    from types import SimpleNamespace

    from chem.elevacion import evidencia_de_la_corrida

    evidencia = evidencia_de_la_corrida(SimpleNamespace(affinity_kcal=None, docking_poses=None,
                                                        structural_evidence=None))

    assert evidencia == {"afinidad_kcal_mol": None, "validez_fisica": None}


# ── Levantar desde el dibujo de Ketcher ───────────────────────────────────────

def _molfile_girado(smiles: str, *, barajar: bool = False, con_h: bool = False) -> tuple[str, Chem.Mol]:
    """Un dibujo «de Ketcher»: coordenadas 2D propias (giradas 90°), en otro orden y,
    si se pide, con hidrógenos explícitos."""
    import numpy as np
    from rdkit.Chem import rdDepictor

    mol = Chem.MolFromSmiles(smiles)
    if con_h:
        mol = Chem.AddHs(mol)
    rdDepictor.Compute2DCoords(mol)
    conf = mol.GetConformer()
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, (-p.y, p.x, 0.0))
    if barajar:
        orden = list(range(mol.GetNumAtoms()))
        np.random.default_rng(5).shuffle(orden)
        mol = Chem.RenumberAtoms(mol, [int(i) for i in orden])
    return Chem.MolToMolBlock(mol), mol


def test_el_dibujo_de_ketcher_es_el_punto_de_partida():
    from chem.elevacion import dibujo_2d

    smiles = "CC(=O)Nc1ccc(O)cc1"
    molfile, dibujada = _molfile_girado(smiles, barajar=True)

    modelo = modelo_desde_conformador(smiles, molfile=molfile)

    assert modelo["dibujo"] == {"fuente": "ketcher", "motivo": None}
    assert [a["elemento"] for a in modelo["atomos"]] == [a.GetSymbol() for a in dibujada.GetAtoms()]
    # El plano es el dibujo recibido, no el de RDKit desde el SMILES.
    propio = dibujo_2d(Chem.MolFromMolBlock(molfile), conservar=True).lienzo
    import numpy as np
    assert np.allclose([a["plano"] for a in modelo["atomos"]], propio, atol=0.01)
    rdkit = dibujo_2d(Chem.MolFromSmiles(smiles)).lienzo
    assert not np.allclose(np.sort(propio, axis=0), np.sort(rdkit, axis=0), atol=5)


def test_los_hidrogenos_dibujados_no_cuentan_como_atomos():
    smiles = "OCC(N)C(=O)O"
    molfile, _ = _molfile_girado(smiles, con_h=True)

    modelo = modelo_desde_conformador(smiles, molfile=molfile)

    assert modelo["dibujo"]["fuente"] == "ketcher"
    assert len(modelo["atomos"]) == Chem.MolFromSmiles(smiles).GetNumAtoms()


def test_un_dibujo_que_no_es_el_smiles_no_se_usa_y_se_dice():
    molfile, _ = _molfile_girado("CCN")

    modelo = modelo_desde_conformador("CCO", molfile=molfile)

    assert modelo["dibujo"]["fuente"] == "rdkit"
    assert modelo["dibujo"]["motivo"]
    assert [a["elemento"] for a in modelo["atomos"]] == ["C", "C", "O"]


def test_un_estereocentro_dibujado_con_cuna_se_respeta():
    smiles = "C[C@H](N)C(=O)O"
    mol = Chem.MolFromSmiles(smiles)
    from rdkit.Chem import rdDepictor
    rdDepictor.Compute2DCoords(mol)
    Chem.WedgeMolBonds(mol, mol.GetConformer())
    molfile = Chem.MolToMolBlock(mol)

    modelo = modelo_desde_conformador(smiles, molfile=molfile)
    contrario = modelo_desde_conformador("C[C@@H](N)C(=O)O", molfile=molfile)

    assert modelo["dibujo"]["fuente"] == "ketcher"
    assert contrario["dibujo"]["fuente"] == "rdkit"  # la cuña dice otro enantiómero


def test_la_vista_acoplada_tambien_parte_del_dibujo():
    smiles = "CC(C)NCC(O)COc1cccc2ccccc12"
    molfile, dibujada = _molfile_girado(smiles, barajar=True)

    modelo = modelo_de_la_especie_acoplada(smiles, molfile=molfile)

    assert modelo["dibujo"]["fuente"] == "ketcher"
    n = next(a.GetIdx() for a in dibujada.GetAtoms() if a.GetSymbol() == "N")
    assert modelo["atomos"][n]["carga"] == 1


@pytest.mark.asyncio
async def test_el_endpoint_acepta_el_dibujo():
    molfile, _ = _molfile_girado("CCO")
    app = FastAPI()
    app.include_router(chem_router.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cliente:
        r = await cliente.post("/chem/elevacion", json={"smiles": "CCO", "molfile": molfile, "rapida": True})

    assert r.json()["dibujo"]["fuente"] == "ketcher"


def test_las_moleculas_medianas_prueban_16_candidatos_por_semilla():
    """Medido en 37 moléculas de 35 a 51 átomos pesados: con 16 se abstienen 8, con 8 se abstenían 16."""
    from chem.elevacion import _candidatos

    assert [_candidatos(n) for n in (30, 45, 60, 61)] == [16, 16, 16, 4]
