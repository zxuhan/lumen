import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TIMESTAMPTZ, UUIDBase


class EditSession(UUIDBase):
    """One conversation in the editor's left sidebar. document is the authoritative description
    of the session's current canvas."""

    __tablename__ = "edit_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(80))
    original_asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT")
    )
    current_asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT")
    )
    # Bumped when a candidate is used or the image wall switches; used to detect stale selections
    revision: Mapped[int] = mapped_column(default=1)
    # Points at the current undo position; a new operation truncates the redo branch after it
    history_seq: Mapped[int] = mapped_column(default=1)
    document: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=func.now(), onupdate=func.now()
    )


class SessionAsset(Base):
    """The session's image wall. Unused candidates are kept too, and switching the current image
    never overwrites an existing result."""

    __tablename__ = "session_assets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    # Rows inserted in one transaction share a timestamp, so an explicit position keeps the
    # image wall order stable
    position: Mapped[int]
