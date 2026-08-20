from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.split import already_split
from app.layers import BACKGROUND_LAYER_ID, LayerDocument, LayerKind
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.ratios import Ratio, cover_size
from app.services import assets, runs
from app.tools.base import ToolSpec
from app.tools.context import document_of, flatten_session, require_session
from app.tools.target import background_target, layer_image, write_layer_image


class ReplaceBackgroundIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    count: int = Field(default=1, ge=1, le=4)
    negative_prompt: str | None = None


class ExpandCanvasIn(BaseModel):
    ratio: Ratio
    prompt: str = Field(
        default="Extend the image edges naturally, keeping the subject intact", max_length=500
    )


class UpscaleImageIn(BaseModel):
    scale: int = Field(default=2, ge=2, le=4)


async def _store(
    session: AsyncSession, run: ToolRun, images: list[bytes], *, adopt_first: bool
) -> dict:
    created = [
        await assets.create_from_bytes(
            session, run.user_id, data, AssetKind.GENERATED, AssetSource.TOOL
        )
        for data in images
    ]
    result: dict = {"asset_ids": [str(asset.id) for asset in created]}
    if adopt_first and created:
        result["adopt_asset_id"] = str(created[0].id)
    return result


async def _progress(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    await runs.report(session, run, progress, stage)


def _layered(document: LayerDocument) -> bool:
    """Split into layers, or more than one image layer: whole-image results only go to the wall
    and are not written back to the document."""
    if already_split(document):
        return True
    return sum(1 for layer in document.layers if layer.kind is LayerKind.IMAGE) > 1


async def replace_background_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    document = document_of(record)
    target = background_target(document)
    wall_only = _layered(document)
    await runs.report(session, run, 15, "Reading background")
    if wall_only or target.id != BACKGROUND_LAYER_ID:
        source = await flatten_session(session, record)
    else:
        source = await layer_image(session, record, target)
    await runs.report(session, run, 30, "Generating new background")
    images = await get_image_provider().edit(
        EditRequest(
            prompt=(
                "Replace only the background; keep the subject, lighting, and edges unchanged. "
                f"New background: {run.params['prompt']}"
            ),
            image=source,
            count=run.params["count"],
            negative_prompt=run.params.get("negative_prompt"),
        ),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    if run.params["count"] > 1 or wall_only:
        await runs.report(
            session, run, 95, "Candidates added to the image wall; click one to use it"
        )
        return await _store(session, run, images, adopt_first=False)
    kind = AssetKind.BACKGROUND if target.id == BACKGROUND_LAYER_ID else AssetKind.GENERATED
    return await write_layer_image(session, run, record, target.id, images[0], kind)


async def expand_canvas_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    canvas = document_of(record)
    width, height = cover_size(canvas.width, canvas.height, Ratio(run.params["ratio"]))
    await runs.report(session, run, 15, "Reading canvas")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "Extending canvas")
    images = await get_image_provider().edit(
        EditRequest(
            prompt=run.params["prompt"], image=source, width=width, height=height, expand=True
        ),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    return await _store(session, run, images, adopt_first=not _layered(canvas))


async def upscale_image_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    canvas = document_of(record)
    await runs.report(session, run, 15, "Reading canvas")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "Increasing resolution")
    output = await get_image_provider().upscale(
        source,
        run.params["scale"],
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    return await _store(session, run, [output], adopt_first=not _layered(canvas))


REPLACE_BACKGROUND = ToolSpec(
    name="replace_background",
    label="Replace background",
    description=(
        "Replace the background from a text description. Before splitting, the result is written "
        "back to the canvas; after splitting, a flattened whole image only goes to the image wall. "
        "Produces 1 to 4 candidates at once; with more than one, nothing goes onto the canvas "
        "automatically and the user picks one from the image wall."
    ),
    params=ReplaceBackgroundIn,
    handler=replace_background_exec,
    queued=True,
    session_required=True,
    agent_hidden=("negative_prompt",),
)

EXPAND_CANVAS = ToolSpec(
    name="expand_canvas",
    label="Expand image",
    description=(
        "Expand the current canvas to the given ratio and fill in the new areas naturally. "
        "Keep the subject intact; don't crop it."
    ),
    params=ExpandCanvasIn,
    handler=expand_canvas_exec,
    queued=True,
    session_required=True,
)

UPSCALE_IMAGE = ToolSpec(
    name="upscale_image",
    label="Upscale",
    description=(
        "Increase the current canvas resolution. scale is 2 or 4, defaulting to 2. Don't use it "
        "to change content or composition."
    ),
    params=UpscaleImageIn,
    handler=upscale_image_exec,
    queued=True,
    session_required=True,
)
