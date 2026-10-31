from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_run import ToolRun
from app.schemas.batch import BatchIn
from app.services import batch
from app.tools.base import ToolSpec

BATCH_NAME = "batch_process"
# Batch operations that call the image provider, once per image
_PAID_OPERATIONS = {"replace_background", "upscale_image", "expand_canvas"}


async def batch_process_exec(session: AsyncSession, run: ToolRun) -> dict:
    return await batch.execute(session, run)


def _paid_images(params: dict) -> int:
    paid = sum(1 for operation in params["operations"] if operation["tool"] in _PAID_OPERATIONS)
    return paid * len(params["asset_ids"])


BATCH_PROCESS = ToolSpec(
    name=BATCH_NAME,
    label="Batch process",
    description=(
        "Run the same pixel pipeline on multiple images: remove background, replace background, "
        "adjust colors, upscale, expand, ad sizes. Don't use it for single-image retouching, "
        "marketing images, region edits, or layer splitting."
    ),
    params=BatchIn,
    handler=batch_process_exec,
    queued=True,
    session_required=False,
    paid_images=_paid_images,
)
