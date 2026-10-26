"""QA2-004: la abstención Molcy se conserva y se lee en el idioma pedido."""
import json

import pytest
from starlette.responses import StreamingResponse
from core import i18n


@pytest.mark.asyncio
@pytest.mark.parametrize("locale,expected", [
    ("es-MX", "Esta versión de Molcy no admite paquetes de corrida."),
    ("en-US", "This version of Molcy does not support run packages."),
])
async def test_molcy_unavailable_reason_in_real_response_localizer(locale, expected):
    reason = "Esta versión de Molcy no admite paquetes de corrida."
    payload = {"disponible": False, "motivo": reason, "motor": "E:/Molcy español"}
    token = i18n.set_request_locale(locale)
    try:
        response = StreamingResponse(iter([json.dumps(payload).encode()]), media_type="application/json")
        localized = await i18n.localize_json_response(response)
        body = b"".join([chunk async for chunk in localized.body_iterator])
    finally:
        i18n.reset_request_locale(token)
    assert json.loads(body) == {"disponible": False, "motivo": expected, "motor": "E:/Molcy español"}