from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.edits.mask import overlay_png, to_luma
from app.edits.split import EmptyCut
from app.layers import (
    BACKGROUND_LAYER_ID,
    Layer,
    LayerDocument,
    LayerKind,
    LayerMissing,
    resolve_layer,
)
from app.models import EditSession, ToolRun
from app.models.asset import AssetKind, AssetSource
from app.services import assets, selections
from app.services.selections import EmptySelection, StaleSelection
from app.tools.context import ToolError, document_of

STALE_SELECTION = "Canvas size changed, so the selection is no longer valid; please select again"


async def selection_mask(
    session: AsyncSession, record: EditSession, mask_asset_id: str | None
) -> bytes | None:
    """Get the current selection. None means there is no selection, and the caller decides
    whether to edit the whole layer."""
    try:
        return await selections.mask_bytes(session, record, mask_asset_id)
    except EmptySelection:
        return None
    except StaleSelection as exc:
        raise ToolError(STALE_SELECTION) from exc


async def require_selection(
    session: AsyncSession, record: EditSession, mask_asset_id: str | None, missing: str
) -> bytes:
    mask = await selection_mask(session, record, mask_asset_id)
    if mask is None:
        raise ToolError(missing)
    return mask


def resolve_target(document: LayerDocument, layer_id: str | None) -> Layer:
    """Get the target layer by id or name; raise a user-facing error if it can't be found."""
    try:
        return resolve_layer(document, layer_id)
    except LayerMissing as exc:
        raise ToolError(str(exc)) from exc


async def layer_image(session: AsyncSession, record: EditSession, layer: Layer) -> bytes:
    if layer.kind is not LayerKind.IMAGE or layer.asset_id is None:
        raise ToolError("This layer has no image to process")
    asset = await assets.get_for_user(session, record.user_id, layer.asset_id)
    if asset is None:
        raise ToolError("The layer's asset doesn't exist")
    return await storage.get(asset.storage_key)


async def write_layer_image(
    session: AsyncSession,
    run: ToolRun,
    record: EditSession,
    layer_id: str | None,
    data: bytes,
    kind: AssetKind,
) -> dict:
    """Write the result back to the given layer. With multiple layers, nothing is flattened and
    the current image isn't switched."""
    document = document_of(record).model_copy(deep=True)
    layer = resolve_layer(document, layer_id)
    if layer.kind is not LayerKind.IMAGE:
        raise ToolError("This operation only works on image layers")
    asset = await assets.create_from_bytes(session, run.user_id, data, kind, AssetSource.TOOL)
    layer.asset_id = asset.id
    result: dict = {
        "document": document.model_dump(mode="json"),
        "asset_ids": [str(asset.id)],
    }
    if _single_image(document):
        result["adopt_asset_id"] = str(asset.id)
    return result


def background_target(document: LayerDocument) -> Layer:
    for layer in document.layers:
        if layer.id == BACKGROUND_LAYER_ID and layer.kind is LayerKind.IMAGE:
            return layer
    return resolve_layer(document, None)


def layer_under_mask(document: LayerDocument, mask: bytes) -> Layer:
    """Topmost image the selection covers; falls back to the default layer if none overlaps."""
    luma = to_luma(mask, (document.width, document.height))
    box = luma.getbbox()
    if box is None:
        return resolve_layer(document, None)
    left, top, right, bottom = box
    for layer in reversed(document.layers):
        if layer.kind is not LayerKind.IMAGE or not layer.visible:
            continue
        x, y = layer.transform.x, layer.transform.y
        if right > x and left < x + layer.width and bottom > y and top < y + layer.height:
            return layer
    return resolve_layer(document, None)


def mask_for_layer(mask: bytes, layer: Layer, canvas: tuple[int, int]) -> bytes:
    luma = to_luma(mask, canvas)
    local = Image.new("L", (layer.width, layer.height), 0)
    local.paste(luma, (-int(round(layer.transform.x)), -int(round(layer.transform.y))))
    if local.getbbox() is None:
        raise EmptyCut
    return overlay_png(local)


def _single_image(document: LayerDocument) -> bool:
    return sum(1 for layer in document.layers if layer.kind is LayerKind.IMAGE) <= 1
