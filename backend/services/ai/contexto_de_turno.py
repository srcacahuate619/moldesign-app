"""Lo que una herramienta de MolChat necesita saber del turno que la invoca.

`run_docking` se llama desde varios sitios de `chat_service` (el clasificador
determinista, las llamadas nativas del modelo, `execute_tool_step`) y ninguno le
pasa la conversación. Una propuesta de docking (LUNA-05) tiene que poder dejar
constancia, cuando se aprueba, en la conversación donde nació: en vez de añadir un
parámetro a cada llamador, el turno publica aquí su conversación y la herramienta
la lee. Es un dato de contexto, no una identidad: la cuenta sigue viniendo del
servidor (`_imponer_identidad`), nunca del modelo ni de este valor.
"""

from __future__ import annotations

from contextvars import ContextVar

#: Id de la conversación activa del turno en curso, o `None` fuera de un turno.
conversacion_del_turno: ContextVar[str | None] = ContextVar(
    "conversacion_del_turno", default=None
)
