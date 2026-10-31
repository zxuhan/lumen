import logging
import uuid

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app import limits
from app.layers import LayerDocument
from app.models import Asset, ToolRun
from app.models.tool_run import RunStatus
from app.providers import ProviderError
from app.queue import enqueue
from app.services import assets, runs, sessions
from app.tools import UnknownTool, spec_of
from app.tools.context import ToolError

TASK = "run_tool"

logger = logging.getLogger(__name__)


class InvalidParams(Exception):
    pass


def validate(tool: str, params: dict) -> dict:
    """Validate params against the tool's own model; the UI and the agent follow the same rules."""
    spec = spec_of(tool)
    try:
        return spec.params.model_validate(params).model_dump(mode="json")
    except ValidationError as exc:
        raise InvalidParams(_first_error(exc)) from exc


async def submit(
    session: AsyncSession,
    user_id: uuid.UUID,
    tool: str,
    params: dict,
    session_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> ToolRun:
    """ip is set when the run comes straight from a visitor's request, so its AI images count
    against the demo limits; agent steps are counted when their plan starts."""
    spec = spec_of(tool)
    if spec.session_required and session_id is None:
        raise InvalidParams("This tool must be used within an editing session")

    checked = validate(tool, params)
    await limits.ai_images(ip, spec.paid_images_for(checked))
    run = await runs.create(session, user_id, tool, checked, session_id)
    if spec.queued:
        await enqueue(TASK, run.id)
    else:
        await execute(session, run)
        await session.refresh(run)
    return run


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """Shared execution wrapper: status transitions and failure handling live here, and each
    tool just returns its result."""
    try:
        spec = spec_of(run.tool)
        await runs.start(session, run)
        result = await spec.handler(session, run)
        await _record(session, run, result)
    except (ProviderError, UnknownTool, ToolError) as exc:
        await runs.finish(session, run, status=RunStatus.FAILED, error=str(exc))
    except Exception:
        logger.exception("Tool execution failed tool=%s run_id=%s", run.tool, run.id)
        await session.rollback()
        await runs.finish(
            session, run, status=RunStatus.FAILED, error="Execution failed, please try again"
        )
    else:
        await runs.finish(session, run, status=RunStatus.SUCCEEDED, result=result)

    from app.services import agent as agent_service

    await agent_service.continue_plan(session, run)


async def _record(session: AsyncSession, run: ToolRun, result: dict) -> None:
    if run.session_id is None:
        return

    try:
        record = await sessions.load(session, run.session_id)
    except sessions.SessionNotFound:
        return

    produced = await _assets(session, run.user_id, result.get("asset_ids", []))
    adopt_id = result.get("adopt_asset_id")
    current = next((asset for asset in produced if str(asset.id) == adopt_id), None)
    raw_document = result.get("document")
    document = LayerDocument.model_validate(raw_document) if raw_document else None

    if document is not None or current is not None:
        await sessions.apply_edit(
            session,
            record,
            run.tool,
            params=run.params,
            document=document,
            current=current,
            extra_assets=produced,
            result=result,
        )
        return

    if produced:
        await sessions.record_result(session, record, produced, run.tool, run.params, result)


async def _assets(session: AsyncSession, user_id: uuid.UUID, ids: list) -> list[Asset]:
    result: list[Asset] = []
    for raw in ids:
        asset = await assets.get_for_user(session, user_id, uuid.UUID(raw))
        if asset is not None:
            result.append(asset)
    return result


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    field = ".".join(str(part) for part in error["loc"]) or "params"
    return f"{field}: {error['msg']}"
