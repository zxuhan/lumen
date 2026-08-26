import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app import agent
from app.agent import plan as plan_mod
from app.layers import Layer, LayerDocument, LayerKind
from app.models import AgentRun, EditSession, ToolRun
from app.models.tool_run import RunStatus
from app.services import assets, runs, selections, tools
from app.tools import spec_of

logger = logging.getLogger(__name__)


class TurnNotFound(Exception):
    pass


class CannotConfirm(Exception):
    pass


class CannotCancel(Exception):
    pass


class CannotRetry(Exception):
    pass


async def describe(session: AsyncSession, record: EditSession) -> str:
    """Canvas summary for the planner model, limited to the facts it needs to decide."""
    document = LayerDocument.model_validate(record.document)
    names = [_layer_name(layer) for layer in document.layers]
    parts = [
        f"Canvas {document.width}×{document.height}",
        f"Layers: {len(document.layers)}, bottom to top ({', '.join(names)})",
        "layer_id takes a layer id or name; if omitted, the topmost image under the selection is "
        "used, and background replacement targets the background layer",
        f"Revision {record.revision}",
    ]

    current = await assets.get_for_user(session, record.user_id, record.current_asset_id)
    if current is not None:
        parts.append(
            f"Current image {current.image_format}"
            f"{', with alpha channel' if current.has_alpha else ''}"
        )

    selected = await selections.get(record.id, record.revision)
    if selected:
        markers = selected.get("markers") or []
        where = (
            f"Existing selection, {len(markers)} point(s)"
            if markers
            else "Existing brush selection"
        )
        parts.append(
            f"{where} (the selection limits the area, not the layer; "
            "when given together with layer_id, their intersection is used)"
        )
    else:
        parts.append("No current selection; region tools apply to the whole layer")
    return "; ".join(parts)


def _layer_name(layer: Layer) -> str:
    text = f'text "{layer.text[:8]}"' if layer.kind is LayerKind.TEXT and layer.text else None
    name = f"{layer.id}={text or layer.name}"
    return name if layer.visible else f"{name} (hidden)"


async def respond(session: AsyncSession, record: EditSession, goal: str) -> AgentRun:
    """Plan one instruction turn and persist it. Multi-step plans pause for confirmation;
    single steps start right away."""
    revision = record.revision
    reply, steps, error = "", [], None

    try:
        reply, steps = await agent.run(goal, await describe(session, record))
        steps = await _pin_selection(session, record, steps)
    except agent.PlannerUnavailable as exc:
        error = str(exc)
    except Exception:
        logger.exception("Instruction planning failed session_id=%s", record.id)
        await session.rollback()
        error = "Planning failed, please try again"

    if error:
        status = RunStatus.FAILED
    elif plan_mod.needs_confirm(steps):
        status = RunStatus.QUEUED
    elif steps:
        status = RunStatus.RUNNING
    else:
        status = RunStatus.SUCCEEDED

    turn = AgentRun(
        user_id=record.user_id,
        session_id=record.id,
        revision=revision,
        goal=goal,
        reply=reply,
        plan=steps,
        status=status,
        error=error,
    )
    session.add(turn)
    await session.commit()
    await session.refresh(turn)

    if turn.status is RunStatus.RUNNING:
        await _advance(session, turn)
    return turn


async def _pin_selection(
    session: AsyncSession, record: EditSession, steps: list[dict]
) -> list[dict]:
    """Pin this turn's selection into every step that needs a mask.

    Clearing the selection and bumping the revision both happen after the first step, so only an
    explicit id lets later steps share the same area.
    """
    stored = await selections.get(record.id, record.revision)
    mask_asset_id = (stored or {}).get("mask_asset_id")
    if not mask_asset_id:
        return steps
    for step in steps:
        params = step["params"]
        if _wants_mask(step["tool"]) and not params.get("mask_asset_id"):
            step["params"] = {**params, "mask_asset_id": mask_asset_id}
    return steps


def _wants_mask(tool: str) -> bool:
    return "mask_asset_id" in spec_of(tool).params.model_fields


