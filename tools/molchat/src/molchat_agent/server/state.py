"""Sidecar process state: single-user, pinned to the host identity (PD-04).

Scope (declared, MP-06): one process serves ONE account — the ``sub`` of the
first authenticated call pins the process. A different account gets 403 and
must restart the sidecar (or reconnect with its own process). Revoked
sessions stay revoked until restart. UI reconnects just work: auth is
stateless per request, nothing lives in the observer connection.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from ..conversation.engine import ConversationEngine
from ..conversation.memory import MemoryStore
from ..conversation.tools import PlatformBackend, ToolBackend
from ..providers.registry import ProviderRegistry
from ..voice.stt import SpeechToText
from .executions import ExecutionManager


class AccountMismatch(ValueError):
    """This sidecar process is already bound to another account."""


@dataclass
class ServerState:
    secret: bytes
    registry: ProviderRegistry
    memory: MemoryStore
    backend: ToolBackend
    allowed_origins: tuple[str, ...] = ()
    provider_id: str | None = None
    executions: ExecutionManager | None = None
    stt: SpeechToText | None = None
    user_id: str | None = None
    revoked: set[str] = field(default_factory=set)
    case_requests: dict[str, tuple[str, asyncio.Future[dict[str, str]]]] = field(default_factory=dict)
    smiles_requests: dict[str, tuple[str, asyncio.Future[dict[str, str]]]] = field(default_factory=dict)
    receptor_requests: dict[str, tuple[str, asyncio.Future[dict[str, str]]]] = field(default_factory=dict)
    evaluation_requests: dict[str, tuple[str, asyncio.Future[dict[str, str]]]] = field(default_factory=dict)
    editor_requests: dict[str, tuple[str, asyncio.Future[dict[str, str]]]] = field(default_factory=dict)
    structure_cache: OrderedDict[str, tuple[float, dict[str, str]]] = field(default_factory=OrderedDict)
    pubchem_client: Any | None = None  # injected only for tests; production creates a restricted client
    # Hosted mode (MOLCHAT_HOST_SECRET set): platform calls forward the
    # request's Bearer instead of a fixed token. `bridge` is the shared
    # platform client the endpoints bind per request.
    hosted: bool = False
    bridge: Any | None = None

    def pin_user(self, sub: str) -> None:
        """Bind the process to the first account; reject any other."""
        if self.user_id is None:
            self.user_id = sub
            return
        if self.user_id != sub:
            raise AccountMismatch(
                "este sidecar ya sirve a otra cuenta; "
                "reinícialo para cambiar de identidad")

    async def registro_de_turno(self, platform_token: str | None = None) -> ProviderRegistry:
        """El registro de esta llamada. En modo alojado trae la clave de la cuenta (sólo
        para esta llamada); fuera de él, el registro de la máquina de siempre."""
        if not (self.hosted and self.bridge is not None):
            return self.registry
        from ..providers.alojado import registro_del_turno
        return await registro_del_turno(self.registry, self.bridge.with_token(platform_token))

    def engine_for(self, sub: str, platform_token: str | None = None,
                   registro: ProviderRegistry | None = None) -> ConversationEngine:
        backend = self.backend
        if self.hosted and isinstance(backend, PlatformBackend):
            backend = backend.with_token(platform_token)
        registro = registro or self.registry
        return ConversationEngine(
            registry=registro, backend=backend, memory=self.memory,
            user_id=sub, provider_id=self.provider_id or registro.active_id)

    def revoke(self, jti: str) -> None:
        self.revoked.add(jti)
        self.structure_cache.clear()

    def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked

    def status(self) -> dict[str, Any]:
        return {"account_bound": self.user_id is not None,
                "revoked_sessions": len(self.revoked)}
