import uuid
from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers import BASE_LAYER_ID, LayerDocument, document_of
from app.models import Asset, EditHistory, EditSession, SessionAsset
from app.models.edit_history import HISTORY_LIMIT

TITLE_LIMIT = 80
DEFAULT_TITLE = "Untitled session"


class SessionNotFound(Exception):
    pass


class CannotUndo(Exception):
    pass


class CannotRedo(Exception):
    pass


def normalize_title(text: str | None) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:TITLE_LIMIT] or DEFAULT_TITLE


def snapshot(record: EditSession) -> dict:
    return {
        "document": record.document,
        "current_asset_id": str(record.current_asset_id),
        "revision": record.revision,
    }


async def _next_position(session: AsyncSession, session_id: uuid.UUID) -> int:
    last = await session.scalar(
        select(func.max(SessionAsset.position)).where(SessionAsset.session_id == session_id)
    )
    return (last or 0) + 1


async def _attach(session: AsyncSession, record: EditSession, assets: Iterable[Asset]) -> int:
    """Attach assets to the session's image wall; returns how many were newly attached."""
    known = set(
        await session.scalars(
            select(SessionAsset.asset_id).where(SessionAsset.session_id == record.id)
        )
    )
    position = await _next_position(session, record.id)
    added = 0

    for asset in assets:
        if asset.id in known:
            continue
        session.add(SessionAsset(session_id=record.id, asset_id=asset.id, position=position))
        known.add(asset.id)
        position += 1
        added += 1
    return added


async def _entry(session: AsyncSession, record: EditSession, seq: int) -> EditHistory | None:
    return await session.scalar(
        select(EditHistory).where(EditHistory.session_id == record.id, EditHistory.seq == seq)
    )


async def _max_seq(session: AsyncSession, record: EditSession) -> int:
    return (
        await session.scalar(
            select(func.max(EditHistory.seq)).where(EditHistory.session_id == record.id)
        )
        or 0
    )


async def _append_history(
    session: AsyncSession, record: EditSession, action: str, params: dict, result: dict
) -> int:
    seq = record.history_seq + 1
    session.add(
        EditHistory(
            user_id=record.user_id,
            session_id=record.id,
            seq=seq,
            action=action,
            params=params,
            result=result,
        )
    )
    await session.execute(
        delete(EditHistory).where(
            EditHistory.session_id == record.id, EditHistory.seq <= seq - HISTORY_LIMIT
        )
    )
    return seq


def _restore(record: EditSession, state: dict) -> None:
    record.document = state["document"]
    record.current_asset_id = uuid.UUID(state["current_asset_id"])
    record.revision = state["revision"]


async def apply_edit(
    session: AsyncSession,
    record: EditSession,
    action: str,
    *,
    params: dict | None = None,
    document: LayerDocument | None = None,
    current: Asset | None = None,
    extra_assets: Iterable[Asset] = (),
    result: dict | None = None,
    bump_revision: bool = True,
) -> EditSession:
    """Apply one undoable edit: truncate the redo branch first, then write the document snapshot."""
    before = snapshot(record)
    next_current = record.current_asset_id
    next_document = record.document
    changed = False

    if current is not None and current.id != record.current_asset_id:
        next_current = current.id
        if document is None:
            document = document_of(current)
        changed = True
    if document is not None:
        payload = document.model_dump(mode="json")
        if payload != record.document:
            next_document = payload
            changed = True

    # When results only go to the image wall the canvas is unchanged, but a record is still kept;
    # otherwise the user couldn't find this generation in the edit history
    attached = await _attach(session, record, extra_assets)
    if not changed and not attached:
        await session.commit()
        await session.refresh(record)
        return record

    await session.execute(
        delete(EditHistory).where(
            EditHistory.session_id == record.id, EditHistory.seq > record.history_seq
        )
    )

    record.current_asset_id = next_current
    record.document = next_document
    if bump_revision:
        record.revision += 1

    record.history_seq = await _append_history(
        session,
        record,
        action,
        {**(params or {}), "before": before},
        {
            **(result or {}),
            "document": record.document,
            "current_asset_id": str(record.current_asset_id),
            "revision": record.revision,
        },
    )
    await session.commit()
    await session.refresh(record)
    return record


async def create(
    session: AsyncSession,
    user_id: uuid.UUID,
    current: Asset,
    wall: Iterable[Asset] = (),
    title: str | None = None,
) -> EditSession:
    """Create a session. current goes onto the canvas; the other images in wall only join the
    image wall as alternatives."""
    record = EditSession(
        user_id=user_id,
        title=normalize_title(title),
        original_asset_id=current.id,
        current_asset_id=current.id,
        document=document_of(current).model_dump(mode="json"),
        history_seq=0,
    )
    session.add(record)
    await session.flush()

    await _attach(session, record, [current, *wall])
    record.history_seq = await _append_history(
        session,
        record,
        "create_session",
        {},
        {"asset_id": str(current.id), **snapshot(record)},
    )
    await session.commit()
    await session.refresh(record)
    return record


