"""Request-scoped localization for API payloads."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from typing import Any

from starlette.responses import Response
from starlette.concurrency import iterate_in_threadpool

from core.i18n_catalog import ENGLISH_MESSAGES

_locale: ContextVar[str] = ContextVar("moldesign_locale", default="es")


def parse_accept_language(value: str | None) -> str:
    """Return the supported locale with the highest quality value."""
    candidates: list[tuple[float, int, str]] = []
    for index, item in enumerate((value or "").split(",")):
        parts = [part.strip() for part in item.split(";")]
        language = parts[0].lower().split("-", 1)[0]
        if language not in {"es", "en"}:
            continue
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if quality > 0:
            candidates.append((quality, -index, language))
    return max(candidates, default=(1.0, 0, "es"))[2]


def set_request_locale(header: str | None) -> Token[str]:
    return _locale.set(parse_accept_language(header))


def reset_request_locale(token: Token[str]) -> None:
    _locale.reset(token)


def current_locale() -> str:
    return _locale.get()


def translate_text(value: str) -> str:
    if current_locale() != "en":
        return value
    normalized = " ".join(value.split())
    direct = ENGLISH_MESSAGES.get(value) or ENGLISH_MESSAGES.get(normalized)
    if direct is not None:
        return direct
    translated = value
    for spanish, english in sorted(
        ENGLISH_MESSAGES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if len(spanish) >= 8 and spanish in translated:
            translated = translated.replace(spanish, english)
    return translated


def localize_payload(value: Any) -> Any:
    if isinstance(value, str):
        return translate_text(value)
    if isinstance(value, list):
        return [localize_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(localize_payload(item) for item in value)
    if isinstance(value, dict):
        return {key: localize_payload(item) for key, item in value.items()}
    return value


async def localize_json_response(response: Response) -> Response:
    """Translate JSON response values without buffering streams or downloads."""
    if current_locale() != "en":
        return response
    content_type = response.headers.get("content-type", "").lower()
    if "application/json" not in content_type or not hasattr(response, "body_iterator"):
        return response
    chunks = [chunk async for chunk in response.body_iterator]
    body = b"".join(chunk.encode("utf-8") if isinstance(chunk, str) else chunk for chunk in chunks)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        response.body_iterator = iterate_in_threadpool(iter([body]))
        return response
    encoded = json.dumps(
        localize_payload(payload), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    response.body_iterator = iterate_in_threadpool(iter([encoded]))
    response.headers["content-length"] = str(len(encoded))
    response.headers["content-language"] = "en"
    return response
