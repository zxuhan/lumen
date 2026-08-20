import asyncio

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.pixels import adjust, remove_background
from app.models.asset import AssetKind
from app.models.tool_run import ToolRun
from app.services import runs
from app.tools.base import LayerRef, ToolSpec
from app.tools.context import document_of, require_session
from app.tools.target import layer_image, resolve_target, write_layer_image

_LAYER = "layer_id"


class RemoveBackgroundIn(LayerRef):
    pass


class AdjustIn(LayerRef):
    brightness: float = Field(default=0, ge=-1, le=1)
    contrast: float = Field(default=0, ge=-1, le=1)
    highlights: float = Field(default=0, ge=-1, le=1)
    shadows: float = Field(default=0, ge=-1, le=1)
    temperature: float = Field(default=0, ge=-1, le=1)
    tint: float = Field(default=0, ge=-1, le=1)
    saturation: float = Field(default=0, ge=-1, le=1)
    vibrance: float = Field(default=0, ge=-1, le=1)
    sharpness: float = Field(default=0, ge=-1, le=1)
    clarity: float = Field(default=0, ge=-1, le=1)
    vignette: float = Field(default=0, ge=0, le=1)


async def remove_background_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    layer = resolve_target(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "Detecting subject")
    data = await layer_image(session, record, layer)
    await runs.report(session, run, 50, "Removing background")
    output = await asyncio.to_thread(remove_background, data)
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.SUBJECT)


async def adjust_image_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    layer = resolve_target(document_of(record), run.params.get(_LAYER))
    await runs.report(session, run, 20, "Reading layer")
    data = await layer_image(session, record, layer)
    params = {key: value for key, value in run.params.items() if value and key != _LAYER}
    await runs.report(session, run, 60, "Adjusting colors")
    output = await asyncio.to_thread(lambda: adjust(data, **params))
    return await write_layer_image(session, run, record, layer.id, output, AssetKind.GENERATED)


REMOVE_BACKGROUND = ToolSpec(
    name="remove_background",
    label="Remove background",
    description=(
        "Detect the subject of the given layer and remove the background. Defaults to the topmost "
        "image. Don't use it to replace the background or generate new content."
    ),
    params=RemoveBackgroundIn,
    handler=remove_background_exec,
    queued=True,
    session_required=True,
)

ADJUST_IMAGE = ToolSpec(
    name="adjust_image",
    label="Adjust colors",
    description=(
        "Adjust the given layer's brightness, contrast, highlights, shadows, temperature, tint, "
        "saturation, vibrance, sharpness, clarity, and vignette. Defaults to the topmost image. "
        "Values range from -1 to 1, vignette from 0 to 1. Leave unmentioned parameters at 0. "
        "To change to a specific color or swap materials, use replace_region instead of this."
    ),
    params=AdjustIn,
    handler=adjust_image_exec,
    queued=True,
    session_required=True,
)
