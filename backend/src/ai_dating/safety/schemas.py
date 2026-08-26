from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID | None = None
    match_id: UUID | None = None
    reason_code: str | None = None

    @model_validator(mode="after")
    def one_subject(self) -> BlockIn:
        if (self.profile_id is None) == (self.match_id is None):
            raise ValueError("exactly one of profile_id or match_id")
        return self


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID
    message_id: UUID | None = None
    reason_code: str
    details: str | None = Field(default=None, max_length=4000)
