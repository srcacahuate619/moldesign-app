"""Una His que coordina un metal conservado no puede llevar H en el nitrógeno que lo coordina (2026-10-11).

En las COX del catálogo, la His388 proximal coordina por NE2 el hierro del hemo conservado, y la plantilla de Meeko
le pone HIE: el H justo en ese NE2. Medido sobre los 368 receptores preparados por el barrido del 2026-10-11: 9 His
coordinan un metal conservado y 8 llevan el H en el nitrógeno coordinante (1Q4G, 2OYE, 2OYU, 3N8W, 3N8X, 3N8Y,
4O1Z, 5WBE). Cambiar la plantilla movería la receta 7 de esas entradas; Preparación lo mide y lo dice.
"""
from __future__ import annotations

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import his_al_metal
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_auditoria import _requisito
from tests.test_preparacion_desde_el_ligando import _auditar, _caso, _contexto


def _linea(n: int, nombre: str, residuo: str, cadena: str, numero: int, xyz: tuple[float, float, float],
           tipo: str, registro: str = "ATOM") -> str:
    return (f"{registro:<6}{n:5d} {nombre:<4} {residuo:>3} {cadena}{numero:4d}    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00    +0.000 {tipo:<2}\n")


def _pdbqt(*, h_en: str | None, d_fe: float = 2.0) -> str:
    """Una His cuyo NE2 mira al Fe de un hemo, con el H polar en `h_en` (o sin él)."""
    texto = _linea(1, "CG", "HIS", "A", 388, (0.0, 0.0, 0.0), "A")
    texto += _linea(2, "ND1", "HIS", "A", 388, (1.2, 0.7, 0.0), "NA" if h_en != "ND1" else "N")
    texto += _linea(3, "NE2", "HIS", "A", 388, (2.2, -0.7, 0.0), "NA" if h_en != "NE2" else "N")
    if h_en == "ND1":
        texto += _linea(4, "HD1", "HIS", "A", 388, (1.4, 1.7, 0.0), "HD")
    if h_en == "NE2":
        texto += _linea(4, "HE2", "HIS", "A", 388, (3.0, -1.3, 0.0), "HD")
    texto += _linea(5, "FE", "HEM", "A", 601, (2.2 + d_fe, -0.7, 0.0), "Fe", "HETATM")
    return texto


def test_el_h_en_el_nitrogeno_que_coordina_se_detecta():
    assert his_al_metal(_pdbqt(h_en="NE2")) == [("A:388", "NE2", "FE HEM A:601", 2.0, True)]


def test_el_h_en_el_otro_nitrogeno_es_el_estado_correcto():
    assert his_al_metal(_pdbqt(h_en="ND1")) == [("A:388", "NE2", "FE HEM A:601", 2.0, False)]


def test_un_metal_lejos_o_ningun_metal_no_cuenta():
    assert his_al_metal(_pdbqt(h_en="NE2", d_fe=3.5)) == []
    sin_metal = "".join(l for l in _pdbqt(h_en="NE2").splitlines(keepends=True) if "HEM" not in l)
    assert his_al_metal(sin_metal) == []


def test_el_nitrogeno_aceptor_no_se_confunde_con_el_sodio():
    """«NA» es el tipo del N aceptor en un PDBQT: no es un metal."""
    texto = _pdbqt(h_en="NE2").replace(" Fe\n", " NA\n")
    assert his_al_metal(texto) == []


def test_preparacion_lo_dice_como_revision_del_caso_y_en_ingles():
    contexto = _contexto(plantillas=[])
    contexto.his_al_metal = [("A:388", "NE2", "FE HEM A:601", 1.87, True)]
    auditoria = _auditar(_caso(), contexto)
    protonacion = _requisito(auditoria, "receptor.protonacion")
    assert protonacion["estado"] == "REVISAR"
    assert ("His que coordinan un metal conservado con el hidrógeno en el nitrógeno que lo coordina: "
            "A:388 NE2–FE HEM A:601 (1.87 Å). Ese estado no existe") in protonacion["razon"]
    assert protonacion["accion_recomendada"].startswith("Antes de un cálculo posterior, protona esa His")
    assert "receptor.protonacion" not in auditoria["en_revision_rutinaria"]
    ingles = _requisito(traducir_dossier(auditoria, "en"), "receptor.protonacion")
    assert "His coordinating a retained metal with the hydrogen on the coordinating nitrogen" in ingles["razon"]
    assert not _PARECE_CASTELLANO.search(ingles["razon"]), ingles["razon"]
    assert not _PARECE_CASTELLANO.search(ingles["accion_recomendada"]), ingles["accion_recomendada"]


def test_con_el_estado_correcto_preparacion_no_anade_nada():
    contexto = _contexto(plantillas=[])
    contexto.his_al_metal = [("A:388", "NE2", "FE HEM A:601", 1.87, False)]
    protonacion = _requisito(_auditar(_caso(), contexto), "receptor.protonacion")
    assert "coordinan un metal" not in protonacion["razon"]
    assert not protonacion.get("accion_recomendada")
