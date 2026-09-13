"""Registro de proveedores de IA.

D-09 (decisión del propietario, 2026-08-31): **el proveedor y sus claves son por
cuenta**. Eso parte el registro en dos cosas que antes estaban mezcladas:

* el **catálogo**, que sí es de la máquina —qué tipos de proveedor existen y qué
  trae el entorno como valor por defecto—; y
* la **configuración aplicada**, que es de la cuenta y se resuelve en cada turno
  (`resolve_for_user`) en vez de mutarse sobre el objeto compartido.

Antes, `POST /ai/providers/configure` escribía `provider.config` del singleton:
la clave, el modelo y el `base_url` de una persona pasaban a ser los de todo el
mundo. Y `_providers` y `_active_provider_id` eran atributos de **clase**, la
misma enfermedad que MOLCHAT-BE-006 curó en `ChatService`.
"""

from __future__ import annotations

import threading
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        # De instancia, no de clase: dos registros no comparten catálogo ni activo.
        self._providers: dict[str, Any] = {}
        self._active_provider_id: str = "local"
        self._active_by_user: dict[str, str] = {}
        self._lock = threading.Lock()

    def register(self, provider: Any):
        with self._lock:
            self._providers[provider.id] = provider
            log.info("provider_registered", id=provider.id, name=provider.name)

    def unregister(self, provider_id: str):
        with self._lock:
            self._providers.pop(provider_id, None)

    def get(self, provider_id: str) -> Any | None:
        """Devuelve el proveedor **del catálogo**, con los valores del entorno.

        No lleva configuración de ninguna cuenta: para eso está
        `resolve_for_user`.
        """
        return self._providers.get(provider_id)

    # ── Resolución por cuenta ────────────────────────────────────────────

    def active_provider_id_for_user(
        self, user_id: str | None, incluir_heredadas: bool = False
    ) -> str:
        """Qué proveedor tiene activo esa cuenta; el del entorno si no eligió."""
        if not user_id:
            return self._active_provider_id

        elegido = self._active_by_user.get(user_id)
        if elegido:
            return elegido

        persistido = self._cargar_activo_persistido(user_id, incluir_heredadas)
        if persistido and persistido in self._providers:
            self._active_by_user[user_id] = persistido
            return persistido

        return self._active_provider_id

    def resolve_for_user(
        self,
        provider_id: str | None,
        user_id: str | None,
        incluir_heredadas: bool = False,
    ) -> Any | None:
        """El proveedor que esa cuenta debe usar, con **su** configuración.

        Construye una copia por turno en vez de mutar el objeto del catálogo.
        Es barato: los proveedores no guardan estado entre llamadas —cada uno
        crea su cliente dentro de `chat()`— y el modelo local sigue siendo uno
        solo por máquina, que es lo correcto: se carga una vez, no por cuenta.
        """
        pid = provider_id or self.active_provider_id_for_user(user_id, incluir_heredadas)
        base = self._providers.get(pid)
        if base is None:
            return None
        if not user_id:
            return base

        cfg = self._cargar_config_persistida(pid, user_id, incluir_heredadas)
        if not cfg:
            return base

        return self._con_configuracion(base, cfg)

    @staticmethod
    def _con_configuracion(base: Any, cfg: dict[str, Any]) -> Any:
        """Copia del proveedor del catálogo con los valores de la cuenta encima."""
        from dataclasses import replace

        cambios: dict[str, Any] = {}
        if cfg.get("api_key"):
            cambios["api_key"] = cfg["api_key"]
        if cfg.get("base_url"):
            cambios["base_url"] = cfg["base_url"]
        if cfg.get("model"):
            cambios["model"] = cfg["model"]
        if cfg.get("temperature") is not None:
            cambios["temperature"] = float(cfg["temperature"])
        if cfg.get("max_tokens") is not None:
            cambios["max_tokens"] = int(cfg["max_tokens"])
        if cfg.get("extra") is not None:
            cambios["extra"] = cfg["extra"]

        if not cambios:
            return base

        try:
            return type(base)(config=replace(base.config, **cambios))
        except Exception as exc:  # pragma: no cover - proveedor mal formado
            log.warning("provider_overlay_failed", id=getattr(base, "id", "?"), error=str(exc))
            return base

    def set_active(self, provider_id: str, user_id: str | None = None) -> bool:
        """Fija el proveedor activo **de una cuenta**.

        Sin `user_id` sólo mueve el valor por defecto del proceso, que es lo que
        usan las sondas sin sesión.
        """
        with self._lock:
            if provider_id not in self._providers:
                return False
            if user_id:
                self._active_by_user[user_id] = provider_id
                self._persist_active_provider(provider_id, user_id)
            else:
                self._active_provider_id = provider_id
            log.info("active_provider_changed", id=provider_id)
            return True

    @property
    def active_provider_id(self) -> str:
        """Valor por defecto del proceso. La vista con sesión es por cuenta."""
        return self._active_provider_id

    def get_active(self) -> Any | None:
        """Proveedor por defecto del proceso, sin configuración de cuenta."""
        return self.get(self._active_provider_id)

    def apply_env_defaults(self) -> None:
        """Antes cargaba la configuración persistida sobre los objetos compartidos.

        Con D-09 eso es justamente lo que no puede hacerse: los valores
        persistidos son de una cuenta y se aplican en `resolve_for_user`. El
        catálogo se queda con lo que trae el entorno.
        """
        return None

    def list_providers(
        self, user_id: str | None = None, incluir_heredadas: bool = False
    ) -> list[dict]:
        """Catálogo visto por una cuenta.

        `configured` y `active` son datos de cuenta desde D-09: sin `user_id`
        —las sondas de arranque `GET /ai/providers` y `GET /ai/status`, que
        responden antes del auto-login— se contestan con el catálogo desnudo,
        para no publicar de quién es la clave.
        """
        activo = self.active_provider_id_for_user(user_id, incluir_heredadas)
        result = []
        for pid, provider in self._providers.items():
            visto = (
                self.resolve_for_user(pid, user_id, incluir_heredadas)
                if user_id
                else provider
            )
            info = visto.get_info()
            result.append({
                "id": info.id,
                "name": info.name,
                "description": info.description,
                "requires_api_key": info.requires_api_key,
                "requires_base_url": info.requires_base_url,
                "default_base_url": info.default_base_url,
                "default_model": info.default_model,
                "available_models": info.available_models,
                "configured": bool(user_id) and info.configured,
                "active": pid == activo,
            })
        return result

    def get_active_info(
        self, user_id: str | None = None, incluir_heredadas: bool = False
    ) -> dict | None:
        provider = self.resolve_for_user(None, user_id, incluir_heredadas)
        if not provider:
            return None
        info = provider.get_info()
        return {
            "id": info.id,
            "name": info.name,
            "configured": bool(user_id) and info.configured,
            "active": True,
        }

    # ── Persistencia ─────────────────────────────────────────────────────

    @staticmethod
    def _cargar_config_persistida(
        provider_id: str, user_id: str, incluir_heredadas: bool
    ) -> dict[str, Any]:
        try:
            from services.ai.provider_config_store import load_provider_config
            return load_provider_config(provider_id, user_id, incluir_heredadas)
        except Exception as exc:
            log.warning("provider_config_load_failed", id=provider_id, error=str(exc)[:200])
            return {}

    @staticmethod
    def _cargar_activo_persistido(user_id: str, incluir_heredadas: bool) -> str | None:
        try:
            from services.ai.provider_config_store import load_active_provider
            return load_active_provider(user_id, incluir_heredadas)
        except Exception as exc:
            log.warning("active_provider_load_failed", error=str(exc)[:200])
            return None

    @staticmethod
    def _persist_active_provider(provider_id: str, user_id: str) -> None:
        """Fallar aquí deja la elección sólo en memoria; hay que enterarse."""
        try:
            from services.ai.provider_config_store import save_active_provider
            save_active_provider(provider_id, user_id)
        except Exception as exc:
            log.warning(
                "active_provider_persist_failed", id=provider_id, error=str(exc)[:200]
            )


_registry: ProviderRegistry | None = None
_rm_lock = threading.Lock()


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        with _rm_lock:
            if _registry is None:
                _registry = ProviderRegistry()
    return _registry
