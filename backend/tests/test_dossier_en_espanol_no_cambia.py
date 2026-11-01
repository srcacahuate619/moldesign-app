"""La capa de traducción no puede alterar la salida española existente."""

import json

import pytest

from tests.dossier_snapshot import (
    DEPENDEN_DE_REPORTLAB,
    SNAPSHOT_DIR,
    manifiesto_sin_el_pdf,
    mismo_pdf_que_la_instantanea,
    salidas_espanol,
)


@pytest.fixture(scope="module")
def actuales():
    return salidas_espanol()


@pytest.mark.parametrize("nombre", ["dossier.json", "README.md", "manifest.json"])
def test_dossier_en_espanol_no_cambia(actuales, nombre):
    assert SNAPSHOT_DIR.is_dir(), "faltan las instantáneas españolas de la Fase 0"
    ruta = SNAPSHOT_DIR / nombre
    assert ruta.is_file(), f"falta la instantánea {nombre}"
    if nombre in DEPENDEN_DE_REPORTLAB and not mismo_pdf_que_la_instantanea():
        # Con otra Arial u otro reportlab el PDF no puede dar el mismo hash, pero el resto del manifiesto sí.
        assert manifiesto_sin_el_pdf(actuales[nombre]) == manifiesto_sin_el_pdf(ruta.read_bytes()), \
            f"la salida española cambió: {nombre}"
        return
    assert ruta.read_bytes() == actuales[nombre], f"la salida española cambió: {nombre}"


def test_las_salidas_protegidas_son_las_que_se_comparan(actuales):
    assert set(actuales) == {"dossier.json", "README.md", "manifest.json"}
    assert DEPENDEN_DE_REPORTLAB <= set(actuales)


def test_sin_el_pdf_sigue_viendo_todo_lo_demas():
    base = (SNAPSHOT_DIR / "manifest.json").read_bytes()
    otro_pdf = json.loads(base)
    pdf = next(entrada for entrada in otro_pdf["files"] if entrada["path"] == "dossier.pdf")
    pdf["sha256"], pdf["tamano"] = "0" * 64, 1
    assert manifiesto_sin_el_pdf(json.dumps(otro_pdf).encode()) == manifiesto_sin_el_pdf(base)
    # Control negativo: cualquier otro hash sigue contando.
    otro_readme = json.loads(base)
    readme = next(entrada for entrada in otro_readme["files"] if entrada["path"] == "README.md")
    readme["sha256"] = "0" * 64
    assert manifiesto_sin_el_pdf(json.dumps(otro_readme).encode()) != manifiesto_sin_el_pdf(base)
