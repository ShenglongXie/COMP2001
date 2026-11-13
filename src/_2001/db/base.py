from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

SCHEMA = "CW2"

NAMING_CONVENTION = {
    "ix": "IX_%(table_name)s_%(column_0_name)s",
    "uq": "UQ_%(table_name)s_%(column_0_N_name)s",
    "fk": "FK_%(table_name)s_%(column_0_name)s",
    "pk": "PK_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)
