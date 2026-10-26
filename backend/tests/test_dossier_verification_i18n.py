"""Request locale applies to the readable output from the dossier verifier."""

from core.i18n import reset_request_locale, set_request_locale
from services.dossier.verify import verificar_paquete


def test_el_informe_del_verificador_se_traduce_al_ingles_y_conserva_datos_dinamicos():
    token = set_request_locale("en")
    try:
        resultado = verificar_paquete(b"not a zip")
        informe = resultado.informe()

        assert informe.startswith("INVALID\n")
        assert "root:        (undetermined)" in informe
        assert "The file is not a readable ZIP:" in informe
        assert resultado.as_dict()["errores"][0].startswith("The file is not a readable ZIP:")
    finally:
        reset_request_locale(token)


def test_el_informe_del_verificador_conserva_el_espanol_por_defecto():
    token = set_request_locale("es")
    try:
        informe = verificar_paquete(b"not a zip").informe()

        assert informe.startswith("INVÁLIDO\n")
        assert "raíz:        (no determinada)" in informe
        assert "El archivo no es un ZIP legible:" in informe
    finally:
        reset_request_locale(token)
