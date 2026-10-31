import uuid

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.agent import graph
from app.agent.llm import planner
from app.config import get_settings
from app.tasks.tools import run_tool
from tests.canvas import apply, error_of, layers, scene, select, settle
from tests.test_sessions import open_session

PROMPT = {"prompt": "A white mug on a light wood tabletop", "ratio": "1:1", "count": 2}


class FakePlanner:
    def __init__(self, message: AIMessage) -> None:
        self._message = message

    async def ainvoke(self, messages):
        self.messages = messages
        return self._message


@pytest.fixture
def fake_planner(monkeypatch):
    def install(message: AIMessage) -> FakePlanner:
        fake = FakePlanner(message)
        monkeypatch.setattr(graph, "planner", lambda: fake)
        return fake

    return install


def tool_call(name: str, args: dict) -> AIMessage:
    return tool_calls((name, args))


def tool_calls(*pairs: tuple[str, dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{index}"}
            for index, (name, args) in enumerate(pairs, start=1)
        ],
    )


@pytest.fixture
async def signed_in(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    return client


async def send(client: httpx.AsyncClient, session_id: str, text: str) -> dict:
    response = await client.post(f"/api/sessions/{session_id}/messages", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()


async def test_tool_call_is_planned_and_dispatched(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_image", PROMPT))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "A white mug on a white background, please")

    assert turn["status"] == "running"
    assert [step["tool"] for step in turn["steps"]] == ["generate_image"]
    assert turn["steps"][0]["label"] == "Generate image"
    assert turn["steps"][0]["run_id"]
    assert "didn't quite understand" not in turn["reply"]
    assert "Generate image" in turn["reply"]


async def test_marketing_tool_is_planned_and_dispatched(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_marketing", {"kind": "product"}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Make a main product image")

    assert turn["status"] == "running"
    assert [step["tool"] for step in turn["steps"]] == ["generate_marketing"]
    assert turn["steps"][0]["label"] == "Marketing image"
    assert "Marketing image" in turn["reply"]


async def test_plain_answer_dispatches_nothing(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(AIMessage(content="The current tools can't do this."))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Write me a poem")

    assert turn["steps"] == []
    assert turn["reply"] == "The current tools can't do this."


async def test_long_refusal_keeps_only_the_first_sentence(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(
        AIMessage(
            content="The selection may not contain the mouse. "
            "replace_region needs a full prompt, and adjust_image can't recolor locally either."
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Make the mouse red")

    assert turn["steps"] == []
    assert turn["reply"] == "The selection may not contain the mouse."
    assert "replace_region" not in turn["reply"]


def test_spoken_ignores_fallback_when_plan_exists():
    from app.agent.graph import _FALLBACK_REPLY, spoken

    assert "didn't quite understand" not in spoken("", [{"tool": "flip_layer"}])
    assert spoken(_FALLBACK_REPLY, [{"tool": "flip_layer"}, {"tool": "rotate_layer"}]).startswith(
        "Here's the plan"
    )


async def test_canvas_facts_are_given_to_the_planner(signed_in: httpx.AsyncClient, fake_planner):
    fake = fake_planner(AIMessage(content="OK."))
    session_id = (await open_session(signed_in))["id"]

    await send(signed_in, session_id, "Take a look at this image")

    system = fake.messages[0].content
    assert "Canvas 320×240" in system
    assert "Revision 1" in system
    assert "Base image" in system
    assert "No current selection" in system


async def test_existing_selection_is_given_to_the_planner(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake = fake_planner(tool_call("replace_region", {"prompt": "make it black"}))
    session = await open_session(signed_in)
    selected = await signed_in.post(
        f"/api/sessions/{session['id']}/selection",
        json={"revision": session["revision"], "points": [{"x": 0.5, "y": 0.5}]},
    )
    assert selected.status_code == 200

    turn = await send(signed_in, session["id"], "Make the bone black")

    assert "Existing selection" in fake.messages[0].content
    assert [step["tool"] for step in turn["steps"]] == ["replace_region"]


async def test_unregistered_tool_is_refused(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("teleport_subject", {}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Teleport the subject away")

    assert turn["steps"] == []
    assert "can't be run" in turn["reply"]


async def test_illegal_params_are_refused(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("generate_image", {"prompt": "  ", "count": 99}))
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Just give me anything")

    assert turn["steps"] == []
    assert "can't be run" in turn["reply"]


async def test_results_join_the_wall_without_switching_current(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(tool_call("generate_image", PROMPT))
    session = await open_session(signed_in)
    turn = await send(signed_in, session["id"], "Give me another one")

    await run_tool({}, uuid.UUID(turn["steps"][0]["run_id"]))

    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()
    assert len(updated["assets"]) == 3
    assert updated["current_asset_id"] == session["current_asset_id"]
    assert updated["revision"] == 1

    turns = (await signed_in.get(f"/api/sessions/{session['id']}/messages")).json()
    assert turns[-1]["status"] == "succeeded"
    assert turns[-1]["steps"][0]["status"] == "succeeded"


async def test_conversation_is_returned_in_order(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(AIMessage(content="OK."))
    session_id = (await open_session(signed_in))["id"]

    await send(signed_in, session_id, "First message")
    await send(signed_in, session_id, "Second message")

    turns = (await signed_in.get(f"/api/sessions/{session_id}/messages")).json()
    assert [turn["goal"] for turn in turns] == ["First message", "Second message"]


async def test_missing_api_key_fails_the_turn(signed_in: httpx.AsyncClient, monkeypatch):
    """When the model is unavailable the turn must fail explicitly, never fake a success."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")
    planner.cache_clear()
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Change the background")

    planner.cache_clear()
    assert turn["status"] == "failed"
    assert "OPENAI_API_KEY" in turn["error"]


async def test_blank_message_is_rejected(signed_in: httpx.AsyncClient):
    session_id = (await open_session(signed_in))["id"]

    response = await signed_in.post(f"/api/sessions/{session_id}/messages", json={"text": "   "})

    assert response.status_code == 422


async def test_messages_require_authentication(client: httpx.AsyncClient):
    path = f"/api/sessions/{uuid.uuid4()}/messages"

    assert (await client.get(path)).status_code == 401
    assert (await client.post(path, json={"text": "Hello"})).status_code == 401


def test_cyclic_dependencies_are_rejected():
    from app.agent.plan import PlanError, assemble

    with pytest.raises(PlanError, match="circular"):
        assemble(
            [
                {"id": "a", "tool": "flip_layer", "params": {}, "depends_on": ["b"]},
                {"id": "b", "tool": "flip_layer", "params": {}, "depends_on": ["a"]},
            ]
        )


def test_plan_longer_than_limit_is_rejected():
    from app.agent.plan import MAX_STEPS, PlanError, assemble

    with pytest.raises(PlanError, match="exceeds"):
        assemble([{"tool": "flip_layer", "params": {}}] * (MAX_STEPS + 1))


async def test_multi_step_plan_waits_for_confirm(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 15}),
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Flip horizontally, then rotate 15 degrees")

    assert turn["status"] == "queued"
    assert "didn't quite understand" not in turn["reply"]
    assert "Confirm to start" in turn["reply"]
    assert [step["tool"] for step in turn["steps"]] == ["flip_layer", "rotate_layer"]
    assert turn["steps"][1]["depends_on"] == ["s1"]
    assert all(step["run_id"] is None for step in turn["steps"])

    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()
    assert session["document"]["layers"][0]["transform"]["scale_x"] == 1


async def test_flip_steps_show_their_direction(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("flip_layer", {"direction": "vertical"}),
        )
    )
    session_id = (await open_session(signed_in))["id"]

    turn = await send(signed_in, session_id, "Flip horizontally, then vertically")

    assert [step["label"] for step in turn["steps"]] == ["Flip horizontal", "Flip vertical"]
    assert "Flip horizontal, Flip vertical" in turn["reply"]


async def test_confirm_runs_dependent_steps_in_order(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 15}),
        )
    )
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "Flip and rotate")

    confirmed = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{turn['id']}/confirm")
    ).json()
    layer = (
        await signed_in.get(f"/api/sessions/{session_id}")
    ).json()["document"]["layers"][0]

    assert confirmed["status"] == "succeeded"
    assert [step["status"] for step in confirmed["steps"]] == ["succeeded", "succeeded"]
    assert layer["transform"]["scale_x"] == -1
    assert layer["transform"]["rotation"] == 15


async def test_queued_step_unblocks_the_next(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("remove_background", {}),
            ("flip_layer", {"direction": "horizontal"}),
        )
    )
    session = await open_session(signed_in)
    turn = await send(signed_in, session["id"], "Remove the background, then flip horizontally")
    started = (
        await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    ).json()

    assert started["status"] == "running"
    assert started["steps"][0]["run_id"]
    assert started["steps"][1]["run_id"] is None

    await run_tool({}, uuid.UUID(started["steps"][0]["run_id"]))
    finished = (await signed_in.get(f"/api/sessions/{session['id']}/messages")).json()[-1]
    updated = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert finished["status"] == "succeeded"
    assert [step["status"] for step in finished["steps"]] == ["succeeded", "succeeded"]
    assert updated["document"]["layers"][0]["transform"]["scale_x"] == -1


async def test_two_layers_in_one_turn_share_the_same_selection(
    signed_in: httpx.AsyncClient, fake_planner
):
    """The selection is pinned into every step, so step one clearing it and bumping the revision
    doesn't affect step two."""
    fake_planner(
        tool_calls(
            ("replace_region", {"prompt": "make it red", "layer_id": "subject"}),
            ("replace_region", {"prompt": "make it blue", "layer_id": "background"}),
        )
    )
    session = await open_session(signed_in, image=scene())
    before = await apply(signed_in, session["id"], "split_layers")
    await select(signed_in, session["id"], before["revision"], points=[{"x": 0.5, "y": 0.5}])

    turn = await send(signed_in, session["id"], "Make the subject red and the background blue")
    await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    finished = await settle(signed_in, session["id"])
    after = (await signed_in.get(f"/api/sessions/{session['id']}")).json()

    assert finished["status"] == "succeeded"
    for layer_id in ("subject", "background"):
        assert layers(after)[layer_id]["asset_id"] != layers(before)[layer_id]["asset_id"]


async def test_selection_expires_when_the_plan_changes_the_canvas(
    signed_in: httpx.AsyncClient, fake_planner
):
    fake_planner(
        tool_calls(
            ("crop_canvas", {"ratio": "1:1"}),
            ("replace_region", {"prompt": "make it red"}),
        )
    )
    session = await open_session(signed_in)
    await select(signed_in, session["id"], session["revision"], points=[{"x": 0.5, "y": 0.5}])

    turn = await send(signed_in, session["id"], "Crop to a square, then make the selection red")
    await signed_in.post(f"/api/sessions/{session['id']}/messages/{turn['id']}/confirm")
    finished = await settle(signed_in, session["id"])
    failed = next(step for step in finished["steps"] if step["tool"] == "replace_region")

    assert finished["status"] == "failed"
    assert "selection is no longer valid" in await error_of(signed_in, failed["run_id"])


async def test_cancel_drops_unstarted_steps(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(
        tool_calls(
            ("flip_layer", {"direction": "horizontal"}),
            ("rotate_layer", {"angle": 10}),
        )
    )
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "Flip, then rotate")

    canceled = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{turn['id']}/cancel")
    ).json()
    session = (await signed_in.get(f"/api/sessions/{session_id}")).json()

    assert canceled["status"] == "canceled"
    assert [step["status"] for step in canceled["steps"]] == ["canceled", "canceled"]
    assert session["document"]["layers"][0]["transform"]["scale_x"] == 1


async def test_failed_step_can_be_retried(signed_in: httpx.AsyncClient, fake_planner):
    fake_planner(tool_call("replace_region", {"prompt": "make it black", "layer_id": "missing"}))
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "Make the missing layer black")

    await run_tool({}, uuid.UUID(turn["steps"][0]["run_id"]))
    failed = (await signed_in.get(f"/api/sessions/{session_id}/messages")).json()[-1]
    assert failed["status"] == "failed"

    retried = (
        await signed_in.post(f"/api/sessions/{session_id}/messages/{failed['id']}/retry")
    ).json()
    assert retried["status"] == "running"
    assert retried["steps"][0]["run_id"] != failed["steps"][0]["run_id"]


async def test_single_step_plan_counts_its_ai_images_before_running(
    signed_in: httpx.AsyncClient, fake_planner, demo_limits, monkeypatch
):
    monkeypatch.setattr(demo_limits, "limit_ai_images_per_ip", 1)
    fake_planner(tool_call("generate_image", PROMPT))
    session_id = (await open_session(signed_in))["id"]

    response = await signed_in.post(
        f"/api/sessions/{session_id}/messages", json={"text": "Two mugs, please"}
    )
    assert response.status_code == 429
    assert "This needs 2 AI images" in response.json()["detail"]


async def test_confirming_a_plan_counts_all_of_its_ai_images(
    signed_in: httpx.AsyncClient, fake_planner, demo_limits
):
    fake_planner(tool_calls(("generate_image", PROMPT), ("generate_image", {**PROMPT, "count": 3})))
    session_id = (await open_session(signed_in))["id"]
    turn = await send(signed_in, session_id, "Two rounds of mugs")
    assert turn["status"] == "queued"

    response = await signed_in.post(f"/api/sessions/{session_id}/messages/{turn['id']}/confirm")
    assert response.status_code == 429
    assert "This needs 5 AI images" in response.json()["detail"]
