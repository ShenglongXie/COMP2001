from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from _2001.api.deps import get_session
from _2001.api.schemas.reference import (
    ActivityCategoryRead,
    ActivityTypeRead,
    CountryRead,
    LocalityRead,
    RegionRead,
    SkillLevelRead,
)
from _2001.db.models import (
    ActivityCategory,
    ActivityType,
    Country,
    Locality,
    Region,
    SkillLevel,
)

router = APIRouter(prefix="/reference", tags=["Reference data"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/countries",
    response_model=list[CountryRead],
    summary="List the UK nations",
)
def list_countries(session: SessionDep) -> list[Country]:
    return list(session.scalars(select(Country).order_by(Country.country_id)))


@router.get(
    "/regions",
    response_model=list[RegionRead],
    summary="List counties and unitary authorities",
)
def list_regions(
    session: SessionDep,
    country_id: Annotated[int | None, Query(description="Restrict to one nation.")] = None,
) -> list[Region]:
    stmt = select(Region).order_by(Region.region_id)
    if country_id is not None:
        stmt = stmt.where(Region.country_id == country_id)
    return list(session.scalars(stmt))


@router.get(
    "/localities",
    response_model=list[LocalityRead],
    summary="List towns and villages",
)
def list_localities(
    session: SessionDep,
    region_id: Annotated[int | None, Query(description="Restrict to one region.")] = None,
) -> list[Locality]:
    stmt = select(Locality).order_by(Locality.locality_id)
    if region_id is not None:
        stmt = stmt.where(Locality.region_id == region_id)
    return list(session.scalars(stmt))


@router.get(
    "/activity-categories",
    response_model=list[ActivityCategoryRead],
    summary="List activity categories",
)
def list_activity_categories(session: SessionDep) -> list[ActivityCategory]:
    return list(
        session.scalars(
            select(ActivityCategory).order_by(ActivityCategory.category_id)
        )
    )


@router.get(
    "/activity-types",
    response_model=list[ActivityTypeRead],
    summary="List activity types",
)
def list_activity_types(
    session: SessionDep,
    category_id: Annotated[
        int | None, Query(description="Restrict to one category.")
    ] = None,
    include_inactive: Annotated[
        bool, Query(description="Include types that are no longer offered.")
    ] = False,
) -> list[ActivityType]:
    stmt = select(ActivityType).order_by(ActivityType.activity_type_id)
    if category_id is not None:
        stmt = stmt.where(ActivityType.category_id == category_id)
    if not include_inactive:
        stmt = stmt.where(ActivityType.is_active == true())
    return list(session.scalars(stmt))


@router.get(
    "/skill-levels",
    response_model=list[SkillLevelRead],
    summary="List skill levels",
)
def list_skill_levels(session: SessionDep) -> list[SkillLevel]:
    return list(
        session.scalars(select(SkillLevel).order_by(SkillLevel.skill_level_id))
    )
