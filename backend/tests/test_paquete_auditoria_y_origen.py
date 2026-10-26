"""El paquete lleva la auditoría de preparación y la estructura de origen (punto 3, 2026-10-10).

Faltaban las dos piezas que un tercero necesita para partir de aquí:

1. **La auditoría.** El ZIP llevaba el dossier y los artefactos, pero no lo que la
   pestaña Preparación dice de la corrida: qué bloqueaba, qué pedía revisión y qué
   decidió el investigador. Quien recibía el paquete tenía que recalcularlo, y no
   podía: el cálculo necesita el disco de quien lo generó.
2. **El crudo depositado.** El paquete llevaba el PDBQT recortado del receptor. Un
   cálculo con disolvente explícito parte de las cadenas enteras del archivo
   depositado, que no viajaba. Va sólo si recalculando `receptor_recipe_hash` con él
   sale la receta de la corrida: sin esa comprobación sería «un PDB con el mismo
   nombre» y el paquete afirmaría una procedencia que no tiene.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from services.dossier.contexto_estructural import origen_comprobado
from services.dossier.model import build_case_dossier
from services.dossier.package import construir_paquete
from services.dossier.pdf import render_dossier_pdf
from services.dossier.preparacion import build_preparacion
from tests.test_preparacion_auditoria import _con_procedencia
from tests.test_diff_de_especies_de_la_corrida import _diff


def _paquete(preparacion=None) -> dict[str, bytes]:
    caso = _con_procedencia(_diff())
    dossier = build_case_dossier(**caso)
    datos, _, raiz = construir_paquete(
        dossier=dossier,
        pdf_bytes=render_dossier_pdf(dossier).getvalue(),
        projection_json=caso["projection"].model_dump_json(indent=2),
        preparacion=preparacion,
    )
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        return {nombre[len(raiz) + 1:]: zf.read(nombre) for nombre in zf.namelist()}


def _auditoria() -> dict:
    caso = _con_procedencia(_diff())
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])


# ── 1 · La auditoría ─────────────────────────────────────────────────


def test_el_paquete_lleva_la_auditoria_tal_como_la_enseña_la_pestaña():
    auditoria = _auditoria()
    contenido = _paquete(auditoria)

    assert json.loads(contenido["preparacion/audit.json"]) == json.loads(json.dumps(auditoria))
    declarado = next(f for f in json.loads(contenido["manifest.json"])["files"]
                     if f["path"] == "preparacion/audit.json")
    assert declarado["rol"] == "auditoria_de_preparacion"
    assert declarado["estado"] == "REGISTRADO"


def test_el_manifiesto_resume_el_veredicto_sin_tener_que_abrir_la_auditoria():
    auditoria = _auditoria()
    manifiesto = json.loads(_paquete(auditoria)["manifest.json"])

    assert manifiesto["preparacion"] == {
        "estado": auditoria["estado"],
        "bloqueantes": auditoria["bloqueantes"],
        "en_revision": auditoria["en_revision"],
        "en_revision_rutinaria": auditoria["en_revision_rutinaria"],
        "decididos": auditoria["decididos"],
    }
    # El veredicto del manifiesto es el de la auditoría que va dentro, no un resumen aparte.
    assert manifiesto["preparacion"]["estado"] in ("BLOQUEADO", "REVISION", "TRANSFERIBLE")


def test_sin_auditoria_no_se_declara_una_ausencia_que_nadie_intento():
    contenido = _paquete(None)
    assert "preparacion/audit.json" not in contenido
    manifiesto = json.loads(contenido["manifest.json"])
    assert all(f["path"] != "preparacion/audit.json" for f in manifiesto["files"])
    assert "preparacion" not in manifiesto


def test_el_readme_declara_la_carpeta():
    assert "preparacion/" in _paquete(_auditoria())["README.md"].decode("utf-8")


# ── 2 · El crudo depositado ──────────────────────────────────────────


class _Corrida:
    """Lo mínimo que `origen_comprobado` lee de una corrida."""

    def __init__(self, receta: str):
        self.docking_protocol = {"execution_provenance": {
            "box_center": [1.0, 2.0, 3.0], "box_size": [20.0, 20.0, 20.0],
            "receptor_prep": {"recipe_hash": receta, "chain": "A", "site_chains": ["A"]},
        }}


@pytest.fixture
def deposito(tmp_path, monkeypatch):
    """Un crudo en disco, con la receta que la preparación calcularía para él."""
    from services.docking import preparer

    archivo = tmp_path / "1ABC.pdb"
    archivo.write_text("HEADER    HYDROLASE\nATOM      1  CA  ALA A   1      0.000   0.000   0.000\nEND\n")
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: archivo)
    # Los bytes, como los lee la auditoría: `read_text` traduciría los saltos de línea
    # en Windows y daría otra receta.
    receta = preparer.receptor_recipe_hash(
        archivo.read_bytes().decode("utf-8"), chains={"A"}, cofactors_whitelist=None,
        center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0), site_ligand=None,
    )
    return archivo, receta


def test_el_crudo_va_con_su_hash_cuando_la_receta_coincide(deposito):
    import hashlib

    archivo, receta = deposito
    comprobado = origen_comprobado(_Corrida(receta), "1ABC")

    assert comprobado.datos == archivo.read_bytes()
    assert comprobado.sha256 == hashlib.sha256(archivo.read_bytes()).hexdigest()
    assert comprobado.nombre == "1ABC.pdb"
    assert comprobado.cadenas == {"A"}


def test_otro_archivo_con_el_mismo_nombre_no_entra(deposito):
    _, receta = deposito
    razon = origen_comprobado(_Corrida("f" * 64), "1ABC")
    assert isinstance(razon, str)
    assert razon.startswith("El archivo de origen no es el que preparó el receptor de esta corrida")
    # Y con la receta buena sí entra: lo que decide es la receta, no el nombre.
    assert not isinstance(origen_comprobado(_Corrida(receta), "1ABC"), str)


def test_sin_receta_o_sin_archivo_se_dice_por_que(monkeypatch):
    from services.docking import preparer

    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: None)
    assert origen_comprobado(_Corrida("a" * 64), "1ABC") == "No se encontró el archivo de origen del receptor"
    sin_receta = _Corrida("a" * 64)
    sin_receta.docking_protocol["execution_provenance"]["receptor_prep"] = {}
    assert origen_comprobado(sin_receta, "1ABC") == "La corrida no registró la receta del receptor o la caja"
    assert origen_comprobado(_Corrida("a" * 64), None) == "La corrida no registró la receta del receptor o la caja"


def test_la_razon_de_la_ausencia_se_lee_en_ingles(deposito):
    from core.i18n_plantillas import _PARECE_CASTELLANO, traducir

    for razon in ("No se encontró el archivo de origen del receptor",
                  "La corrida no registró la receta del receptor o la caja",
                  "El archivo de origen no es el que preparó el receptor de esta corrida "
                  "(la receta no coincide)",
                  "No se pudo comprobar la estructura de origen del receptor"):
        en = traducir(razon, "en")
        assert en != razon and not _PARECE_CASTELLANO.search(en), razon
