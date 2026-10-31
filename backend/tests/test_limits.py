import uuid

import httpx
import pytest

from app import limits

PROMPT = {"prompt": "A white mug on a light wood tabletop"}


def account() -> dict[str, str]:
    return {"username": f"test_{uuid.uuid4().hex[:10]}", "password": "secret123"}


@pytest.fixture
async def visitor(client: httpx.AsyncClient, demo_limits) -> httpx.AsyncClient:
    await client.post("/api/auth/register", json=account())
    return client


async def generate(client: httpx.AsyncClient, count: int) -> httpx.Response:
    return await client.post("/api/runs/generations", json={**PROMPT, "count": count})


async def test_limits_stay_off_outside_production(client: httpx.AsyncClient):
    # One more than the default sign-up limit
    for _ in range(4):
        assert (await client.post("/api/auth/register", json=account())).status_code == 201


async def test_sign_ups_are_limited_per_ip(client: httpx.AsyncClient, demo_limits, monkeypatch):
    monkeypatch.setattr(demo_limits, "limit_signups_per_ip", 1)
    assert (await client.post("/api/auth/register", json=account())).status_code == 201

    response = await client.post("/api/auth/register", json=account())
    assert response.status_code == 429
    assert "sign-ups" in response.json()["detail"]


async def test_ai_images_are_limited_per_ip(visitor: httpx.AsyncClient):
    assert (await generate(visitor, 3)).status_code == 202

    refused = await generate(visitor, 2)
    assert refused.status_code == 429
    assert "only 1 of today's 4" in refused.json()["detail"]

    assert (await generate(visitor, 1)).status_code == 202
    assert "today's 4 AI images" in (await generate(visitor, 1)).json()["detail"]


async def test_shared_budget_caps_every_visitor(
    visitor: httpx.AsyncClient, demo_limits, monkeypatch
):
    monkeypatch.setattr(demo_limits, "limit_ai_images_total", 2)

    refused = await generate(visitor, 3)
    assert refused.status_code == 429
    assert "budget" in refused.json()["detail"]
    # A refused request doesn't use up the visitor's own allowance
    assert (await generate(visitor, 2)).status_code == 202


async def test_requests_are_limited_per_minute(
    visitor: httpx.AsyncClient, demo_limits, monkeypatch
):
    monkeypatch.setattr(demo_limits, "limit_requests_per_minute", 1)
    # Keep both requests in the same one-minute window
    monkeypatch.setattr(limits, "_window", lambda: 1)

    assert (await generate(visitor, 1)).status_code == 202
    refused = await generate(visitor, 1)
    assert refused.status_code == 429
    assert "Wait a minute" in refused.json()["detail"]
