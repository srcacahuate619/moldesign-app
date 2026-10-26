"""El inventario AST debe detectar tanto entradas como pendientes nuevos."""

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from inventario_i18n import (  # noqa: E402
    _parece_espanol,
    es_ruta_incluida,
    extraer_plantillas,
    inventariar_fuente,
    pendiente_subio,
)


def test_filtro_detecta_marcas_y_palabras_funcion_y_rechaza_muestras_negativas():
    assert _parece_espanol("La pose conserva la orientación del ligando.")
    assert _parece_espanol("Métricas calculadas para la corrida.")
    assert not _parece_espanol("The receptor and ligand are ready for docking.")
    assert not _parece_espanol("corta")
    assert not _parece_espanol("TextoSinEspaciosDeLectura")
    assert not _parece_espanol("palabra " + "x" * 410)


def test_ast_registra_fstring_completo_sin_contar_fragmentos_por_separado():
    cadenas = inventariar_fuente(
        'mensaje = f"Se generaron ahora {n} poses dentro del sitio."\n',
        "modulo.py",
    )

    assert [(item["tipo"], item["texto_es"]) for item in cadenas] == [
        ("f-string", "Se generaron ahora {n1} poses dentro del sitio."),
    ]


def test_inventario_omite_fragmentos_de_concatenacion_dinamica_y_une_las_estaticas():
    cadenas = inventariar_fuente(
        'dinamica = "La selección establecida" + valor + ". El motivo sigue sin resolver."\n'
        'estatica = "El motivo" + " está declarado por completo."\n'
        'descripcion = "La selección queda declarada."\n'
        'descripcion += "; el grupo sigue en revisión"\n',
        "modulo.py",
    )

    assert [(item["tipo"], item["texto_es"]) for item in cadenas] == [
        ("fija", "El motivo está declarado por completo."),
        ("fija", "La selección queda declarada."),
    ]


def test_inventario_excluye_docstrings_que_no_salen_en_la_interfaz_ni_en_el_paquete():
    cadenas = inventariar_fuente(
        '"""Este docstring explica el módulo y no se muestra al usuario."""\n'
        'def ejemplo():\n'
        '    """Este docstring explica la función y tampoco se muestra."""\n'
        '    return "Este mensaje sí puede llegar a la interfaz."\n',
        "modulo.py",
    )

    assert [item["texto_es"] for item in cadenas] == [
        "Este mensaje sí puede llegar a la interfaz."
    ]


def test_inventario_omite_prefijos_que_solo_detectan_descripciones_genericas():
    cadenas = inventariar_fuente(
        'def render(descripcion):\n'
        '    _generic_prefixes = ("Descripción fisiológica no disponible.", '
        '"Receptor Biológico PDB:")\n'
        '    if any(descripcion.startswith(prefijo) for prefijo in _generic_prefixes):\n'
        '        return "La salida generada sí se muestra al usuario."\n',
        "services/blockchain/pdf_generator.py",
    )

    assert [item["texto_es"] for item in cadenas] == [
        "La salida generada sí se muestra al usuario."
    ]


def test_inventario_reconoce_el_original_de_pares_de_plantillas():
    fuente = '''
PLANTILLAS_ES_EN: tuple[tuple[str, str], ...] = (
    ("Se pidieron {n} poses para la corrida.", "{n} poses were requested for the run."),
)
'''

    assert extraer_plantillas(fuente) == {"Se pidieron {n1} poses para la corrida."}


def test_excluye_suites_y_scripts_pero_incluye_codigo_de_producto():
    assert es_ruta_incluida(Path("services/dossier/model.py"))
    assert not es_ruta_incluida(Path("tests/test_model.py"))
    assert not es_ruta_incluida(Path("migrations/versions/001.py"))
    assert not es_ruta_incluida(Path("scripts/generar.py"))


def test_ratchet_falla_solo_si_aumenta_el_pendiente():
    assert pendiente_subio(10, 11)
    assert not pendiente_subio(10, 10)
    assert not pendiente_subio(10, 9)
