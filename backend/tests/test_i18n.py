from __future__ import annotations

import json

import pytest
from starlette.responses import StreamingResponse

from core import i18n


def test_accept_language_respects_quality_and_region() -> None:
    assert i18n.parse_accept_language("es-MX;q=0.7,en-US;q=0.9") == "en"
    assert i18n.parse_accept_language("es-ES,en;q=0.5") == "es"


def test_accept_language_defaults_to_spanish() -> None:
    assert i18n.parse_accept_language(None) == "es"
    assert i18n.parse_accept_language("fr-FR,de;q=0.8") == "es"


def test_payload_translation_is_recursive_and_request_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(i18n.ENGLISH_MESSAGES, "No encontrado", "Not found")
    token = i18n.set_request_locale("en-US")
    try:
        assert i18n.localize_payload({"detail": "No encontrado", "items": ["No encontrado"]}) == {
            "detail": "Not found",
            "items": ["Not found"],
        }
    finally:
        i18n.reset_request_locale(token)
    assert i18n.localize_payload("No encontrado") == "No encontrado"


def test_real_catalog_message_and_multiline_normalization() -> None:
    token = i18n.set_request_locale("en")
    try:
        assert (
            i18n.translate_text("No existe la corrida solicitada.")
            == "The requested run does not exist."
        )
        assert (
            i18n.translate_text("No existe   la corrida\nsolicitada.")
            == "The requested run does not exist."
        )
    finally:
        i18n.reset_request_locale(token)


def test_english_catalog_has_no_known_machine_translation_failures() -> None:
    forbidden = (
        "cumshot",
        "receiver",
        "recipient",
        "coupling",
        "skullprint",
        "moleculas",
        "veredicate",
    )
    lowered = "\n".join(i18n.ENGLISH_MESSAGES.values()).lower()
    assert not [term for term in forbidden if term in lowered]
    assert all(spanish != english for spanish, english in i18n.ENGLISH_MESSAGES.items())


@pytest.mark.asyncio
async def test_json_response_is_translated_without_touching_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(i18n.ENGLISH_MESSAGES, "No encontrado", "Not found")
    token = i18n.set_request_locale("en")
    try:
        response = StreamingResponse(
            iter([json.dumps({"detail": "No encontrado"}).encode()]),
            media_type="application/json",
        )
        localized = await i18n.localize_json_response(response)
        body = b"".join([chunk async for chunk in localized.body_iterator])
    finally:
        i18n.reset_request_locale(token)
    assert json.loads(body) == {"detail": "Not found"}
    assert localized.headers["content-language"] == "en"
