"""
api/rate_limiter.py

Rate limiter por IP para protección anti brute-force.

Implementación:
- Token bucket en memoria (dict por IP) con limpieza periódica.
- Diseñado para proteger /auth/login y /auth/register.
- Para procesos locales independientes, el límite se reinicia con el backend.

Limitaciones conocidas:
- Estado en memoria: no compartido entre workers/procesos.
- IPs detrás de proxy: depende de que el proxy setee X-Forwarded-For
  y que FastAPI use la middleware de trusted hosts.
- No sobrevive reinicios del servidor.

Para el MVP, esta protección es suficiente para prevenir brute-force
básico contra un solo proceso.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request, status

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class _BucketEntry:
    """Estado del bucket para una IP."""
    tokens: float
    last_refill: float
    blocked_until: float = 0.0


class RateLimiter:
    """
    Rate limiter basado en token bucket por IP.

    Parámetros:
        max_requests: número máximo de requests permitidas en la ventana.
        window_seconds: duración de la ventana de refill (segundos).
        block_seconds: duración del bloqueo tras exceder el límite.
        cleanup_interval: intervalo de limpieza de entradas expiradas.

    Uso:
        limiter = RateLimiter(max_requests=5, window_seconds=60, block_seconds=300)

        @router.post("/login")
        async def login(request: Request, ...):
            limiter.check(request)
            ...
    """

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 60,
        block_seconds: int = 300,
        cleanup_interval: int = 600,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.cleanup_interval = cleanup_interval

        self._buckets: dict[str, _BucketEntry] = {}
        self._lock = Lock()
        self._last_cleanup = time.monotonic()

    def _get_client_ip(self, request: Request) -> str:
        """Extrae IP del cliente de forma segura."""
        from slowapi.util import get_remote_address
        try:
            return get_remote_address(request)
        except Exception:
            return request.client.host if request.client else "unknown"

    def _maybe_cleanup(self, now: float) -> None:
        """Limpia entradas expiradas para evitar memory leak."""
        if now - self._last_cleanup < self.cleanup_interval:
            return

        expired_keys = [
            ip for ip, entry in self._buckets.items()
            if entry.blocked_until < now and (now - entry.last_refill) > self.window_seconds * 2
        ]
        for key in expired_keys:
            del self._buckets[key]

        self._last_cleanup = now
        if expired_keys:
            log.debug("rate_limiter cleanup", removed=len(expired_keys))

    def check(self, request: Request) -> None:
        """
        Verifica si la IP del request tiene tokens disponibles.

        Lanza HTTPException 429 si el límite se excedió.
        """
        ip = self._get_client_ip(request)
        now = time.monotonic()

        with self._lock:
            self._maybe_cleanup(now)

            if ip not in self._buckets:
                self._buckets[ip] = _BucketEntry(
                    tokens=self.max_requests,
                    last_refill=now,
                )

            entry = self._buckets[ip]

            # Check si está bloqueada
            if entry.blocked_until > now:
                remaining = int(entry.blocked_until - now)
                log.warning(
                    "rate_limit_blocked",
                    ip=ip,
                    remaining_seconds=remaining,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Demasiados intentos. Intente de nuevo en {remaining} segundos.",
                    headers={"Retry-After": str(remaining)},
                )

            # Refill tokens proporcional al tiempo transcurrido
            elapsed = now - entry.last_refill
            refill = elapsed * (self.max_requests / self.window_seconds)
            entry.tokens = min(self.max_requests, entry.tokens + refill)
            entry.last_refill = now

            # Consume token
            if entry.tokens >= 1:
                entry.tokens -= 1
                return

            # Sin tokens — bloquear
            entry.blocked_until = now + self.block_seconds
            log.warning(
                "rate_limit_exceeded",
                ip=ip,
                block_seconds=self.block_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos. Intente de nuevo en {self.block_seconds} segundos.",
                headers={"Retry-After": str(self.block_seconds)},
            )

    def reset(self, ip: str | None = None) -> None:
        """
        Reset manual del rate limiter.
        Si ip es None, resetea todas las IPs (útil en tests).
        """
        with self._lock:
            if ip is None:
                self._buckets.clear()
            elif ip in self._buckets:
                del self._buckets[ip]


# ── Instancias globales para los endpoints de auth ────────────────────────────

# Login: 5 intentos por minuto, bloqueo 5 minutos
# Protege contra brute-force de contraseñas.
login_limiter = RateLimiter(
    max_requests=5,
    window_seconds=60,
    block_seconds=300,
)

# Register: 3 intentos por minuto, bloqueo 10 minutos
# Protege contra spam de cuentas.
register_limiter = RateLimiter(
    max_requests=3,
    window_seconds=60,
    block_seconds=600,
)
