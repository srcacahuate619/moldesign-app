"""MOLCHAT-AUD-01 — higiene transversal del §8: tamaños, tiempos y secretos.

Tres exigencias del §8 que ningún hallazgo numerado cubría, y que la lectura
confirmó abiertas:

* **Tamaños.** `AIChatRequest` aceptaba mensajes de longitud arbitraria y una
  lista de mensajes sin tope. Ese texto entra al prompt, viaja al proveedor y se
  persiste en `ai_memory.db`. En una aplicación de escritorio el atacante no es
  un extraño: es un `molecule_context` mal construido o una pestaña que
  reenvía su historial entero, y el resultado es el mismo —memoria, disco y una
  petición que no termina—.

* **Tiempos.** El turno tenía tope por petición HTTP, pero el flujo del motor
  local abría el stream con `read=None`: un servidor que acepta la conexión y
  deja de emitir colgaba el turno para siempre. Un tope por petición no es un
  tope si una de ellas puede no terminar nunca.

* **Secretos.** Los errores de proveedor se devolvían al investigador y se
  escribían en el log tal cual. Un `base_url` con credenciales embebidas, o una
  excepción que arrastra la cabecera de autorización, salía entero.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models import AIChatRequest, ChatMessage
from services.ai.redaccion import redactar_secretos


def _mensaje(texto: str) -> dict:
    return {"role": "user", "content": texto}


class TestTamanos:
    def test_un_mensaje_desmedido_se_rechaza(self):
        with pytest.raises(ValidationError):
            AIChatRequest(messages=[_mensaje("a" * 100_000)])

    def test_un_mensaje_largo_pero_razonable_se_acepta(self):
        peticion = AIChatRequest(messages=[_mensaje("a" * 8_000)])
        assert len(peticion.messages) == 1

    def test_un_historial_sin_fin_se_rechaza(self):
        with pytest.raises(ValidationError):
            AIChatRequest(messages=[_mensaje("hola") for _ in range(5_000)])

    def test_el_contexto_de_molecula_tiene_tope(self):
        with pytest.raises(ValidationError):
            AIChatRequest(
                messages=[_mensaje("hola")],
                molecule_context={"notas": "x" * 200_000},
            )

    def test_el_contexto_de_molecula_normal_pasa(self):
        peticion = AIChatRequest(
            messages=[_mensaje("hola")],
            molecule_context={"smiles": "CCO", "target": "7E2Y"},
        )
        assert peticion.molecule_context is not None

    def test_el_tope_es_del_modelo_y_no_de_una_ruta(self):
        """Si viviera en el endpoint, el siguiente consumidor lo perdería."""
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="a" * 100_000)


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


class TestArchivos:
    """El audio del dictado es lo unico que MolChat recibe como archivo."""

    def _peticion(self, cabeceras, cuerpo=b"", ruta="/ai/speech-to-text"):
        from starlette.requests import Request

        async def _recibir():
            return {"type": "http.request", "body": cuerpo, "more_body": False}

        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": ruta,
                "raw_path": ruta.encode(),
                "query_string": b"",
                "headers": [(k.lower().encode(), v.encode()) for k, v in cabeceras],
                "client": ("127.0.0.1", 5555),
                "server": ("testserver", 80),
            },
            receive=_recibir,
        )

    @pytest.mark.asyncio
    async def test_un_cuerpo_declarado_enorme_se_rechaza_antes_de_leerlo(self, monkeypatch):
        from fastapi import HTTPException

        from api.routers import ai as router

        monkeypatch.setattr(
            "services.ai.speech_to_text.is_whisper_available", lambda: True
        )

        peticion = self._peticion(
            [("content-type", "audio/webm"), ("content-length", str(999_000_000))]
        )

        with pytest.raises(HTTPException) as error:
            await router.speech_to_text(request=peticion, current_user=None)

        assert error.value.status_code == 413

    @pytest.mark.asyncio
    async def test_lo_que_no_es_audio_no_entra(self, monkeypatch):
        from fastapi import HTTPException

        from api.routers import ai as router

        monkeypatch.setattr(
            "services.ai.speech_to_text.is_whisper_available", lambda: True
        )

        peticion = self._peticion([("content-type", "application/zip")])

        with pytest.raises(HTTPException) as error:
            await router.speech_to_text(request=peticion, current_user=None)

        assert error.value.status_code == 415

    @pytest.mark.asyncio
    async def test_sin_cabecera_de_tamano_el_corte_ocurre_al_leer(self, monkeypatch):
        """Un cliente puede no declarar `content-length`; el tope sigue valiendo."""
        from fastapi import HTTPException

        from api.routers import ai as router

        monkeypatch.setattr(
            "services.ai.speech_to_text.is_whisper_available", lambda: True
        )
        monkeypatch.setattr(router, "MAX_BYTES_AUDIO", 32)

        peticion = self._peticion([("content-type", "audio/webm")], b"x" * 500)

        with pytest.raises(HTTPException) as error:
            await router.speech_to_text(request=peticion, current_user=None)

        assert error.value.status_code == 413


class TestTiempos:
    def test_el_stream_local_no_puede_quedarse_sin_tope_de_lectura(self):
        """`read=None` es «espera indefinidamente». Un motor mudo colgaba el turno."""
        import inspect

        from services.ai import local_llm

        fuente = inspect.getsource(local_llm)
        assert "read=None" not in fuente, (
            "un stream sin tope de lectura hace que un tope por petición no sea un tope"
        )

    def test_hay_un_tope_declarado_y_es_finito(self):
        from services.ai.local_llm import STREAM_READ_TIMEOUT_S

        assert 0 < STREAM_READ_TIMEOUT_S < 600
