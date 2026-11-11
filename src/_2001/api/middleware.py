from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from _2001.api.header_names import REQUEST_ID as DEFAULT_HEADER
from _2001.core.logging import get_logger, reset_request_id, set_request_id

logger = get_logger("_2001.api.middleware")

# Clients must not be able to inject newlines or unbounded junk into log lines.
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_HEALTH_PATHS = frozenset({"/healthz", "/livez", "/readyz"})


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, *, header_name: str = DEFAULT_HEADER) -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(self.header_name, "")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid4().hex

        token = set_request_id(request_id)
        started = time.perf_counter()
        status_code: int | None = None
        response_started = False
        header_key = self.header_name.lower().encode("latin-1")

        client = scope.get("client")
        context: dict[str, Any] = {
            "http.method": scope.get("method", ""),
            "http.path": scope.get("path", ""),
            "http.client_ip": client[0] if client else None,
        }

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)[self.header_name] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "http.request.failed",
                extra={**context, "http.duration_ms": duration_ms},
            )
            if not response_started:
                body = json.dumps(
                    {
                        "error": {
                            "code": "internal_error",
                            "message": "Unexpected server error.",
                            "request_id": request_id,
                        }
                    }
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("ascii")),
                            (header_key, request_id.encode("ascii", "ignore")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            payload: dict[str, Any] = {
                **context,
                "http.status_code": status_code,
                "http.duration_ms": duration_ms,
            }
            if scope.get("path") in _HEALTH_PATHS:
                logger.debug("http.request.completed", extra=payload)
            else:
                logger.info("http.request.completed", extra=payload)
        finally:
            reset_request_id(token)
