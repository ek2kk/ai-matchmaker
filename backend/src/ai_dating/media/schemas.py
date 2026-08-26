from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UploadIntentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_type: str
    byte_size: int = Field(gt=0)
    content_sha256: str


class PhotoPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    position: int = Field(ge=0, le=5)
