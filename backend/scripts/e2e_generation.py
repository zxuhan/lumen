"""End-to-end check of the text-to-image flow: sign in, start a generation, follow progress,
read the candidates, and verify signed URLs."""

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:7302"
USER = {"username": "s3tester", "password": "s3pass123"}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0, trust_env=False) as client:
        response = await client.post("/api/auth/register", json=USER)
        if response.status_code == httpx.codes.CONFLICT:
            response = await client.post("/api/auth/login", json=USER)
        assert response.status_code in (200, 201), response.text
        print(f"[1] Signed in as {response.json()['username']}")

        response = await client.post(
            "/api/generations",
            json={"prompt": "An orange cat on grass in soft sunlight", "ratio": "4:5", "count": 4},
        )
        assert response.status_code == httpx.codes.ACCEPTED, response.text
        run_id = response.json()["id"]
        print(f"[2] Task queued status={response.json()['status']} id={run_id}")

        frames = []
        async with client.stream("GET", f"/events/runs/{run_id}", timeout=90.0) as stream:
            assert stream.status_code == httpx.codes.OK, stream.status_code
            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                frames.append(payload)
                print(
                    f"    SSE {payload['status']:<10} {payload['progress']:>3}% {payload['stage']}"
                )
                if payload["status"] in ("succeeded", "failed", "canceled"):
                    break

        assert frames, "No SSE frames received"
        assert frames[-1]["status"] == "succeeded", frames[-1]
        print(f"[3] SSE received {len(frames)} frames, final status succeeded")

        response = await client.get(f"/api/runs/{run_id}")
        assert response.status_code == httpx.codes.OK, response.text
        candidates = response.json()["candidates"]
        assert len(candidates) == 4, f"Expected 4 candidates, got {len(candidates)}"
        sizes = {(c["width"], c["height"]) for c in candidates}
        assert sizes == {(1080, 1350)}, sizes
        print(f"[4] 4 candidates, size {sizes.pop()} matches 4:5")

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as anon:
            image = await anon.get(candidates[0]["url"])
        assert image.status_code == httpx.codes.OK, image.status_code
        assert image.content[:8] == b"\x89PNG\r\n\x1a\n", "Signed URL did not return a PNG"
        print(f"[5] Signed URL is downloadable, PNG {len(image.content)} bytes")

        response = await client.post(
            "/api/generations", json={"prompt": "   ", "ratio": "1:1", "count": 4}
        )
        assert response.status_code == httpx.codes.UNPROCESSABLE_ENTITY, response.status_code
        print("[6] Empty prompt rejected")

        async with httpx.AsyncClient(base_url=BASE, timeout=10.0, trust_env=False) as anon:
            response = await anon.get(f"/api/runs/{run_id}")
        assert response.status_code == httpx.codes.UNAUTHORIZED, response.status_code
        print("[7] Unauthenticated task access rejected")

    print("\nAll checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
