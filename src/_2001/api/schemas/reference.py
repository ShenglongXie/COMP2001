from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CountryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_id: int
    iso_code: str
    name: str


class RegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: int
    country_id: int
    gss_code: str
    name: str


class LocalityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locality_id: int
    region_id: int
    name: str


class ActivityCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    name: str
    description: str | None = None


class ActivityTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_type_id: int
    category_id: int
    slug: str
    label: str
    is_active: bool


class SkillLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_level_id: int
    code: str
    label: str
    max_trail_difficulty: int
