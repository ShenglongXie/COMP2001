from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from _2001.core.auth import AuthUnavailable, AuthenticatorClient
from _2001.core.logging import get_logger, get_request_id

logger = get_logger("_2001.api.auth")

PUBLIC_PATHS = frozenset(
    {
        "/healthz",
        "/livez",
        "/readyz",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)
REALM = "profile-service"


def basic_credentials(scope: Scope) -> tuple[str, str] | None:
    header = Headers(scope=scope).get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic" or not token.strip():
        return None
    try:
        decoded = base64.b64decode(token.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    email, separator, password = decoded.partition(":")
    if not separator or not email or not password:
        return None
    return email, password


async def deny(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps(
        {
            "error": {
                "code": code,
                "message": message,
                "request_id": get_request_id(),
            }
        }
    ).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if status == 401:
        headers.append(
            (b"www-authenticate", f'Basic realm="{REALM}"'.encode("ascii"))
        )
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class AuthenticationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        authenticator: AuthenticatorClient,
        *,
        public_paths: frozenset[str] = PUBLIC_PATHS,
    ) -> None:
        self.app = app
        self.authenticator = authenticator
        self.public_paths = public_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "").upper()
        if method == "OPTIONS" or path in self.public_paths:
            await self.app(scope, receive, send)
            return

        credentials = basic_credentials(scope)
        if credentials is None:
            await deny(
                send,
                401,
                "unauthorized",
                "Basic authentication with email and password is required.",
            )
            return

        email, password = credentials
        try:
            user = await self.authenticator.authenticate(email, password)
        except AuthUnavailable:
            logger.warning("auth.unavailable", extra={"auth.subject": email})
            await deny(
                send,
                503,
                "authenticator_unavailable",
                "The authentication service is unavailable.",
            )
            return

        if user is None:
            logger.info("auth.rejected", extra={"auth.subject": email})
            await deny(send, 401, "invalid_credentials", "Invalid email or password.")
            return

        scope.setdefault("state", {})["user"] = user
        logger.debug("auth.accepted", extra={"auth.subject": email})
        await self.app(scope, receive, send)
