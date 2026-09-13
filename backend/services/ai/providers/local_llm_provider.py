from __future__ import annotations

from typing import AsyncIterator

from services.ai.local_llm import diagnosticar_llm_local, get_local_llm
from services.ai.providers.base import AIProvider, ProviderConfig, ProviderInfo
from utils.logger import get_logger

log = get_logger(__name__)


class LocalLLMProvider(AIProvider):
    id = "local"
    name = "MolChat Local"
    description = (
        "Modelo GGUF local cargado via llama-server.exe (CUDA b10199). "
        "El modelo concreto lo elige el usuario dinámicamente desde la UI; "
        "este provider no asume ninguno por defecto."
    )

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        # Resolución DINÁMICA del modelo: si el usuario no eligió uno (config.model
        # vacío), tomamos el primer .gguf disponible en models/llm/. No hardcodeamos
        # ningún nombre de modelo — el catálogo viene de model_registry.get_local_models().
        if not self._config.model:
            self._config.model = self._pick_first_available_model()
        if not self._config.temperature:
            # 0.05 (no 0.0): determinismo sin degeneración. Modelos Q1-bit en temp=0
            # a veces entran en loops de generación repetidos. 0.05 preserva la
            # reproducibilidad necesaria para debugear alucinaciones, manteniendo
            # un minimo de divergencia que evita el degenerativo.
            self._config.temperature = 0.05
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    @staticmethod
    def _pick_first_available_model() -> str:
        """Elegir el modelo .gguf disponible para usar por defecto.

        Prioridad: (1) el _DEFAULT_MODEL_FILE de local_llm.py (Qwen 2.5 Q4 —
        el modelo de producción validado), si existe en disco; (2) si no,
        el primero alfabético de los .gguf disponibles. "" si no hay ninguno.
        """
        try:
            from services.ai.local_llm import _DEFAULT_MODEL_FILE
            from services.ai.model_registry import get_local_models
            models = get_local_models()
            if not models:
                return ""
            # El default documentado tiene prioridad absoluta: el orden
            # alfabético podía elegir Bonsai-8B-Q1_0 (1-bit, peor calidad)
            # porque "Bonsai" < "qwen" — y el usuario quedaba con el modelo
            # equivocado sin haberlo elegido (bug de producción destapado
            # en la quality suite 2026-08-01).
            for m in models:
                if m.get("filename") == _DEFAULT_MODEL_FILE:
                    return m["filename"]
            return models[0]["filename"]
        except ImportError:
            pass
        return ""

    def validate_config(self) -> tuple[bool, str]:
        # Si el LLM ya está cargado y vivo, está configurado — el chequeo de
        # RAM/VRAM solo decide si PODEMOS cargar, no debe matar una sesión viva.
        # BUG encontrado en stress test 100 queries: la conversación acumulada
        # hace bajar la RAM libre (10.6 → 4.2GB) y con fluctuaciones del sistema
        # < 4GB, is_local_llm_available() devolvía False → TODA query moría con
        # warning silencioso (0.0s, sin log de classifier).
        try:
            from services.ai.local_llm import get_local_llm
            llm = get_local_llm()
            if llm and llm.is_loaded:
                return True, "OK"
        except Exception:
            pass
        # Un solo diagnóstico, que además distingue las tres causas. Antes esto
        # eran dos mensajes escritos a mano: el primero acusaba siempre al
        # binario —aunque estuviera en su sitio— y citaba una ruta de
        # documentación interna que no viaja en el producto, así que el usuario
        # leía «Detalles: docs/33_MIGRATION_LLAMA_SERVER.md» y no tenía ese
        # archivo en ninguna parte.
        disponible, motivo = diagnosticar_llm_local()
        if not disponible:
            return False, motivo
        if not self._config.model:
            return (
                False,
                "Hay modelos descargados, pero ninguno seleccionado. Elige uno en "
                "Opciones ▸ Modelos.",
            )
        return True, "OK"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=False,
            requires_base_url=False,
            # default_model dinámico: el primero disponible localmente.
            # La UI usa esto como sugerencia inicial, no como restricción.
            default_model=self._pick_first_available_model(),
            configured=self.validate_config()[0],
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        llm = get_local_llm()
        if not llm:
            yield "Error: No se pudo inicializar el motor LLM local."
            return

        # Respetar SIEMPRE el modelo que eligió el usuario en la UI.
        # Antes esto tenía un workaround `if model != "qwen..."` para no recargar
        # el default — pero eso rompe la selección dinámica: si el usuario cambiaba
        # de modelo, esa guarda impedía aplicar el cambio cuando re-usaba Qwen.
        # Desde el fix de set_model_file() (idempotente: solo descarga si CAMBIÓ),
        # es seguro llamarlo siempre. Aplica a chat() y a chat_with_tools().
        if self._config.model:
            llm.set_model_file(self._config.model)

        if not llm.load(retry=True):
            error = llm.load_error or "razón desconocida"
            if "Pipeline ocupado" in error:
                yield (
                    "__WARNING__:⏳ Evaluación en curso. MolChat está en espera. "
                    "Cuando termine el acoplamiento, el modelo se cargará solo. "
                    "Mientras tanto, si tienes una clave de API puedes configurar un "
                    "proveedor en la nube desde Opciones ▸ Intérprete IA y usar MolChat "
                    "sin esperar."
                )
            elif "RAM insuficiente" in error:
                yield f"__WARNING__:💾 {error}"
            elif "not found" in error or "not installed" in error:
                yield (
                    "__WARNING__:El modelo que tenías seleccionado ya no está en "
                    "este equipo. Vuelve a descargarlo desde Opciones ▸ Modelos, o "
                    "usa un proveedor en la nube desde Opciones ▸ Intérprete IA."
                )
            else:
                yield f"__WARNING__:{error}"
            return

        # Multi-turno nativo: pasamos `messages` directo a generate_stream/generate.
        # ANTES (llama-cpp-python): el wrapper solo aceptaba prompt+system_prompt
        # separados, así que este provider aplanaba todo el historial en dos strings,
        # metiendo "Assistant: ..." adentro del user content. Eso rompía el
        # multi-turno — el modelo perdía el sentido de conversación y respondía
        # muy genérico, casi amnésico (bug #4 de la migración).
        # AHORA (llama-server.exe): el wrapper acepta `messages: list[dict]`
        # OpenAI-style y lo pasa directo a /v1/chat/completions, preservando
        # la estructura de turnos [system, user, assistant, user, assistant, ...].
        if not messages:
            yield "Error: No hay mensaje de usuario."
            return

        try:
            from services.ai.resource_manager import get_resource_manager
            get_resource_manager().touch()
        except ImportError:
            pass

        if stream:
            # generate_stream es AsyncIterator[str] desde la migración a llama-server.exe
            # (corrige bug #3: antes era Iterator[str] síncrono que bloqueaba el event loop).
            # temperature ahora se respeta (corrige bug #2: antes hardcodeada a 0.1 en el wrapper).
            async for token in llm.generate_stream(
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            ):
                if token:
                    yield token
        else:
            result = llm.generate(
                messages=messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )
            if result:
                yield result
            else:
                yield "Error: El modelo local no generó respuesta."

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
    ) -> dict:
        """Llamar al LLM con herramientas nativas (OpenAI function calling).

        No hace streaming — devuelve {"content": str, "tool_calls": [...]}.
        El caller debe ejecutar las tools e inyectar los resultados.
        """
        llm = get_local_llm()
        if not llm:
            return {"content": "Error: LLM no disponible.", "tool_calls": []}

        # Mismo contrato que chat(): respetar el modelo del usuario SIEMPRE.
        # Antes este path faltaba y el tool-calling nativo cargaba el modelo default
        # del server, ignorando la selección del usuario (bug silencioso).
        if self._config.model:
            llm.set_model_file(self._config.model)

        if not llm.load(retry=True):
            error = llm.load_error or "razon desconocida"
            return {"content": f"Error al cargar LLM: {error}", "tool_calls": []}

        try:
            from services.ai.resource_manager import get_resource_manager
            get_resource_manager().touch()
        except ImportError:
            pass

        return llm.generate_with_tools(
            messages=messages,
            tools=tools,
            max_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
        )

    async def list_models(self) -> list[str]:
        try:
            from services.ai.model_registry import get_local_models
            models = get_local_models()
            return [m["filename"] for m in models]
        except ImportError:
            return []
        # No hay fallback hardcodeado: si no hay .gguf en models/llm/, devolvemos []
        # para que la UI muestre "sin modelos" honestamente. Antes devolvía
        # ["qwen2.5-1.5b-instruct-q4_k_m.gguf"] que fingía que existía un archivo.
