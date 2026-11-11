from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from _2001 import __version__
from _2001.api.middleware import RequestContextMiddleware
from _2001.api.routes import health
from _2001.core.config import Settings
from _2001.core.logging import configure_logging, get_logger

logger = get_logger("_2001.api.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "service.starting",
        extra={
            "service.name": settings.service_name,
            "deployment.environment": settings.environment,
            "service.version": __version__,
        },
    )
    try:
        yield
    finally:
        logger.info("service.stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = configure_logging(settings)

    app = FastAPI(
        title="Trail App · ProfileService",
        version=__version__,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        RequestContextMiddleware, header_name=settings.request_id_header
    )
    app.include_router(health.router)

    logger.info(
        "service.configured",
        extra={
            "service.name": settings.service_name,
            "log.format": settings.log_format,
            "log.level": settings.log_level,
        },
    )
    return app
