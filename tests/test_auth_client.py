from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from _2001.core.auth import (
    AuthUnavailable,
    AuthenticatorClient,
    is_verified,
)

URL = "https://authenticator.test/api/users"


def run(coro):
    return asyncio.run(coro)


def make_client(handler, *, cache_ttl: float = 30.0) -> AuthenticatorClient:
    return AuthenticatorClient(
        URL, transport=httpx.MockTransport(handler), cache_ttl=cache_ttl
    )


def test_verified_payload_variants() -> None:
    assert is_verified(["Verified", "True"]) is True
    assert is_verified(["Verified", True]) is True
    assert is_verified(["Verified", "False"]) is False
    assert is_verified(["Not Verified", "False"]) is False
    assert is_verified({"verified": "True"}) is True
    assert is_verified({"authenticated": False}) is False
    assert is_verified(["garbage"]) is None
    assert is_verified({"unexpected": "shape"}) is None


def test_authenticate_posts_credentials_and_accepts_verified() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=["Verified", "True"])

    client = make_client(handler)
    user = run(client.authenticate("grace@plymouth.ac.uk", "ISAD123!"))
    run(client.aclose())

    assert user is not None
    assert user.email == "grace@plymouth.ac.uk"
    assert seen == [{"email": "grace@plymouth.ac.uk", "password": "ISAD123!"}]


def test_authenticate_rejects_when_not_verified() -> None:
    client = make_client(lambda request: httpx.Response(200, json=["Verified", "False"]))

    assert run(client.authenticate("a@b.c", "x")) is None


def test_authenticate_maps_401_to_rejection() -> None:
    client = make_client(lambda request: httpx.Response(401))

    assert run(client.authenticate("a@b.c", "x")) is None


@pytest.mark.parametrize("status", [429, 500, 503])
def test_authenticate_reports_upstream_failure(status: int) -> None:
    client = make_client(lambda request: httpx.Response(status))

    with pytest.raises(AuthUnavailable):
        run(client.authenticate("a@b.c", "x"))


def test_authenticate_reports_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = make_client(handler)

    with pytest.raises(AuthUnavailable):
        run(client.authenticate("a@b.c", "x"))


def test_authenticate_rejects_unparseable_body() -> None:
    client = make_client(lambda request: httpx.Response(200, text="<html>nope</html>"))

    assert run(client.authenticate("a@b.c", "x")) is None


def test_successful_authentication_is_cached() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=["Verified", "True"])

    client = make_client(handler)
    first = run(client.authenticate("a@b.c", "x"))
    second = run(client.authenticate("a@b.c", "x"))

    assert first == second
    assert calls["count"] == 1


def test_cache_is_keyed_by_credentials() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=["Verified", "True"])

    client = make_client(handler)
    run(client.authenticate("a@b.c", "one"))
    run(client.authenticate("a@b.c", "two"))

    assert calls["count"] == 2
