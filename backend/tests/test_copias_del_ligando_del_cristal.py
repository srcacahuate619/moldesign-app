"""Otra copia del ligando del cristal no es «el ligando»: se declara.

FEP-06-PRE-2 (P09, 6SXC) encontró dos 4-hidroxitamoxifenos en la cadena A, OHT A:305 y OHT A:307, a 3,32 Å. El diff de
especies clasificaba como ligando del sitio todo residuo con ese código CCD, la preparación no informa del ligando del
cristal, y la auditoría decía «Ninguna retirada a 6 Å o menos del ligando». En el catálogo, 14 de 381 entradas tienen otra
copia a 6 Å o menos.

Lo que fijan estas pruebas:

1. Sólo la copia más cercana al centro de la caja es el ligando del sitio, sea cual sea su número de residuo; es la misma que
   `contexto_estructural` toma como referencia.
2. Las demás se retiran igual, pero cuentan como otra especie y lo dicen (`site_ligand_copy`).
3. Junto al sitio, la auditoría pide revisión y nombra la copia, en castellano y en inglés.
4. La distancia de una copia es al ligando del cristal, no a la pose, como la de metales y cofactores: en 7JVU, SHH A:404
   está a 0,31 Å de la pose de la corrida y a 3,21 Å de SHH B:404.
"""

from __future__ import annotations

from services.docking import preflight, preparer
from services.dossier.contexto_estructural import ContextoEstructural
from services.dossier.localization import traducir_dossier
from tests.test_diff_de_especies_de_la_corrida import CAJA, CENTRO, _atomo
from tests.test_preparacion_auditoria import _con_procedencia, _requisito
from tests.test_preparacion_desde_el_ligando import _auditar

ESTRUCTURA = "\n".join([
    _atomo("ATOM", 1, "N", "ALA", "A", 1, 1.0, 0.0, 0.0, "N"),
    _atomo("ATOM", 2, "CA", "ALA", "A", 1, 2.0, 0.0, 0.0, "C"),
    # La copia con el número MÁS BAJO está más lejos del centro: la referencia se elige por distancia, no por orden.
    _atomo("HETATM", 3, "C1", "LIG", "A", 601, 0.0, 0.0, 4.3, "C"),
    _atomo("HETATM", 4, "C1", "LIG", "A", 605, 0.0, 0.0, 1.0, "C"),
    # Una tercera copia lejos de la caja: no entra en `near_site`.
    _atomo("HETATM", 5, "C1", "LIG", "A", 609, 0.0, 60.0, 0.0, "C"),
    "END",
]) + "\n"


def _diff() -> dict:
    entrada = preparer.filter_pdb_content(ESTRUCTURA, chain_id={"A"}, keep_hetatm=True, cofactors_whitelist=[],
                                          site_ligand="LIG")
    return preflight.diff_de_especies_de_la_corrida(ESTRUCTURA, entrada, cadenas="A", center=CENTRO, size=CAJA,
                                                    site_ligand="LIG")


def _fila(diff: dict, numero: str) -> dict:
    return next(f for f in diff["near_site"]["removed"] if f["residue_number"] == numero)


def test_solo_la_copia_mas_cercana_es_el_ligando_del_sitio():
    diff = _diff()
    referencia, copia = _fila(diff, "605"), _fila(diff, "601")
    assert referencia["category"] == "site_ligand" and "site_ligand_copy" not in referencia
    assert copia["category"] == "other_heteroatom" and copia["site_ligand_copy"] is True
    assert {f["residue_number"] for f in diff["near_site"]["removed"]} == {"601", "605"}


def test_con_una_sola_copia_no_cambia_nada():
    estructura = "\n".join(l for l in ESTRUCTURA.splitlines() if " 601 " not in l and " 609 " not in l) + "\n"
    entrada = preparer.filter_pdb_content(estructura, chain_id={"A"}, keep_hetatm=True, cofactors_whitelist=[],
                                          site_ligand="LIG")
    diff = preflight.diff_de_especies_de_la_corrida(estructura, entrada, cadenas="A", center=CENTRO, size=CAJA,
                                                    site_ligand="LIG")
    [fila] = diff["near_site"]["removed"]
    assert fila["category"] == "site_ligand" and "site_ligand_copy" not in fila


def _contexto(distancia_copia: float, al_cristal: float | None = None) -> ContextoEstructural:
    return ContextoEstructural(medido=True, referencia="Pose top-1 y ligando del cristal LIG A:605",
                               especies={("A", "601", "", "LIG"): distancia_copia, ("A", "605", "", "LIG"): 0.0},
                               especies_al_cristal={} if al_cristal is None else {("A", "601", "", "LIG"): al_cristal})


def test_la_auditoria_nombra_la_copia_junto_al_sitio_y_pide_revision():
    caso = _con_procedencia(_diff())
    # La pose cae encima de la copia (0,31 Å), pero la razón da la distancia al cristal (3,21 Å).
    auditoria = _auditar(caso, _contexto(0.31, al_cristal=3.21))
    otras = _requisito(auditoria, "entorno.otras_especies")
    assert otras["estado"] == "REVISAR"
    assert otras["valor"] == "Retiradas a 6 Å o menos del ligando: LIG A:601 (3.21 Å)"
    assert otras["razon"].startswith("Incluye otra(s) copia(s) del ligando del cristal: LIG A:601.")
    ingles = _requisito(traducir_dossier(auditoria, "en"), "entorno.otras_especies")
    assert ingles["valor"] == "Removed within 6 Å of the ligand: LIG A:601 (3.21 Å)"
    assert ingles["razon"].startswith("Includes other copy(ies) of the crystal ligand: LIG A:601.")


def test_una_copia_lejos_se_registra_sin_revision():
    auditoria = _auditar(_con_procedencia(_diff()), _contexto(14.0))
    otras = _requisito(auditoria, "entorno.otras_especies")
    assert otras["estado"] == "REGISTRADO"
    assert otras["valor"] == "Ninguna retirada a 6 Å o menos del ligando; más lejos: LIG A:601 (14 Å)"
