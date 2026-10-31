import enum

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.pixels import letterbox, resize_to
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import EditRequest, get_image_provider
from app.ratios import DELIVERY_RATIOS, Ratio, size_of
from app.services import assets, runs
from app.tools.base import ToolSpec
from app.tools.context import flatten_session, require_session


class MarketingKind(enum.StrEnum):
    PRODUCT = "product"
    SCENE = "scene"
    MODEL = "model"
    POSTER = "poster"


_PROMPTS = {
    MarketingKind.PRODUCT: (
        "Place the product on a pure white background, centered, with soft top lighting and "
        "clean edges. Keep the product's original materials and colors. Output an e-commerce "
        "main image."
    ),
    MarketingKind.SCENE: (
        "Place the product in a real-life scene with side/back lighting, shallow depth of field, "
        "and a natural mood. Keep the product's original materials and colors."
    ),
    MarketingKind.MODEL: (
        "Generate a half-body shot of a model holding or wearing the product, with a clean "
        "indoor background and natural light, and the product details clearly visible."
    ),
    MarketingKind.POSTER: (
        "Make a promotional poster that features the product, leaving space for text on the "
        "right or at the bottom, with a clean, striking composition."
    ),
}


class GenerateMarketingIn(BaseModel):
    kind: MarketingKind = Field(
        description=(
            "product: main product image, scene: lifestyle scene, model: on-model shot, "
            "poster: promo poster"
        )
    )
    caption: str | None = Field(
        default=None, max_length=200, description="Poster copy or additional requirements"
    )
    count: int = Field(default=1, ge=1, le=4)
    ratio: Ratio = Field(default=Ratio.SQUARE, description="Output ratio, 1:1 by default")


class PrepareDeliverySizesIn(BaseModel):
    ratios: list[Ratio] = Field(
        default_factory=lambda: list(DELIVERY_RATIOS),
        min_length=1,
        max_length=len(Ratio),
        description="Ad ratios to output (default 1:1, 4:5, 9:16). The subject is never cropped.",
    )
    prompt: str = Field(
        default="Extend the edges naturally, keeping the subject intact; don't crop the product",
        max_length=500,
    )


async def _store(
    session: AsyncSession,
    run: ToolRun,
    images: list[bytes],
    *,
    kind: AssetKind,
    variants: list[dict],
) -> dict:
    created = [
        await assets.create_from_bytes(session, run.user_id, data, kind, AssetSource.TOOL)
        for data in images
    ]
    labeled = []
    for asset, variant in zip(created, variants, strict=True):
        labeled.append({**variant, "asset_id": str(asset.id)})
    return {"asset_ids": [str(asset.id) for asset in created], "variants": labeled}


async def _progress(session: AsyncSession, run: ToolRun, progress: int, stage: str) -> None:
    await runs.report(session, run, progress, stage)


def _prompt_of(kind: MarketingKind, caption: str | None) -> str:
    text = _PROMPTS[kind]
    extra = (caption or "").strip()
    return f"{text} Copy: {extra}" if extra else text


def _unique(ratios: list[Ratio]) -> list[Ratio]:
    seen: list[Ratio] = []
    for ratio in ratios:
        if ratio not in seen:
            seen.append(ratio)
    return seen


async def generate_marketing_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    kind = MarketingKind(run.params["kind"])
    ratio = Ratio(run.params["ratio"])
    width, height = size_of(ratio)
    await runs.report(session, run, 15, "Reading canvas")
    source = await flatten_session(session, record)
    await runs.report(session, run, 30, "Generating marketing images")
    images = await get_image_provider().edit(
        EditRequest(
            prompt=_prompt_of(kind, run.params.get("caption")),
            image=source,
            count=run.params["count"],
            width=width,
            height=height,
        ),
        on_progress=lambda progress, stage: _progress(session, run, progress, stage),
    )
    fitted = [resize_to(data, width, height) for data in images]
    await runs.report(session, run, 95, "Marketing images added to the image wall")
    return await _store(
        session,
        run,
        fitted,
        kind=AssetKind.MARKETING,
        variants=[{"kind": kind.value, "ratio": ratio.value, "width": width, "height": height}]
        * len(fitted),
    )


async def prepare_delivery_sizes_exec(session: AsyncSession, run: ToolRun) -> dict:
    record = await require_session(session, run)
    ratios = _unique([Ratio(value) for value in run.params["ratios"]])
    await runs.report(session, run, 20, "Reading canvas")
    source = await flatten_session(session, record)
    images: list[bytes] = []
    variants: list[dict] = []
    total = len(ratios)
    for index, ratio in enumerate(ratios):
        width, height = size_of(ratio)
        await runs.report(session, run, 30 + int(60 * index / total), f"Fitting {ratio.value}")
        images.append(letterbox(source, width, height))
        variants.append({"kind": "export", "ratio": ratio.value, "width": width, "height": height})
    await runs.report(session, run, 95, "Ad sizes added to the image wall")
    return await _store(session, run, images, kind=AssetKind.EXPORT, variants=variants)


GENERATE_MARKETING = ToolSpec(
    name="generate_marketing",
    label="Marketing image",
    description=(
        "Generate e-commerce marketing images from the current canvas; results only go to the "
        "image wall and the canvas is left unchanged. kind: product (main image on white), "
        "scene (lifestyle scene), model (on-model shot), poster (promo poster). caption can "
        "hold a poster headline or extra requirements."
    ),
    params=GenerateMarketingIn,
    handler=generate_marketing_exec,
    queued=True,
    session_required=True,
    paid_images=lambda params: params["count"],
)

PREPARE_DELIVERY_SIZES = ToolSpec(
    name="prepare_delivery_sizes",
    label="Ad sizes",
    description=(
        "Fit the whole current canvas into ad ratios without cropping or altering it; results "
        "only go to the image wall. Defaults to 1:1, 4:5, and 9:16 in one go. Use this when the "
        "user asks to resize or produce ad assets; don't use crop_canvas."
    ),
    params=PrepareDeliverySizesIn,
    handler=prepare_delivery_sizes_exec,
    queued=False,
    session_required=True,
)
