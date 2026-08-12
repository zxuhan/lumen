import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.ratios import Ratio, size_of
from app.services import assets, runs


async def _references(session: AsyncSession, run: ToolRun) -> list[bytes]:
    result: list[bytes] = []
    for raw in run.params.get("reference_asset_ids") or []:
        asset = await assets.get_for_user(session, run.user_id, uuid.UUID(raw))
        if asset is None:
            raise ProviderError("Reference image not found")
        result.append(await storage.get(asset.storage_key))
    return result


async def execute(session: AsyncSession, run: ToolRun) -> dict:
    """Run one text-to-image generation and save the candidates as assets.

    The links returned by the model expire after 24 hours, so images must be copied into our
    own storage before they are exposed.
    """

    async def on_progress(progress: int, stage: str) -> None:
        await runs.report(session, run, progress, stage)

    width, height = size_of(Ratio(run.params["ratio"]))
    request = GenerateRequest(
        prompt=run.params["prompt"],
        width=width,
        height=height,
        count=run.params["count"],
        negative_prompt=run.params.get("negative_prompt"),
        seed=run.params.get("seed"),
        references=await _references(session, run),
    )

    images = await get_image_provider().generate(request, on_progress)

    await runs.report(session, run, 90, "Saving candidates")
    created = [
        await assets.create_from_bytes(
            session, run.user_id, data, AssetKind.GENERATED, AssetSource.GENERATE
        )
        for data in images
    ]
    return {"asset_ids": [str(asset.id) for asset in created]}
