from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from _2001.api.auth import AuthenticationMiddleware
from _2001.core.auth import AuthenticatedUser, AuthUnavailable


class FakeAuthenticator:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def authenticate(self, email: str, password: str):
        self.calls.append((email, password))
        if self.error is not None:
            raise self.error
        return self.result


def basic(email: str, password: str) -> str:
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {token}"


def build_client(authenticator: FakeAuthenticator) -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(request: Request) -> dict[str, str]:
        return {"email": request.state.user.email}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(AuthenticationMiddleware(app, authenticator))


def test_missing_credentials_are_rejected() -> None:
    authenticator = FakeAuthenticator(result=AuthenticatedUser(email="a@b.c"))
    response = build_client(authenticator).get("/whoami")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="profile-service"'
    assert response.json()["error"]["code"] == "unauthorized"
    assert authenticator.calls == []


def test_malformed_scheme_is_rejected() -> None:
    authenticator = FakeAuthenticator()
    client = build_client(authenticator)

    assert client.get("/whoami", headers={"Authorization": "Bearer abc"}).status_code == 401
    assert client.get("/whoami", headers={"Authorization": "Basic ###"}).status_code == 401
    assert client.get("/whoami", headers={"Authorization": "Basic "}).status_code == 401
    assert authenticator.calls == []


def test_valid_credentials_reach_the_route() -> None:
    authenticator = FakeAuthenticator(
        result=AuthenticatedUser(email="grace@plymouth.ac.uk")
    )
    response = build_client(authenticator).get(
        "/whoami", headers={"Authorization": basic("grace@plymouth.ac.uk", "ISAD123!")}
    )

    assert response.status_code == 200
    assert response.json() == {"email": "grace@plymouth.ac.uk"}
    assert authenticator.calls == [("grace@plymouth.ac.uk", "ISAD123!")]


def test_password_may_contain_a_colon() -> None:
    authenticator = FakeAuthenticator(result=AuthenticatedUser(email="a@b.c"))
    build_client(authenticator).get(
        "/whoami", headers={"Authorization": basic("a@b.c", "pa:ss:word")}
    )

    assert authenticator.calls == [("a@b.c", "pa:ss:word")]


def test_rejected_credentials_return_401() -> None:
    authenticator = FakeAuthenticator(result=None)
    response = build_client(authenticator).get(
        "/whoami", headers={"Authorization": basic("a@b.c", "wrong")}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_unavailable_authenticator_returns_503() -> None:
    authenticator = FakeAuthenticator(error=AuthUnavailable("down"))
    response = build_client(authenticator).get(
        "/whoami", headers={"Authorization": basic("a@b.c", "x")}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authenticator_unavailable"


def test_public_paths_skip_authentication() -> None:
    authenticator = FakeAuthenticator()
    response = build_client(authenticator).get("/healthz")

    assert response.status_code == 200
    assert authenticator.calls == []


def test_options_requests_skip_authentication() -> None:
    authenticator = FakeAuthenticator()
    response = build_client(authenticator).options("/whoami")

    assert response.status_code != 401
    assert authenticator.calls == []
