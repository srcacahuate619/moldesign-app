"""Una Cys que coordina un metal conservado es un tiolato: Preparación lo dice si la plantilla le dejó el HG (2026-10-24).

FEP-06-PRE lo encontró en 4NY4 (CYP3A4): la Cys442 axial del hemo quedó como tiol neutro, con HG a 2,54 Å del Fe
(SG–Fe 2,39 Å), y ningún fichero del paquete lo declaraba. Preparación ya avisaba del caso análogo con His.
"""
from __future__ import annotations

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import cys_al_metal
from services.dossier.localization import traducir_dossier
from tests.test_his_que_coordina_un_metal import _linea
from tests.test_preparacion_auditoria import _requisito
from tests.test_preparacion_desde_el_ligando import _auditar, _caso, _contexto


def _pdbqt(*, con_hg: bool, d_fe: float = 2.39, residuo: str = "CYS") -> str:
    """La Cys442 de 4NY4 con su SG frente al Fe del hemo, con o sin el HG del tiol."""
    texto = _linea(1, "CB", residuo, "A", 442, (0.0, 0.0, 0.0), "C")
    texto += _linea(2, "SG", residuo, "A", 442, (1.8, 0.0, 0.0), "SA")
    if con_hg:
        texto += _linea(3, "HG", residuo, "A", 442, (2.2, 1.28, 0.0), "HD")
    texto += _linea(4, "FE", "HEM", "A", 601, (1.8 + d_fe, 0.0, 0.0), "Fe", "HETATM")
    return texto


def test_el_tiol_junto_al_metal_se_detecta():
    assert cys_al_metal(_pdbqt(con_hg=True)) == [("A:442", "SG", "FE HEM A:601", 2.39, True)]


def test_el_tiolato_es_el_estado_correcto():
    assert cys_al_metal(_pdbqt(con_hg=False)) == [("A:442", "SG", "FE HEM A:601", 2.39, False)]
    assert cys_al_metal(_pdbqt(con_hg=False, residuo="CYM")) == [("A:442", "SG", "FE HEM A:601", 2.39, False)]


def test_un_metal_lejos_o_ningun_metal_no_cuenta():
    assert cys_al_metal(_pdbqt(con_hg=True, d_fe=3.5)) == []
    sin_metal = "".join(l for l in _pdbqt(con_hg=True).splitlines(keepends=True) if "HEM" not in l)
    assert cys_al_metal(sin_metal) == []


def test_preparacion_lo_dice_como_revision_del_caso_y_en_ingles():
    contexto = _contexto(plantillas=[])
    contexto.cys_al_metal = [("A:442", "SG", "FE HEM A:601", 2.39, True)]
    auditoria = _auditar(_caso(), contexto)
    protonacion = _requisito(auditoria, "receptor.protonacion")
    assert protonacion["estado"] == "REVISAR"
    assert ("Cys que coordinan un metal conservado como tiol neutro, con el HG en el azufre que lo coordina: "
            "A:442 SG–FE HEM A:601 (2.39 Å).") in protonacion["razon"]
    assert protonacion["accion_recomendada"].startswith("Antes de un cálculo posterior, desprotona esa Cys")
    assert "receptor.protonacion" not in auditoria["en_revision_rutinaria"]
    ingles = _requisito(traducir_dossier(auditoria, "en"), "receptor.protonacion")
    assert "Cys coordinating a retained metal as a neutral thiol" in ingles["razon"]
    assert not _PARECE_CASTELLANO.search(ingles["razon"]), ingles["razon"]
    assert not _PARECE_CASTELLANO.search(ingles["accion_recomendada"]), ingles["accion_recomendada"]


def test_his_y_cys_a_la_vez_dan_las_dos_acciones_y_se_traducen():
    contexto = _contexto(plantillas=[])
    contexto.his_al_metal = [("A:388", "NE2", "FE HEM A:601", 1.87, True)]
    contexto.cys_al_metal = [("A:442", "SG", "ZN ZN A:700", 2.31, True)]
    protonacion = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")
    assert "protona esa His" in protonacion["accion_recomendada"]
    assert "desprotona esa Cys" in protonacion["accion_recomendada"]
    ingles = _requisito(traducir_dossier(_auditar(_caso(), contexto), "en"), "receptor.protonacion")
    assert not _PARECE_CASTELLANO.search(ingles["accion_recomendada"]), ingles["accion_recomendada"]


def test_con_el_tiolato_preparacion_no_anade_nada():
    contexto = _contexto(plantillas=[])
    contexto.cys_al_metal = [("A:442", "SG", "FE HEM A:601", 2.39, False)]
    protonacion = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")
    assert "tiol neutro" not in protonacion["razon"]
    assert not protonacion.get("accion_recomendada")
