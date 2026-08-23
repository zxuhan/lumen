from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.mask import apply_masked
from app.edits.split import EmptyCut, alpha_mask
from app.layers import Layer, LayerDocument
from app.models.asset import AssetKind
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.services import runs, selections
from app.tools.base import HIDDEN_MASK, LayerRef, MaskRef, ToolSpec
from app.tools.context import ToolError, document_of, require_session
from app.tools.target import (
    layer_image,
    layer_under_mask,
    mask_for_layer,
    resolve_target,
    selection_mask,
    write_layer_image,
)


class RegionIn(LayerRef, MaskRef):
    prompt: str = Field(default="", max_length=500)


class ReplaceRegionIn(LayerRef, MaskRef):
    prompt: str = Field(min_length=1, max_length=500)


def _target(document: LayerDocument, layer_id: str | None, mask: bytes | None) -> Layer:
    """Edit the named layer if given; otherwise the topmost layer under the selection, or the
    topmost image when there is no selection."""
    if not layer_id and mask is not None:
        return layer_under_mask(document, mask)
    return resolve_target(document, layer_id)


def _region(source: bytes, mask: bytes | None, layer: Layer, canvas: tuple[int, int]) -> bytes:
    """Without a selection, use the layer's alpha channel as the region (the whole layer); with
    one, use its intersection with the layer."""
    if mask is None:
        return alpha_mask(source)
    try:
        return mask_for_layer(mask, layer, canvas)
    except EmptyCut as exc:
        raise ToolError("The selection doesn't cover this layer") from exc


async def _edit_region(session: AsyncSession, run: ToolRun, *, scoped: str, whole: str) -> dict:
    """Edit one layer by "layer × selection": with a selection, only inside it; without one,
    the whole layer."""
    record = await require_session(session, run)
    if run.params.get("revision") not in (None, record.revision):
        raise ToolError("The selection has expired; please select again")

    document = document_of(record)
    mask = await selection_mask(session, record, run.params.get("mask_asset_id"))
    layer = _target(document, run.params.get("layer_id"), mask)

    await runs.report(session, run, 20, "Reading layer")
    source = await layer_image(session, record, layer)
    local_mask = _region(source, mask, layer, (document.width, document.height))
    await runs.report(session, run, 40, "Generating region")
    edited = (
        await get_image_provider().edit(
            EditRequest(prompt=whole if mask is None else scoped, image=source),
            on_progress=lambda progress, stage: runs.report(session, run, progress, stage),
        )
    )[0]
    await runs.report(session, run, 85, "Merging result")
    output = apply_masked(source, edited, local_mask)
    await selections.clear(record.id)
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.GENERATED)


async def erase_region_exec(session: AsyncSession, run: ToolRun) -> dict:
    asked = run.params.get("prompt")
    return await _edit_region(
        session,
        run,
        scoped=asked
        or (
            "Remove the selected object and fill the gap naturally with the surrounding "
            "background. Don't change anything outside the selection."
        ),
        whole=asked
        or "Remove the object from the image and fill the gap naturally with the background.",
    )


async def replace_region_exec(session: AsyncSession, run: ToolRun) -> dict:
    what = run.params["prompt"]
    return await _edit_region(
        session,
        run,
        scoped=(
            f"Edit only the selected area: {what}. The subject, lighting, and background outside "
            "the selection must stay exactly as they are."
        ),
        whole=(
            f"{what}. Keep the composition, perspective, and canvas size unchanged; transparent "
            "areas stay transparent."
        ),
    )


ERASE_REGION = ToolSpec(
    name="erase_region",
    label="Erase region",
    description=(
        "Erase objects and fill the gap naturally with the surrounding content. With a selection, "
        "only erases inside it; with layer_id, erases that layer's content; with both, uses "
        "their intersection."
    ),
    params=RegionIn,
    handler=erase_region_exec,
    queued=True,
    session_required=True,
    agent_hidden=HIDDEN_MASK,
)

REPLACE_REGION = ToolSpec(
    name="replace_region",
    label="Replace region",
    description=(
        "Replace image content from a text description; use it to change colors, swap materials, "
        "or turn something into another object. With a selection, only edits inside it; with "
        "layer_id, edits that whole layer; with both, uses their intersection. Just give the "
        "replacement description; no need to confirm whether the selection is accurate."
    ),
    params=ReplaceRegionIn,
    handler=replace_region_exec,
    queued=True,
    session_required=True,
    agent_hidden=HIDDEN_MASK,
)
