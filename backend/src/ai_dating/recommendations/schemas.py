from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SurfaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: str = Field(min_length=1)


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    reason_code: str | None = None

    @model_validator(mode="after")
    def reason_only_for_pass(self) -> FeedbackIn:
        if self.action not in {"like", "pass"}:
            raise ValueError("action")
        if self.reason_code is not None and self.action != "pass":
            raise ValueError("reason_code")
        return self


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
