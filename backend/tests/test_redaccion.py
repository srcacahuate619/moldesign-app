"""Redacción de secretos en textos de error (salvada del corte, Fase 6.6).

`redactar_secretos` vivía para el turno del asistente interno, pero la usa
la superficie preservada (`/ai/speech-to-text` redacta el error de carga de
whisper): se reubicó a `services/redaccion.py` con sus pruebas.
"""

from services.redaccion import redactar_secretos


class TestSecretos:
    def test_una_clave_en_la_url_no_sale_en_el_texto(self):
        texto = redactar_secretos(
            "Error conectando con https://api.openai.com/v1?api_key=sk-abcdef123456"
        )

        assert "sk-abcdef123456" not in texto
        assert "[redactado]" in texto

    def test_una_cabecera_de_autorizacion_no_sale(self):
        texto = redactar_secretos("fallo con Authorization: Bearer sk-proj-XYZ987")

        assert "sk-proj-XYZ987" not in texto
        assert "[redactado]" in texto

    def test_credenciales_embebidas_en_el_host_no_salen(self):
        texto = redactar_secretos("http://juan:contrasena@10.0.0.7:11434/api/chat")

        assert "contrasena" not in texto
        assert "10.0.0.7" in texto, "el host sí debe verse: es el destino de los datos"

    def test_una_clave_suelta_con_prefijo_conocido_no_sale(self):
        texto = redactar_secretos("la clave sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX quedo mal")

        assert "ABCDEFGHIJKLMNOPQRSTUVWX" not in texto

    def test_un_mensaje_sin_secretos_no_se_toca(self):
        original = "Timeout conectando a http://127.0.0.1:8080 tras 120s"

        assert redactar_secretos(original) == original

    def test_redactar_tolera_lo_que_no_es_texto(self):
        assert redactar_secretos(None) == ""
        assert redactar_secretos(1234) == "1234"