async def confirm(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    turn = await _get(session, record, turn_id)
    steps = _copy(turn.plan)
    waiting = [step for step in steps if step["status"] == plan_mod.WAITING]
    if turn.status is not RunStatus.QUEUED and not waiting:
        raise CannotConfirm
    for step in waiting:
        step["status"] = plan_mod.PENDING
        step["approved"] = True
    turn.plan = steps
    turn.status = RunStatus.RUNNING
    _touch(turn)
    await session.commit()
    return await _advance(session, turn)


async def cancel(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    turn = await _get(session, record, turn_id)
    if turn.status.is_terminal:
        raise CannotCancel
    turn.plan = plan_mod.cancel_remaining(_copy(turn.plan))
    await _cancel_queued_runs(session, turn.plan)
    _touch(turn)
    turn.status = RunStatus(plan_mod.settle(turn.plan))
    await session.commit()
    await session.refresh(turn)
    return turn


async def retry(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    turn = await _get(session, record, turn_id)
    steps = _copy(turn.plan)
    failed = next((step for step in reversed(steps) if step["status"] == plan_mod.FAILED), None)
    if failed is None:
        raise CannotRetry
    failed["run_id"] = None
    failed["status"] = plan_mod.PENDING
    turn.plan = steps
    turn.status = RunStatus.RUNNING
    turn.error = None
    _touch(turn)
    await session.commit()
    return await _advance(session, turn)


async def continue_plan(session: AsyncSession, run: ToolRun) -> None:
    """Advance dependent steps once a step finishes; resumes from the persisted plan even after
    a refresh."""
    if run.session_id is None:
        return
    turn = await _turn_of_run(session, run)
    if turn is None:
        return

    steps = _copy(turn.plan)
    for step in steps:
        if step.get("run_id") == str(run.id):
            step["status"] = run.status.value
    turn.plan = steps
    _touch(turn)
    # Don't commit yet: a synchronous next step (e.g. flip) is committed together with this one,
    # so the frontend never sees "previous step finished, next step not started"
    await _advance(session, turn)


async def turns_of(session: AsyncSession, record: EditSession, limit: int = 50) -> list[AgentRun]:
    result = await session.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == record.id)
        .order_by(AgentRun.created_at)
        .limit(limit)
    )
    return list(result)


async def _advance(session: AsyncSession, turn: AgentRun) -> AgentRun:
    steps = _copy(turn.plan)
    progressed = True
    while progressed:
        progressed = False
        for step in plan_mod.ready(steps):
            if spec_of(step["tool"]).needs_approval and not step.get("approved"):
                step["status"] = plan_mod.WAITING
                continue
            run = await tools.submit(
                session, turn.user_id, step["tool"], step["params"], turn.session_id
            )
            step["run_id"] = str(run.id)
            step["status"] = run.status.value
            turn.plan = steps
            turn.status = RunStatus.RUNNING
            _touch(turn)
            await session.commit()
            progressed = run.status is RunStatus.SUCCEEDED

    turn.plan = steps
    turn.status = RunStatus(plan_mod.settle(steps))
    waiting = any(step["status"] == plan_mod.WAITING for step in steps)
    if turn.status is RunStatus.QUEUED and waiting:
        turn.reply = turn.reply or "The next step needs your confirmation before it runs."
    _touch(turn)
    await session.commit()
    await session.refresh(turn)
    return turn


async def _cancel_queued_runs(session: AsyncSession, steps: list[dict]) -> None:
    for step in steps:
        if not step.get("run_id") or step["status"] != plan_mod.QUEUED:
            continue
        run = await session.get(ToolRun, uuid.UUID(step["run_id"]))
        if run is None or run.status is not RunStatus.QUEUED:
            continue
        await runs.finish(session, run, status=RunStatus.CANCELED, error="Canceled")
        step["status"] = plan_mod.CANCELED


async def _get(session: AsyncSession, record: EditSession, turn_id: uuid.UUID) -> AgentRun:
    turn = await session.scalar(
        select(AgentRun).where(AgentRun.id == turn_id, AgentRun.session_id == record.id)
    )
    if turn is None:
        raise TurnNotFound
    return turn


async def _turn_of_run(session: AsyncSession, run: ToolRun) -> AgentRun | None:
    turns = await session.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == run.session_id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
    )
    run_id = str(run.id)
    for turn in turns:
        if any(step.get("run_id") == run_id for step in turn.plan):
            return turn
    return None


def _copy(steps: list) -> list[dict]:
    return [dict(step) for step in steps]


def _touch(turn: AgentRun) -> None:
    flag_modified(turn, "plan")
