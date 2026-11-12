from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

ENGINE_OPTIONS: dict[str, Any] = {"pool_pre_ping": True, "future": True}


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, **ENGINE_OPTIONS)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
