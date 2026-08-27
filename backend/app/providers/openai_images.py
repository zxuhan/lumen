import base64
import io
import math
from dataclasses import dataclass

import httpx
from openai import APIError, AsyncOpenAI
from PIL import Image

from app.config import get_settings
from app.providers.base import (
    EditRequest,
    GenerateRequest,
    ImageProvider,
    ProgressCallback,
    ProviderError,
)

_TIMEOUT = 300.0
# gpt-image-1, gpt-image-1.5, and gpt-image-1-mini only render these sizes
_FIXED_SIZES = ((1024, 1024), (1536, 1024), (1024, 1536))
# gpt-image-2 and later take any size whose edges are multiples of 16, under 3840px, at most 3:1,
# between 655,360 and 8,294,400 pixels. Above 2560x1440 is experimental, so only upscaling goes
# past that
_MIN_PIXELS = 655_360
_MAX_PIXELS = 8_294_400
_USUAL_PIXELS = 2560 * 1440
_MAX_EDGE = 3824
_MAX_RATIO = 2.9
# Larger inputs only cost upload time and input tokens
_MAX_INPUT_EDGE = 2048
# Transparent pixels are sent as white; padding is a flat grey the expansion prompt refers to
_BACKDROP = (255, 255, 255)
_BORDER = (128, 128, 128)
_EXPAND_PROMPT = (
    "Extend this picture into the flat grey border so the scene fills the whole frame "
    "naturally. Keep the existing picture, its position, and its scale unchanged."
)
_UPSCALE_PROMPT = (
    "Increase clarity and fine detail while keeping the subject, composition, and colors "
    "unchanged. Don't add new elements."
)


class OpenAIImageProvider(ImageProvider):
    """OpenAI image models (gpt-image-*). Both endpoints answer synchronously with base64 images,
    and one request returns all count candidates."""

    name = "openai"

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not configured")
        self._model = settings.image_model
        self._quality = settings.image_quality
        # The SDK retries rate limits and server errors on its own
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=_TIMEOUT,
            http_client=http_client,
        )

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        size = request_size(self._model, request.width, request.height)
        prompt = _with_negative(request.prompt, request.negative_prompt)
        if request.references:
            images = [_flatten(Image.open(io.BytesIO(raw))) for raw in request.references]
            results = await self._edit(images, prompt, size, request.count, on_progress)
        else:
            results = await self._call(
                self._client.images.generate, on_progress, prompt=prompt, n=request.count, size=size
            )
        return [_cover(data, (request.width, request.height)) for data in results]

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        source = _flatten(Image.open(io.BytesIO(request.image)))
        size = (request.width or source.width, request.height or source.height)
        prompt = _with_negative(request.prompt, request.negative_prompt)

        if size != source.size and not request.expand:
            # A new size without expanding asks for a fresh composition at that ratio
            target = request_size(self._model, *size)
            results = await self._edit([source], prompt, target, request.count, on_progress)
            return [_cover(data, size) for data in results]

        canvas = source
        if size != source.size:
            canvas, prompt = _bordered(source, size), f"{_EXPAND_PROMPT} {prompt}"
        frame = Frame.around(canvas, request_size(self._model, *canvas.size))
        results = await self._edit([frame.image], prompt, frame.size, request.count, on_progress)
        return [frame.restore(data, size) for data in results]

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        source = _flatten(Image.open(io.BytesIO(image)))
        factor = min(
            scale,
            math.sqrt(_MAX_PIXELS / (source.width * source.height)),
            _MAX_EDGE / max(source.size),
        )
        size = (round(source.width * factor), round(source.height * factor))
        frame = Frame.around(source, request_size(self._model, *size, max_pixels=_MAX_PIXELS))
        results = await self._edit([frame.image], _UPSCALE_PROMPT, frame.size, 1, on_progress)
        return frame.restore(results[0], size)

    async def _edit(
        self,
        images: list[Image.Image],
        prompt: str,
        size: tuple[int, int],
        count: int,
        on_progress: ProgressCallback | None,
    ) -> list[bytes]:
        files = [
            (f"image-{index}.png", _upload(image), "image/png")
            for index, image in enumerate(images)
        ]
        return await self._call(
            self._client.images.edit, on_progress, image=files, prompt=prompt, n=count, size=size
        )

    async def _call(
        self, method, on_progress: ProgressCallback | None, *, size: tuple[int, int], **params
    ) -> list[bytes]:
        if on_progress:
            await on_progress(20, "Generating with OpenAI")
        try:
            response = await method(
                model=self._model,
                quality=self._quality,
                output_format="png",
                size=f"{size[0]}x{size[1]}",
                **params,
            )
        except APIError as exc:
            raise ProviderError(f"OpenAI: {getattr(exc, 'message', None) or exc}") from exc
        images = [base64.b64decode(item.b64_json) for item in response.data or [] if item.b64_json]
        if not images:
            raise ProviderError("OpenAI returned no image")
        if on_progress:
            await on_progress(90, "Saving result")
        return images


