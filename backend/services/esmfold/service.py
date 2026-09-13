"""
services/esmfold/service.py

Capa de cliente para ESMFold con degradación elegante.

Mejoras v2 (jun-2026):
  - Manejo granular de errores: distingue "PC apagada" (ConnectionRefused)
    de "servicio colgado" (Timeout) de "error HTTP" del propio ESMFold.
  - Circuit breaker simple: si la URL falla N veces en M segundos, deja
    de intentarlo hasta que pase un cooldown (evita spam de timeouts).
  - Health check perezoso: solo se revalida después de `health_ttl_seconds`.
  - Retry una vez con backoff antes de rendirse.
  - Logging estructurado que el operador puede leer para entender
    exactamente qué pasó cuando algo falla.

Contrato del servicio externo (compatible con `local_services/esmfold/`):
  GET  /health   → 200 {"status": "ok", ...}
  POST /predict  → 200 {"success": bool, "poses": [{"rank","confidence","peptide_pdb","rmsd"}], ...}
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import httpx  # preferimos httpx: async nativo, timeouts precisos
    _USE_HTTPX = True
except ImportError:
    # Fallback a urllib estándar si httpx no está disponible
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
    _USE_HTTPX = False

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


# ── Tipos públicos ────────────────────────────────────────────────────────


@dataclass
class ESMFoldPose:
    """Una pose predicha por ESMFold.

    `confidence` es confianza ESTRUCTURAL del plegado (pLDDT/100). No es una
    afinidad, no se deriva de una afinidad y no se convierte a kcal/mol.

    `vina_affinity_kcal_mol` es la salida literal de Vina cuando esta pose pasó
    por Vina, y `None` cuando no. `origen` dice cuál de los dos casos es. Ver
    `sidecars/esmfold/predictor.py::PredictedPose` para lo que pasaba antes de
    que existieran estos dos campos.
    """

    rank: int
    confidence: float
    ligand_pdb: str
    rmsd: float | None = None
    vina_affinity_kcal_mol: float | None = None
    ligand_sdf: str | None = None
    origen: str = "vina_docked"


@dataclass
class ESMFoldResult:
    """Resultado completo de una predicción de ESMFold."""

    success: bool
    poses: list[ESMFoldPose] = field(default_factory=list)
    best_confidence: float | None = None
    method: str = "ESMFold"
    execution_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    scientific_status: str = "EXPERIMENTAL"
    transfer_manifest: dict[str, Any] | None = None

    @property
    def scientific_context(self) -> str:
        return (
            "ESMFold predice la estructura del péptido a partir de su secuencia; "
            "no es un modelo de docking ni una medida de afinidad. En MolDesign "
            "sus coordenadas se transfieren al grafo del SMILES y Vina realiza el "
            "acoplamiento cuando la reconstrucción química es válida."
        )


class ServiceUnavailableReason:
    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    CIRCUIT_OPEN = "circuit_open"          # demasiados fallos recientes
    CONNECTION_REFUSED = "connection_refused"  # PC apagada o puerto cerrado
    TIMEOUT = "timeout"                    # prendida pero no responde
    HTTP_ERROR = "http_error"              # prendida, responde, pero error
    INVALID_RESPONSE = "invalid_response"  # prendida, responde 200, JSON raro
    UNKNOWN = "unknown"


# ── Circuit breaker ──────────────────────────────────────────────────────


class CircuitBreaker:
    """
    Circuit breaker minimalista.

    Estado:
      - closed:   tráfico normal, se cuentan fallos.
      - open:     demasiados fallos → no se intenta hasta `cooldown_seconds`.

    Cuenta fallos en una ventana deslizante de `window_seconds`. Si supera
    `failure_threshold`, abre el circuito. Tras `cooldown_seconds` pasa a
    half-open implícito: el siguiente intento se permite y, si tiene éxito,
    resetea; si falla, vuelve a abrir.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._failures: list[float] = []
        self._opened_at: float | None = None

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures.append(now)
        # podar ventana
        cutoff = now - self.window_seconds
        self._failures = [t for t in self._failures if t >= cutoff]
        if len(self._failures) >= self.failure_threshold:
            self._opened_at = now

    def record_success(self) -> None:
        self._failures.clear()
        self._opened_at = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown_seconds:
            # cooldown cumplido: half-open, dejamos pasar el próximo intento
            self._opened_at = None
            return False
        return True


