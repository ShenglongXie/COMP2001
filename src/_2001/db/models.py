from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Unicode,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from _2001.db.base import Base

TIMESTAMP = DateTime().with_variant(mssql.DATETIME2(precision=0), "mssql")
TINY_INT = SmallInteger().with_variant(mssql.TINYINT(), "mssql")


def ci_nvarchar(length: int) -> Unicode:
    return Unicode(length).with_variant(
        mssql.NVARCHAR(length, collation="Latin1_General_100_CI_AS"), "mssql"
    )


class Country(Base):
    __tablename__ = "Country"
    __table_args__ = (
        UniqueConstraint("IsoCode", name="UQ_Country_IsoCode"),
        UniqueConstraint("Name", name="UQ_Country_Name"),
        CheckConstraint(
            "IsoCode LIKE 'GB-[A-Z][A-Z][A-Z]'", name="CK_Country_IsoCode"
        ),
    )

    country_id: Mapped[int] = mapped_column("CountryId", SmallInteger, primary_key=True)
    iso_code: Mapped[str] = mapped_column("IsoCode", CHAR(6), nullable=False)
    name: Mapped[str] = mapped_column("Name", Unicode(80), nullable=False)

    regions: Mapped[list[Region]] = relationship(back_populates="country")


class Region(Base):
    __tablename__ = "Region"
    __table_args__ = (
        UniqueConstraint("CountryId", "GssCode", name="UQ_Region_GssCode"),
        CheckConstraint(
            "GssCode LIKE '[EWSN][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'",
            name="CK_Region_GssCode",
        ),
        Index("IX_Region_CountryId", "CountryId"),
    )

    region_id: Mapped[int] = mapped_column("RegionId", Integer, primary_key=True)
    country_id: Mapped[int] = mapped_column(
        "CountryId",
        SmallInteger,
        ForeignKey(
            "profile.Country.CountryId", name="FK_Region_Country", ondelete="NO ACTION"
        ),
        nullable=False,
    )
    gss_code: Mapped[str] = mapped_column("GssCode", CHAR(9), nullable=False)
    name: Mapped[str] = mapped_column("Name", Unicode(120), nullable=False)

    country: Mapped[Country] = relationship(back_populates="regions")
    localities: Mapped[list[Locality]] = relationship(back_populates="region")


