"""Meeko cita el residuo que no pudo construir: la subida lo nombra, sin rutas (RESULTS.md §5.1).

El detalle real trae la línea de comandos y la salida de error de Meeko, con rutas temporales del disco. Sólo se
cita la etiqueta del residuo («A:438»); el resto no llega a quien sube el archivo.
"""
from core.exceptions import ProteinPreparationError
from services.targets.errores_subida import desde_preparacion

DETALLE_CON_RESIDUO = (
    "Traceback (most recent call last):\n"
    '  File "C:\\Users\\Johan\\AppData\\Local\\Temp\\moldesign\\receptor.pdb", line 1\n'
    "RuntimeError: interrupted residues in PDB: {'A:438'}\n"
)


def test_la_subida_nombra_el_residuo_que_meeko_cita():
    error = desde_preparacion(ProteinPreparationError("1IEP", "mk_prepare_receptor", DETALLE_CON_RESIDUO), cadena="A")
    assert error.codigo == "MEEKO_NO_PUDO"
    assert error.datos["residuos"] == ["A:438"]
    assert "A:438" in error.mensaje("es") and "A:438" in error.mensaje("en")


def test_la_ruta_del_disco_no_llega_a_quien_sube_el_archivo():
    error = desde_preparacion(ProteinPreparationError("1IEP", "mk_prepare_receptor", DETALLE_CON_RESIDUO))
    for idioma in ("es", "en"):
        texto = error.mensaje(idioma)
        assert "Users" not in texto and "AppData" not in texto and "C:\\" not in texto and "<ruta omitida>" not in texto


def test_sin_cita_de_meeko_queda_el_mensaje_general():
    error = desde_preparacion(ProteinPreparationError("1IEP", "mk_prepare_receptor", "fallo sin residuo"))
    assert error.codigo == "MEEKO_NO_PUDO"
    assert "residuos" not in error.datos
    assert "Suele deberse a residuos no estándar" in error.mensaje("es")


def test_solo_se_citan_etiquetas_de_residuo_validas():
    detalle = "RuntimeError: interrupted residues in PDB: {'A:438', 'B:12', 'C:\\ruta\\x.pdb'}"
    error = desde_preparacion(ProteinPreparationError("1IEP", "mk_prepare_receptor", detalle))
    assert error.datos["residuos"] == ["A:438", "B:12"]
