from functools import lru_cache

from app.config import get_settings
from app.providers.base import EditRequest, GenerateRequest, ImageProvider, ProviderError
from app.providers.mock import MockImageProvider


@lru_cache
def get_image_provider() -> ImageProvider:
    """Pick the implementation by config. Register new platforms here; callers need no changes."""
    name = get_settings().image_provider

    if name == "mock":
        return MockImageProvider()
    if name == "openai":
        from app.providers.openai_images import OpenAIImageProvider

        return OpenAIImageProvider()

    raise ProviderError(f"Unknown IMAGE_PROVIDER: {name}")


__all__ = [
    "EditRequest",
    "GenerateRequest",
    "ImageProvider",
    "ProviderError",
    "get_image_provider",
]
