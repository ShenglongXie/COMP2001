from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from _2001.api.errors import ApiError


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int


def get_session(request: Request) -> Iterator[Session]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise ApiError(
            503, "service_unavailable", "The database is not configured."
        )
    with factory() as session:
        try:
            yield session
        finally:
            session.close()


def get_pagination(
    limit: int = Query(20, ge=1, le=100, description="Maximum rows to return."),
    offset: int = Query(0, ge=0, description="Rows to skip."),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
