"""HTTP bridge to the *existing* MolDesign FastAPI contracts.

No filesystem, shell, or arbitrary HTTP endpoint is exposed as an agent tool.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from .tools import capability
from .config import load_config


class BridgeError(RuntimeError):
    """A MolDesign service call failed without exposing credentials."""

    def __init__(self, message: str, *, status_code: int | None = None,
                 detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code  # HTTP status when a response arrived
        self.detail = detail  # server detail, truncated, for 4xx mapping


class BridgeTransportError(BridgeError):
    """No response was received at all (transport lost, timeout, disconnect).

    A subclass of BridgeError, but the executor treats it differently on
    effectful steps: an error RESPONSE is definitive (failed), a lost
    response is unknown (ambiguous, never auto-resent).
    """


def validate_base_url(value: str, *, allow_remote: bool = False) -> str:
    url = urlsplit(value)
    local = url.hostname in ("127.0.0.1", "localhost", "::1")
    if (
        url.scheme not in ("http", "https") or not url.hostname or
        url.username or url.password or url.path not in ("", "/") or
        url.query or url.fragment
    ):
        raise ValueError("URL base MolDesign no válida")
    if not local and (not allow_remote or url.scheme != "https"):
        raise ValueError("Sólo loopback; un servidor remoto exige HTTPS y autorización expresa")
    return value.rstrip("/")


def _error_detail(response: Any) -> str | None:
    """Best-effort server detail for 4xx mapping (truncated, never raises)."""
    try:
        payload = response.json()
    except ValueError:
        return None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if detail is None:
        return None
    text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return text[:300]


class MolDesignBridge:
    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", *,
        token: str | None = None, allow_remote: bool = False,
        client: httpx.AsyncClient | None = None,
        require_contract: bool = True,
    ) -> None:
        self.base_url = validate_base_url(base_url, allow_remote=allow_remote)
        self._token = token
        self._allow_remote = allow_remote
        self._require_contract = require_contract
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url, timeout=30.0, follow_redirects=False,
            trust_env=False,
        )

    def with_token(self, token: str | None) -> "MolDesignBridge":
        """Same client and URL policy, different Authorization.

        Per-request identity in hosted mode: the sidecar re-sends the
        request's Bearer to the platform instead of a fixed token. The
        shared client is never closed through the bound copy.
        """
        return MolDesignBridge(self.base_url, token=token,
                               allow_remote=self._allow_remote,
                               client=self._client, require_contract=self._require_contract)

    @classmethod
    def from_env(cls) -> "MolDesignBridge":
        config = load_config()
        return cls(
            base_url=config.moldesign_base_url,
            token=config.moldesign_token,
            allow_remote=config.moldesign_allow_remote,
            require_contract=True,
        )

    async def ensure_contract(self, capability_name: str) -> None:
        """Fail closed before any platform operation when negotiation is required."""
        if not self._token:
            raise BridgeError("La plataforma requiere una sesión autenticada")
        try:
            r = await self._client.get('/molchat-host/contract',
                                       headers={'Authorization': f'Bearer {self._token}'})
            if r.status_code != 200 or len(r.content) > 65536:
                raise BridgeError("MolDesign no ofrece el contrato de agente")
            data = r.json()
            if (not isinstance(data, dict) or data.get('contract') != 'moldesign.molchat/1'
                    or not isinstance(data.get('capabilities'), list)
                    or capability_name not in data['capabilities']):
                raise BridgeError("Contrato de MolDesign incompatible o capacidad ausente")
        except (httpx.RequestError, ValueError) as exc:
            raise BridgeError("No se pudo verificar el contrato de MolDesign") from exc

    @property
    def client(self) -> httpx.AsyncClient:
        """Shared HTTP client (the sidecar reuses it for STT)."""
        return self._client

    @property
    def token(self) -> str | None:
        return self._token

    async def __aenter__(self) -> "MolDesignBridge":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def call(self, name: str, arguments: dict[str, Any],
                   *, idempotency_key: str | None = None) -> Any:
        if self._require_contract:
            await self.ensure_contract('platform-actions/1')
        tool = capability(name)
        method, path, query, body, response_kind = tool.request(arguments)
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        if tool.risk == "approval_required" and not self._token:
            raise BridgeError("Se requiere una sesión autenticada para aprobar")
        if response_kind == "sse":
            return await self._collect_sse(name, path, query, headers)
        try:
            if method == "GET":
                response = await self._client.get(path, params=query, headers=headers)
            else:
                kwargs: dict[str, Any] = {"params": query} if query else {}
                if body is not None:
                    kwargs["json"] = body
                response = await self._client.post(path, headers=headers, **kwargs)
            if response.status_code >= 400:
                raise BridgeError(f"MolDesign devolvió HTTP {response.status_code} en {name}",
                                  status_code=response.status_code,
                                  detail=_error_detail(response))
            if response.is_redirect:
                raise BridgeError("MolDesign respondió con una redirección inesperada")
            if len(response.content) > 5_000_000:
                raise BridgeError("Respuesta superior al límite de 5 MB")
            if response_kind == "bytes":
                return response.content
            return response.json()
        except httpx.RequestError as exc:
            raise BridgeTransportError(f"Sin respuesta de MolDesign en {name}") from exc
        except ValueError as exc:
            raise BridgeError(f"No se pudo obtener una respuesta JSON de {name}") from exc

    async def _collect_sse(self, name: str, path: str, query: dict[str, Any],
                           headers: dict[str, str]) -> dict[str, Any]:
        """Collect SSE data events, bounded (500 events / 5 MB total)."""
        events: list[Any] = []
        total = 0
        try:
            async with self._client.stream(
                    "GET", path, params=query, headers=headers,
                    timeout=30.0) as response:
                if response.status_code >= 400:
                    raise BridgeError(f"MolDesign devolvió HTTP {response.status_code} en {name}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    total += len(payload)
                    if total > 5_000_000 or len(events) >= 500:
                        break
                    try:
                        events.append(json.loads(payload))
                    except ValueError:
                        events.append({"text": payload})
        except httpx.RequestError as exc:
            raise BridgeTransportError(f"No se pudo leer el stream de {name}") from exc
        return {"events": events}

    async def _pedir_proveedor(self, metodo: str, ruta: str,
                               cuerpo: dict[str, Any] | None = None) -> dict[str, Any]:
        """Petición de proveedores a MolDesign con la identidad de la sesión. Un 4xx
        devuelve el `motivo` del host en `detail`; nunca una clave en el mensaje."""
        if not self._token:
            raise BridgeError("La plataforma requiere una sesión autenticada")
        try:
            r = await self._client.request(metodo, ruta, json=cuerpo,
                                           headers={"Authorization": f"Bearer {self._token}"})
        except httpx.TimeoutException as exc:
            raise BridgeTransportError("MolDesign no respondió a tiempo") from exc
        except httpx.RequestError as exc:
            raise BridgeTransportError("MolDesign no está disponible") from exc
        if r.status_code >= 400:
            motivo = ""
            try:
                detalle = r.json().get("detail")
                motivo = str(detalle.get("motivo", "")) if isinstance(detalle, dict) else str(detalle or "")
            except (ValueError, AttributeError):
                motivo = ""
            raise BridgeError("MolDesign no entregó la credencial de proveedor",
                              status_code=r.status_code, detail=motivo[:80])
        if len(r.content) > 65536:
            raise BridgeError("respuesta de MolDesign demasiado grande")
        datos = r.json()
        if not isinstance(datos, dict):
            raise BridgeError("respuesta de MolDesign no válida")
        return datos

    async def proveedores_de_cuenta(self) -> dict[str, Any]:
        """Estado de los proveedores de esta cuenta: activo y autorizaciones. Sin claves."""
        return await self._pedir_proveedor("GET", "/molchat-host/proveedores")

    async def credencial(self, proveedor: str, host: str) -> dict[str, Any]:
        """Clave y modelo para UNA llamada. MolDesign sólo la entrega si la cuenta
        autorizó `proveedor@host` y ese host es el del catálogo verificado."""
        return await self._pedir_proveedor("POST", "/molchat-host/credencial",
                                           {"proveedor": proveedor, "host": host})

    async def authorize_pubchem(self) -> None:
        """Check this account's current network policy; do not execute the lookup."""
        if not self._token:
            raise BridgeError("La consulta requiere una sesión MolDesign")
        try:
            response = await self._client.get("/ai/consent/red",
                headers={"Authorization": f"Bearer {self._token}"}, timeout=30.0)
            if response.status_code != 200 or len(response.content) > 65536:
                raise BridgeError("No se pudo consultar el permiso de red", status_code=response.status_code)
            data = response.json()
            if not isinstance(data, dict) or data.get("modo_offline") is not False:
                raise PermissionError("PubChem no disponible en modo sin red")
            destinations = data.get("destinos")
            if not isinstance(destinations, list):
                raise PermissionError("Permiso de PubChem no disponible")
            if not any(isinstance(item, dict) and item.get("servicio") == "pubchem"
                       and item.get("host") == "pubchem.ncbi.nlm.nih.gov"
                       and item.get("consentido") is True for item in destinations):
                raise PermissionError("La cuenta no autorizó PubChem")
        except (httpx.RequestError, ValueError) as exc:
            raise BridgeError("No se pudo consultar el permiso de red") from exc

    async def pubchem_consent(self, *, grant: bool = False, revoke: bool = False) -> dict[str, Any]:
        """Read or explicitly change the account's PubChem permission."""
        if not self._token:
            raise BridgeError("Se necesita una sesión MolDesign")
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            if revoke:
                response = await self._client.delete("/ai/consent/red/pubchem", headers=headers)
            elif grant:
                response = await self._client.post("/ai/consent/red", headers=headers,
                    json={"servicio": "pubchem", "host": "pubchem.ncbi.nlm.nih.gov"})
            else:
                response = await self._client.get("/ai/consent/red", headers=headers)
            if response.status_code != 200 or len(response.content) > 65536:
                raise BridgeError("No se pudo consultar el permiso", status_code=response.status_code)
            data = response.json()
            if not isinstance(data, dict):
                raise BridgeError("Respuesta de permiso no válida")
            return data
        except (httpx.RequestError, ValueError) as exc:
            raise BridgeError("No se pudo consultar el permiso") from exc

    async def transcribe_local(self, audio_bytes: bytes, *, lang: str = "es",
                             token: str | None = None) -> str:
        """Use MolDesign's authenticated local Whisper endpoint.

        ``token`` overrides the configured one for this call (hosted mode
        forwards the request's Bearer); otherwise the fixed token applies.
        """
        effective = token or self._token
        if not effective:
            raise BridgeError("La transcripción requiere una sesión MolDesign")
        if self._require_contract:
            await self.with_token(effective).ensure_contract('platform-actions/1')
        from .voice.moldesign_whisper import MolDesignWhisper  # noqa: PLC0415
        from .voice.stt import STTError  # noqa: PLC0415

        try:
            return await MolDesignWhisper(self._client, effective).transcribe(
                audio_bytes, lang=lang)
        except STTError as exc:
            raise BridgeError(str(exc)) from exc

