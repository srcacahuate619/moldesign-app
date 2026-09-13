"""
El panel de anti-dianas acoplaba contra media cavidad en las dos cardíacas.

# Lo que se midió

`preparer.py` deriva el modo multicadena de `site_chains`, que viene de
`curated_targets.json`. El camino principal de evaluación lo pasa; las tres
rutas del panel de anti-dianas no lo pasaban, y usaban `chain: "A"` escrito a
mano en `ANTI_TARGET_PANEL`. Cruzando el panel con el catálogo:

    5VA1  hERG (KCNH2)    panel chain=A   catálogo site_chains ["A","B"]
    4NY4  CYP3A4          panel chain=A   catálogo site_chains ["A"]        ok
    4NC3  5-HT2B          panel chain=A   catálogo site_chains ["A"]        ok
    1SO2  PDE3A           panel chain=A   catálogo site_chains ["A"]        ok
    6MVW  NaV1.5 (SCN5A)  panel chain=A   catálogo site_chains ["C","D","A"]

Dos de cinco, y son las DOS cardíacas: las que existen para detectar la
prolongación del QT que retiró la terfenadina y la cisaprida. El mismo receptor
recibía la cavidad entera como diana principal y un trozo como anti-diana.

Y el endpoint de anti-diana individual, para un receptor que no estuviera en el
panel, fabricaba `center=(0,0,0)` con `size=20³`: eso acopla contra el origen
del sistema de coordenadas y devuelve la afinidad como dato de seguridad.
"""

import json
from pathlib import Path

import pytest

from services.docking.anti_target_sitio import (
    AntiDianaSinSitio,
    SitioDeAntiDiana,
    resolver_sitio_de_anti_diana,
)
from services.docking.selectivity import ANTI_TARGET_PANEL, seleccionar_anti_dianas

RAIZ = Path(__file__).resolve().parents[2]


class _FilaDeCatalogo:
    def __init__(self, **campos):
        self.__dict__.update(campos)


class _RepoFalso:
    def __init__(self, filas: dict):
        self._filas = filas

    async def get_target_by_pdb_id(self, pdb_id):
        return self._filas.get(pdb_id)


HERG = _FilaDeCatalogo(
    pdb_id="5VA1", name="hERG", site_chains=["A", "B"], chain="A",
    grid_center_x=79.1, grid_center_y=68.5, grid_center_z=78.5,
    grid_size_x=24.0, grid_size_y=24.0, grid_size_z=24.0,
    affinity_threshold=-7.0,
)


@pytest.mark.asyncio
async def test_las_cadenas_del_sitio_salen_del_catalogo():
    panel = next(t for t in ANTI_TARGET_PANEL if t["pdb_id"] == "5VA1")
    sitio = await resolver_sitio_de_anti_diana(panel, _RepoFalso({"5VA1": HERG}))
    assert isinstance(sitio, SitioDeAntiDiana)
    assert sitio.site_chains == ["A", "B"], "el sitio de hERG abarca dos cadenas"


@pytest.mark.asyncio
async def test_la_caja_curada_del_panel_manda_sobre_la_del_catalogo():
    """La del panel describe el bolsillo tóxico; la del catálogo, el receptor."""
    panel = next(t for t in ANTI_TARGET_PANEL if t["pdb_id"] == "5VA1")
    sitio = await resolver_sitio_de_anti_diana(panel, _RepoFalso({"5VA1": HERG}))
    assert sitio.center == panel["center"]
    assert sitio.procedencia_caja == "panel"


@pytest.mark.asyncio
async def test_sin_caja_del_panel_se_toma_la_del_catalogo():
    definicion = {"pdb_id": "5VA1", "name": "hERG", "affinity_threshold": -7.0}
    sitio = await resolver_sitio_de_anti_diana(definicion, _RepoFalso({"5VA1": HERG}))
    assert sitio.procedencia_caja == "catalogo"
    assert sitio.center == (79.1, 68.5, 78.5)


