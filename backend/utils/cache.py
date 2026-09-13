"""Estado efímero local del runtime de MolDesign Desktop.

Este módulo es la única fuente para datos que no deben persistirse en SQLite:

* resultados deterministas que se pueden recalcular (TTL);
* progreso de jobs en ejecución;
* eventos SSE de la Torre de Control;
* límites temporales por sesión.

No es un adaptador de infraestructura remota. El proceso del backend posee el
estado y lo descarta al reiniciarse; los resultados científicos y archivos son
responsabilidad de SQLite y ``utils.local_storage`` respectivamente.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


class CacheKey:
    """Construye las claves lógicas del estado efímero local."""

    @staticmethod
    def docking(
        smiles_hash: str,
        target_pdb_id: str,
        config_fingerprint: str | None = None,
    ) -> str:
        suffix = f":{config_fingerprint}" if config_fingerprint else ":legacy"
        return f"docking:{smiles_hash}:{target_pdb_id}{suffix}"

    @staticmethod
    def properties(smiles_hash: str) -> str:
        return f"props:{smiles_hash}"

    @staticmethod
    def job_progress(task_id: str) -> str:
        return f"progress:{task_id}"

    @staticmethod
    def stage_events(task_id: str) -> str:
        return f"events:{task_id}"

    @staticmethod
    def molecule_score(smiles_hash: str, target_pdb_id: str) -> str:
        return f"score:{smiles_hash}:{target_pdb_id}"

    @staticmethod
    def rate_limit(user_id: str, endpoint: str) -> str:
        return f"ratelimit:{user_id}:{endpoint}"

    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"


class LocalRuntimeStore:
    """Caché y bus de eventos acotados al proceso desktop.

    El almacenamiento es deliberadamente efímero. Ningún caller puede asumir
    que sobreviva a un reinicio: para eso existen el repositorio SQLite y el
    almacenamiento local de archivos. Las claves y los TTL se mantienen para
    no alterar los contratos del pipeline que ya está en producción.
    """

    _max_memory_items = 10_000
    _max_stage_events_per_task = 1_000
    _stage_event_ttl_seconds = 3_600
    _subscriber_queue_size = 256

    def __init__(self) -> None:
        self._memory: dict[str, Any] = {}
        self._memory_ttl: dict[str, float] = {}
        self._memory_order: list[str] = []
        self._stage_event_subscribers: dict[
            str,
            set[asyncio.Queue[dict[str, Any]]],
        ] = {}
        # La suscripción y su replay deben ser una operación indivisible: evita
        # que un evento se pierda entre ambos pasos.
        self._stage_event_lock = asyncio.Lock()

    def _remove_key(self, key: str) -> bool:
        existed = key in self._memory
        self._memory.pop(key, None)
        self._memory_ttl.pop(key, None)
        try:
            self._memory_order.remove(key)
        except ValueError:
            pass
        return existed

    def _clean_expired(self) -> None:
        now = time.monotonic()
        for key, expires_at in tuple(self._memory_ttl.items()):
            if expires_at <= now:
                self._remove_key(key)

    def _touch(self, key: str) -> None:
        try:
            self._memory_order.remove(key)
        except ValueError:
            pass
        self._memory_order.append(key)

    def _evict_lru(self) -> None:
        while len(self._memory) > self._max_memory_items and self._memory_order:
            self._remove_key(self._memory_order[0])

    async def get(self, key: str) -> Any | None:
        """Obtiene un valor vigente, o ``None`` si no existe/expiró."""
        self._clean_expired()
        value = self._memory.get(key)
        if value is not None:
            self._touch(key)
        log.debug("runtime_store_get", key=key, hit=value is not None)
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Guarda un valor efímero y opcionalmente fija su TTL en segundos."""
        self._clean_expired()
        self._memory[key] = value
        if ttl is None:
            self._memory_ttl.pop(key, None)
        else:
            self._memory_ttl[key] = time.monotonic() + ttl
        self._touch(key)
        self._evict_lru()
        log.debug("runtime_store_set", key=key, ttl=ttl)
        return True

    async def delete(self, key: str) -> bool:
        """Elimina una clave; retorna si existía antes de la eliminación."""
        self._clean_expired()
        existed = self._remove_key(key)
        log.debug("runtime_store_delete", key=key, existed=existed)
        return existed

    async def exists(self, key: str) -> bool:
        self._clean_expired()
        return key in self._memory

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> bool:
        """Guarda varios valores con el mismo TTL sin exponer estado parcial."""
        self._clean_expired()
        expires_at = time.monotonic() + ttl if ttl is not None else None
        for key, value in items.items():
            self._memory[key] = value
            if expires_at is None:
                self._memory_ttl.pop(key, None)
            else:
                self._memory_ttl[key] = expires_at
            self._touch(key)
        self._evict_lru()
        log.debug("runtime_store_set_many", count=len(items), ttl=ttl)
        return True

    async def increment(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        """Incrementa un contador; su TTL inicia sólo con el primer valor."""
        self._clean_expired()
        is_new = key not in self._memory
        current = self._memory.get(key, 0)
        if not isinstance(current, (int, float)):
            current = 0
        value = current + amount
        self._memory[key] = value
        if is_new and ttl is not None:
            self._memory_ttl[key] = time.monotonic() + ttl
        self._touch(key)
        self._evict_lru()
        return value

    async def get_docking_result(
        self,
        smiles_hash: str,
        target_pdb_id: str,
        config_fingerprint: str | None = None,
    ) -> dict[str, Any] | None:
        value = await self.get(
            CacheKey.docking(smiles_hash, target_pdb_id, config_fingerprint)
        )
        return value if isinstance(value, dict) else None

    async def set_docking_result(
        self,
        smiles_hash: str,
        target_pdb_id: str,
        result: dict[str, Any],
        config_fingerprint: str | None = None,
    ) -> bool:
        return await self.set(
            CacheKey.docking(smiles_hash, target_pdb_id, config_fingerprint),
            result,
            ttl=settings.runtime_cache_docking_ttl,
        )

    async def set_job_progress(
        self,
        task_id: str,
        progress: int,
        status: str,
        detail: str | None = None,
    ) -> bool:
        """Actualiza el progreso local preservando timestamps reales."""
        existing = await self.get(CacheKey.job_progress(task_id))
        existing = existing if isinstance(existing, dict) else {}
        started_at = existing.get("started_at")
        if started_at is None and progress > 0:
            started_at = datetime.now(UTC).isoformat()

        finished_at = existing.get("finished_at")
        if finished_at is None and status in {"done", "failed"}:
            finished_at = datetime.now(UTC).isoformat()

        return await self.set(
            CacheKey.job_progress(task_id),
            {
                "task_id": task_id,
                "progress": max(0, min(100, progress)),
                "status": status,
                "detail": detail,
                "started_at": started_at,
                "finished_at": finished_at,
            },
            ttl=self._stage_event_ttl_seconds,
        )

    async def get_job_progress(self, task_id: str) -> dict[str, Any] | None:
        value = await self.get(CacheKey.job_progress(task_id))
        return value if isinstance(value, dict) else None

    async def push_stage_event(self, task_id: str, event_dict: dict[str, Any]) -> bool:
        """Registra y difunde un evento SSE sin depender de un servicio externo."""
        key = CacheKey.stage_events(task_id)
        event = dict(event_dict)
        async with self._stage_event_lock:
            self._clean_expired()
            events = self._memory.get(key, [])
            if not isinstance(events, list):
                events = []
            events.append(event)
            if len(events) > self._max_stage_events_per_task:
                events = events[-self._max_stage_events_per_task :]
            self._memory[key] = events
            self._memory_ttl[key] = time.monotonic() + self._stage_event_ttl_seconds
            self._touch(key)
            self._evict_lru()

            for subscriber in tuple(self._stage_event_subscribers.get(task_id, ())):
                try:
                    subscriber.put_nowait(dict(event))
                except asyncio.QueueFull:
                    # La recuperación autoritativa sigue siendo replay/polling;
                    # un cliente lento sólo pierde su evento vivo más antiguo.
                    try:
                        subscriber.get_nowait()
                        subscriber.put_nowait(dict(event))
                    except asyncio.QueueEmpty:
                        pass
        return True

    async def get_stage_events(self, task_id: str) -> list[dict[str, Any]]:
        self._clean_expired()
        events = self._memory.get(CacheKey.stage_events(task_id), [])
        if not isinstance(events, list):
            return []
        return [dict(event) for event in events if isinstance(event, dict)]

    async def subscribe_stage_events(
        self,
        task_id: str,
    ) -> tuple[list[dict[str, Any]], asyncio.Queue[dict[str, Any]]]:
        """Suscribe al SSE y obtiene un replay sin hueco entre ambos pasos."""
        subscriber: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._subscriber_queue_size,
        )
        async with self._stage_event_lock:
            self._clean_expired()
            events = self._memory.get(CacheKey.stage_events(task_id), [])
            replay = (
                [dict(event) for event in events if isinstance(event, dict)]
                if isinstance(events, list)
                else []
            )
            self._stage_event_subscribers.setdefault(task_id, set()).add(subscriber)
        return replay, subscriber

    async def unsubscribe_stage_events(
        self,
        task_id: str,
        subscriber: asyncio.Queue[dict[str, Any]],
    ) -> None:
        """Elimina un suscriptor SSE sin afectar a los demás clientes."""
        async with self._stage_event_lock:
            subscribers = self._stage_event_subscribers.get(task_id)
            if subscribers is None:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._stage_event_subscribers.pop(task_id, None)

    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        count = await self.increment(
            CacheKey.rate_limit(user_id, endpoint),
            ttl=window_seconds,
        )
        allowed = count <= limit
        if not allowed:
            log.warning(
                "runtime_rate_limit_exceeded",
                user_id=user_id,
                endpoint=endpoint,
                count=count,
                limit=limit,
            )
        return allowed, count


# Singleton para jobs del dispatcher y dependencia FastAPI para endpoints.
runtime_store = LocalRuntimeStore()
cache = runtime_store


async def get_cache() -> LocalRuntimeStore:
    """Inyecta el almacenamiento efímero local en un endpoint FastAPI."""
    return runtime_store
