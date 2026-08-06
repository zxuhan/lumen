import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 50_000_000
MIN_SIDE = 32

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class ImageRejected(Exception):
    pass


@dataclass(frozen=True)
class ImageMeta:
    image_format: str
    content_type: str
    extension: str
    width: int
    height: int
    size_bytes: int
    has_alpha: bool


def probe(data: bytes) -> ImageMeta:
    """Validate an image and extract its metadata. The format is taken from actually decoding
    it, never from the file extension."""
    if not data:
        raise ImageRejected("The file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise ImageRejected(f"File exceeds the {MAX_FILE_BYTES // 1024 // 1024} MB limit")

    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format or ""
            width, height = image.size
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
            # Force a full decode to expose truncated or corrupted data
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageRejected("The file is corrupted or not a supported image") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ImageRejected("Only JPG, PNG, and WebP are supported")
    if min(width, height) < MIN_SIDE:
        raise ImageRejected(f"Image too small; the shortest side must be at least {MIN_SIDE} px")
    if width * height > MAX_PIXELS:
        raise ImageRejected("The image has too many pixels")

    return ImageMeta(
        image_format=image_format,
        content_type=ALLOWED_FORMATS[image_format],
        extension=EXTENSIONS[image_format],
        width=width,
        height=height,
        size_bytes=len(data),
        has_alpha=has_alpha,
    )
