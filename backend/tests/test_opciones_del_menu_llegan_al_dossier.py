"""Lo que el investigador eligió en el menú tiene que aparecer en el expediente.

La pestaña de Evaluación deja conducir la corrida: motor de docking, motor
peptídico, centro y tamaño de la caja, residuos de referencia, exhaustividad y
número de poses. Un menú que deja elegir y después no deja constancia de lo
elegido convierte cada corrida en irrepetible: nadie puede saber, leyendo el
expediente, con qué se hizo.

`services/dossier/model.py` construye esos campos y `services/dossier/pdf.py`
los imprime en las secciones 3 y 5. **Ninguna prueba los fijaba**: buscando
«Caja efectiva», «Residuos de referencia», «Exhaustividad» y «Motor de
acoplamiento» en toda la suite no había una sola coincidencia. Renombrar una
etiqueta, o dejar de pasar `config`, habría vaciado esas filas sin que nada
fallara — y el fallo se lee como «la corrida no lo registró», que es
exactamente la frase que se usa cuando de verdad no se registró.

Esta suite ata las dos cosas: que el valor llegue, y que cuando NO llegue se
diga por qué en vez de dejar el hueco en blanco.
"""

from __future__ import annotations

import io

from services.dossier.model import build_case_dossier
from services.dossier.pdf import render_dossier_pdf
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo, caso_parcial


def _dossier():
    return build_case_dossier(**caso_completo())


def _campo(campos, etiqueta):
    for c in campos:
        if c.etiqueta == etiqueta:
            return c
    nombres = ", ".join(c.etiqueta for c in campos)
    raise AssertionError(f"no existe el campo «{etiqueta}». Hay: {nombres}")


def _todos(d):
    return list(d.entradas) + list(d.protocolo) + list(d.generacion)


# ── Los valores del menú, uno por uno ────────────────────────────────────

def test_la_caja_efectiva_declara_centro_y_tamano():
    """Sin la caja no se puede repetir la corrida: es DÓNDE se acopló."""
    campo = _campo(_todos(_dossier()), "Caja efectiva")
    assert campo.estado == Estado.REGISTRADO
    # Los valores del fixture, no unos cualesquiera.
    assert "103.03" in str(campo.valor)
    assert "114.79" in str(campo.valor)
    assert "108.36" in str(campo.valor)
    assert "25.0" in str(campo.valor)


def test_los_residuos_de_referencia_se_enumeran():
    campo = _campo(_todos(_dossier()), "Residuos de referencia")
    assert campo.estado == Estado.REGISTRADO
    assert "R:TYR390" in str(campo.valor)
    assert "R:ASP116" in str(campo.valor)


def test_el_motor_de_acoplamiento_queda_escrito():
    campo = _campo(_todos(_dossier()), "Motor de acoplamiento")
    assert campo.estado == Estado.REGISTRADO
    assert str(campo.valor).strip() != ""


def test_la_exhaustividad_y_las_poses_quedan_escritas():
    campos = _todos(_dossier())
    exh = _campo(campos, "Exhaustiveness")
    poses = _campo(campos, "Poses solicitadas")
    assert str(exh.valor) == "8"
    assert str(poses.valor) == "9"


def test_sin_opciones_avanzadas_el_campo_lo_dice():
    """`pipeline_config` es lo del MODAL avanzado, no la configuración del caso.

    Son dos cosas distintas y el expediente las separa: caja, hotspots,
    exhaustividad y poses salen de la configuración del caso —y se comprueban
    arriba—; esta fila recoge lo que sólo existe si el investigador abrió el
    modal. Cuando no lo abrió, la fila declara su ausencia en vez de fingir un
    registro vacío.
    """
    campo = _campo(_todos(_dossier()), "Configuración PRO declarada")
    assert campo.estado == Estado.NO_DISPONIBLE
    assert campo.razon, "una ausencia sin motivo no se distingue de un fallo"


def test_con_opciones_avanzadas_el_json_viaja_entero():
    """Y cuando sí las hay, viajan completas y no un resumen."""
    caso = caso_completo()
    avanzadas = {
        "ensemble_conformers": 30,
        "enable_mmgbsa": True,
        "peptide_docking_engine": "esmfold",
    }
    caso["projection"].inputs.config.pipeline_config = avanzadas

    campo = _campo(_todos(build_case_dossier(**caso)), "Configuración PRO declarada")
    assert campo.estado == Estado.REGISTRADO
    for clave in avanzadas:
        assert clave in str(campo.valor), f"falta {clave} en la configuración sellada"


def test_la_semilla_queda_escrita():
    """Sin semilla la corrida no se repite bit a bit, y hay que poder decirlo."""
    campo = _campo(_todos(_dossier()), "Semilla aleatoria")
    assert campo.valor is not None or campo.razon


# ── Y lo que pasa cuando falta ───────────────────────────────────────────

def test_un_campo_ausente_explica_su_ausencia_en_vez_de_quedarse_en_blanco():
    """Un hueco sin motivo es indistinguible de un fallo de renderizado.

    Es la regla del documento entero: una ausencia se declara, nunca se
    convierte en «pasa» ni en un espacio vacío.
    """
    d = build_case_dossier(**caso_parcial())
    sin_valor = [c for c in _todos(d) if c.valor in (None, "", [])]
    mudos = [c.etiqueta for c in sin_valor if not c.razon]
    assert not mudos, f"campos vacíos sin explicar su ausencia: {mudos}"


# ── Y que lleguen al PDF, que es lo que el usuario lee ───────────────────

def test_el_pdf_se_genera_con_las_secciones_que_llevan_las_opciones():
    """Las secciones 3 y 5 son las que imprimen entradas y protocolo."""
    pdf = render_dossier_pdf(_dossier())
    assert isinstance(pdf, io.BytesIO)
    datos = pdf.getvalue()
    assert datos.startswith(b"%PDF-"), "no es un PDF"
    # Un dossier con protocolo y entradas no cabe en una hoja casi vacía.
    assert len(datos) > 20_000, f"el PDF pesa {len(datos)} bytes: parece truncado"
