import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ENUM_LENGTH = 16

# All timestamps are stored with a time zone, to avoid ambiguity across time zones
TIMESTAMPTZ = DateTime(timezone=True)


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    """Store the enum value itself as VARCHAR and restore the enum member on read.

    PostgreSQL native enums aren't used, so adding or removing values needs no ALTER TYPE.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda cls: [member.value for member in cls],
        length=ENUM_LENGTH,
    )


class UUIDBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