class Locality(Base):
    __tablename__ = "Locality"
    __table_args__ = (
        UniqueConstraint("RegionId", "Name", name="UQ_Locality_Name"),
        Index("IX_Locality_RegionId", "RegionId"),
    )

    locality_id: Mapped[int] = mapped_column("LocalityId", Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(
        "RegionId",
        Integer,
        ForeignKey(
            "profile.Region.RegionId", name="FK_Locality_Region", ondelete="NO ACTION"
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column("Name", Unicode(120), nullable=False)

    region: Mapped[Region] = relationship(back_populates="localities")
    members: Mapped[list[Member]] = relationship(back_populates="locality")


class ActivityCategory(Base):
    __tablename__ = "ActivityCategory"
    __table_args__ = (
        UniqueConstraint("Name", name="UQ_ActivityCategory_Name"),
    )

    category_id: Mapped[int] = mapped_column(
        "CategoryId", SmallInteger, primary_key=True
    )
    name: Mapped[str] = mapped_column("Name", String(24), nullable=False)
    description: Mapped[str | None] = mapped_column(
        "Description", Unicode(120), nullable=True
    )

    activity_types: Mapped[list[ActivityType]] = relationship(back_populates="category")


class ActivityType(Base):
    __tablename__ = "ActivityType"
    __table_args__ = (
        UniqueConstraint("Slug", name="UQ_ActivityType_Slug"),
        Index("IX_ActivityType_CategoryId", "CategoryId"),
    )

    activity_type_id: Mapped[int] = mapped_column(
        "ActivityTypeId", SmallInteger, primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        "CategoryId",
        SmallInteger,
        ForeignKey(
            "profile.ActivityCategory.CategoryId",
            name="FK_ActivityType_Category",
            ondelete="NO ACTION",
        ),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column("Slug", String(24), nullable=False)
    label: Mapped[str] = mapped_column("Label", Unicode(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        "IsActive", Boolean, nullable=False, server_default=text("1")
    )

    category: Mapped[ActivityCategory] = relationship(back_populates="activity_types")
    preferences: Mapped[list[MemberPreference]] = relationship(
        back_populates="activity_type"
    )


class SkillLevel(Base):
    __tablename__ = "SkillLevel"
    __table_args__ = (
        UniqueConstraint("Code", name="UQ_SkillLevel_Code"),
        CheckConstraint(
            "MaxTrailDifficulty BETWEEN 1 AND 5", name="CK_SkillLevel_MaxDiff"
        ),
    )

    skill_level_id: Mapped[int] = mapped_column(
        "SkillLevelId", SmallInteger, primary_key=True
    )
    code: Mapped[str] = mapped_column("Code", String(16), nullable=False)
    label: Mapped[str] = mapped_column("Label", Unicode(24), nullable=False)
    max_trail_difficulty: Mapped[int] = mapped_column(
        "MaxTrailDifficulty", TINY_INT, nullable=False
    )

    preferences: Mapped[list[MemberPreference]] = relationship(
        back_populates="skill_level"
    )


class Member(Base):
    __tablename__ = "Member"
    __table_args__ = (
        UniqueConstraint("Username", name="UQ_Member_Username"),
        UniqueConstraint("Email", name="UQ_Member_Email"),
        CheckConstraint(
            "PreferredUnitSystem IN ('metric', 'imperial')",
            name="CK_Member_UnitSystem",
        ),
        CheckConstraint(
            "ProfileVisibility IN ('public', 'followers', 'private')",
            name="CK_Member_Visibility",
        ),
        CheckConstraint(
            "AccountStatus IN ('active', 'suspended', 'deactivated')",
            name="CK_Member_Status",
        ),
        Index("IX_Member_LocalityId", "LocalityId"),
    )

    member_id: Mapped[int] = mapped_column(
        "MemberId", BigInteger, Identity(start=1, increment=1), primary_key=True
    )
    username: Mapped[str] = mapped_column(
        "Username", ci_nvarchar(30), nullable=False
    )
    email: Mapped[str] = mapped_column("Email", ci_nvarchar(320), nullable=False)
    first_name: Mapped[str] = mapped_column("FirstName", Unicode(60), nullable=False)
    last_name: Mapped[str] = mapped_column("LastName", Unicode(60), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(
        "AvatarUrl", Unicode(400), nullable=True
    )
    bio: Mapped[str | None] = mapped_column("Bio", Unicode(500), nullable=True)
    locality_id: Mapped[int | None] = mapped_column(
        "LocalityId",
        Integer,
        ForeignKey(
            "profile.Locality.LocalityId", name="FK_Member_Locality", ondelete="SET NULL"
        ),
        nullable=True,
    )
    preferred_unit_system: Mapped[str] = mapped_column(
        "PreferredUnitSystem",
        String(8),
        nullable=False,
        server_default=text("'metric'"),
    )
    preferred_language: Mapped[str] = mapped_column(
        "PreferredLanguage", CHAR(5), nullable=False, server_default=text("'en-GB'")
    )
    profile_visibility: Mapped[str] = mapped_column(
        "ProfileVisibility", String(10), nullable=False, server_default=text("'public'")
    )
    account_status: Mapped[str] = mapped_column(
        "AccountStatus", String(12), nullable=False, server_default=text("'active'")
    )
    password_hash: Mapped[str] = mapped_column(
        "PasswordHash", String(255), nullable=False
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        "EmailVerifiedAt", TIMESTAMP, nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        "LastLoginAt", TIMESTAMP, nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        "JoinedAt",
        TIMESTAMP,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        "UpdatedAt",
        TIMESTAMP,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )

    locality: Mapped[Locality | None] = relationship(back_populates="members")
    preferences: Mapped[list[MemberPreference]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    following: Mapped[list[MemberFollow]] = relationship(
        back_populates="follower",
        foreign_keys="MemberFollow.follower_member_id",
        cascade="all, delete-orphan",
    )
    followers: Mapped[list[MemberFollow]] = relationship(
        back_populates="followee",
        foreign_keys="MemberFollow.followee_member_id",
        cascade="all, delete-orphan",
    )


class MemberPreference(Base):
    __tablename__ = "MemberPreference"
    __table_args__ = (
        UniqueConstraint("MemberId", "PreferenceRank", name="UQ_MemberPreference_Rank"),
        CheckConstraint(
            "PreferenceRank BETWEEN 1 AND 20", name="CK_MemberPreference_Rank"
        ),
        Index(
            "IX_MemberPreference_TypeId", "ActivityTypeId", mssql_include=["MemberId"]
        ),
        Index(
            "IX_MemberPreference_SkillLevel",
            "SkillLevelId",
            mssql_include=["MemberId"],
        ),
    )

    member_id: Mapped[int] = mapped_column(
        "MemberId",
        BigInteger,
        ForeignKey(
            "profile.Member.MemberId",
            name="FK_MemberPreference_Member",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    activity_type_id: Mapped[int] = mapped_column(
        "ActivityTypeId",
        SmallInteger,
        ForeignKey(
            "profile.ActivityType.ActivityTypeId",
            name="FK_MemberPreference_Type",
            ondelete="NO ACTION",
        ),
        primary_key=True,
    )
    preference_rank: Mapped[int] = mapped_column(
        "PreferenceRank", SmallInteger, nullable=False
    )
    skill_level_id: Mapped[int | None] = mapped_column(
        "SkillLevelId",
        SmallInteger,
        ForeignKey(
            "profile.SkillLevel.SkillLevelId",
            name="FK_MemberPreference_Skill",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "CreatedAt",
        TIMESTAMP,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )

    member: Mapped[Member] = relationship(back_populates="preferences")
    activity_type: Mapped[ActivityType] = relationship(back_populates="preferences")
    skill_level: Mapped[SkillLevel | None] = relationship(back_populates="preferences")


class MemberFollow(Base):
    __tablename__ = "MemberFollow"
    __table_args__ = (
        CheckConstraint(
            "FollowerMemberId <> FolloweeMemberId", name="CK_MemberFollow_NoSelf"
        ),
        Index(
            "IX_MemberFollow_FolloweeId",
            "FolloweeMemberId",
            mssql_include=["FollowerMemberId"],
        ),
    )

    follower_member_id: Mapped[int] = mapped_column(
        "FollowerMemberId",
        BigInteger,
        ForeignKey(
            "profile.Member.MemberId",
            name="FK_MemberFollow_Follower",
            ondelete="NO ACTION",
        ),
        primary_key=True,
    )
    followee_member_id: Mapped[int] = mapped_column(
        "FolloweeMemberId",
        BigInteger,
        ForeignKey(
            "profile.Member.MemberId",
            name="FK_MemberFollow_Followee",
            ondelete="NO ACTION",
        ),
        primary_key=True,
    )
    followed_at: Mapped[datetime] = mapped_column(
        "FollowedAt",
        TIMESTAMP,
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
    )

    follower: Mapped[Member] = relationship(
        back_populates="following", foreign_keys=[follower_member_id]
    )
    followee: Mapped[Member] = relationship(
        back_populates="followers", foreign_keys=[followee_member_id]
    )


__all__ = [
    "ActivityCategory",
    "ActivityType",
    "Country",
    "Locality",
    "Member",
    "MemberFollow",
    "MemberPreference",
    "Region",
    "SkillLevel",
]
