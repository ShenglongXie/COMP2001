from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from _2001.api.app import create_app
from _2001.core.config import Settings
from _2001.core.logging import configure_logging

REQUEST_ID_HEADER = "X-Request-ID"


@pytest.fixture()
def stream() -> io.StringIO:
    return io.StringIO()


@pytest.fixture()
def settings(stream: io.StringIO) -> Settings:
    settings = Settings(
        service_name="profile-service",
        environment="test",
        log_level="DEBUG",
        log_format="json",
        auth_enabled=False,
    )
    configure_logging(settings, stream=stream, force=True)
    return settings


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    app = create_app(settings)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _records(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_healthz_returns_service_identity(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "profile-service",
        "environment": "test",
    }


def test_readyz_is_ok(client: TestClient) -> None:
    assert client.get("/readyz").json() == {"status": "ready"}


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    response = client.get("/healthz")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert len(request_id) == 32
    assert request_id.isalnum()


def test_incoming_request_id_is_reused(client: TestClient, stream: io.StringIO) -> None:
    response = client.get("/healthz", headers={REQUEST_ID_HEADER: "caller-supplied-1"})

    assert response.headers[REQUEST_ID_HEADER] == "caller-supplied-1"
    assert any(
        record.get("request_id") == "caller-supplied-1" for record in _records(stream)
    )


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/healthz", headers={REQUEST_ID_HEADER: "bad id\n"})

    request_id = response.headers[REQUEST_ID_HEADER]
    assert request_id != "bad id\n"
    assert len(request_id) == 32


def test_access_log_records_status_and_duration(
    client: TestClient, stream: io.StringIO
) -> None:
    client.get("/healthz")

    completed = [
        record
        for record in _records(stream)
        if record["message"] == "http.request.completed"
    ]
    assert completed, "no access log line was written"
    record = completed[-1]
    assert record["http.method"] == "GET"
    assert record["http.path"] == "/healthz"
    assert record["http.status_code"] == 200
    assert isinstance(record["http.duration_ms"], float)
    assert record["request_id"]


def test_unhandled_error_returns_json_with_request_id(
    client: TestClient, stream: io.StringIO
) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]

    failed = [
        record
        for record in _records(stream)
        if record["message"] == "http.request.failed"
    ]
    assert failed, "the traceback was not logged"
    assert failed[-1]["exception"]["type"] == "RuntimeError"
    assert "kaboom" in failed[-1]["exception"]["message"]
