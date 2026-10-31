from app.schemas.run import GenerateIn
from app.services import generation
from app.tools.base import ToolSpec

GENERATE_IMAGE = ToolSpec(
    name="generate_image",
    label="Generate image",
    description=(
        "Generate image candidates from scratch from a text description. Use it when there is "
        "no image to edit, or the user explicitly asks for a brand-new image; don't use it to "
        "modify an existing image."
    ),
    params=GenerateIn,
    handler=generation.execute,
    agent_hidden=("seed", "reference_asset_ids"),
    paid_images=lambda params: params["count"],
)
