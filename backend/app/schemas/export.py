import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.asset import AssetKind


class ExportIn(BaseModel):
    asset_ids: list[uuid.UUID] = []


class ExportItemOut(BaseModel):
    file: str
    kind: str
    ratio: str | None = None
    width: int
    height: int
    asset_id: uuid.UUID | None = None


class ExportManifestOut(BaseModel):
    title: str
    session_id: uuid.UUID
    created_at: datetime
    items: list[ExportItemOut]


class ExportOut(BaseModel):
    url: str
    filename: str
    manifest: ExportManifestOut


# Pack marketing images and ad sizes by default; unspecified requests include only these kinds
EXPORT_KINDS = (AssetKind.MARKETING, AssetKind.EXPORT)
