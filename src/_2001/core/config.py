from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
LOG_FORMATS = ("json", "console")


def _as_bool(raw: str, *, name: str) -> bool:
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _as_float(raw: str, *, name: str) -> float:
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _as_int(raw: str, *, name: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = "profile-service"
    environment: str = "local"
    log_level: str = "INFO"
    log_format: str = "json"
    log_include_caller: bool = False
    request_id_header: str = "X-Request-ID"
    database_url: str = ""
    auth_enabled: bool = True
    auth_url: str = (
        "https://web.socem.plymouth.ac.uk/COMP2001/auth/api/users"
    )
    auth_timeout_seconds: float = 5.0
    auth_cache_ttl_seconds: float = 30.0
    docs_enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ

        log_format = env.get("LOG_FORMAT", "json").strip().lower()
        if log_format not in LOG_FORMATS:
            raise ValueError(
                f"LOG_FORMAT must be one of {LOG_FORMATS}, got {log_format!r}"
            )

        log_level = env.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in logging.getLevelNamesMapping():
            raise ValueError(f"LOG_LEVEL is not a known level: {log_level!r}")

        port = _as_int(env.get("PORT", "8000"), name="PORT")
        if not 1 <= port <= 65535:
            raise ValueError(f"PORT must be within 1..65535, got {port}")

        return cls(
            service_name=env.get("SERVICE_NAME", "profile-service").strip(),
            environment=env.get("ENVIRONMENT", "local").strip(),
            log_level=log_level,
            log_format=log_format,
            log_include_caller=_as_bool(
                env.get("LOG_INCLUDE_CALLER", "false"), name="LOG_INCLUDE_CALLER"
            ),
            request_id_header=env.get("REQUEST_ID_HEADER", "X-Request-ID").strip(),
            database_url=env.get("DATABASE_URL", "").strip(),
            auth_enabled=_as_bool(
                env.get("AUTH_ENABLED", "true"), name="AUTH_ENABLED"
            ),
            auth_url=env.get(
                "AUTH_URL",
                "https://web.socem.plymouth.ac.uk/COMP2001/auth/api/users",
            ).strip(),
            auth_timeout_seconds=_as_float(
                env.get("AUTH_TIMEOUT_SECONDS", "5"), name="AUTH_TIMEOUT_SECONDS"
            ),
            auth_cache_ttl_seconds=_as_float(
                env.get("AUTH_CACHE_TTL_SECONDS", "30"),
                name="AUTH_CACHE_TTL_SECONDS",
            ),
            docs_enabled=_as_bool(env.get("DOCS_ENABLED", "true"), name="DOCS_ENABLED"),
            host=env.get("HOST", "127.0.0.1").strip(),
            port=port,
        )
