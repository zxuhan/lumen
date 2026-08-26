import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase, enum_column
from app.models.tool_run import RunStatus


class AgentRun(UUIDBase):
    """Planning and execution progress of one natural-language instruction turn, i.e. one Q&A in
    the editor's left sidebar.

    plan doubles as a checkpoint: after a refresh or worker restart, execution resumes from the
    persisted step statuses.
    """

    __tablename__ = "agent_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("edit_sessions.id", ondelete="CASCADE"), index=True
    )
    # Revision the plan was based on, used to tell whether the canvas changed before execution
    revision: Mapped[int]
    goal: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus))
    error: Mapped[str | None] = mapped_column(Text, default=None)
