"""Validate model-proposed case creation without treating a proposal as success."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..providers.base import LLMProvider, TurnContext


@dataclass(frozen=True)
class CreateCase:
    name: str


async def select_case(provider: LLMProvider, user_text: str) -> CreateCase | None:
    """Ask the active model for the one supported case action, without executing it."""
    system = (
        'Decide si el usuario pide crear un caso nuevo en MolDesign. '
        'Si lo pide y da un nombre literal, responde solo JSON '
        '{"tool":"create_case","name":"nombre literal"}. '
        'Para cualquier otra petición o sin nombre, responde solo {}. '
        'No inventes nombres ni afirmes que se creó el caso.'
    )
    events = [event async for event in provider.chat(TurnContext(
        text=user_text, messages=[{"role": "system", "content": system},
                                  {"role": "user", "content": user_text}]))]
    return parse_case_selection("".join(event.text for event in events if not event.done), user_text)


def parse_case_selection(response: str, user_text: str) -> CreateCase | None:
    """Accept only a closed-schema proposal whose name appears in the user turn.

    This parser does not create anything. The caller must obtain a confirmed
    result from the authenticated host before reporting success.
    """
    try:
        payload = json.loads(response)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {"tool", "name"}:
        return None
    name = payload.get("name")
    if payload.get("tool") != "create_case" or not isinstance(name, str):
        return None
    if name != name.strip() or not name or len(name) > 100:
        return None
    if any(ord(character) < 32 for character in name):
        return None
    if not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", user_text):
        return None
    return CreateCase(name=name)
