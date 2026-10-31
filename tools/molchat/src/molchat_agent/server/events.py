"""SSE primitives for the sidecar API (one JSON object per data event)."""

from __future__ import annotations

import json
from typing import Any


def encode_event(payload: dict[str, Any], *, event: str | None = None) -> bytes:
    """Encode one server-sent event (UTF-8, LF only, no buffering games)."""
    text = f"event: {event}\n" if event else ""
    text += f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return text.encode("utf-8")


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}
