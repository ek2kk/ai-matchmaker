from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_code: str
    answer_text: str


class ProfilePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    display_name: str | None = None
    bio: str | None = None
    answers: list[AnswerIn] | None = None


class FactCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_code: str
    value: str
    profile_side: str | None = None
    preference_strength: str | None = None
    visibility: str | None = None


class FactReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    value: str | None = None
    visibility: str | None = None
    expected_source_version: int | None = None
