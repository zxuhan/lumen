import base64
import json
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.agent.llm import PlannerUnavailable, _schema_of, planner
from app.config import get_settings
from app.providers import EditRequest, GenerateRequest, ProviderError
from app.providers.openai_images import Frame, OpenAIImageProvider, request_size
from app.ratios import SIZES
from app.tools import SPECS


def _png(size: tuple[int, int], color=(200, 30, 30)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _size_of(data: bytes) -> tuple[int, int]:
    return Image.open(BytesIO(data)).size


def _uploaded_image(request: httpx.Request) -> Image.Image:
    """The first PNG in a multipart edit upload."""
    body = request.content
    start = body.index(b"\x89PNG")
    end = body.index(b"IEND", start) + 8
    return Image.open(BytesIO(body[start:end]))


def _form_field(request: httpx.Request, name: str) -> str:
    body = request.content.decode("latin-1")
    marker = f'name="{name}"\r\n\r\n'
    start = body.index(marker) + len(marker)
    return body[start : body.index("\r\n", start)]


@pytest.fixture
def configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "image_model", "gpt-image-2")
    monkeypatch.setattr(settings, "image_quality", "medium")


@pytest.fixture
def openai_api(configured):
    """Fake images API that answers with n images of the requested size."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/images/generations"):
            params = json.loads(request.content)
        else:
            params = {"size": _form_field(request, "size"), "n": _form_field(request, "n")}
        width, height = (int(edge) for edge in params["size"].split("x"))
        image = base64.b64encode(_png((width, height))).decode()
        return httpx.Response(
            200, json={"created": 0, "data": [{"b64_json": image}] * int(params["n"])}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAIImageProvider(http_client=client), calls


@pytest.mark.parametrize("ratio", list(SIZES))
def test_flexible_sizes_follow_the_requested_ratio(ratio):
    width, height = SIZES[ratio]

    w, h = request_size("gpt-image-2", width, height)

    assert w % 16 == 0 and h % 16 == 0
    assert 655_360 <= w * h <= 2560 * 1440
    assert abs(w / h - width / height) < 0.02


def test_fixed_size_models_get_their_closest_size():
    assert request_size("gpt-image-1-mini", 1080, 1350) == (1024, 1536)
    assert request_size("gpt-image-1.5", 1920, 1080) == (1536, 1024)
    assert request_size("gpt-image-1", 1080, 1080) == (1024, 1024)


def test_upscale_sizes_stay_within_the_model_limits():
    w, h = request_size("gpt-image-2", 4320, 4320, max_pixels=8_294_400)

    assert w * h <= 8_294_400 and max(w, h) < 3840


def test_frame_pads_odd_sizes_and_cuts_them_back_out():
    original = Image.new("RGB", (1120, 1000), (200, 30, 30))
    original.paste((30, 30, 200), (560, 0, 1120, 1000))

    frame = Frame.around(original, (1024, 1024))
    answer = BytesIO()
    frame.image.resize((1024, 1024)).save(answer, format="PNG")
    restored = Image.open(BytesIO(frame.restore(answer.getvalue(), original.size))).convert("RGB")

    assert frame.image.size == (1120, 1120)
    assert restored.size == (1120, 1000)
    red, _, blue = restored.getpixel((100, 10))
    assert red > 150 and blue < 100
    assert restored.getpixel((1100, 500))[2] > 150


async def test_generate_asks_for_every_candidate_in_one_request(openai_api):
    provider, calls = openai_api

    images = await provider.generate(
        GenerateRequest(prompt="A mug", width=1080, height=1350, count=3)
    )

    assert len(calls) == 1
    params = json.loads(calls[0].content)
    assert params["model"] == "gpt-image-2"
    assert params["n"] == 3
    assert params["quality"] == "medium"
    assert calls[0].headers["authorization"] == "Bearer test-key"
    assert [_size_of(data) for data in images] == [(1080, 1350)] * 3


async def test_expand_sends_the_original_inside_a_grey_border(openai_api):
    provider, calls = openai_api

    images = await provider.edit(
        EditRequest(prompt="Extend", image=_png((1080, 1080)), width=1080, height=1920, expand=True)
    )

    sent = _uploaded_image(calls[0]).convert("RGB")
    assert calls[0].url.path.endswith("/images/edits")
    assert _size_of(images[0]) == (1080, 1920)
    assert sent.getpixel((sent.width // 2, 5)) == (128, 128, 128)
    assert sent.getpixel((sent.width // 2, sent.height // 2)) == (200, 30, 30)


async def test_api_errors_are_reported(configured):
    def handler(request: httpx.Request) -> httpx.Response:
        error = {
            "message": "Your request was rejected by the safety system.",
            "code": "moderation_blocked",
        }
        return httpx.Response(400, json={"error": error})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAIImageProvider(http_client=client)

    with pytest.raises(ProviderError, match="safety system"):
        await provider.edit(EditRequest(prompt="Brighter", image=_png((64, 64))))


def test_missing_key_is_reported(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "")

    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIImageProvider()

    planner.cache_clear()
    with pytest.raises(PlannerUnavailable, match="OPENAI_API_KEY"):
        planner()
    planner.cache_clear()


def test_planner_tools_hide_internal_parameters():
    generate = next(_schema_of(spec) for spec in SPECS if spec.name == "generate_image")

    properties = generate["function"]["parameters"]["properties"]
    assert "seed" not in properties and "reference_asset_ids" not in properties
    assert properties["count"]["maximum"] == 6
