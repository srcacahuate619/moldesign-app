"""Small, bounded tool-calling loop; execution is supplied by the host."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Awaitable, Callable

from ..providers.base import ProviderError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name,
                "description": self.description, "parameters": self.parameters}}


@dataclass(frozen=True)
class LoopResult:
    text: str
    messages: list[dict[str, Any]]
    exhausted: bool = False


def _arguments(raw: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate closed schemas; normalize decimal strings for integer fields."""
    if not isinstance(raw, str) or len(raw) > 4096:
        raise ValueError("argumentos no válidos")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Los argumentos deben ser un objeto JSON válido.") from None
    def validate(value: Any, spec: Any, key: str) -> Any:
        if not isinstance(spec, dict):
            raise ValueError("Esquema de herramienta no válido.")
        kind = spec.get("type")
        if kind == "object":
            properties, required = spec.get("properties", {}), spec.get("required", [])
            if (not isinstance(value, dict) or spec.get("additionalProperties") is not False
                    or not isinstance(properties, dict) or not isinstance(required, list)):
                raise ValueError("argumentos no válidos")
            if not set(required).issubset(value) or not set(value).issubset(properties):
                raise ValueError(f"Usa solo los campos {', '.join(properties)}; son obligatorios: {', '.join(required)}.")
            return {name: validate(item, properties[name], name) for name, item in value.items()}
        if kind == "array":
            if not isinstance(value, list) or not spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", 3):
                raise ValueError(f"El campo {key} debe ser una lista dentro del límite indicado.")
            return [validate(item, spec.get("items"), key) for item in value]
        if kind == "integer":
            if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 12:
                value = int(value)
            if type(value) is not int or not spec.get("minimum", 0) <= value <= spec.get("maximum", 999999999999):
                raise ValueError(f"El campo {key} debe ser un entero válido dentro del rango indicado.")
            return value
        if kind == "string":
            if (not isinstance(value, str) or not value.strip() or len(value) > spec.get("maxLength", 120)
                    or any(ord(char) < 32 for char in value)):
                raise ValueError(f"El campo {key} debe ser un texto válido y no vacío.")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError(f"El campo {key} debe usar una de las opciones indicadas.")
            return value
        raise ValueError("Esquema de herramienta no válido.")
    result = validate(data, schema, "argumentos")
    if not isinstance(result, dict):
        raise ValueError("argumentos no válidos")
    return result


async def run_tool_loop(provider: Any, messages: list[dict[str, Any]],
                        tools: list[Tool], *, max_steps: int = 4,
                        observe: Callable[[str, str, str, dict[str, Any] | None], None] | None = None) -> LoopResult:
    """Run at most max_steps model requests, preserving structured call/result pairs.

    The caller supplies authorized context and only the tool implementations
    available for this user. This function never retries a tool automatically.
    """
    if not 1 <= max_steps <= 12:
        raise ValueError("límite de pasos no válido")
    by_name = {tool.name: tool for tool in tools}
    if len(by_name) != len(tools):
        raise ValueError("herramientas duplicadas")
    transcript = list(messages)
    seen_ids = {call["id"] for entry in transcript if entry.get("role") == "assistant"
                for call in entry.get("tool_calls", [])
                if isinstance(call, dict) and isinstance(call.get("id"), str)}
    for _ in range(max_steps):
        message = await provider.chat_with_tools(transcript, [tool.schema() for tool in tools])
        if not isinstance(message, dict) or message.get("role") not in (None, "assistant"):
            raise ProviderError("El modelo devolvió un mensaje no válido.")
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list) or len(calls) > 8:
            raise ProviderError("El modelo devolvió demasiadas llamadas.")
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ProviderError("El modelo devolvió contenido no válido.")
        if not calls:
            if not content:
                raise ProviderError("El modelo no devolvió una respuesta.")
            transcript.append({"role": "assistant", "content": content})
            return LoopResult(content, transcript)
        clean_calls: list[dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, dict) or call.get("type") != "function":
                raise ProviderError("La llamada del modelo no es válida.")
            call_id, function = call.get("id"), call.get("function")
            if (not isinstance(call_id, str) or not 0 < len(call_id) <= 128
                    or call_id in seen_ids or not isinstance(function, dict)
                    or not isinstance(function.get("name"), str)
                    or not isinstance(function.get("arguments"), str)):
                raise ProviderError("La llamada del modelo no es válida o está duplicada.")
            seen_ids.add(call_id)
            clean_calls.append({"id": call_id, "type": "function", "function": {
                "name": function["name"], "arguments": function["arguments"]}})
        assistant_message: dict[str, Any] = {"role": "assistant", "content": content,
                                             "tool_calls": clean_calls}
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str):
            assistant_message["reasoning_content"] = reasoning
        transcript.append(assistant_message)
        for call in clean_calls:
            function = call["function"]
            if observe:
                observe("start", function["name"], call["id"], None)
            tool = by_name.get(function["name"])
            try:
                if tool is None:
                    raise ValueError("herramienta no disponible")
                args = _arguments(function["arguments"], tool.parameters)
            except (ValueError, TypeError) as exc:
                detail = str(exc) if tool is not None else "Herramienta no disponible."
                result = {"error": f"{detail} La solicitud no se ejecutó; puedes corregir los argumentos y volver a intentar."}
            else:
                if observe:
                    observe("arguments", "", call["id"], args)
                try:
                    result = await tool.execute(args)
                    if not isinstance(result, dict):
                        raise TypeError("resultado no válido")
                except Exception:  # never retry an operation whose result may be unknown
                    result = {"error": "No se pudo confirmar el resultado; verifica el estado antes de reintentar."}
            try:
                serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
                if len(serialized) > 100_000:
                    raise ValueError("resultado demasiado grande")
            except (ValueError, TypeError):
                result = {"error": "El resultado no se pudo comunicar; verifica el estado antes de reintentar."}
                serialized = json.dumps(result)
            transcript.append({"role": "tool", "tool_call_id": call["id"], "content": serialized})
            if observe:
                observe("end", str(result.get("status") or ("error" if result.get("error") else "ok")), call["id"], None)
    return LoopResult("La respuesta quedó incompleta al alcanzar el límite de pasos. Revisa los resultados confirmados antes de continuar.", transcript, True)