async def load(session: AsyncSession, session_id: uuid.UUID) -> EditSession:
    """Load without a user filter; only for background jobs whose ownership is already checked."""
    record = await session.get(EditSession, session_id)
    if record is None:
        raise SessionNotFound
    return record


async def get_for_user(
    session: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID
) -> EditSession:
    record = await session.scalar(
        select(EditSession).where(EditSession.id == session_id, EditSession.user_id == user_id)
    )
    if record is None:
        raise SessionNotFound
    return record


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[EditSession]:
    result = await session.scalars(
        select(EditSession)
        .where(EditSession.user_id == user_id)
        .order_by(EditSession.updated_at.desc())
        .limit(limit)
    )
    return list(result)


async def assets_of(session: AsyncSession, record: EditSession) -> list[Asset]:
    result = await session.scalars(
        select(Asset)
        .join(SessionAsset, SessionAsset.asset_id == Asset.id)
        .where(SessionAsset.session_id == record.id)
        .order_by(SessionAsset.position)
    )
    return list(result)


async def history_of(session: AsyncSession, record: EditSession) -> list[EditHistory]:
    result = await session.scalars(
        select(EditHistory)
        .where(EditHistory.session_id == record.id)
        .order_by(EditHistory.seq.desc())
    )
    return list(result)


async def undo_state(session: AsyncSession, record: EditSession) -> tuple[bool, bool]:
    return record.history_seq > 1, await _max_seq(session, record) > record.history_seq


async def previous_document(session: AsyncSession, record: EditSession) -> LayerDocument | None:
    """The canvas before the latest operation, for before/after comparison."""
    if record.history_seq <= 1:
        return None
    entry = await _entry(session, record, record.history_seq)
    before = (entry.params if entry else {}).get("before") or {}
    raw = before.get("document")
    return LayerDocument.model_validate(raw) if raw else None


async def record_result(
    session: AsyncSession,
    record: EditSession,
    assets: Iterable[Asset],
    action: str,
    params: dict,
    result: dict,
) -> EditSession:
    """Add tool output to the image wall. The revision is unchanged if the current image is kept."""
    return await apply_edit(
        session,
        record,
        action,
        params=params,
        extra_assets=assets,
        result=result,
        bump_revision=False,
    )


async def rename(session: AsyncSession, record: EditSession, title: str) -> EditSession:
    record.title = normalize_title(title)
    await session.commit()
    await session.refresh(record)
    return record


async def switch_current(session: AsyncSession, record: EditSession, asset: Asset) -> EditSession:
    """Switch the canvas's current image. The revision is bumped, which invalidates selections
    and masks from the old revision."""
    document = await _last_document_for(session, record, asset.id)
    if _cropped_base(document, asset):
        document = document_of(asset)

    if record.current_asset_id == asset.id:
        # Cropping keeps the same asset, so clicking the current image means returning to its
        # original size; if the canvas was never cropped, there's nothing to do
        if not _cropped_base(LayerDocument.model_validate(record.document), asset):
            return record
        document = document_of(asset)

    return await apply_edit(
        session,
        record,
        "switch_current",
        current=asset,
        document=document,
        extra_assets=[asset],
    )


def _cropped_base(document: LayerDocument | None, asset: Asset) -> bool:
    """Cropping only shrinks the canvas without changing the asset. Clicking back to this image
    on such a document means the user wants its native size."""
    if document is None or len(document.layers) != 1:
        return False
    layer = document.layers[0]
    if layer.id != BASE_LAYER_ID or layer.asset_id != asset.id:
        return False
    return document.width < asset.width or document.height < asset.height


def _document_for(state: dict | None, asset_id: str) -> LayerDocument | None:
    if not state or state.get("current_asset_id") != asset_id:
        return None
    raw = state.get("document")
    return LayerDocument.model_validate(raw) if raw else None


async def _last_document_for(
    session: AsyncSession, record: EditSession, asset_id: uuid.UUID
) -> LayerDocument | None:
    """The image's last document on the canvas; if none, apply_edit builds one with document_of."""
    target = str(asset_id)
    for entry in await history_of(session, record):
        found = _document_for(entry.result, target) or _document_for(
            (entry.params or {}).get("before"), target
        )
        if found is not None:
            return found
    return None


async def undo(session: AsyncSession, record: EditSession) -> EditSession:
    if record.history_seq <= 1:
        raise CannotUndo
    entry = await _entry(session, record, record.history_seq)
    before = (entry.params if entry else {}).get("before")
    if not before:
        raise CannotUndo
    _restore(record, before)
    record.history_seq -= 1
    await session.commit()
    await session.refresh(record)
    return record


async def redo(session: AsyncSession, record: EditSession) -> EditSession:
    entry = await _entry(session, record, record.history_seq + 1)
    if entry is None or "document" not in entry.result:
        raise CannotRedo
    _restore(record, entry.result)
    record.history_seq += 1
    await session.commit()
    await session.refresh(record)
    return record
