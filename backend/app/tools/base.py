from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolRun

ToolHandler = Callable[[AsyncSession, ToolRun], Awaitable[dict]]

# The server fills in the mask from the current selection; the model only names the layer
HIDDEN_MASK = ("mask_asset_id", "revision")


class UnknownTool(Exception):
    pass


class LayerRef(BaseModel):
    """Which layer to edit. Orthogonal to the selection: the selection limits the area,
    layer_id limits the layer."""

    layer_id: str | None = Field(
        default=None,
        description=(
            "ID or name of the layer to edit, e.g. background, subject, Object 2. "
            "If omitted, applies to the topmost visible image under the selection."
        ),
    )


class MaskRef(BaseModel):
    """Which area to edit. Both fields are filled in by the server and hidden from the model."""

    mask_asset_id: str | None = None
    revision: int | None = None


@dataclass(frozen=True)
class ToolSpec:
    """Complete definition of one tool, shared by the UI and the agent.

    params drives both server-side validation and the function signature given to the model,
    so the two never drift apart. handler only cares about the business result; status
    transitions are handled by the shared execution wrapper.
    """

    name: str
    label: str
    description: str
    params: type[BaseModel]
    handler: ToolHandler
    needs_approval: bool = False
    # Tools that only change the LayerDocument run inline; pixel tools still go through the queue
    queued: bool = True
    session_required: bool = False
    # Params such as asset IDs and random seeds are filled in by the server from context and
    # are hidden from the model
    agent_hidden: tuple[str, ...] = field(default_factory=tuple)
    # Refines the label by params, e.g. flip distinguishes horizontal from vertical;
    # returning None falls back to label
    detail: Callable[[dict], str | None] | None = None
    # Images a run asks the image provider for, which cost money; the demo's usage limits count
    # them. Local tools leave it at 0
    paid_images: int | Callable[[dict], int] = 0

    def label_for(self, params: dict | None = None) -> str:
        refined = self.detail(params or {}) if self.detail else None
        return refined or self.label

    def paid_images_for(self, params: dict) -> int:
        """params must already be validated, so defaults such as count are filled in."""
        return self.paid_images(params) if callable(self.paid_images) else self.paid_images
