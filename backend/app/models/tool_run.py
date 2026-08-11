import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TIMESTAMPTZ, UUIDBase, enum_column


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}


class ToolRun(UUIDBase):
    """Execution record of a single tool call. The run id doubles as the queue job ID, so
    duplicate deliveries never run twice."""

    __tablename__ = "tool_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Generations started from the Create page have no session yet, so their images join no
    # image wall
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), default=None
    )
    tool: Mapped[str] = mapped_column(String(48))
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus), default=RunStatus.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    retries: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, default=None)
