"""Canvas document structure. Tools only modify this document; the renderer composites pixels
from it."""

import enum
import uuid

from pydantic import BaseModel, Field

from app.models import Asset

BASE_LAYER_ID = "base"
BACKGROUND_LAYER_ID = "background"
SUBJECT_LAYER_ID = "subject"


class LayerKind(enum.StrEnum):
    IMAGE = "image"
    TEXT = "text"
    SHAPE = "shape"


class Transform(BaseModel):
    """Position and transform relative to the canvas's top-left; scale is a factor, not pixels."""

    x: float = 0
    y: float = 0
    scale_x: float = 1
    scale_y: float = 1
    rotation: float = 0


class Layer(BaseModel):
    id: str
    kind: LayerKind
    name: str
    width: int
    height: int
    asset_id: uuid.UUID | None = None
    transform: Transform = Field(default_factory=Transform)
    opacity: float = 1
    visible: bool = True
    locked: bool = False
    source_hash: str | None = None
    text: str | None = None
    font_size: float = 24
    fill: str = "#141414"


class LayerDocument(BaseModel):
    width: int
    height: int
    layers: list[Layer] = Field(default_factory=list)


class LayerMissing(Exception):
    """The given layer doesn't exist, or the canvas has no image layer to operate on."""


def resolve_layer(document: LayerDocument, layer_id: str | None) -> Layer:
    """Get a layer by id, falling back to its name, so the agent can just say "Object 2".

    Without a layer id, takes the topmost visible image layer: the default target shared by the
    UI and the agent.
    """
    if layer_id:
        wanted = layer_id.strip()
        for layer in document.layers:
            if layer.id == wanted:
                return layer
        for layer in document.layers:
            if layer.name == wanted:
                return layer
        raise LayerMissing(f"Layer not found: {layer_id}")

    for layer in reversed(document.layers):
        if layer.kind is LayerKind.IMAGE and layer.visible:
            return layer
    raise LayerMissing("No layer available to operate on")


def document_of(asset: Asset) -> LayerDocument:
    """Build a document with the whole image as the base layer. The base is locked and is only
    replaced by subject and background layers after splitting."""
    return LayerDocument(
        width=asset.width,
        height=asset.height,
        layers=[
            Layer(
                id=BASE_LAYER_ID,
                kind=LayerKind.IMAGE,
                name="Base image",
                width=asset.width,
                height=asset.height,
                asset_id=asset.id,
                locked=True,
            )
        ],
    )
