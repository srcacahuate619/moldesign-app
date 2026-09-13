"""Contratos del estado de conversación extraído de MolChat (C-09)."""

from __future__ import annotations

from services.ai.chat_service import Conversation as ChatServiceConversation
from services.ai.conversation_state import Conversation


def test_chat_service_reexports_conversation_state_without_changing_compression():
    assert ChatServiceConversation is Conversation

    conversation = Conversation(id="conv-prueba")
    for index in range(12):
        role = "user" if index % 2 == 0 else "assistant"
        conversation.add_message(role, f"Mensaje científico extenso {index} sobre afinidad y docking.")

    recent, summary = conversation.get_recent_and_compressed()

    assert len(recent) == 6
    assert recent == conversation.messages[-6:]
    assert summary.startswith("Charla anterior (6 msgs)")
    assert conversation.summary == summary
    assert conversation.estimated_tokens() > 0