def request_size(
    model: str, width: int, height: int, *, max_pixels: int = _USUAL_PIXELS
) -> tuple[int, int]:
    """The output size to ask the model for: as close to width x height as it can render."""
    if model.startswith(("gpt-image-1", "dall-e")):
        target = width / height
        return min(_FIXED_SIZES, key=lambda size: abs(size[0] / size[1] - target))

    ratio = min(max(width / height, 1 / _MAX_RATIO), _MAX_RATIO)
    pixels = min(max(width * height, _MIN_PIXELS), max_pixels)
    w, h = _snap(math.sqrt(pixels * ratio)), _snap(math.sqrt(pixels / ratio))
    while w * h > max_pixels or max(w, h) > _MAX_EDGE:
        w, h = (w - 16, h) if w >= h else (w, h - 16)
    while w * h < _MIN_PIXELS:
        w, h = (w + 16, h) if w <= h else (w, h + 16)
    return w, h


@dataclass(frozen=True)
class Frame:
    """The input padded out to the ratio of the size the model will render, so odd sizes come
    back undistorted.

    box is where the original sits inside the padded image, as fractions of its size.
    """

    image: Image.Image
    size: tuple[int, int]
    box: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

    @classmethod
    def around(cls, image: Image.Image, size: tuple[int, int]) -> "Frame":
        rw, rh = size
        if image.width * rh >= image.height * rw:
            width, height = image.width, max(image.height, round(image.width * rh / rw))
        else:
            width, height = max(image.width, round(image.height * rw / rh)), image.height
        if (width, height) == image.size:
            return cls(image, size)
        canvas = Image.new("RGB", (width, height), _BORDER)
        left, top = (width - image.width) // 2, (height - image.height) // 2
        canvas.paste(image, (left, top))
        box = (
            left / width,
            top / height,
            (left + image.width) / width,
            (top + image.height) / height,
        )
        return cls(canvas, size, box)

    def restore(self, data: bytes, size: tuple[int, int]) -> bytes:
        """Cut the original's area out of the result and bring it to the requested size."""
        result = Image.open(io.BytesIO(data)).convert("RGBA")
        left, top, right, bottom = self.box
        region = result.crop(
            (
                round(left * result.width),
                round(top * result.height),
                round(right * result.width),
                round(bottom * result.height),
            )
        )
        if region.size != size:
            region = region.resize(size, Image.Resampling.LANCZOS)
        return _png(region)


def _snap(value: float) -> int:
    return max(16, round(value / 16) * 16)


def _flatten(image: Image.Image) -> Image.Image:
    """Transparent areas become a white backdrop, so they can't be taken for a mask."""
    if image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, _BACKDROP)
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")


def _bordered(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Center the original on the larger frame; the model paints the grey border."""
    canvas = Image.new("RGB", size, _BORDER)
    canvas.paste(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return canvas


def _with_negative(prompt: str, negative: str | None) -> str:
    return f"{prompt}\nAvoid: {negative}" if negative else prompt


def _upload(image: Image.Image) -> bytes:
    if max(image.size) > _MAX_INPUT_EDGE:
        image = image.copy()
        image.thumbnail((_MAX_INPUT_EDGE, _MAX_INPUT_EDGE), Image.Resampling.LANCZOS)
    return _png(image)


def _cover(data: bytes, size: tuple[int, int]) -> bytes:
    """Scale to fill the requested size, trimming the edges if the ratio is slightly off."""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    scale = max(size[0] / image.width, size[1] / image.height)
    scaled = (max(size[0], round(image.width * scale)), max(size[1], round(image.height * scale)))
    if scaled != image.size:
        image = image.resize(scaled, Image.Resampling.LANCZOS)
    left, top = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    return _png(image.crop((left, top, left + size[0], top + size[1])))


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
