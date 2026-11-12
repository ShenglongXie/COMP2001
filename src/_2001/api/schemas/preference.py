from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from _2001.db.models import MemberPreference


class PreferenceWrite(BaseModel):
    activity_type_id: int
    preference_rank: int = Field(ge=1, le=20)
    skill_level_id: int | None = None


class SkillRef(BaseModel):
    skill_level_id: int
    code: str
    label: str


class PreferenceRead(BaseModel):
    activity_type_id: int
    activity_slug: str
    activity_label: str
    category: str
    preference_rank: int
    skill_level: SkillRef | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, preference: MemberPreference) -> PreferenceRead:
        activity_type = preference.activity_type
        skill_level = preference.skill_level
        return cls(
            activity_type_id=activity_type.activity_type_id,
            activity_slug=activity_type.slug,
            activity_label=activity_type.label,
            category=activity_type.category.name,
            preference_rank=preference.preference_rank,
            skill_level=(
                SkillRef(
                    skill_level_id=skill_level.skill_level_id,
                    code=skill_level.code,
                    label=skill_level.label,
                )
                if skill_level
                else None
            ),
            created_at=preference.created_at,
        )
