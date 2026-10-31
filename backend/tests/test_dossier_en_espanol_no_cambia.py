"""La capa de traducción no puede alterar la salida española existente."""

import pytest

from tests.dossier_snapshot import (
    DEPENDEN_DE_REPORTLAB,
    SNAPSHOT_DIR,
    fuente_de_la_instantanea,
    reportlab_de_este_interprete,
    reportlab_del_runtime,
    salidas_espanol,
)


@pytest.fixture(scope="module")
def actuales():
    return salidas_espanol()


@pytest.mark.parametrize("nombre", ["dossier.json", "README.md", "manifest.json"])
def test_dossier_en_espanol_no_cambia(actuales, nombre):
    assert SNAPSHOT_DIR.is_dir(), "faltan las instantáneas españolas de la Fase 0"
    if nombre in DEPENDEN_DE_REPORTLAB and reportlab_de_este_interprete() != reportlab_del_runtime():
        pytest.skip(f"{nombre} lleva el hash del PDF, que depende de reportlab: la instantánea se fija con "
                    f"la {reportlab_del_runtime()} del runtime distribuido y este intérprete trae "
                    f"la {reportlab_de_este_interprete()}")
    if nombre in DEPENDEN_DE_REPORTLAB and not fuente_de_la_instantanea():
        pytest.skip(f"{nombre} lleva el hash del PDF, y la instantánea se fija con Arial, que sólo está en Windows")
    ruta = SNAPSHOT_DIR / nombre
    assert ruta.is_file(), f"falta la instantánea {nombre}"
    assert ruta.read_bytes() == actuales[nombre], f"la salida española cambió: {nombre}"


def test_las_salidas_protegidas_son_las_que_se_comparan(actuales):
    assert set(actuales) == {"dossier.json", "README.md", "manifest.json"}
    assert DEPENDEN_DE_REPORTLAB <= set(actuales)
