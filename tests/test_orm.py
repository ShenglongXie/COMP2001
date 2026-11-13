from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import Identity
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable

from _2001.db import SCHEMA, Base

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "CW2_schema.sql"

EXPECTED_TABLES = {
    "ActivityCategory",
    "ActivityType",
    "Country",
    "Locality",
    "Member",
    "MemberFollow",
    "MemberPreference",
    "Region",
    "SkillLevel",
}


def _table(name: str):
    return Base.metadata.tables[f"{SCHEMA}.{name}"]


def _ddl(name: str) -> str:
    return str(CreateTable(_table(name)).compile(dialect=mssql.dialect()))


@pytest.fixture(scope="module", autouse=True)
def _configure() -> None:
    configure_mappers()


def test_every_table_lives_in_the_profile_schema() -> None:
    assert set(Base.metadata.tables) == {f"{SCHEMA}.{name}" for name in EXPECTED_TABLES}
    assert all(t.schema == SCHEMA for t in Base.metadata.tables.values())


def test_primary_keys() -> None:
    assert [c.name for c in _table("Country").primary_key] == ["CountryId"]
    assert [c.name for c in _table("Member").primary_key] == ["MemberId"]
    assert [c.name for c in _table("MemberPreference").primary_key] == [
        "MemberId",
        "ActivityTypeId",
    ]
    assert [c.name for c in _table("MemberFollow").primary_key] == [
        "FollowerMemberId",
        "FolloweeMemberId",
    ]


def test_member_identity_is_explicit() -> None:
    column = _table("Member").c.MemberId
    assert isinstance(column.identity, Identity)
    assert column.identity.start == 1
    assert column.identity.increment == 1
    assert "IDENTITY(1,1)" in _ddl("Member")


def test_sql_server_types_are_used() -> None:
    ddl = _ddl("Member")
    assert "DATETIME2(0)" in ddl
    assert "NVARCHAR(30) COLLATE Latin1_General_100_CI_AS" in ddl
    assert "DEFAULT SYSUTCDATETIME()" in ddl
    assert "DEFAULT 'metric'" in ddl
    assert "BIT" in _ddl("ActivityType")
    assert "TINYINT" in _ddl("SkillLevel")


def test_indexes_keep_included_columns() -> None:
    statements = {
        str(CreateIndex(index).compile(dialect=mssql.dialect()))
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    expected = (
        f"CREATE INDEX [IX_MemberPreference_TypeId] ON [{SCHEMA}].[MemberPreference] "
        "([ActivityTypeId]) INCLUDE ([MemberId])"
    )
    assert expected in statements


def test_orm_objects_match_the_handwritten_script() -> None:
    script = SCHEMA_SQL.read_text(encoding="utf-8")

    script_constraints = {
        name
        for name in re.findall(r"CONSTRAINT\s+(\w+)", script)
        if not name.startswith("DF_")
    }
    orm_constraints = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if constraint.name
    }
    assert orm_constraints == script_constraints

    script_indexes = set(re.findall(r"CREATE (?:UNIQUE )?INDEX\s+(\w+)", script))
    orm_indexes = {
        index.name for table in Base.metadata.tables.values() for index in table.indexes
    }
    assert orm_indexes == script_indexes


def test_relationships_are_bidirectional() -> None:
    member = _table("Member")
    assert member is not None

    from _2001.db import (
        ActivityType,
        Country,
        Locality,
        Member,
        MemberFollow,
        MemberPreference,
        Region,
        SkillLevel,
    )
    from sqlalchemy import inspect

    member_mapper = inspect(Member)
    assert {"locality", "preferences", "following", "followers"} <= set(
        member_mapper.relationships.keys()
    )

    assert inspect(Locality).relationships["members"].back_populates == "locality"
    assert inspect(Region).relationships["localities"].back_populates == "region"
    assert inspect(Country).relationships["regions"].back_populates == "country"
    assert (
        inspect(ActivityType).relationships["preferences"].back_populates
        == "activity_type"
    )
    assert inspect(SkillLevel).relationships["preferences"].back_populates == (
        "skill_level"
    )
    assert inspect(MemberPreference).relationships["member"].back_populates == (
        "preferences"
    )

    follow = inspect(MemberFollow)
    assert follow.relationships["follower"].back_populates == "following"
    assert follow.relationships["followee"].back_populates == "followers"
    assert len(follow.relationships["follower"]._user_defined_foreign_keys) == 1
