from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    api_port: int = 7302

    database_url: str = "postgresql+asyncpg://lumen:lumen_dev@localhost:7311/lumen"
    redis_url: str = "redis://localhost:7312"

    s3_endpoint: str = "http://localhost:7313"
    # Address browsers use to open signed URLs; empty means the same as s3_endpoint
    s3_public_endpoint: str = ""
    s3_access_key: str = "lumen"
    s3_secret_key: str = "lumen_dev"
    s3_bucket: str = "lumen"
    # Cloudflare R2 expects "auto" (us-east-1 is accepted as an alias); MinIO uses the default
    s3_region: str = "us-east-1"
    # Signed URL lifetime, in seconds
    s3_url_ttl: int = 900

    # HS256 requires a key of at least 32 bytes
    jwt_secret: str = "dev-only-secret-please-change-in-production"
    jwt_ttl_hours: int = 24

    # image provider: mock | openai
    image_provider: str = "mock"
    openai_api_key: str = ""
    # https://eu.api.openai.com/v1 for a project created with EU data residency
    openai_base_url: str = "https://api.openai.com/v1"
    # Text model behind the chat planner; it only needs reliable tool calling
    planner_model: str = "gpt-5-mini"
    # minimal | low | medium | high for reasoning models; empty for models without reasoning
    planner_reasoning: str = "low"
    # Used for both generating and editing images
    image_model: str = "gpt-image-2"
    # low | medium | high; each step costs roughly 4x the one before
    image_quality: str = "medium"
    # auto: rembg if installed, otherwise corner-color matting; tests force corner to avoid
    # downloading models
    matting_provider: str = "auto"
    # rembg model for background removal. isnet-general-use fits a 4 GB server; bria-rmbg has
    # finer edges but needs several GB of RAM
    matting_model: str = "isnet-general-use"
    # auto: detect text layers if rapidocr is installed; none skips it; tests force none
    ocr_provider: str = "auto"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def frontend_dist(self) -> Path:
        return ROOT_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
