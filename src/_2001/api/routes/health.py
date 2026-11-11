from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@router.get("/readyz", summary="Readiness probe")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
