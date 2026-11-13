from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from _2001.api.deps import Pagination, get_pagination, get_session
from _2001.api.errors import ApiError, conflict, not_found, unprocessable
from _2001.api.schemas.common import ErrorResponse, Page
from _2001.api.schemas.member import (
    LocationRead,
    MemberCreate,
    MemberRead,
    MemberSummary,
    MemberUpdate,
    display_name,
)
from _2001.api.schemas.preference import PreferenceRead
from _2001.core.security import hash_password
from _2001.db.models import (
    ActivityType,
    Country,
    Locality,
    Member,
    MemberFollow,
    MemberPreference,
    Region,
)

router = APIRouter(prefix="/members", tags=["Members"])

SessionDep = Annotated[Session, Depends(get_session)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]

MEMBER_NOT_FOUND = {
    404: {"model": ErrorResponse, "description": "Member does not exist."}
}
CONFLICT = {
    409: {"model": ErrorResponse, "description": "Username or email already used."}
}


def member_query():
    return select(Member).options(
        selectinload(Member.locality)
        .selectinload(Locality.region)
        .selectinload(Region.country),
        selectinload(Member.preferences)
        .selectinload(MemberPreference.activity_type)
        .selectinload(ActivityType.category),
        selectinload(Member.preferences).selectinload(MemberPreference.skill_level),
    )


def load_member(session: Session, member_id: int) -> Member:
    member = session.scalars(member_query().where(Member.member_id == member_id)).one_or_none()
    if member is None:
        raise not_found("Member", member_id)
    return member


def present_member(session: Session, member: Member) -> MemberRead:
    following = session.scalar(
        select(func.count())
        .select_from(MemberFollow)
        .where(MemberFollow.follower_member_id == member.member_id)
    )
    followers = session.scalar(
        select(func.count())
        .select_from(MemberFollow)
        .where(MemberFollow.followee_member_id == member.member_id)
    )
    preferences = sorted(member.preferences, key=lambda item: item.preference_rank)
    return MemberRead(
        member_id=member.member_id,
        username=member.username,
        display_name=display_name(member),
        email=member.email,
        first_name=member.first_name,
        last_name=member.last_name,
        avatar_url=member.avatar_url,
        bio=member.bio,
        location=LocationRead.from_member(member),
        preferred_unit_system=member.preferred_unit_system,
        preferred_language=member.preferred_language,
        profile_visibility=member.profile_visibility,
        account_status=member.account_status,
        email_verified_at=member.email_verified_at,
        last_login_at=member.last_login_at,
        joined_at=member.joined_at,
        updated_at=member.updated_at,
        preferences=[PreferenceRead.from_model(item) for item in preferences],
        preference_count=len(preferences),
        following_count=following or 0,
        follower_count=followers or 0,
    )


def ensure_locality(session: Session, locality_id: int) -> None:
    if session.get(Locality, locality_id) is None:
        raise unprocessable(
            "unknown_locality", f"Locality {locality_id} does not exist."
        )


def ensure_unique(session: Session, *, username: str | None, email: str | None, member_id: int | None = None) -> None:
    if username is not None:
        stmt = select(Member.member_id).where(Member.username == username)
        if member_id is not None:
            stmt = stmt.where(Member.member_id != member_id)
        if session.scalar(stmt) is not None:
            raise conflict(f"Username '{username}' is already taken.")
    if email is not None:
        stmt = select(Member.member_id).where(Member.email == email)
        if member_id is not None:
            stmt = stmt.where(Member.member_id != member_id)
        if session.scalar(stmt) is not None:
            raise conflict(f"Email '{email}' is already registered.")


def current_member(request: Request, session: Session) -> Member:
    user = getattr(request.state, "user", None)
    if user is None:
        raise ApiError(401, "unauthorized", "Authentication is required.")
    member = session.scalars(
        member_query().where(Member.email == user.email)
    ).one_or_none()
    if member is None:
        raise not_found("Member", f"email {user.email}")
    return member


def apply_update(session: Session, member: Member, payload: MemberUpdate) -> MemberRead:
    changes = payload.model_dump(exclude_unset=True)
    password = changes.pop("password", None)
    if "locality_id" in changes and changes["locality_id"] is not None:
        ensure_locality(session, changes["locality_id"])
    ensure_unique(
        session,
        username=changes.get("username"),
        email=changes.get("email"),
        member_id=member.member_id,
    )
    for field, value in changes.items():
        setattr(member, field, value)
    if password is not None:
        member.password_hash = hash_password(password)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("Username or email is already registered.") from exc
    return present_member(session, load_member(session, member.member_id))


