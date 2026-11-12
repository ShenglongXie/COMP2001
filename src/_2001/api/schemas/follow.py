from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from _2001.db.models import MemberFollow


class FollowRead(BaseModel):
    member_id: int
    username: str
    followed_at: datetime

    @classmethod
    def as_followee(cls, follow: MemberFollow) -> FollowRead:
        return cls(
            member_id=follow.followee_member_id,
            username=follow.followee.username,
            followed_at=follow.followed_at,
        )

    @classmethod
    def as_follower(cls, follow: MemberFollow) -> FollowRead:
        return cls(
            member_id=follow.follower_member_id,
            username=follow.follower.username,
            followed_at=follow.followed_at,
        )
