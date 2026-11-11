from __future__ import annotations

import io
import json
import logging

import pytest

from _2001.core.config import Settings
from _2001.core.logging import (
    REDACTED,
    bind,
    configure_logging,
    get_logger,
    reset_request_id,
    set_request_id,
)

SERVICE = "profile-service"


def _configure(
    stream: io.StringIO, *, log_format: str = "json", level: str = "DEBUG"
) -> Settings:
    settings = Settings(
        service_name=SERVICE,
        environment="test",
        log_level=level,
        log_format=log_format,
    )
    configure_logging(settings, stream=stream, force=True)
    return settings


def _records(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def _last_json(stream: io.StringIO) -> dict:
    records = _records(stream)
    assert records, "nothing was logged"
    return records[-1]


def test_json_line_has_service_envelope() -> None:
    stream = io.StringIO()
    _configure(stream)

    get_logger("_2001.test").info("hello")

    payload = _last_json(stream)
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "_2001.test"
    assert payload["service"] == SERVICE
    assert payload["environment"] == "test"
    assert payload["timestamp"].endswith("Z")


def test_request_id_is_injected_from_context() -> None:
    stream = io.StringIO()
    _configure(stream)

    token = set_request_id("abc123")
    try:
        get_logger("_2001.test").info("inside request")
    finally:
        reset_request_id(token)

    assert _last_json(stream)["request_id"] == "abc123"


def test_bind_adds_structured_fields() -> None:
    stream = io.StringIO()
    _configure(stream)

    with bind(member_id=42, route="/profiles/42"):
        get_logger("_2001.test").info("lookup")

    payload = _last_json(stream)
    assert payload["member_id"] == 42
    assert payload["route"] == "/profiles/42"


def test_bind_does_not_leak_between_calls() -> None:
    stream = io.StringIO()
    _configure(stream)
    logger = get_logger("_2001.test")

    with bind(member_id=1):
        logger.info("first")
    logger.info("second")

    first, second = _records(stream)
    assert "member_id" in first
    assert "member_id" not in second


def test_sensitive_values_are_redacted() -> None:
    stream = io.StringIO()
    _configure(stream)

    get_logger("_2001.test").info(
        "signup",
        extra={
            "password": "s3cret",
            "Authorization": "Bearer token",
            "payload": {"email": "a@b.c", "refresh_token": "xyz"},
            "accounts": [{"token": "abc", "member_id": 1}],
        },
    )

    payload = _last_json(stream)
    assert payload["password"] == REDACTED
    assert payload["Authorization"] == REDACTED
    assert payload["payload"]["refresh_token"] == REDACTED
    assert payload["payload"]["email"] == "a@b.c"
    assert payload["accounts"] == [{"token": REDACTED, "member_id": 1}]


def test_exception_is_structured() -> None:
    stream = io.StringIO()
    _configure(stream)

    try:
        raise ValueError("boom")
    except ValueError:
        get_logger("_2001.test").exception("failed")

    payload = _last_json(stream)
    assert payload["level"] == "ERROR"
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["message"] == "boom"
    assert "ValueError: boom" in payload["exception"]["stacktrace"]


def test_console_format_is_readable() -> None:
    stream = io.StringIO()
    _configure(stream, log_format="console", level="INFO")

    token = set_request_id("rid-1")
    try:
        get_logger("_2001.test").info("request completed", extra={"status": 200})
    finally:
        reset_request_id(token)

    line = stream.getvalue().strip()
    assert "INFO" in line
    assert "request completed" in line
    assert "status=200" in line
    assert "request_id=rid-1" in line
    assert not line.startswith("{")


def test_configure_is_idempotent() -> None:
    stream = io.StringIO()
    settings = _configure(stream)
    root = logging.getLogger()

    before = len(root.handlers)
    configure_logging(settings, stream=stream)
    after = len(root.handlers)

    assert before == after == 1


def test_unknown_log_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="LOG_FORMAT"):
        Settings.from_env({"LOG_FORMAT": "xml"})


def test_unknown_log_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="LOG_LEVEL"):
        Settings.from_env({"LOG_LEVEL": "LOUD"})