def remove_member(session: Session, member: Member) -> Response:
    session.delete(member)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("Member is still referenced by other records.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=MemberRead,
    responses={401: {"model": ErrorResponse}, **MEMBER_NOT_FOUND},
    summary="Read the authenticated member's own profile",
)
def get_own_profile(request: Request, session: SessionDep) -> MemberRead:
    return present_member(session, current_member(request, session))


@router.patch(
    "/me",
    response_model=MemberRead,
    responses={401: {"model": ErrorResponse}, **MEMBER_NOT_FOUND, **CONFLICT},
    summary="Update the authenticated member's own profile",
)
def update_own_profile(
    request: Request, payload: MemberUpdate, session: SessionDep
) -> MemberRead:
    return apply_update(session, current_member(request, session), payload)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={401: {"model": ErrorResponse}, **MEMBER_NOT_FOUND},
    summary="Delete the authenticated member's own profile",
)
def delete_own_profile(request: Request, session: SessionDep) -> Response:
    return remove_member(session, current_member(request, session))


@router.get(
    "",
    response_model=Page[MemberSummary],
    summary="List members",
    description=(
        "Returns members ordered by identifier. Filters can be combined; "
        "the activity filter matches the activity slug (for example `hiking`)."
    ),
)
def list_members(
    session: SessionDep,
    page: PaginationDep,
    nation: Annotated[
        str | None, Query(description="ISO 3166-2 nation code, for example GB-SCT.")
    ] = None,
    locality_id: Annotated[int | None, Query(description="Home locality.")] = None,
    activity_type: Annotated[
        str | None, Query(description="Preferred activity slug.")
    ] = None,
    visibility: Annotated[
        Literal["public", "followers", "private"] | None, Query()
    ] = None,
    username: Annotated[
        str | None, Query(description="Case-insensitive username prefix.")
    ] = None,
) -> Page[MemberSummary]:
    stmt = select(Member)
    if locality_id is not None:
        stmt = stmt.where(Member.locality_id == locality_id)
    if visibility is not None:
        stmt = stmt.where(Member.profile_visibility == visibility)
    if username:
        stmt = stmt.where(Member.username.ilike(f"{username}%"))
    if nation:
        stmt = (
            stmt.join(Member.locality)
            .join(Locality.region)
            .join(Region.country)
            .where(Country.iso_code == nation)
        )
    if activity_type:
        stmt = stmt.where(
            Member.member_id.in_(
                select(MemberPreference.member_id)
                .join(
                    ActivityType,
                    ActivityType.activity_type_id == MemberPreference.activity_type_id,
                )
                .where(ActivityType.slug == activity_type)
            )
        )

    total = session.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    rows = (
        session.scalars(
            stmt.options(selectinload(Member.locality))
            .order_by(Member.member_id)
            .limit(page.limit)
            .offset(page.offset)
        )
        .unique()
        .all()
    )
    return Page[MemberSummary](
        items=[MemberSummary.from_member(member) for member in rows],
        total=total or 0,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    responses={**CONFLICT, 422: {"model": ErrorResponse}},
    summary="Register a member",
)
def create_member(
    payload: MemberCreate, response: Response, session: SessionDep
) -> MemberRead:
    if payload.locality_id is not None:
        ensure_locality(session, payload.locality_id)
    ensure_unique(session, username=payload.username, email=payload.email)

    member = Member(
        username=payload.username,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        password_hash=(
            hash_password(payload.password) if payload.password else None
        ),
        avatar_url=payload.avatar_url,
        bio=payload.bio,
        locality_id=payload.locality_id,
        preferred_unit_system=payload.preferred_unit_system,
        preferred_language=payload.preferred_language,
        profile_visibility=payload.profile_visibility,
        account_status=payload.account_status,
    )
    session.add(member)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("Username or email is already registered.") from exc

    created = load_member(session, member.member_id)
    response.headers["Location"] = f"/api/v1/members/{created.member_id}"
    return present_member(session, created)


@router.get(
    "/{member_id}",
    response_model=MemberRead,
    responses=MEMBER_NOT_FOUND,
    summary="Read a member profile",
)
def get_member(member_id: int, session: SessionDep) -> MemberRead:
    return present_member(session, load_member(session, member_id))


@router.patch(
    "/{member_id}",
    response_model=MemberRead,
    responses={**MEMBER_NOT_FOUND, **CONFLICT, 422: {"model": ErrorResponse}},
    summary="Update a member profile",
    description="Only the provided fields are changed; omitted fields are untouched.",
)
def update_member(
    member_id: int, payload: MemberUpdate, session: SessionDep
) -> MemberRead:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("Member", member_id)
    return apply_update(session, member, payload)


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**MEMBER_NOT_FOUND, 409: {"model": ErrorResponse}},
    summary="Delete a member",
)
def delete_member(member_id: int, session: SessionDep) -> Response:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("Member", member_id)
    return remove_member(session, member)
