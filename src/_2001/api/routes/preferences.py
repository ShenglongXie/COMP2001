from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from _2001.api.deps import get_session
from _2001.api.errors import conflict, not_found, unprocessable
from _2001.api.schemas.common import ErrorResponse
from _2001.api.schemas.preference import PreferenceRead, PreferenceWrite
from _2001.db.models import ActivityType, Member, MemberPreference, SkillLevel

router = APIRouter(prefix="/members/{member_id}/preferences", tags=["Preferences"])

SessionDep = Annotated[Session, Depends(get_session)]


def load_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("Member", member_id)
    return member


def load_preferences(session: Session, member_id: int) -> list[MemberPreference]:
    return list(
        session.scalars(
            select(MemberPreference)
            .where(MemberPreference.member_id == member_id)
            .options(
                selectinload(MemberPreference.activity_type).selectinload(
                    ActivityType.category
                ),
                selectinload(MemberPreference.skill_level),
            )
            .order_by(MemberPreference.preference_rank)
        )
    )


def validate_payload(session: Session, items: list[PreferenceWrite]) -> None:
    activity_ids = [item.activity_type_id for item in items]
    ranks = [item.preference_rank for item in items]
    if len(set(activity_ids)) != len(activity_ids):
        raise unprocessable(
            "duplicate_activity", "Each activity type may appear only once."
        )
    if len(set(ranks)) != len(ranks):
        raise unprocessable("duplicate_rank", "Preference ranks must be unique.")

    if activity_ids:
        known = set(
            session.scalars(
                select(ActivityType.activity_type_id).where(
                    ActivityType.activity_type_id.in_(activity_ids)
                )
            )
        )
        missing = sorted(set(activity_ids) - known)
        if missing:
            raise unprocessable(
                "unknown_activity_type",
                f"Activity types {missing} do not exist.",
            )

    skill_ids = [item.skill_level_id for item in items if item.skill_level_id]
    if skill_ids:
        known = set(
            session.scalars(
                select(SkillLevel.skill_level_id).where(
                    SkillLevel.skill_level_id.in_(skill_ids)
                )
            )
        )
        missing = sorted(set(skill_ids) - known)
        if missing:
            raise unprocessable(
                "unknown_skill_level", f"Skill levels {missing} do not exist."
            )


@router.get(
    "",
    response_model=list[PreferenceRead],
    responses={404: {"model": ErrorResponse}},
    summary="List the member's preferred activities",
)
def list_preferences(member_id: int, session: SessionDep) -> list[PreferenceRead]:
    load_member(session, member_id)
    return [
        PreferenceRead.from_model(item)
        for item in load_preferences(session, member_id)
    ]


@router.put(
    "",
    response_model=list[PreferenceRead],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Replace the member's preferred activities",
    description=(
        "Idempotent: the supplied list becomes the complete set of preferences, "
        "ordered by `preference_rank`."
    ),
)
def replace_preferences(
    member_id: int, payload: list[PreferenceWrite], session: SessionDep
) -> list[PreferenceRead]:
    member = load_member(session, member_id)
    validate_payload(session, payload)

    member.preferences.clear()
    session.flush()
    for item in sorted(payload, key=lambda entry: entry.preference_rank):
        member.preferences.append(
            MemberPreference(
                activity_type_id=item.activity_type_id,
                preference_rank=item.preference_rank,
                skill_level_id=item.skill_level_id,
            )
        )
    session.commit()
    return [
        PreferenceRead.from_model(item)
        for item in load_preferences(session, member_id)
    ]


@router.post(
    "",
    response_model=PreferenceRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Add one preferred activity",
)
def add_preference(
    member_id: int, payload: PreferenceWrite, session: SessionDep
) -> PreferenceRead:
    member = load_member(session, member_id)
    existing = session.get(MemberPreference, (member_id, payload.activity_type_id))
    if existing is not None:
        raise conflict("The member already prefers this activity type.")
    taken = session.scalar(
        select(MemberPreference.activity_type_id).where(
            MemberPreference.member_id == member_id,
            MemberPreference.preference_rank == payload.preference_rank,
        )
    )
    if taken is not None:
        raise conflict(f"Preference rank {payload.preference_rank} is already used.")

    validate_payload(session, [payload])
    member.preferences.append(
        MemberPreference(
            activity_type_id=payload.activity_type_id,
            preference_rank=payload.preference_rank,
            skill_level_id=payload.skill_level_id,
        )
    )
    session.commit()
    return PreferenceRead.from_model(
        session.get(MemberPreference, (member_id, payload.activity_type_id))
    )


@router.delete(
    "/{activity_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={404: {"model": ErrorResponse}},
    summary="Remove one preferred activity",
)
def remove_preference(
    member_id: int, activity_type_id: int, session: SessionDep
) -> Response:
    load_member(session, member_id)
    preference = session.get(MemberPreference, (member_id, activity_type_id))
    if preference is None:
        raise not_found("Preference", activity_type_id)
    session.delete(preference)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
