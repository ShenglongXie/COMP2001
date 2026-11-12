from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from _2001 import __version__
from _2001.api.auth import AuthenticationMiddleware
from _2001.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    validation_error_handler,
)
from _2001.api.middleware import RequestContextMiddleware
from _2001.api.routes import follows, health, members, preferences, reference
from _2001.core.auth import AuthenticatorClient
from _2001.core.config import Settings
from _2001.core.logging import configure_logging, get_logger
from _2001.db.session import build_engine, build_session_factory

logger = get_logger("_2001.api.app")

API_PREFIX = "/api/v1"

TAGS_METADATA = [
    {"name": "Health", "description": "Liveness and readiness probes."},
    {
        "name": "Members",
        "description": "Member profiles: registration, lookup, update and removal.",
    },
    {
        "name": "Preferences",
        "description": "Preferred activities of a member (link entity MemberPreference).",
    },
    {
        "name": "Social",
        "description": "Follows between members (link entity MemberFollow).",
    },
    {"name": "Reference data", "description": "Read-only lookup tables."},
]

DESCRIPTION = """
Profile microservice for the Trail App (Country Trust). It owns member records:
identity, home locality, preferences and the follow graph.

**Conventions**

* All endpoints below live under `/api/v1`.
* Collections are paginated with `limit` (1-100) and `offset`, and answer with
  `{ items, total, limit, offset }`.
* Timestamps are UTC ISO 8601.
* Errors use one envelope:
  `{ "error": { "code", "message", "request_id" } }`, where `request_id`
  echoes the `X-Request-ID` response header.
* Writes are validated against the same rules the database enforces
  (domain checks, unique keys and foreign keys), so a `422` never reaches SQL.

**Authentication**

Every `/api/v1` route requires HTTP Basic credentials
(`email:password`), which the service verifies against the university
authenticator before the request reaches a route. `/healthz`, `/readyz`,
`/docs`, `/redoc` and `/openapi.json` stay public. Use the **Authorize**
button with your Plymouth email and password.

* missing or malformed credentials → `401 unauthorized`
* rejected credentials → `401 invalid_credentials`
* authenticator down or timing out → `503 authenticator_unavailable`

Successful logins are cached in memory for a short window, so repeated calls
do not re-contact the authenticator on every request.
"""


def _document_basic_auth(app: FastAPI) -> None:
    build_spec = app.openapi

    def openapi() -> dict:
        spec = build_spec()
        schemes = spec.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes["basicAuth"] = {
            "type": "http",
            "scheme": "basic",
            "description": "Email and password of the university authenticator account.",
        }
        for path, operations in spec["paths"].items():
            if not path.startswith(API_PREFIX):
                continue
            for operation in operations.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"basicAuth": []}])
        return spec

    app.openapi = openapi


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "service.starting",
        extra={
            "service.name": settings.service_name,
            "deployment.environment": settings.environment,
            "service.version": __version__,
            "database.configured": bool(settings.database_url),
        },
    )
    try:
        yield
    finally:
        authenticator = app.state.authenticator
        if authenticator is not None:
            await authenticator.aclose()
        engine = app.state.engine
        if engine is not None:
            await _dispose(engine)
        logger.info("service.stopped")


async def _dispose(engine) -> None:
    await asyncio.to_thread(engine.dispose)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = configure_logging(settings)

    app = FastAPI(
        title="Trail App · ProfileService",
        version=__version__,
        summary="Member profiles, preferences and follows.",
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.database_url:
        engine = build_engine(settings.database_url)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
    else:
        app.state.engine = None
        app.state.session_factory = None

    if settings.auth_enabled:
        authenticator = AuthenticatorClient(
            settings.auth_url,
            timeout=settings.auth_timeout_seconds,
            cache_ttl=settings.auth_cache_ttl_seconds,
        )
        app.state.authenticator = authenticator
        app.add_middleware(AuthenticationMiddleware, authenticator=authenticator)
    else:
        app.state.authenticator = None

    app.add_middleware(
        RequestContextMiddleware, header_name=settings.request_id_header
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(health.router)
    app.include_router(members.router, prefix=API_PREFIX)
    app.include_router(preferences.router, prefix=API_PREFIX)
    app.include_router(follows.router, prefix=API_PREFIX)
    app.include_router(reference.router, prefix=API_PREFIX)

    _document_basic_auth(app)
    logger.info(
        "service.configured",
        extra={
            "service.name": settings.service_name,
            "log.format": settings.log_format,
            "log.level": settings.log_level,
        },
    )
    return app
