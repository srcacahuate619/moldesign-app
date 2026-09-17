"""Límite HTTP antes del parser multipart, incluso sin Content-Length."""
from __future__ import annotations

import asyncio
from tempfile import SpooledTemporaryFile

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=32 * 1024 * 1024, timeout=30.0):
        self.app, self.max_bytes, self.timeout = app, max_bytes, timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        async def reject(code, detail):
            await JSONResponse({"detail": detail}, status_code=code)(scope, receive, send)
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    length = int(value)
                    if length < 0:
                        raise ValueError()
                except ValueError:
                    return await reject(400, "Content-Length inválido")
                if length > self.max_bytes:
                    return await reject(413, "La solicitud supera el límite de tamaño")
        # Hasta 1 MiB en memoria; el resto en temporal, siempre eliminado.
        with SpooledTemporaryFile(max_size=1024 * 1024) as body:
            total = 0
            deadline = asyncio.get_running_loop().time() + self.timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return await reject(408, "Tiempo agotado al recibir la solicitud")
                try:
                    message = await asyncio.wait_for(receive(), remaining)
                except asyncio.TimeoutError:
                    return await reject(408, "Tiempo agotado al recibir la solicitud")
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                data = message.get("body", b"")
                total += len(data)
                if total > self.max_bytes:
                    return await reject(413, "La solicitud supera el límite de tamaño")
                body.write(data)
                if not message.get("more_body", False):
                    break
            body.seek(0)
            delivered = False
            async def replay():
                nonlocal delivered
                if delivered:
                    return await receive()
                data = body.read(65536)
                more = body.tell() < total
                if not more:
                    delivered = True
                return {"type": "http.request", "body": data, "more_body": more}
            await self.app(scope, replay, send)
