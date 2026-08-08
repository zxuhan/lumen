import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings

IDLE_TICK = 15.0


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _channel(run_id: uuid.UUID) -> str:
    return f"run:{run_id}"


async def publish(run_id: uuid.UUID, payload: dict) -> None:
    await redis_client().publish(_channel(run_id), json.dumps(payload))


@asynccontextmanager
async def subscribe(run_id: uuid.UUID) -> AsyncIterator[AsyncIterator[dict | None]]:
    """Subscribe to progress. Yields None when idle for IDLE_TICK seconds, for caller heartbeats."""
    channel = _channel(run_id)
    pubsub = redis_client().pubsub()
    await pubsub.subscribe(channel)

    async def messages() -> AsyncIterator[dict | None]:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=IDLE_TICK)
            yield json.loads(message["data"]) if message else None

    try:
        yield messages()
    finally:
        await pubsub.aclose()