@pytest.mark.asyncio
async def test_nunca_se_acopla_contra_el_origen():
    """Era el respaldo del endpoint individual: `center=(0,0,0)`, `size=20³`."""
    desconocida = {
        "pdb_id": "9ZZZ", "name": "Target 9ZZZ",
        "center": (0.0, 0.0, 0.0), "size": (20.0, 20.0, 20.0),
        "affinity_threshold": -7.0,
    }
    sitio = await resolver_sitio_de_anti_diana(desconocida, _RepoFalso({}))
    assert isinstance(sitio, AntiDianaSinSitio)
    assert "caja de acoplamiento calibrada" in sitio.motivo


@pytest.mark.asyncio
async def test_un_receptor_sin_caja_en_ningun_sitio_se_abstiene():
    sin_caja = _FilaDeCatalogo(
        pdb_id="9ZZZ", name="X", site_chains=None, chain="A",
        grid_center_x=None, grid_center_y=None, grid_center_z=None,
    )
    sitio = await resolver_sitio_de_anti_diana(
        {"pdb_id": "9ZZZ", "name": "X"}, _RepoFalso({"9ZZZ": sin_caja})
    )
    assert isinstance(sitio, AntiDianaSinSitio)


# ── La selección: nada se cae en silencio ──────────────────────────────────

@pytest.mark.asyncio
async def test_una_anti_diana_del_usuario_ya_no_se_descarta():
    """`[t for t in ANTI_TARGET_PANEL if …]` tiraba las subidas por el usuario."""
    propia = _FilaDeCatalogo(
        pdb_id="USR_1", name="Mi diana", site_chains=["A"], chain="A",
        grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        affinity_threshold=-6.0, anti_target_risk="riesgo declarado",
    )
    elegidas, desconocidas = await seleccionar_anti_dianas(
        ["5VA1", "USR_1"], _RepoFalso({"USR_1": propia})
    )
    assert [t["pdb_id"] for t in elegidas] == ["5VA1", "USR_1"]
    assert desconocidas == []


@pytest.mark.asyncio
async def test_lo_que_no_existe_se_nombra_en_vez_de_desaparecer():
    elegidas, desconocidas = await seleccionar_anti_dianas(["5VA1", "NOEXISTE"], _RepoFalso({}))
    assert [t["pdb_id"] for t in elegidas] == ["5VA1"]
    assert desconocidas == ["NOEXISTE"], (
        "sin esta lista, el cociente de selectividad se calculaba sobre menos "
        "anti-dianas de las que el usuario marcó, y nada lo decía"
    )


@pytest.mark.asyncio
async def test_sin_seleccion_se_evalua_el_panel_completo():
    elegidas, desconocidas = await seleccionar_anti_dianas(None, _RepoFalso({}))
    assert len(elegidas) == len(ANTI_TARGET_PANEL)
    assert desconocidas == []


# ── El catálogo real: que la corrección siga siendo necesaria ──────────────

def test_el_catalogo_sigue_declarando_multicadena_las_dos_cardiacas():
    """Si esto falla, el catálogo cambió y hay que volver a mirar el panel."""
    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    filas = catalogo if isinstance(catalogo, list) else catalogo.get("targets", catalogo)
    por_id = {f["pdb_id"]: f for f in filas if isinstance(f, dict) and "pdb_id" in f}

    assert len(set(por_id["5VA1"].get("site_chains") or [])) > 1, "hERG"
    assert len(set(por_id["6MVW"].get("site_chains") or [])) > 1, "NaV1.5"

    # Y que ninguna entrada del panel se quede sin comprobar por olvido.
    for entrada in ANTI_TARGET_PANEL:
        assert entrada["pdb_id"] in por_id, (
            f"{entrada['pdb_id']} está en el panel de anti-dianas y no en el "
            f"catálogo: su sitio no se puede resolver y se abstendría siempre."
        )
