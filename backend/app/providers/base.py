from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

ProgressCallback = Callable[[int, str], Awaitable[None]]


class ProviderError(Exception):
    """The model service is unavailable or returned a failure."""


@dataclass(frozen=True)
class GenerateRequest:
    prompt: str
    width: int
    height: int
    count: int = 1
    negative_prompt: str | None = None
    seed: int | None = None
    # Reference images are passed as raw bytes; each adapter decides how to encode them
    references: list[bytes] = field(default_factory=list)


@dataclass(frozen=True)
class EditRequest:
    prompt: str
    image: bytes
    count: int = 1
    width: int | None = None
    height: int | None = None
    negative_prompt: str | None = None
    # With a new width/height: True keeps the original in place and fills the added border;
    # False lets the model recompose at the new size
    expand: bool = False


class ImageProvider(Protocol):
    name: str

    async def generate(
        self, request: GenerateRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        """Return the raw bytes of count images. Raises ProviderError on failure."""
        ...

    async def edit(
        self, request: EditRequest, on_progress: ProgressCallback | None = None
    ) -> list[bytes]:
        """Edit an existing image from a prompt. When width/height are set, the output has that
        size; see EditRequest.expand."""
        ...

    async def upscale(
        self, image: bytes, scale: int, on_progress: ProgressCallback | None = None
    ) -> bytes:
        """Increase resolution without changing the composition."""
        ...