# ── Cliente principal ─────────────────────────────────────────────────────


class ESMFoldService:
    """
    Cliente del servicio ESMFold externo (típicamente la PC local del
    desarrollador, `local_services/esmfold/`).
    """

    # ── Timeouts ─────────────────────────────────────────────────────────
    #
    # EL CLIENTE NO PUEDE RENDIRSE ANTES QUE EL SERVIDOR. Estaba en 180 s
    # mientras el sidecar aborta a los 300 (`ESMFOLD_PREDICT_TIMEOUT`): el
    # cliente declaraba «ESMFold no responde a tiempo» con el sidecar todavía
    # trabajando, y cuando éste terminaba no había nadie recogiendo el
    # resultado. Peor: el reintento encontraba el proceso ocupado.
    #
    # Y 180 s no daban ni para un caso pequeño. Medido en CPU con el runtime
    # embebido, receptor 1HSG y la caja del catálogo:
    #
    #     GRGDSP, 6 residuos, 41 átomos pesados     120 s
    #     péptidos de 8-9 residuos                  agotan los 300 s del sidecar
    #
    # El plegado es la parte rápida —5-10 s—; lo que tarda es Vina con un
    # ligando de 70-80 átomos pesados y sus grados de libertad. 1200 s es lo
    # que `services/esmfold_pro/service.py` ya usa para la misma clase de
    # trabajo; el cliente espera un poco más para que el veredicto de abortar
    # sea del servidor, que es quien sabe por qué.
    HEALTH_TIMEOUT_S = 3.0       # health check debe ser rapidísimo
    PREDICT_TIMEOUT_S = 1320.0
    READ_TIMEOUT_S = 1320.0

    # Caché de health
    HEALTH_TTL_S = 30.0          # cache de "está vivo" por 30s

    # Retry
    PREDICT_MAX_RETRIES = 1      # un reintento antes de fallback

    def __init__(self):
        self._api_url: str | None = None
        self._available: bool | None = None
        self._last_health_check: float = 0.0
        self._last_reason: str = ServiceUnavailableReason.NOT_CONFIGURED
        self._circuit = CircuitBreaker()
        self._load_config()

    def _load_config(self) -> None:
        try:
            settings = get_settings()
            self._api_url = settings.esmfold_api_url
        except Exception:
            self._api_url = None

    @property
    def is_configured(self) -> bool:
        return self._api_url is not None and len(self._api_url) > 0

    @property
    def api_url(self) -> str | None:
        return self._api_url

    # ── Health check con caché y circuit breaker ─────────────────────────

    async def check_health(self, force: bool = False) -> dict[str, Any]:
        """Comprueba si el servicio está disponible. Cachea por HEALTH_TTL_S."""
        if not self.is_configured:
            self._available = False
            self._last_reason = ServiceUnavailableReason.NOT_CONFIGURED
            return {
                "status": "not_configured",
                "message": "ESMFold no está configurado en las variables de entorno (ESMFOLD_API_URL).",
            }

        # Circuit breaker abierto → no intentar
        if self._circuit.is_open():
            self._available = False
            self._last_reason = ServiceUnavailableReason.CIRCUIT_OPEN
            return {
                "status": "circuit_open",
                "message": "Circuit breaker abierto: ESMFold falló demasiadas veces. Se reintenta tras cooldown.",
                "api_url": self._api_url,
            }

        # Caché válida
        now = time.monotonic()
        if not force and self._available is not None and (now - self._last_health_check) < self.HEALTH_TTL_S:
            return {
                "status": "healthy" if self._available else "unhealthy",
                "api_url": self._api_url,
                "cached": True,
                "reason": self._last_reason,
            }

        # Real check
        result = await self._ping_api()
        self._available = result["ok"]
        self._last_reason = result["reason"]
        self._last_health_check = now
        if result["ok"]:
            self._circuit.record_success()
        else:
            self._circuit.record_failure()

        return {
            "status": "healthy" if result["ok"] else "unhealthy",
            "api_url": self._api_url,
            "reason": self._last_reason,
            "error": result.get("error"),
        }

    async def _ping_api(self) -> dict[str, Any]:
        if not self._api_url:
            return {"ok": False, "reason": ServiceUnavailableReason.NOT_CONFIGURED}
        url = f"{self._api_url}/health"
        try:
            if _USE_HTTPX:
                async with httpx.AsyncClient(timeout=self.HEALTH_TIMEOUT_S) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return {"ok": True, "reason": ServiceUnavailableReason.OK}
                    return {
                        "ok": False,
                        "reason": ServiceUnavailableReason.HTTP_ERROR,
                        "error": f"HTTP {r.status_code}",
                    }
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, self._ping_api_urllib)
                return result
        except httpx.ConnectError if _USE_HTTPX else Exception as e:
            # Connection refused → PC apagada o servicio no corriendo
            err_str = str(e).lower()
            if _USE_HTTPX and isinstance(e, httpx.ConnectError):
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.CONNECTION_REFUSED,
                    "error": f"No se pudo conectar a {self._api_url}: ¿PC apagada o servicio no corriendo?",
                }
            if "connection refused" in err_str or "actively refused" in err_str:
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.CONNECTION_REFUSED,
                    "error": f"Conexión rechazada por {self._api_url}: ¿PC apagada o servicio no corriendo?",
                }
            if "timed out" in err_str or "timeout" in err_str:
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.TIMEOUT,
                    "error": f"Timeout ({self.HEALTH_TIMEOUT_S}s) contacting {self._api_url}",
                }
            return {
                "ok": False,
                "reason": ServiceUnavailableReason.UNKNOWN,
                "error": str(e),
            }
        except httpx.TimeoutException if _USE_HTTPX else Exception as e:
            return {
                "ok": False,
                "reason": ServiceUnavailableReason.TIMEOUT,
                "error": f"Timeout ({self.HEALTH_TIMEOUT_S}s): {e}",
            }

    def _ping_api_urllib(self) -> dict[str, Any]:
        """Fallback urllib síncrono."""
        if not self._api_url:
            return {"ok": False, "reason": ServiceUnavailableReason.NOT_CONFIGURED}
        try:
            req = Request(f"{self._api_url}/health", method="GET")
            with urlopen(req, timeout=self.HEALTH_TIMEOUT_S) as resp:
                if resp.status == 200:
                    return {"ok": True, "reason": ServiceUnavailableReason.OK}
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.HTTP_ERROR,
                    "error": f"HTTP {resp.status}",
                }
        except HTTPError as e:
            return {
                "ok": False,
                "reason": ServiceUnavailableReason.HTTP_ERROR,
                "error": f"HTTP {e.code}",
            }
        except URLError as e:
            err_str = str(e).lower()
            if "connection refused" in err_str or "actively refused" in err_str:
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.CONNECTION_REFUSED,
                    "error": f"Conexión rechazada: {e}",
                }
            if "timed out" in err_str:
                return {
                    "ok": False,
                    "reason": ServiceUnavailableReason.TIMEOUT,
                    "error": f"Timeout: {e}",
                }
            return {
                "ok": False,
                "reason": ServiceUnavailableReason.UNKNOWN,
                "error": str(e),
            }
        except Exception as e:
            return {"ok": False, "reason": ServiceUnavailableReason.UNKNOWN, "error": str(e)}

    # ── Predicción con retry ────────────────────────────────────────────

    async def predict(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
        num_poses: int = 5,
        grid_center: tuple[float, float, float] | None = None,
        grid_size: tuple[float, float, float] | None = None,
    ) -> ESMFoldResult:
        """Envía el PDB del receptor y el SMILES del péptido al servicio ESMFold."""
        if not self.is_configured:
            return ESMFoldResult(
                success=False,
                error="ESMFold no está configurado",
                warnings=[
                    "Servicio ESMFold no configurado (ESMFOLD_API_URL ausente). "
                    "Se usó AutoDock Vina como fallback."
                ],
            )

        # Circuit breaker abierto → no insistir
        if self._circuit.is_open():
            return ESMFoldResult(
                success=False,
                error="Circuit breaker abierto",
                warnings=[
                    f"ESMFold en {self._api_url} falló recientemente. "
                    "Se usó Vina como fallback. Espera unos segundos o revisa si la PC está encendida."
                ],
            )

        # Health check (usa caché si está fresca)
        health = await self.check_health()
        if not health.get("status") == "healthy":
            return self._unavailable_result(health)

        # Llamada con retry
        last_error: str | None = None
        last_reason: str | None = None
        for attempt in range(1, self.PREDICT_MAX_RETRIES + 2):
            try:
                start = time.monotonic()
                if _USE_HTTPX:
                    result = await self._call_api_httpx(
                        protein_pdb_path, peptide_smiles, num_poses, grid_center, grid_size
                    )
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None,
                        self._call_api_urllib,
                        protein_pdb_path, peptide_smiles, num_poses, grid_center, grid_size,
                    )
                elapsed = time.monotonic() - start

                if result is None:
                    last_error = "API no retornó respuesta"
                    last_reason = ServiceUnavailableReason.INVALID_RESPONSE
                    self._circuit.record_failure()
                    if attempt <= self.PREDICT_MAX_RETRIES:
                        await asyncio.sleep(1.0)
                        continue
                    break

                self._circuit.record_success()
                return self._parse_response(result, elapsed)

            except Exception as e:
                last_error = str(e)
                last_reason = self._classify_exception(e)
                self._circuit.record_failure()
                log.warning(
                    f"ESMFold intento {attempt} falló ({last_reason}): {e}"
                )
                if attempt <= self.PREDICT_MAX_RETRIES:
                    await asyncio.sleep(2.0)
                    continue
                break

        return ESMFoldResult(
            success=False,
            error=last_error or "Fallo desconocido",
            warnings=[
                f"ESMFold no respondió tras {self.PREDICT_MAX_RETRIES + 1} intentos "
                f"(causa: {last_reason}). Se usó Vina como fallback."
            ],
        )

    def _classify_exception(self, e: Exception) -> str:
        if _USE_HTTPX:
            if isinstance(e, httpx.ConnectError):
                return ServiceUnavailableReason.CONNECTION_REFUSED
            if isinstance(e, httpx.TimeoutException):
                return ServiceUnavailableReason.TIMEOUT
            if isinstance(e, httpx.HTTPStatusError):
                return ServiceUnavailableReason.HTTP_ERROR
        err_str = str(e).lower()
        if "connection refused" in err_str:
            return ServiceUnavailableReason.CONNECTION_REFUSED
        if "timed out" in err_str or "timeout" in err_str:
            return ServiceUnavailableReason.TIMEOUT
        return ServiceUnavailableReason.UNKNOWN

    def _unavailable_result(self, health: dict[str, Any]) -> ESMFoldResult:
        reason = health.get("reason", "unknown")
        err = health.get("error", "Servicio no disponible")
        if reason == ServiceUnavailableReason.CONNECTION_REFUSED:
            user_msg = (
                f"ESMFold en {self._api_url} no responde: conexión rechazada. "
                "¿La PC local está encendida? ¿El servicio está corriendo? "
                "Se usó AutoDock Vina como fallback."
            )
        elif reason == ServiceUnavailableReason.TIMEOUT:
            user_msg = (
                f"ESMFold en {self._api_url} no responde a tiempo. "
                "El servicio puede estar cargando el modelo. "
                "Se usó AutoDock Vina como fallback."
            )
        elif reason == ServiceUnavailableReason.CIRCUIT_OPEN:
            user_msg = (
                f"ESMFold en {self._api_url} falló demasiadas veces seguidas. "
                "Circuit breaker activo. Se usó Vina como fallback."
            )
        else:
            user_msg = (
                f"ESMFold no disponible ({reason}): {err}. "
                "Se usó Vina como fallback."
            )
        return ESMFoldResult(
            success=False,
            error=str(err),
            warnings=[user_msg],
        )

    # ── HTTP calls (httpx async + urllib sync fallback) ─────────────────

    async def _call_api_httpx(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None,
        grid_size: tuple[float, float, float] | None,
    ) -> dict | None:
        if not self._api_url:
            return None
        protein_content = Path(protein_pdb_path).read_text()
        payload: dict[str, Any] = {
            "protein_pdb": protein_content,
            "peptide_smiles": peptide_smiles,
            "num_poses": num_poses,
        }
        if grid_center is not None:
            payload["grid_center"] = list(grid_center)
        if grid_size is not None:
            payload["grid_size"] = list(grid_size)

        async with httpx.AsyncClient(timeout=self.PREDICT_TIMEOUT_S) as client:
            r = await client.post(f"{self._api_url}/predict", json=payload)
            if r.status_code != 200:
                log.warning(
                    f"ESMFold HTTP {r.status_code}: {r.text[:300]}"
                )
                return None
            return r.json()

    def _call_api_urllib(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
        num_poses: int,
        grid_center: tuple[float, float, float] | None = None,
        grid_size: tuple[float, float, float] | None = None,
    ) -> dict | None:
        if not self._api_url:
            return None
        protein_content = Path(protein_pdb_path).read_text()
        payload_dict: dict[str, Any] = {
            "protein_pdb": protein_content,
            "peptide_smiles": peptide_smiles,
            "num_poses": num_poses,
        }
        if grid_center is not None:
            payload_dict["grid_center"] = list(grid_center)
        if grid_size is not None:
            payload_dict["grid_size"] = list(grid_size)
        payload = json.dumps(payload_dict).encode("utf-8")

        req = Request(
            f"{self._api_url}/predict",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.PREDICT_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning(f"Fallo en comunicación con ESMFold API: {e}")
            return None

    # ── Parseo de respuesta ─────────────────────────────────────────────

    def _parse_response(self, result: dict, elapsed: float) -> ESMFoldResult:
        if not result.get("success"):
            return ESMFoldResult(
                success=False,
                error=result.get("error"),
                warnings=result.get("warnings", []),
            )
        poses = []
        for i, p in enumerate(result.get("poses", [])):
            poses.append(
                ESMFoldPose(
                    rank=p.get("rank", i + 1),
                    confidence=p.get("confidence", 0.0),
                    ligand_pdb=p.get("peptide_pdb", ""),
                    ligand_sdf=p.get("ligand_sdf"),
                    rmsd=p.get("rmsd"),
                    # La afinidad real de Vina, si la hubo. Un sidecar antiguo
                    # no manda estas claves: entonces queda None y `origen`
                    # dice que no se sabe, en vez de fabricar un número.
                    vina_affinity_kcal_mol=p.get("vina_affinity_kcal_mol"),
                    origen=p.get("origen", "desconocido"),
                )
            )
        # La confianza de plegado vive en el resultado de la predicción, no en
        # las poses de Vina. Estas poses pueden llevar confidence=0 porque no
        # miden confianza estructural; recomputarla desde ellas borraría el
        # pLDDT real (y lo presentaría como 0.00 en el dossier).
        _reported_best_confidence = result.get("best_confidence")
        try:
            best_conf = (
                float(_reported_best_confidence)
                if _reported_best_confidence is not None
                else max((p.confidence for p in poses), default=None)
            )
        except (TypeError, ValueError):
            best_conf = max((p.confidence for p in poses), default=None)
        return ESMFoldResult(
            success=True,
            poses=poses,
            best_confidence=best_conf,
            execution_time_s=round(elapsed, 2),
            warnings=result.get("warnings", []),
            scientific_status=result.get("scientific_status", "EXPERIMENTAL"),
            transfer_manifest=result.get("transfer_manifest"),
        )


# ── Singleton ─────────────────────────────────────────────────────────────


_esmfold_service: ESMFoldService | None = None


def get_esmfold_service() -> ESMFoldService:
    global _esmfold_service
    if _esmfold_service is None:
        _esmfold_service = ESMFoldService()
    return _esmfold_service
