"""Los avisos de la preparación salen enteros en inglés, o enteros en castellano, nunca a medias.

# Qué se midió (2026-10-09, entrega de receptores propios)

El arnés de la subida encontró seis textos en castellano en la versión inglesa, anteriores a ese
trabajo y emitidos también para receptores del catálogo con metales junto al sitio o ligandos
quirales sin estereoquímica: los residuos que Meeko retira, las cadenas laterales truncadas, los
cofactores lejos del sitio, la estereoquímica sin declarar, los metales retirados («NA (2 átomos)»)
y las especies retiradas («La preparación retira …»). Casi todos tenían la frase de fuera
traducida y la lista de dentro no: `{lista}` y `{frase}` traducen ahora lo capturado elemento a
elemento, y si algo queda en castellano la plantilla no se aplica.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.i18n_plantillas import _PARECE_CASTELLANO, _partir_lista, traducir
from services.docking.ligand_state_warnings import avisos_estado_ligando

BACKEND = Path(__file__).resolve().parents[1]


def _ingles(texto: str) -> str:
    en = traducir(texto, "en")
    assert en != texto, texto
    assert not _PARECE_CASTELLANO.search(en), en
    return en


@pytest.mark.parametrize("es, en", [
    ("Meeko eliminó residuos del receptor fuera del margen crítico: A:12 HOH (14.2 Å de la caja), "
     "B:301 SO4 (15.0 Å de la caja).",
     "Meeko removed receptor residues outside the critical margin: A:12 HOH (14.2 Å from the box), "
     "B:301 SO4 (15.0 Å from the box)."),
    ("El cristal no resolvía 3 cadena(s) lateral(es); se truncaron a ALA o GLY, conservando sólo átomos "
     "observados. EN EL SITIO, así que la cavidad acoplada pierde esos grupos: A:45 LYS→ALA (3.2 Å).",
     "The crystal did not resolve 3 side chain(s); they were truncated to ALA or GLY, keeping only the observed "
     "atoms. IN THE SITE, so the docked cavity loses those groups: A:45 LYS→ALA (3.2 Å)."),
    ("El cristal no resolvía 2 cadena(s) lateral(es); se truncaron a ALA o GLY, conservando sólo átomos "
     "observados, todas fuera del sitio.",
     "The crystal did not resolve 2 side chain(s); they were truncated to ALA or GLY, keeping only the observed "
     "atoms, all outside the site."),
    ("Cofactores o residuos modificados sin plantilla Meeko validada, lejos del sitio: HEM A:500 "
     "(14.2 Å de la caja, retirado), NAG B:601 (22.0 Å de la caja, retirado). No forman parte de la cavidad acoplada.",
     "Cofactors or modified residues without a local Meeko template, far from the site: HEM A:500 "
     "(14.2 Å from the box, removed), NAG B:601 (22.0 Å from the box, removed). They are not part of the docked cavity."),
    ("Se eliminan 3 átomos metálicos antes del acoplamiento: NA (2 átomos), ZN (1 átomo).",
     "3 metal atoms are removed before docking: NA (2 atoms), ZN (1 atom)."),
    ("La preparación retira 120 átomos de agua, 2 átomos metálicos, 31 átomos de cofactor orgánico.",
     "Preparation removes 120 water atoms, 2 metal atoms, 31 organic cofactor atoms."),
])
def test_cada_aviso_sale_entero_en_ingles(es, en):
    assert _ingles(es) == en


def test_la_estereoquimica_sin_declarar_sale_en_ingles():
    for estereo in (
        {"centros_sin_asignar": 1, "dobles_sin_asignar": 0, "smiles_3d_efectivo": "C[C@H](N)C(=O)O"},
        {"centros_sin_asignar": 2, "dobles_sin_asignar": 1, "smiles_3d_efectivo": None, "dobles_sin_clasificar_3d": 1},
    ):
        avisos = avisos_estado_ligando({"estereoquimica": estereo})
        mensajes = [a["mensaje"] for a in avisos if a["codigo"] == "ESTEREOQUIMICA_NO_DECLARADA"]
        assert len(mensajes) == 1
        _ingles(mensajes[0])


def test_lo_que_no_tiene_traduccion_queda_entero_en_castellano():
    """Una lista con un elemento desconocido no produce una frase inglesa con castellano dentro."""
    texto = "Se eliminan 2 átomos metálicos antes del acoplamiento: NA (2 átomos), algo raro sin plantilla."
    assert traducir(texto, "en") == texto


def test_una_lista_se_parte_sólo_fuera_de_los_paréntesis():
    assert _partir_lista("HEM A:500 (14.2 Å de la caja, retirado), NAG B:601 (22.0 Å)") == [
        "HEM A:500 (14.2 Å de la caja, retirado)", "NAG B:601 (22.0 Å)"]


@pytest.mark.parametrize("archivo, literal", [
    ("services/docking/vina_service.py", "Meeko eliminó residuos del receptor fuera del margen crítico: "),
    ("services/docking/vina_service.py", "Å de la caja)"),
    ("services/docking/vina_service.py", "El cristal no resolvía "),
    ("services/docking/vina_service.py", "se truncaron a "),
    ("services/docking/vina_service.py", "Å de la caja, {row['action']})"),
    ("services/docking/preparer_respetando.py", '"action": "retirado"'),
    ("services/docking/preflight.py", "átomos metálicos antes del acoplamiento"),
    ("services/docking/preflight.py", '"La preparación retira " + ", ".join(parts) + "."'),
])
def test_los_formatos_de_las_pruebas_son_los_que_emite_el_codigo(archivo, literal):
    """Si el código cambia el formato, esta prueba avisa de que las de arriba ya no lo representan."""
    assert literal in (BACKEND / archivo).read_text(encoding="utf-8"), (archivo, literal)
