from __future__ import annotations

import io

from fastapi.testclient import TestClient

from _2001.api.app import API_PREFIX, create_app
from _2001.core.config import Settings
from _2001.core.logging import configure_logging


def _client() -> TestClient:
    configure_logging(
        Settings(environment="test", log_level="WARNING", log_format="json"),
        stream=io.StringIO(),
        force=True,
    )
    return TestClient(
        create_app(Settings(environment="test", log_level="WARNING", auth_enabled=False))
    )


def test_expected_paths_are_documented() -> None:
    spec = _client().get("/openapi.json").json()
    paths = spec["paths"]

    expected = {
        f"{API_PREFIX}/members",
        f"{API_PREFIX}/members/{{member_id}}",
        f"{API_PREFIX}/members/{{member_id}}/preferences",
        f"{API_PREFIX}/members/{{member_id}}/preferences/{{activity_type_id}}",
        f"{API_PREFIX}/members/{{member_id}}/following",
        f"{API_PREFIX}/members/{{member_id}}/following/{{followee_id}}",
        f"{API_PREFIX}/members/{{member_id}}/followers",
        f"{API_PREFIX}/reference/countries",
        f"{API_PREFIX}/reference/regions",
        f"{API_PREFIX}/reference/localities",
        f"{API_PREFIX}/reference/activity-types",
        f"{API_PREFIX}/reference/activity-categories",
        f"{API_PREFIX}/reference/skill-levels",
        "/healthz",
        "/readyz",
    }
    assert expected <= set(paths)


def test_operations_are_restful() -> None:
    ops = _client().get("/openapi.json").json()["paths"]

    members = ops[f"{API_PREFIX}/members"]
    assert {"get", "post"} <= set(members)
    assert members["post"]["responses"].keys() >= {"201", "409", "422"}

    member = ops[f"{API_PREFIX}/members/{{member_id}}"]
    assert {"get", "patch", "delete"} <= set(member)
    assert "204" in member["delete"]["responses"]

    preferences = ops[f"{API_PREFIX}/members/{{member_id}}/preferences"]
    assert {"get", "post", "put"} <= set(preferences)


def test_error_schema_is_documented() -> None:
    spec = _client().get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    assert "ErrorResponse" in schemas
    assert "ErrorDetail" in schemas
    assert {"code", "message"} <= set(schemas["ErrorDetail"]["properties"])


def test_swagger_and_redoc_are_served() -> None:
    client = _client()

    swagger = client.get("/docs")
    assert swagger.status_code == 200
    assert "swagger-ui" in swagger.text

    assert client.get("/redoc").status_code == 200


def test_api_without_database_reports_503() -> None:
    response = _client().get(f"{API_PREFIX}/members")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
