"""Smoke test for the OpenAI setup: plans one chat instruction, then generates one image.

Needs only OPENAI_API_KEY (no database, queue, or storage) and costs a few cents. From backend/:

    uv run python -m scripts.smoke_openai
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from app.agent import PlannerUnavailable, graph
from app.config import get_settings
from app.providers import GenerateRequest, ProviderError
from app.providers.openai_images import OpenAIImageProvider


async def main() -> int:
    settings = get_settings()
    try:
        print(f"[1] Planning with {settings.planner_model}")
        reply, plan = await graph.run(
            "Make the background a sunny beach", "1080x1080 canvas, one image layer"
        )
        print(f"    reply: {reply}")
        print(f"    plan:  {plan}")

        print(f"[2] Generating with {settings.image_model} ({settings.image_quality})")
        images = await OpenAIImageProvider().generate(
            GenerateRequest(
                prompt="A white ceramic mug on a light wood table", width=1080, height=1080
            )
        )
    except (PlannerUnavailable, ProviderError) as exc:
        print(f"    FAILED: {exc}")
        return 1

    output = Path(tempfile.gettempdir()) / "openai-smoke.png"
    output.write_bytes(images[0])
    print(f"    saved {output}")
    return 0 if plan else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
