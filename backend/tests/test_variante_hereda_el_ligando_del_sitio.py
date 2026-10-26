"""Una variante de un receptor del catálogo retira el mismo ligando del cristal que su padre.

MET-01 (2026-10-11) lo encontró en 8UBR: el catálogo declara ATP como `site_ligand`, pero `POST /targets/{id}/variants`
no lo pasaba al preparar, y la variante conservaba como cofactor los dos ATP del sitio (70 átomos de A1502/A1503). La
prueba pasa por la API con Meeko real sobre el depósito del catálogo.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest
import pytest_asyncio

from tests.receptores_propios_ayudas import aislar_almacen
from tests.test_target_authorization import _Environment

RAIZ = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture
async def entorno(tmp_path, monkeypatch):
    aislar_almacen(monkeypatch, tmp_path / "almacen")
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


def _residuos(pdbqt: str) -> set[str]:
    return {l[17:20].strip() for l in pdbqt.splitlines() if l.startswith(("ATOM", "HETATM"))}


def test_el_ligando_del_sitio_sale_del_catalogo_o_del_perfil(monkeypatch):
    from services.docking import preparer
    from services.targets import perfil_receptor

    assert preparer.ligando_del_sitio("8UBR") == "ATP"
    monkeypatch.setattr(perfil_receptor, "cargar", lambda pdb_id: {"modo": "automatico", "site_ligand": "atp"})
    assert preparer.ligando_del_sitio("USR_ABC123") == "ATP"
    monkeypatch.setattr(perfil_receptor, "cargar", lambda pdb_id: {"modo": "automatico"})
    assert preparer.ligando_del_sitio("USR_ABC123") is None


@pytest.mark.asyncio
async def test_la_variante_de_8ubr_no_conserva_los_atp_del_sitio(entorno):
    from services.targets import perfil_receptor
    from utils.file_handlers import StoragePath
    from utils.local_storage import path_for

    crudo = gzip.decompress((RAIZ / "data" / "targets" / "8UBR.pdb.gz").read_bytes())
    destino = Path(path_for(StoragePath.target_raw("8UBR")))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(crudo)

    ana = await entorno.user("ana")
    padre = await entorno.target("8UBR")
    async with entorno.factory() as sesion:
        objeto = await sesion.get(type(padre), padre.id)
        objeto.grid_center_x, objeto.grid_center_y, objeto.grid_center_z = 161.76, 151.88, 99.41
        objeto.grid_size_x = objeto.grid_size_y = objeto.grid_size_z = 31.6
        await sesion.commit()

    respuesta = entorno.client(ana).post("/targets/8UBR/variants", json={"name": "8UBR otra caja"})

    assert respuesta.status_code == 201, respuesta.text
    hijo = respuesta.json()
    assert hijo["preparation_recipe"]["site_ligand"] == "ATP"
    assert perfil_receptor.cargar(hijo["pdb_id"])["site_ligand"] == "ATP"
    preparados = sorted(Path(path_for(f"targets/{hijo['pdb_id']}")).glob("prepared-*.pdbqt"))
    assert len(preparados) == 1
    assert "ATP" not in _residuos(preparados[0].read_text(encoding="utf-8"))
