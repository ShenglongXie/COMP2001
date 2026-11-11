from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, TextIO

from _2001.core.config import Settings

REDACTED = "***"

SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "authorization",
    "cookie",
    "session",
    "credential",
)

_RESERVED: frozenset[str] = frozenset(
    vars(
        logging.LogRecord(
            name="_",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=None,
            exc_info=None,
        )
    )
)

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_context_var: ContextVar[Mapping[str, Any]] = ContextVar(
    "log_context", default=MappingProxyType({})
)

_configured: Settings | None = None


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(value: str) -> Token[str | None]:
    return request_id_var.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_var.reset(token)


@contextmanager
def bind(**fields: Any) -> Iterator[None]:
    current = dict(_context_var.get())
    current.update(fields)
    token = _context_var.set(MappingProxyType(current))
    try:
        yield
    finally:
        _context_var.reset(token)


def _iso_utc(created: float) -> str:
    stamp = datetime.fromtimestamp(created, tz=UTC)
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def redact(key: str, value: Any) -> Any:
    if _is_sensitive(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(key, item) for item in value]
    return value


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in _context_var.get().items():
        payload[key] = redact(key, value)
    for key, value in record.__dict__.items():
        if (
            key in _RESERVED
            or key.startswith("_")
            or key.startswith("color_")
            or key == "request_id"
        ):
            continue
        payload[key] = redact(key, value)
    return payload


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id is not None:
            record.request_id = request_id
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _iso_utc(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "environment": self._environment,
        }

        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            payload["request_id"] = request_id

        payload.update(_extras(record))

        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            payload["exception"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": str(exc_value),
                "stacktrace": self.formatException(record.exc_info),
            }
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    _LEVEL_WIDTH = 7

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            _iso_utc(record.created),
            f"{record.levelname:<{self._LEVEL_WIDTH}}",
            f"{record.name:<26}",
            record.getMessage(),
        ]
        for key, value in _extras(record).items():
            rendered = f"{value!r}" if isinstance(value, str) else str(value)
            parts.append(f"{key}={rendered}")
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            parts.append(f"request_id={request_id}")

        line = " ".join(parts)
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(
    settings: Settings | None = None,
    *,
    stream: TextIO | None = None,
    force: bool = False,
) -> Settings:
    global _configured

    settings = settings or Settings.from_env()
    if _configured == settings and not force:
        return settings

    handler = logging.StreamHandler(stream or sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(
            JsonFormatter(
                service=settings.service_name, environment=settings.environment
            )
        )
    else:
        handler.setFormatter(ConsoleFormatter())
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        existing.close()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Uvicorn would otherwise keep its own handlers and duplicate every line.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    logging.captureWarnings(True)
    _configured = settings
    return settings


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
