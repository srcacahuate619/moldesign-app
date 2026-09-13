"""
services/ai/tool_registry.py

Sistema de herramientas (Tools) para MolChat.
100% offline. Sin function calling nativo.
El LLM invoca tools via formato de texto simple.

Formato de tool call (en la respuesta del LLM):
  🛠️ TOOL_NAME | param1=valor | param2=valor

Las tools pueden devolver texto o JSON. El resultado se inyecta
como mensaje del sistema en el siguiente turno de la conversación.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from utils.logger import get_logger

log = get_logger(__name__)

_MAX_TOOL_CALLS_PER_TURN = 3


#: MOLCHAT-AUD-01, eje SCI. El §8 exige clasificar cada respuesta, y hasta aquí
#: el turno inyectaba `compute_properties: MW: 180.2` y `predict_admet:
#: LogS: -2.1` con el mismo formato y la misma autoridad aparente. Uno es
#: aritmética determinista sobre el grafo molecular; el otro, la salida de un
#: modelo entrenado. La clase es del contrato de la herramienta, no del texto
#: que el modelo redacte después.
CLASES_EPISTEMICAS: dict[str, str] = {
    #: Determinista sobre la entrada: mismo SMILES, mismo número, siempre.
    "calculo": "cálculo",
    #: Leído de una corrida ya ejecutada y guardada de ESTA cuenta.
    "dato_persistido": "dato persistido",
    #: Predicción de un modelo. No es una medida.
    "inferencia": "inferencia (predicción de modelo, no medida)",
    #: Traído de una base externa; la fuente se nombra.
    "recuperacion_externa": "recuperación externa",
    #: Texto sin números propios.
    "explicacion": "explicación",
}


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, dict] = field(default_factory=dict)
    offline: bool = True
    category: str = "general"  # "general", "analog", "docking", "web"
    fn: Callable[..., Awaitable[str]] | None = None
    #: Qué estatuto tiene lo que devuelve. Ver `CLASES_EPISTEMICAS`.
    clase: str = ""
    #: De dónde sale el número: "RDKit", "PubChem", "evaluación persistida de
    #: la cuenta", "ADMET-AI local"… Se imprime junto al resultado.
    procedencia: str = ""

    def to_openai_tool(self) -> dict:
        """Convertir a formato OpenAI function calling nativo.

        Qwen2.5-1.5B-Instruct entiende nativamente este formato via template
        Hermes 2 Pro — no necesita el formato custom 🛠️ que usabamos antes.
        """
        # Mapear tipos Python usados en ToolDef → JSON Schema types
        _PY_TO_JSON = {
            "str": "string", "int": "integer", "float": "number",
            "bool": "boolean", "list": "array", "dict": "object",
            "string": "string", "integer": "integer", "number": "number",
            "boolean": "boolean", "array": "array", "object": "object",
        }
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        k: {
                            "type": _PY_TO_JSON.get(v.get("type", ""), "string"),
                            "description": v.get("description", ""),
                        }
                        for k, v in self.parameters.items()
                    },
                    "required": [
                        k for k, v in self.parameters.items()
                        if v.get("required")
                    ],
                },
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef):
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_offline(self) -> list[ToolDef]:
        return [t for t in self._tools.values() if t.offline]

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    def get_tools_openai(self, offline_only: bool = True) -> list[dict]:
        """Convertir todas las tools a formato OpenAI function calling.
        Listo para pasar al payload `tools=[]` de /v1/chat/completions.
        """
        tools = self.list_offline() if offline_only else self.list_all()
        return [t.to_openai_tool() for t in tools]

    def build_prompt_section(self, show_all: bool = False, exclude_categories: set[str] | None = None) -> str:
        tools = self.list_all() if show_all else self.list_offline()
        if exclude_categories:
            tools = [t for t in tools if t.category not in exclude_categories]
        if not tools:
            return ""
        lines = ["\n[Tools: 🛠️ nombre | param=valor. Max 1 tool/respuesta.]"]
        for t in tools:
            params = ", ".join(t.parameters.keys())
            lines.append(f"  {t.name}({params}) — {t.description[:100]}")
        return "\n".join(lines)

    def build_few_shot_example(self) -> str:
        return "\n[Ej: Usuario: propiedades aspirina? | Asistente: 🛠️ compute_properties | smiles=CC(=O)Oc1ccccc1C(=O)O]"


_TOOL_CALL_RE = re.compile(
    r"🛠️\s*(\w+)\s*\|(.+?)(?:\n|$)",
    re.MULTILINE,
)


def parse_tool_call(text: str) -> tuple[str | None, dict[str, str]]:
    match = _TOOL_CALL_RE.search(text)
    if not match:
        return None, {}
    name = match.group(1).strip()
    args_str = match.group(2).strip()
    args = {}
    for part in args_str.split("|"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            args[k.strip()] = v.strip().strip("\"'")
    return name, args


def strip_tool_markers(text: str) -> str:
    """Remover marcadores de tool call del texto visible."""
    return _TOOL_CALL_RE.sub("", text).strip()


def _guard_validate_smiles(smiles: str) -> tuple[bool, str, str]:
    """Validar SMILES con RDKit. Retorna (valido, canonico, error).

    Usado por execute_tool_step como guard antes de ejecutar cualquier tool
    que reciba un SMILES como argumento. Previene alucinaciones del modelo 1.5B.
    """
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, "", "RDKit no pudo parsear el SMILES"
        canon = Chem.MolToSmiles(mol, canonical=True)
        return True, canon, ""
    except ImportError:
        # Sin RDKit no podemos validar — permitir (confiar en la tool destino)
        return True, smiles, ""
    except Exception as e:
        return False, "", str(e)[:100]


#: Argumentos que **nunca** vienen del modelo. Los pone el servidor.
_ARGUMENTOS_DE_IDENTIDAD = ("user_id",)


def _imponer_identidad(tool: ToolDef, args: dict[str, str], identidad: str | None) -> None:
    """La identidad la fija el servidor, no el texto que escribió el modelo.

    Gate de MolChat, frente de prompt injection. `execute_tool_step` ejecutaba
    los argumentos tal como venían en la respuesta del modelo, y varias
    herramientas aceptan `user_id` —`query_evaluation_details`, `query_history`,
    `run_docking`, `check_docking_status`—. El turno de MolChat lleva dentro
    texto de terceros (PubChem, ChEMBL, RCSB) que el modelo puede repetir, así
    que bastaba con que ese texto consiguiera una línea
    `🛠️ query_evaluation_details | user_id=<otra cuenta>` para leer el historial
    ajeno: la fuga que MOLCHAT-BE-004 cerró, vuelta a abrir por la puerta del
    modelo.

    Se borra siempre, se repone sólo si la herramienta la acepta. Sin identidad
    autenticada se pasa vacía, que es lo que las herramientas ya tratan como
    «no leo el historial de nadie» (D-05).
    """
    for clave in _ARGUMENTOS_DE_IDENTIDAD:
        args.pop(clave, None)

    if tool.fn is None:
        return
    try:
        firma = inspect.signature(tool.fn)
    except (TypeError, ValueError):  # pragma: no cover - callables exóticos
        return
    for clave in _ARGUMENTOS_DE_IDENTIDAD:
        if clave in firma.parameters:
            args[clave] = identidad or ""


async def execute_tool_step(
    registry: ToolRegistry,
    llm_response: str,
    max_turns: int = _MAX_TOOL_CALLS_PER_TURN,
    *,
    identidad: str | None = None,
) -> list[dict]:
    """
    Detectar tool calls en la respuesta del LLM, ejecutarlas en secuencia,
    y devolver los resultados. Soporta múltiples tools encadenadas.

    `identidad` es la cuenta autenticada del turno. Sobrescribe cualquier
    identidad que el modelo haya escrito en los argumentos: ver
    `_imponer_identidad`.
    """
    results = []
    remaining_text = llm_response
    turns = 0

    while turns < max_turns:
        name, args = parse_tool_call(remaining_text)
        if not name:
            break

        tool = registry.get(name)
        if not tool:
            results.append({
                "tool": name,
                "error": f"Herramienta '{name}' no encontrada. Tools disponibles: {', '.join(registry.list_offline()[0].name for _ in [1])}",
            })
            break

        if not tool.fn:
            results.append({"tool": name, "error": "Tool no implementada"})
            break

        try:
            # SMILES guard: validar con RDKit ANTES de pasar a cualquier tool.
            # Previene que el modelo 1.5B pase SMILES alucinados como argumentos.
            # Solo se aplica a tools que reciben 'smiles' Y no son validate_smiles
            # (validate_smiles ES el validador, no debe pre-validarse a si mismo).
            if name != "validate_smiles":
                smiles_arg = args.get("smiles") or args.get("init_smiles") or args.get("query_smiles")
                if smiles_arg:
                    valid, canon, err = _guard_validate_smiles(smiles_arg)
                    if not valid:
                        results.append({
                            "tool": name,
                            "error": f"SMILES invalido '{smiles_arg[:40]}': {err}. "
                                     f"Usa 'validate_smiles' para verificar o genera un SMILES valido.",
                        })
                        remaining_text = _TOOL_CALL_RE.sub("", remaining_text, count=1)
                        turns += 1
                        continue
                    # Reemplazar con el SMILES canónico para consistencia
                    if canon != smiles_arg:
                        for k in ("smiles", "init_smiles", "query_smiles"):
                            if k in args:
                                args[k] = canon
                                break

            _imponer_identidad(tool, args, identidad)
            log.info("tool_executed", tool=name, args=args)
            # Tool cache: evitar recalcular mismo SMILES
            cached = None
            try:
                from services.ai.tool_cache import get_cached
                cached = get_cached(name, args)
            except ImportError:
                pass
            if cached:
                result = cached
                log.info("tool_cache_hit", tool=name)
            else:
                result = await tool.fn(**args)
                try:
                    from services.ai.tool_cache import set_cache
                    set_cache(name, args, result)
                except ImportError:
                    pass
            results.append({"tool": name, "result": result})
        except Exception as e:
            log.error("tool_failed", tool=name, error=str(e)[:150])
            results.append({"tool": name, "error": str(e)[:200]})

        remaining_text = _TOOL_CALL_RE.sub("", remaining_text, count=1)
        turns += 1

    return results


def format_tool_results(results: list[dict]) -> str:
    """Inyectar los resultados **declarando qué es cada uno**.

    MOLCHAT-AUD-01 (SCI). Antes todas las salidas entraban con el mismo
    formato: un cálculo determinista, la predicción de un modelo y un dato
    traído de PubChem eran indistinguibles para el lector y para el modelo que
    redacta la respuesta. Ahora cada bloque lleva su clase y su fuente, y un
    error se presenta como abstención —no hay número— en lugar de como una
    línea más.
    """
    if not results:
        return ""
    registry = get_tool_registry()
    lines = [
        "\n[Sistema: resultados de herramientas ejecutadas. Cada bloque declara "
        "QUÉ es y DE DÓNDE sale; conserva esa distinción al responder y cita la "
        "fuente cuando des un número:]"
    ]
    for r in results:
        nombre = r.get("tool", "?")
        tool = registry.get(nombre)
        if tool is not None and tool.clase in CLASES_EPISTEMICAS:
            etiqueta = CLASES_EPISTEMICAS[tool.clase]
            fuente = tool.procedencia or "sin fuente declarada"
            cabecera = f"[{etiqueta} · {fuente}] {nombre}"
        else:
            cabecera = f"[sin clasificar — trátalo como no verificado] {nombre}"
        if "error" in r:
            lines.append(
                f"{cabecera}: no se obtuvo dato ({r['error']}). "
                "No inventes el valor: dilo y ofrece cómo obtenerlo."
            )
        else:
            lines.append(f"{cabecera}: {r['result']}")
    return "\n".join(lines)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
