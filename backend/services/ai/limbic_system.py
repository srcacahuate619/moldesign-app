"""
services/ai/limbic_system.py

Sistema limbico de MolChat: personalidad evolutiva basada en uso.
XP, nivel, mood, preferencias — todo en un archivo JSON liviano (~2 KB).

Etapas:
  Nivel 0-2: Recién Nacido — respuestas básicas, aprende del usuario
  Nivel 3-6: Aprendiz — empieza a recordar preferencias
  Nivel 7-12: Experto — anticipa necesidades, sugiere proactivamente
  Nivel 13+: Arquitecto — modo avanzado, propone estrategias de diseño

Mood se ajusta por:
  +1 por cada evaluación exitosa detectada (score > 50)
  +1 por cada "gracias" o feedback positivo
  -1 por error en tool o respuesta insatisfactoria
  Se resetea entre sesiones.
"""

from __future__ import annotations

import json
import time

from core.config import directorio_de_datos

_STATE_PATH = directorio_de_datos("limbic") / "limbic.json"

_DEFAULT_STATE = {
    "xp": 0,
    "level": 0,
    "conversations_count": 0,
    "messages_count": 0,
    "total_tokens_used": 0,
    "mood": 3,
    "mood_label": "neutral",
    "preferred_targets": {},
    "preferred_tools": {},
    "last_active": 0.0,
    "created_at": 0.0,
}


_cache: dict | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 5.0  # segundos


def _load() -> dict:
    global _cache, _cache_ts
    now = time.time()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache
    try:
        if _STATE_PATH.exists():
            with open(_STATE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
                _cache_ts = now
                return _cache
    except Exception:
        pass
    _cache = dict(_DEFAULT_STATE)
    _cache["created_at"] = time.time()
    _cache_ts = now
    return _cache


def _save(state: dict):
    global _cache_ts
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        _cache_ts = 0  # invalidar cache tras escritura
    except Exception:
        pass


def get_level(xp: int) -> int:
    if xp < 10:
        return 0
    if xp < 30:
        return 1
    if xp < 60:
        return 2
    if xp < 100:
        return 3
    if xp < 150:
        return 4
    if xp < 220:
        return 5
    if xp < 300:
        return 6
    if xp < 400:
        return 7
    if xp < 550:
        return 8
    if xp < 750:
        return 9
    if xp < 1000:
        return 10
    if xp < 1300:
        return 11
    if xp < 1700:
        return 12
    return 13


def get_stage(level: int) -> str:
    if level <= 2:
        return "Recién Nacido"
    if level <= 6:
        return "Aprendiz"
    if level <= 12:
        return "Experto"
    return "Arquitecto"


def get_mood_label(mood: int) -> str:
    if mood >= 8:
        return "eufórico"
    if mood >= 6:
        return "contento"
    if mood >= 4:
        return "neutral"
    if mood >= 2:
        return "cansado"
    return "frustrado"


def get_state() -> dict:
    state = _load()
    state["level"] = get_level(state["xp"])
    state["stage"] = get_stage(state["level"])
    state["mood_label"] = get_mood_label(state["mood"])
    return state


def on_conversation_opened():
    state = _load()
    state["conversations_count"] += 1
    state["last_active"] = time.time()
    _save(state)


def on_message_sent(content: str):
    state = _load()
    state["messages_count"] += 1
    state["xp"] += 1
    if "gracias" in content.lower() or "excelente" in content.lower():
        state["mood"] = min(10, state["mood"] + 1)
    state["last_active"] = time.time()
    _save(state)


def on_tool_used(tool_name: str, success: bool):
    state = _load()
    prefs = state.setdefault("preferred_tools", {})
    prefs[tool_name] = prefs.get(tool_name, 0) + 1
    if success:
        state["xp"] += 3
    else:
        state["mood"] = max(0, state["mood"] - 1)
    state["last_active"] = time.time()
    _save(state)


def on_target_used(target: str):
    state = _load()
    prefs = state.setdefault("preferred_targets", {})
    prefs[target] = prefs.get(target, 0) + 1
    _save(state)


def on_evaluation_complete(total_score: float | None):
    state = _load()
    state["xp"] += 5
    if total_score and total_score > 50:
        state["mood"] = min(10, state["mood"] + 1)
    state["last_active"] = time.time()
    _save(state)


def build_limbic_prompt() -> str:
    state = get_state()
    stage = state.get("stage", "Recién Nacido")
    mood = state.get("mood_label", "neutral")
    convs = state.get("conversations_count", 0)
    msgs = state.get("messages_count", 0)
    xp = state.get("xp", 0)

    lines = [
        f"\n[Perfil del usuario — etapa: {stage}, mood: {mood}]",
        f"Has tenido {convs} conversaciones y {msgs} mensajes ({xp} XP).",
    ]

    targets = state.get("preferred_targets", {})
    if targets:
        top = sorted(targets.items(), key=lambda x: x[1], reverse=True)[:3]
        names = ", ".join(f"{t} ({c}x)" for t, c in top)
        lines.append(f"Targets favoritos: {names}.")

    tools = state.get("preferred_tools", {})
    if tools:
        top = sorted(tools.items(), key=lambda x: x[1], reverse=True)[:3]
        names = ", ".join(f"{t} ({c}x)" for t, c in top)
        lines.append(f"Herramientas más usadas: {names}.")

    return "\n".join(lines)
