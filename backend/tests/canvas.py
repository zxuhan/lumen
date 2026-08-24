"""Canvas test helpers: invoke tools, make selections, build scene images, get layers by id."""

import uuid
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from app.tasks.tools import run_tool

_QUEUED = {"queued", "running"}


async def invoke(
    client: httpx.AsyncClient, session_id: str, tool: str, params: dict | None = None
) -> dict:
    response = await client.post(
        f"/api/sessions/{session_id}/tools", json={"tool": tool, "params": params or {}}
    )
    assert response.status_code == 202, response.text
    return response.json()


async def apply(
    client: httpx.AsyncClient, session_id: str, tool: str, params: dict | None = None
) -> dict:
    """Invoke a queued tool and run it to completion; returns the resulting session."""
    body = await invoke(client, session_id, tool, params)
    await run_tool({}, uuid.UUID(body["run"]["id"]))
    return (await client.get(f"/api/sessions/{session_id}")).json()


async def select(client: httpx.AsyncClient, session_id: str, revision: int, **payload) -> dict:
    response = await client.post(
        f"/api/sessions/{session_id}/selection", json={"revision": revision, **payload}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def settle(client: httpx.AsyncClient, session_id: str) -> dict:
    """Run the queued steps of the last turn one by one, refetching the plan after each step."""
    while True:
        turn = (await client.get(f"/api/sessions/{session_id}/messages")).json()[-1]
        pending = next(
            (step for step in turn["steps"] if step["run_id"] and step["status"] in _QUEUED),
            None,
        )
        if pending is None:
            return turn
        await run_tool({}, uuid.UUID(pending["run_id"]))


async def error_of(client: httpx.AsyncClient, run_id: str) -> str:
    return (await client.get(f"/api/runs/{run_id}")).json()["error"] or ""


def scene(size: tuple[int, int] = (320, 240)) -> bytes:
    """Light backdrop with a centered blue ellipse that cutouts and clicks reliably hit."""
    image = Image.new("RGB", size, (230, 220, 200))
    ImageDraw.Draw(image).ellipse((80, 40, 240, 200), fill=(30, 90, 180))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def layers(session: dict) -> dict[str, dict]:
    return {layer["id"]: layer for layer in session["document"]["layers"]}
