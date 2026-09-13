from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from services.ai.providers.base import AIProvider, ProviderConfig, ProviderInfo
from services.ai.redaccion import redactar_secretos
from utils.logger import get_logger

log = get_logger(__name__)


class OllamaProvider(AIProvider):
    id = "ollama"
    name = "Ollama"
    description = "Servidor Ollama local (localhost:11434). Sin API key, requiere Ollama instalado."

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        if not self._config.base_url:
            self._config.base_url = "http://localhost:11434"
        if not self._config.model:
            self._config.model = "gemma3:1b"
        if not self._config.temperature:
            self._config.temperature = 0.1
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    def validate_config(self) -> tuple[bool, str]:
        try:
            import httpx
            resp = httpx.get(f"{self._config.base_url.rstrip('/')}/api/tags", timeout=3)
            if resp.status_code == 200:
                return True, "OK"
            return False, f"Ollama no responde en {self._config.base_url}"
        except Exception as e:
            return False, f"No se pudo conectar a Ollama: {str(e)[:80]}"

    def get_info(self) -> ProviderInfo:
        models = []
        try:
            import httpx
            resp = httpx.get(f"{self._config.base_url.rstrip('/')}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=False,
            requires_base_url=True,
            default_base_url="http://localhost:11434",
            default_model="gemma3:1b",
            available_models=models,
            configured=bool(models),
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        url = f"{self._config.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if stream:
                    async with client.stream("POST", url, json=payload) as response:
                        if response.status_code != 200:
                            yield f"Error Ollama ({response.status_code})"
                            return
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    yield data["message"]["content"]
                            except json.JSONDecodeError:
                                pass
                else:
                    payload["stream"] = False
                    resp = await client.post(url, json=payload, timeout=120.0)
                    if resp.status_code != 200:
                        yield f"Error Ollama ({resp.status_code})"
                        return
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
        except Exception as e:
            yield f"Error conectando con Ollama: {redactar_secretos(e)[:100]}"

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._config.base_url.rstrip('/')}/api/tags")
                if resp.status_code == 200:
                    return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return [self._config.model]
