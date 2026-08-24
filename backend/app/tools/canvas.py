from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.edits.document import (
    EditError,
    crop,
    flip,
    move,
    reorder,
    rotate,
    scale,
    set_opacity,
    set_text,
    set_visible,
)
from app.layers import LayerMissing
from app.models import ToolRun
from app.ratios import Ratio
from app.tools.base import LayerRef, ToolSpec
from app.tools.context import ToolError, document_of, require_session

_LAYER = "layer_id"
# Corner-drag scaling also moves the center: the UI computes the position and fills it in,
# so the model only provides the factor
_PLACEMENT = ("x", "y")
# In multi-step plans, two flips must be distinguishable (e.g. horizontal, then vertical)
_FLIP_LABELS = {"horizontal": "Flip horizontal", "vertical": "Flip vertical"}


class FlipIn(LayerRef):
    direction: Literal["horizontal", "vertical"]


class OpacityIn(LayerRef):
    opacity: float = Field(ge=0, le=1)


class VisibleIn(LayerRef):
    visible: bool


class TextIn(LayerRef):
    text: str = Field(max_length=500)
    font_size: float | None = Field(default=None, ge=8, le=400)
    fill: str | None = Field(default=None, pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ScaleIn(LayerRef):
    factor: float | None = Field(default=None, gt=0, le=8)
    scale_x: float | None = Field(default=None, gt=0, le=8)
    scale_y: float | None = Field(default=None, gt=0, le=8)
    x: float | None = None
    y: float | None = None

    @model_validator(mode="after")
    def _need_target(self) -> "ScaleIn":
        if self.factor is None and self.scale_x is None and self.scale_y is None:
            raise ValueError("A relative factor or an absolute scale is required")
        return self


class RotateIn(LayerRef):
    angle: float | None = Field(default=None, ge=-360, le=360)
    rotation: float | None = Field(default=None, ge=-360, le=360)

    @model_validator(mode="after")
    def _need_angle(self) -> "RotateIn":
        if self.angle is None and self.rotation is None:
            raise ValueError("A rotation angle is required")
        return self


class ReorderIn(LayerRef):
    place: Literal["top", "bottom", "up", "down"]


class MoveIn(LayerRef):
    x: float | None = None
    y: float | None = None
    dx: float | None = None
    dy: float | None = None

    @model_validator(mode="after")
    def _need_delta(self) -> "MoveIn":
        if self.x is None and self.y is None and self.dx is None and self.dy is None:
            raise ValueError("Coordinates or an offset are required")
        return self


class CropRect(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> "CropRect":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("The crop box extends beyond the canvas")
        return self


class CropIn(BaseModel):
    ratio: Ratio | None = None
    rect: CropRect | None = None

    @model_validator(mode="after")
    def _need_one(self) -> "CropIn":
        if (self.ratio is None) == (self.rect is None):
            raise ValueError("Cropping requires either a ratio or a crop box")
        return self


async def _apply(session: AsyncSession, run: ToolRun, mutate) -> dict:
    record = await require_session(session, run)
    try:
        document = mutate(document_of(record), run.params)
    except (LayerMissing, EditError) as exc:
        raise ToolError(str(exc)) from exc
    return {"document": document.model_dump(mode="json")}


async def flip_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: flip(doc, params.get(_LAYER), params["direction"]),
    )


async def set_layer_opacity(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_opacity(doc, params.get(_LAYER), params["opacity"]),
    )


async def set_layer_visible(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_visible(doc, params.get(_LAYER), params["visible"]),
    )


async def set_layer_text(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: set_text(
            doc,
            params.get(_LAYER),
            params["text"],
            font_size=params.get("font_size"),
            fill=params.get("fill"),
        ),
    )


async def scale_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: scale(
            doc,
            params.get(_LAYER),
            factor=params.get("factor"),
            scale_x=params.get("scale_x"),
            scale_y=params.get("scale_y"),
            x=params.get("x"),
            y=params.get("y"),
        ),
    )


async def rotate_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: rotate(
            doc,
            params.get(_LAYER),
            angle=params.get("angle"),
            rotation=params.get("rotation"),
        ),
    )


async def move_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: move(
            doc,
            params.get(_LAYER),
            x=params.get("x"),
            y=params.get("y"),
            dx=params.get("dx"),
            dy=params.get("dy"),
        ),
    )


async def reorder_layer(session: AsyncSession, run: ToolRun) -> dict:
    return await _apply(
        session,
        run,
        lambda doc, params: reorder(doc, params.get(_LAYER), params["place"]),
    )


async def crop_canvas(session: AsyncSession, run: ToolRun) -> dict:
    def mutate(doc, params):
        rect = params.get("rect")
        box = (rect["x"], rect["y"], rect["width"], rect["height"]) if rect else None
        ratio = Ratio(params["ratio"]) if params.get("ratio") else None
        return crop(doc, ratio=ratio, rect=box)

    return await _apply(session, run, mutate)


def _canvas(
    name: str,
    label: str,
    description: str,
    params,
    handler,
    hidden: tuple[str, ...] = (),
    detail=None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        label=label,
        description=description,
        params=params,
        handler=handler,
        queued=False,
        session_required=True,
        agent_hidden=hidden,
        detail=detail,
    )


CROP_CANVAS = _canvas(
    "crop_canvas",
    "Crop",
    "Crop the canvas to a ratio or a normalized rectangle. Only edits the layer document; "
    "no generation model is called.",
    CropIn,
    crop_canvas,
)
FLIP_LAYER = _canvas(
    "flip_layer",
    "Flip",
    "Flip the given layer horizontally or vertically. Defaults to the topmost image.",
    FlipIn,
    flip_layer,
    detail=lambda params: _FLIP_LABELS.get(params.get("direction")),
)
SET_LAYER_OPACITY = _canvas(
    "set_layer_opacity",
    "Opacity",
    "Set the layer's opacity, from 0 to 1.",
    OpacityIn,
    set_layer_opacity,
)
SET_LAYER_VISIBLE = _canvas(
    "set_layer_visible",
    "Visibility",
    "Show or hide the given layer without deleting its content.",
    VisibleIn,
    set_layer_visible,
)
SET_LAYER_TEXT = _canvas(
    "set_layer_text",
    "Edit text",
    "Change a text layer's copy, optionally with font size and color. Without a layer, edits "
    "the topmost visible text.",
    TextIn,
    set_layer_text,
)
REORDER_LAYER = _canvas(
    "reorder_layer",
    "Layer order",
    "Change the layer stacking order: top / bottom / up / down.",
    ReorderIn,
    reorder_layer,
)
SCALE_LAYER = _canvas(
    "scale_layer",
    "Scale",
    "Scale the given layer, defaulting to the topmost image. factor is a relative multiplier; "
    "scale_x / scale_y are absolute values.",
    ScaleIn,
    scale_layer,
    _PLACEMENT,
)
ROTATE_LAYER = _canvas(
    "rotate_layer",
    "Rotate",
    "Rotate a layer. angle is a relative angle and rotation an absolute one; clockwise is "
    "positive.",
    RotateIn,
    rotate_layer,
)
MOVE_LAYER = _canvas(
    "move_layer",
    "Move",
    "Move the given layer. x/y are absolute coordinates; dx/dy are relative pixel offsets. "
    "Defaults to the topmost image.",
    MoveIn,
    move_layer,
)
