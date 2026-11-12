from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from _2001.api.deps import Pagination, get_pagination, get_session
from _2001.api.errors import not_found, unprocessable
from _2001.api.schemas.common import ErrorResponse, Page
from _2001.api.schemas.follow import FollowRead
from _2001.db.models import Member, MemberFollow

router = APIRouter(prefix="/members/{member_id}", tags=["Social"])

SessionDep = Annotated[Session, Depends(get_session)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]

NOT_FOUND = {404: {"model": ErrorResponse}}


def load_member(session: Session, member_id: int) -> Member:
    member = session.get(Member, member_id)
    if member is None:
        raise not_found("Member", member_id)
    return member


@router.get(
    "/following",
    response_model=Page[FollowRead],
    responses=NOT_FOUND,
    summary="List the members this member follows",
)
def list_following(
    member_id: int, session: SessionDep, page: PaginationDep
) -> Page[FollowRead]:
    load_member(session, member_id)
    stmt = (
        select(MemberFollow)
        .where(MemberFollow.follower_member_id == member_id)
        .options(selectinload(MemberFollow.followee))
        .order_by(MemberFollow.followee_member_id)
    )
    total = session.scalar(
        select(func.count())
        .select_from(MemberFollow)
        .where(MemberFollow.follower_member_id == member_id)
    )
    rows = session.scalars(stmt.limit(page.limit).offset(page.offset)).all()
    return Page[FollowRead](
        items=[FollowRead.as_followee(row) for row in rows],
        total=total or 0,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/followers",
    response_model=Page[FollowRead],
    responses=NOT_FOUND,
    summary="List the members following this member",
)
def list_followers(
    member_id: int, session: SessionDep, page: PaginationDep
) -> Page[FollowRead]:
    load_member(session, member_id)
    stmt = (
        select(MemberFollow)
        .where(MemberFollow.followee_member_id == member_id)
        .options(selectinload(MemberFollow.follower))
        .order_by(MemberFollow.follower_member_id)
    )
    total = session.scalar(
        select(func.count())
        .select_from(MemberFollow)
        .where(MemberFollow.followee_member_id == member_id)
    )
    rows = session.scalars(stmt.limit(page.limit).offset(page.offset)).all()
    return Page[FollowRead](
        items=[FollowRead.as_follower(row) for row in rows],
        total=total or 0,
        limit=page.limit,
        offset=page.offset,
    )


@router.put(
    "/following/{followee_id}",
    status_code=status.HTTP_201_CREATED,
    responses={**NOT_FOUND, 204: {"description": "The follow already existed."}},
    summary="Follow a member",
    description="Idempotent: returns 201 when the follow is created, 204 when it exists.",
)
def follow_member(
    member_id: int, followee_id: int, response: Response, session: SessionDep
) -> Response:
    load_member(session, member_id)
    load_member(session, followee_id)
    if member_id == followee_id:
        raise unprocessable("self_follow", "A member cannot follow themselves.")

    existing = session.get(MemberFollow, (member_id, followee_id))
    if existing is not None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    session.add(MemberFollow(follower_member_id=member_id, followee_member_id=followee_id))
    session.commit()
    return Response(status_code=status.HTTP_201_CREATED)


@router.delete(
    "/following/{followee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND,
    summary="Stop following a member",
)
def unfollow_member(
    member_id: int, followee_id: int, session: SessionDep
) -> Response:
    load_member(session, member_id)
    follow = session.get(MemberFollow, (member_id, followee_id))
    if follow is None:
        raise not_found("Follow", f"{member_id}->{followee_id}")
    session.delete(follow)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
