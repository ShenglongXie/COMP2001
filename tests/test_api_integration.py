from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from _2001.api.app import API_PREFIX, create_app
from _2001.core.auth import AuthenticatedUser
from _2001.core.config import Settings

DATABASE_URL = os.environ.get("PROFILE_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="PROFILE_TEST_DATABASE_URL is not set"
)

MEMBER = f"{API_PREFIX}/members"


@pytest.fixture(scope="module")
def client() -> TestClient:
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url=DATABASE_URL,
        auth_enabled=False,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture()
def authed_client(monkeypatch) -> TestClient:
    class StubAuthenticator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def authenticate(self, email: str, password: str):
            if password != "good-pass":
                return None
            return AuthenticatedUser(email=email)

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr("_2001.api.app.AuthenticatorClient", StubAuthenticator)
    settings = Settings(
        environment="test", log_level="WARNING", database_url=DATABASE_URL
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


ROWAN = ("rowan.ashby@example.org", "good-pass")


def test_own_profile_requires_authentication(authed_client: TestClient) -> None:
    response = authed_client.get(f"{MEMBER}/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic realm=")


def test_own_profile_resolves_by_authenticated_email(authed_client: TestClient) -> None:
    response = authed_client.get(f"{MEMBER}/me", auth=ROWAN)

    assert response.status_code == 200
    assert response.json()["username"] == "rowan.ashby"
    assert response.json()["display_name"] == "Rowan Ashby"


def test_own_profile_unknown_email_is_404(authed_client: TestClient) -> None:
    response = authed_client.get(f"{MEMBER}/me", auth=("nobody@example.org", "good-pass"))

    assert response.status_code == 404


def test_update_own_profile(authed_client: TestClient) -> None:
    response = authed_client.patch(
        f"{MEMBER}/me", json={"bio": "Updated through /me."}, auth=ROWAN
    )

    assert response.status_code == 200
    assert response.json()["bio"] == "Updated through /me."


def test_delete_own_profile(authed_client: TestClient) -> None:
    created = authed_client.post(
        MEMBER,
        json={"username": "self.delete", "email": "self.delete@example.org"},
        auth=("grace@plymouth.ac.uk", "good-pass"),
    )
    assert created.status_code == 201

    account = ("self.delete@example.org", "good-pass")
    assert authed_client.delete(f"{MEMBER}/me", auth=account).status_code == 204
    assert authed_client.get(f"{MEMBER}/me", auth=account).status_code == 404


def test_list_members_returns_demo_data(client: TestClient) -> None:
    response = client.get(MEMBER)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 10
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == min(body["total"], 20)
    assert {
        "member_id",
        "username",
        "locality_name",
        "profile_visibility",
        "account_status",
    } <= set(body["items"][0])


def test_list_members_filters_by_nation(client: TestClient) -> None:
    body = client.get(MEMBER, params={"nation": "GB-SCT"}).json()

    assert body["total"] == 2
    assert {item["locality_name"] for item in body["items"]} == {"Aviemore", "Oban"}


def test_list_members_filters_by_activity(client: TestClient) -> None:
    body = client.get(MEMBER, params={"activity_type": "hiking"}).json()

    assert 5 <= body["total"] < 11
    assert any(item["member_id"] == 1 for item in body["items"])
    assert all(item["member_id"] != 4 for item in body["items"])


def test_read_member_profile(client: TestClient) -> None:
    body = client.get(f"{MEMBER}/1").json()

    assert body["username"] == "rowan.ashby"
    assert body["location"]["display"] == "Bakewell, Derbyshire, England"
    assert body["preference_count"] == 3
    assert body["follower_count"] == 4
    assert body["following_count"] == 2
    assert body["joined_at"].startswith("2025-03-04T10:12:00")
    assert "password_hash" not in body


def test_missing_member_is_404(client: TestClient) -> None:
    response = client.get(f"{MEMBER}/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_register_member_and_reject_duplicates(client: TestClient) -> None:
    payload = {
        "username": "test.walker",
        "email": "test.walker@example.org",
        "first_name": "Test",
        "last_name": "Walker",
        "password": "a-very-secret-password",
        "locality_id": 3,
        "bio": "Created by the integration test.",
    }
    created = client.post(MEMBER, json=payload)

    assert created.status_code == 201
    member_id = created.json()["member_id"]
    assert created.headers["Location"].endswith(f"/members/{member_id}")
    assert created.json()["location"]["locality"] == "Keswick"
    assert created.json()["preference_count"] == 0

    duplicate = client.post(MEMBER, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"

    assert client.delete(f"{MEMBER}/{member_id}").status_code == 204


def test_create_member_with_only_a_username(client: TestClient) -> None:
    first = client.post(MEMBER, json={"username": "solo.walker"})
    assert first.status_code == 201
    body = first.json()
    assert body["display_name"] == "solo.walker"
    assert body["email"] is None
    assert body["first_name"] is None
    assert body["location"] is None
    assert body["preference_count"] == 0

    second = client.post(MEMBER, json={"username": "solo.walker.two"})
    assert second.status_code == 201
    assert second.json()["email"] is None

    for member_id in (body["member_id"], second.json()["member_id"]):
        assert client.delete(f"{MEMBER}/{member_id}").status_code == 204


def test_email_remains_unique_when_supplied(client: TestClient) -> None:
    created = client.post(
        MEMBER, json={"username": "dup.one", "email": "dup@example.org"}
    )
    assert created.status_code == 201

    clash = client.post(
        MEMBER, json={"username": "dup.two", "email": "DUP@example.org"}
    )
    assert clash.status_code == 409

    assert client.delete(f"{MEMBER}/{created.json()['member_id']}").status_code == 204


def test_profile_includes_preferences(client: TestClient) -> None:
    body = client.get(f"{MEMBER}/1").json()

    assert [item["activity_slug"] for item in body["preferences"]] == [
        "walking",
        "hiking",
        "cycling",
    ]
    assert body["preferences"][0]["preference_rank"] == 1


def test_register_rejects_unknown_locality(client: TestClient) -> None:
    response = client.post(
        MEMBER,
        json={
            "username": "test.ghost",
            "email": "test.ghost@example.org",
            "first_name": "Ghost",
            "last_name": "Member",
            "password": "a-very-secret-password",
            "locality_id": 4242,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_locality"


def test_register_validates_payload(client: TestClient) -> None:
    response = client.post(
        MEMBER,
        json={
            "username": "x",
            "email": "not-an-email",
            "first_name": "",
            "last_name": "Walker",
            "password": "short",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert len(body["error"]["details"]) >= 3


def test_update_member(client: TestClient) -> None:
    response = client.patch(f"{MEMBER}/1", json={"bio": "Updated by the test suite."})

    assert response.status_code == 200
    assert response.json()["bio"] == "Updated by the test suite."
    assert response.json()["username"] == "rowan.ashby"


def test_update_rejects_taken_username(client: TestClient) -> None:
    response = client.patch(f"{MEMBER}/1", json={"username": "megan.pryce"})

    assert response.status_code == 409


def test_replace_preferences(client: TestClient) -> None:
    response = client.put(
        f"{MEMBER}/5/preferences",
        json=[
            {"activity_type_id": 1, "preference_rank": 1, "skill_level_id": 2},
            {"activity_type_id": 2, "preference_rank": 2},
        ],
    )

    assert response.status_code == 200
    items = response.json()
    assert [item["activity_slug"] for item in items] == ["walking", "hiking"]
    assert items[0]["skill_level"]["code"] == "intermediate"
    assert items[1]["skill_level"] is None


def test_replace_preferences_rejects_duplicate_ranks(client: TestClient) -> None:
    response = client.put(
        f"{MEMBER}/6/preferences",
        json=[
            {"activity_type_id": 1, "preference_rank": 1},
            {"activity_type_id": 2, "preference_rank": 1},
        ],
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "duplicate_rank"


def test_add_and_remove_single_preference(client: TestClient) -> None:
    created = client.post(
        f"{MEMBER}/5/preferences",
        json={"activity_type_id": 4, "preference_rank": 3, "skill_level_id": 1},
    )
    assert created.status_code == 201
    assert created.json()["activity_slug"] == "cycling"

    duplicate = client.post(
        f"{MEMBER}/5/preferences",
        json={"activity_type_id": 4, "preference_rank": 4},
    )
    assert duplicate.status_code == 409

    removed = client.delete(f"{MEMBER}/5/preferences/4")
    assert removed.status_code == 204
    assert client.delete(f"{MEMBER}/5/preferences/4").status_code == 404


def test_follow_is_idempotent(client: TestClient) -> None:
    first = client.put(f"{MEMBER}/5/following/1")
    assert first.status_code == 201

    second = client.put(f"{MEMBER}/5/following/1")
    assert second.status_code == 204

    following = client.get(f"{MEMBER}/5/following").json()
    assert [item["member_id"] for item in following["items"]] == [1]

    assert client.delete(f"{MEMBER}/5/following/1").status_code == 204
    assert client.delete(f"{MEMBER}/5/following/1").status_code == 404


def test_self_follow_is_rejected(client: TestClient) -> None:
    response = client.put(f"{MEMBER}/1/following/1")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "self_follow"


def test_followers_are_listed(client: TestClient) -> None:
    body = client.get(f"{MEMBER}/1/followers").json()

    assert body["total"] == 4
    assert {item["username"] for item in body["items"]} == {
        "megan.pryce",
        "callum.fraser",
        "freya.whitlock",
        "harriet.vale",
    }


def test_delete_member_removes_dependent_rows(client: TestClient) -> None:
    created = client.post(
        MEMBER,
        json={
            "username": "test.temporary",
            "email": "test.temporary@example.org",
            "first_name": "Temp",
            "last_name": "Orary",
            "password": "a-very-secret-password",
        },
    ).json()
    member_id = created["member_id"]

    client.put(f"{MEMBER}/1/following/{member_id}")
    client.put(
        f"{MEMBER}/{member_id}/preferences",
        json=[{"activity_type_id": 1, "preference_rank": 1}],
    )

    removed = client.delete(f"{MEMBER}/{member_id}")
    assert removed.status_code == 204
    assert client.get(f"{MEMBER}/{member_id}").status_code == 404


def test_reference_data(client: TestClient) -> None:
    countries = client.get(f"{API_PREFIX}/reference/countries").json()
    assert len(countries) == 4
    assert countries[0]["iso_code"] == "GB-ENG"

    regions = client.get(f"{API_PREFIX}/reference/regions", params={"country_id": 2}).json()
    assert {region["name"] for region in regions} == {"Highland", "Argyll and Bute"}

    localities = client.get(
        f"{API_PREFIX}/reference/localities", params={"region_id": 1}
    ).json()
    assert {locality["name"] for locality in localities} == {"Bakewell", "Castleton"}

    active_types = client.get(f"{API_PREFIX}/reference/activity-types").json()
    assert len(active_types) == 4
    all_types = client.get(
        f"{API_PREFIX}/reference/activity-types", params={"include_inactive": True}
    ).json()
    assert len(all_types) == 5
    assert {item["slug"] for item in active_types} == {
        "walking",
        "hiking",
        "trail-running",
        "cycling",
    }

    skill_levels = client.get(f"{API_PREFIX}/reference/skill-levels").json()
    assert [level["code"] for level in skill_levels] == [
        "beginner",
        "intermediate",
        "advanced",
        "expert",
    ]
