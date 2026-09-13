"""
services/ai/tool_cache.py

Cache global de resultados de herramientas por hash de argumentos.
Evita ejecutar dos veces compute_properties con el mismo SMILES.
TTL: 300s (5 min). In-memory + SQLite fallback.
"""

from __future__ import annotations

import hashlib
import json
import time

_cache: dict[str, tuple[float, str]] = {}
_MAX_SIZE = 512
_TTL = 300.0


def _make_key(tool_name: str, args: dict) -> str:
    raw = json.dumps([tool_name, args], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_cached(tool_name: str, args: dict) -> str | None:
    key = _make_key(tool_name, args)
    entry = _cache.get(key)
    if entry:
        ts, result = entry
        if time.time() - ts < _TTL:
            return result
        del _cache[key]
    return None


def set_cache(tool_name: str, args: dict, result: str):
    key = _make_key(tool_name, args)
    if len(_cache) >= _MAX_SIZE:
        oldest = min(_cache.keys(), key=lambda k: _cache[k][0])
        del _cache[oldest]
    _cache[key] = (time.time(), result)
