from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from _2001.api.schemas.preference import PreferenceRead
from _2001.db.models import Member

Username = Annotated[
    str,
    StringConstraints(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9._-]+$"),
]
Email = Annotated[
    str,
    StringConstraints(
        max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
PersonName = Annotated[str, StringConstraints(min_length=1, max_length=60)]
Language = Annotated[str, StringConstraints(min_length=2, max_length=5)]

Visibility = Literal["public", "followers", "private"]
AccountStatus = Literal["active", "suspended", "deactivated"]
UnitSystem = Literal["metric", "imperial"]


def display_name(member: Member) -> str:
    parts = [member.first_name, member.last_name]
    joined = " ".join(part.strip() for part in parts if part and part.strip())
    return joined or member.username


class LocationRead(BaseModel):
    locality_id: int
    locality: str
    region: str
    country: str
    display: str

    @classmethod
    def from_member(cls, member: Member) -> LocationRead | None:
        locality = member.locality
        if locality is None:
            return None
        region = locality.region
        country = region.country
        return cls(
            locality_id=locality.locality_id,
            locality=locality.name,
            region=region.name,
            country=country.name,
            display=f"{locality.name}, {region.name}, {country.name}",
        )


class MemberSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: int
    username: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    locality_name: str | None = None
    profile_visibility: Visibility
    account_status: AccountStatus
    joined_at: datetime

    @classmethod
    def from_member(cls, member: Member) -> MemberSummary:
        locality = member.locality
        return cls(
            member_id=member.member_id,
            username=member.username,
            display_name=display_name(member),
            first_name=member.first_name,
            last_name=member.last_name,
            locality_name=locality.name if locality else None,
            profile_visibility=member.profile_visibility,
            account_status=member.account_status,
            joined_at=member.joined_at,
        )


class MemberCreate(BaseModel):
    username: Username
    email: Email | None = None
    first_name: PersonName | None = None
    last_name: PersonName | None = None
    password: (
        Annotated[str, StringConstraints(min_length=8, max_length=128)] | None
    ) = None
    avatar_url: Annotated[str, StringConstraints(max_length=400)] | None = None
    bio: Annotated[str, StringConstraints(max_length=500)] | None = None
    locality_id: int | None = None
    preferred_unit_system: UnitSystem = "metric"
    preferred_language: Language = "en-GB"
    profile_visibility: Visibility = "public"
    account_status: AccountStatus = "active"


class MemberUpdate(BaseModel):
    username: Username | None = None
    email: Email | None = None
    first_name: PersonName | None = None
    last_name: PersonName | None = None
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)] | None = None
    avatar_url: Annotated[str, StringConstraints(max_length=400)] | None = None
    bio: Annotated[str, StringConstraints(max_length=500)] | None = None
    locality_id: int | None = None
    preferred_unit_system: UnitSystem | None = None
    preferred_language: Language | None = None
    profile_visibility: Visibility | None = None
    account_status: AccountStatus | None = None


class MemberRead(BaseModel):
    member_id: int
    username: str
    display_name: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    location: LocationRead | None = None
    preferred_unit_system: UnitSystem
    preferred_language: str
    profile_visibility: Visibility
    account_status: AccountStatus
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    joined_at: datetime
    updated_at: datetime
    preferences: list[PreferenceRead] = Field(default_factory=list)
    preference_count: int = Field(ge=0)
    following_count: int = Field(ge=0)
    follower_count: int = Field(ge=0)
