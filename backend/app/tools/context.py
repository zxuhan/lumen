import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.render import WHITE, flatten
from app.layers import LayerDocument
from app.models import EditSession, ToolRun
from app.services import assets, sessions


class ToolError(Exception):
    """A tool failure that can be shown to the user as-is."""


async def require_session(session: AsyncSession, run: ToolRun) -> EditSession:
    if run.session_id is None:
        raise ToolError("This tool must be used within an editing session")
    try:
        return await sessions.load(session, run.session_id)
    except sessions.SessionNotFound as exc:
        raise ToolError("Session not found") from exc


def document_of(record: EditSession) -> LayerDocument:
    return LayerDocument.model_validate(record.document)


async def flatten_session(
    session: AsyncSession,
    record: EditSession,
    *,
    background: tuple[int, int, int, int] = WHITE,
    include_text: bool = True,
) -> bytes:
    """Flatten the current document to a PNG to hand off to pixel tools."""
    document = document_of(record)
    images: dict[uuid.UUID, bytes] = {}
    for layer in document.layers:
        if layer.asset_id is None:
            continue
        asset = await assets.get_for_user(session, record.user_id, layer.asset_id)
        if asset is None:
            continue
        images[asset.id] = await storage.get(asset.storage_key)
    return flatten(document, images, background=background, include_text=include_text)
