import asyncio
from unittest.mock import AsyncMock

import pytest
from api.body_limit import BodyLimitMiddleware


@pytest.mark.asyncio
@pytest.mark.parametrize("declared", [False, True])
async def test_excessive_body_never_reaches_parser(declared):
    app, send = AsyncMock(), AsyncMock()
    receive = AsyncMock(side_effect=[{"type": "http.request", "body": b"123", "more_body": True},
                                     {"type": "http.request", "body": b"456", "more_body": False}])
    scope = {"type": "http", "headers": [(b"content-length", b"6")] if declared else []}
    await BodyLimitMiddleware(app, max_bytes=5)(scope, receive, send)
    app.assert_not_called()
    assert send.call_args_list[0].args[0]["status"] == 413
    if declared:
        receive.assert_not_called()


@pytest.mark.asyncio
async def test_chunked_body_is_preserved_byte_for_byte():
    received = bytearray()
    async def app(scope, receive, send):
        while True:
            message = await receive()
            received.extend(message["body"])
            if not message["more_body"]:
                break
    source = AsyncMock(side_effect=[{"type": "http.request", "body": b"123", "more_body": True},
                                    {"type": "http.request", "body": b"456", "more_body": False}])
    await BodyLimitMiddleware(app, max_bytes=6)({"type": "http", "headers": []}, source, AsyncMock())
    assert received == b"123456"


@pytest.mark.asyncio
async def test_slow_body_has_finite_timeout():
    async def receive():
        await asyncio.sleep(10)
    app, send = AsyncMock(), AsyncMock()
    await BodyLimitMiddleware(app, timeout=0.01)({"type": "http", "headers": []}, receive, send)
    app.assert_not_called()
    assert send.call_args_list[0].args[0]["status"] == 408
