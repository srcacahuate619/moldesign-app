"""Request-scoped localization for API payloads."""

from __future__ import annotations

import json
import os
import re
import threading
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from starlette.responses import Response
from starlette.concurrency import iterate_in_threadpool

from core.i18n_catalog import ENGLISH_MESSAGES
from core.i18n_plantillas import traducir

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
    return traducir(value, current_locale())


_MESSAGE_FIELDS = frozenset({
    "message", "msg", "detail", "motivo", "observation", "reason",
    "error", "errors", "warning", "warnings", "advertencia", "avisos",
    "detalle_apoyo", "etapa", "nota", "motivo_no_disponible", "resumen",
    "fallback_reason", "protonation_method", "muegge_violations",
    "poblaciones_motivo", "scientific_warnings",
    # Los límites de la evidencia de un lote: sin esto salían en castellano en la
    # interfaz inglesa (QA de 1.0.2, B02).
    "limits",
})
_NESTED_MESSAGE_FIELDS = {("scientific_warnings", "mensaje")}
_SPANISH_MARKERS = re.compile(
    r"[áéíóúñ¿¡]|\b(?:el|la|los|las|de|del|que|con|sin|una|un|por|para|se|es|en)\b"
    r"|\bno\s+(?:se|hay|era|fue|es|está|esta|puede|pueden|tiene|tienen|hubo|"
    r"existe|faltan?|corre|ejecuta|registró|reemplaza|aplica|incluye|autoriza)\b",
    re.IGNORECASE,
)
_I18N_REPORT_LOCK = threading.Lock()
_I18N_REPORTED_BY_PATH: dict[Path, set[tuple[str, str]]] = {}


def _is_message_field(key: Any, parent_key: str) -> bool:
    return (
        isinstance(key, str)
        and (key in _MESSAGE_FIELDS or (parent_key, key) in _NESTED_MESSAGE_FIELDS)
    )


def _message_values(
    value: Any,
    *,
    _message: bool = False,
    _parent_key: str = "",
):
    """Yield only strings in fields that ``localize_payload`` treats as messages."""
    if isinstance(value, str):
        if _message:
            yield value
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _message_values(
                item,
                _message=_message,
                _parent_key=_parent_key,
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _message_values(
                item,
                _message=_is_message_field(key, _parent_key),
                _parent_key=key if isinstance(key, str) else "",
            )


def _openapi_message_values(value: Any):
    """Yield OpenAPI prose fields handled by ``localize_openapi_payload``."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                yield from _openapi_message_values(item)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        if key in {"summary", "description"} and isinstance(item, str):
            yield item
        elif key == "tags" and isinstance(item, list):
            yield from (tag for tag in item if isinstance(tag, str))
        else:
            yield from _openapi_message_values(item)


def _i18n_report_path() -> Path:
    data_dir = os.environ.get("LOCAL_DATA_DIR")
    if data_dir:
        root = Path(data_dir)
    else:
        root = Path.home() / "MolDesign" / "data"
    return root / "i18n_faltantes.jsonl"


def _record_i18n_missing(endpoint: str, payload: Any, *, openapi: bool) -> None:
    if os.environ.get("MOLDESIGN_I18N_REPORT") != "1":
        return
    candidates = _openapi_message_values(payload) if openapi else _message_values(payload)
    missing = {
        text
        for text in candidates
        if _SPANISH_MARKERS.search(text) and translate_text(text) == text
    }
    if not missing:
        return

    path = _i18n_report_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _I18N_REPORT_LOCK:
            if path not in _I18N_REPORTED_BY_PATH:
                conocidos: set[tuple[str, str]] = set()
                try:
                    with path.open("r", encoding="utf-8") as previo:
                        for line in previo:
                            try:
                                row = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(row, dict):
                                continue
                            endpoint_previo = row.get("endpoint")
                            texto_previo = row.get("text")
                            if isinstance(endpoint_previo, str) and isinstance(texto_previo, str):
                                conocidos.add((endpoint_previo, texto_previo))
                except FileNotFoundError:
                    pass
                _I18N_REPORTED_BY_PATH[path] = conocidos

            conocidos = _I18N_REPORTED_BY_PATH[path]
            nuevos = sorted(
                (endpoint, text) for text in missing
                if (endpoint, text) not in conocidos
            )
            if not nuevos:
                return
            with path.open("a", encoding="utf-8", newline="\n") as salida:
                for endpoint_nuevo, texto_nuevo in nuevos:
                    salida.write(json.dumps(
                        {"endpoint": endpoint_nuevo, "text": texto_nuevo},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ) + "\n")
            conocidos.update(nuevos)
    except (OSError, UnicodeError):
        # This opt-in diagnostic must never change or fail an API response.
        return


def localize_payload(
    value: Any,
    *,
    _message: bool = False,
    _parent_key: str = "",
) -> Any:
    """Translate only declared message fields, never names or user data."""
    if isinstance(value, str):
        return translate_text(value) if _message else value
    if isinstance(value, list):
        return [
            localize_payload(item, _message=_message, _parent_key=_parent_key)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            localize_payload(item, _message=_message, _parent_key=_parent_key)
            for item in value
        )
    if isinstance(value, dict):
        return {
            key: localize_payload(
                item,
                _message=_is_message_field(key, _parent_key),
                _parent_key=key if isinstance(key, str) else "",
            )
            for key, item in value.items()
        }
    return value


def localize_openapi_payload(value: Any) -> Any:
    """Translate OpenAPI prose without treating arbitrary ``description`` data as a message."""
    if isinstance(value, list):
        return [localize_openapi_payload(item) if isinstance(item, (dict, list)) else item for item in value]
    if not isinstance(value, dict):
        return value

    localized: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"summary", "description"} and isinstance(item, str):
            localized[key] = translate_text(item)
        elif key == "tags" and isinstance(item, list):
            localized[key] = [
                translate_text(tag) if isinstance(tag, str) else localize_openapi_payload(tag)
                for tag in item
            ]
        else:
            localized[key] = localize_openapi_payload(item)
    return localized


async def localize_json_response(
    response: Response,
    *,
    openapi: bool = False,
    endpoint: str = "",
) -> Response:
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
    _record_i18n_missing(endpoint, payload, openapi=openapi)
    localized_payload = (
        localize_openapi_payload(payload) if openapi else localize_payload(payload)
    )
    encoded = json.dumps(localized_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    response.body_iterator = iterate_in_threadpool(iter([encoded]))
    response.headers["content-length"] = str(len(encoded))
    response.headers["content-language"] = "en"
    return response
