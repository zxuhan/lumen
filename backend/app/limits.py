"""Usage limits for the public demo. Counters live in Redis, keyed by client IP, so checking a
limit never writes to the database. Daily limits reset at 00:00 UTC; the request limit is a
one-minute window."""

import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from app.config import get_settings
from app.events import redis_client

_RESETS = "It resets at 00:00 UTC."
_DAY = 24 * 3600


class LimitExceeded(Exception):
    """Turned into a 429 response by the app's exception handler."""


def _client_ip(request: Request) -> str:
    # Behind Caddy, uvicorn takes the client address from X-Forwarded-For (FORWARDED_ALLOW_IPS)
    return request.client.host if request.client else "unknown"


ClientIP = Annotated[str, Depends(_client_ip)]


async def signup(ip: str) -> None:
    limit = get_settings().limit_signups_per_ip
    if _active(limit) and await _take(_daily("signups", ip), 1, limit) is not None:
        raise LimitExceeded("Too many sign-ups from your network today. Try again tomorrow.")


async def message(ip: str) -> None:
    limit = get_settings().limit_messages_per_ip
    if _active(limit) and await _take(_daily("messages", ip), 1, limit) is not None:
        raise LimitExceeded(f"You've used today's {limit} chat messages. {_RESETS}")


async def request(ip: str) -> None:
    limit = get_settings().limit_requests_per_minute
    key = f"limit:requests:{_window()}:{ip}"
    if _active(limit) and await _take(key, 1, limit, ttl=120) is not None:
        raise LimitExceeded("Too many requests. Wait a minute and try again.")


async def ai_images(ip: str | None, count: int) -> None:
    """Reserve images from the image provider: first against the visitor's daily allowance, then
    against the budget all visitors share. ip is None for work that isn't a visitor's request."""
    settings = get_settings()
    if ip is None or count <= 0 or not settings.limits_active:
        return
    per_ip, total = settings.limit_ai_images_per_ip, settings.limit_ai_images_total
    own_key, shared_key = _daily("images", ip), _daily("images", "all")
    if per_ip > 0:
        left = await _take(own_key, count, per_ip)
        if left is not None:
            raise LimitExceeded(_images_message(count, left, per_ip))
    if total > 0 and await _take(shared_key, count, total) is not None:
        if per_ip > 0:
            await redis_client().decrby(own_key, count)
        raise LimitExceeded(f"The demo's AI budget for today is used up. {_RESETS}")


def _images_message(count: int, left: int, limit: int) -> str:
    if left == 0:
        return f"You've used today's {limit} AI images. {_RESETS}"
    return f"This needs {count} AI images, but only {left} of today's {limit} are left. {_RESETS}"


async def _take(key: str, amount: int, limit: int, ttl: int = 2 * _DAY) -> int | None:
    """Add amount to a counter unless that would pass the limit. Returns None when it fits,
    otherwise how many were still left."""
    redis = redis_client()
    async with redis.pipeline() as pipe:
        total, _ = await pipe.incrby(key, amount).expire(key, ttl, nx=True).execute()
    if total <= limit:
        return None
    await redis.decrby(key, amount)
    return max(limit - (total - amount), 0)


def _active(limit: int) -> bool:
    return limit > 0 and get_settings().limits_active


def _daily(name: str, who: str) -> str:
    return f"limit:{name}:{datetime.now(UTC):%Y-%m-%d}:{who}"


def _window() -> int:
    return int(time.time() // 60)
