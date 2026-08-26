from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_message_id: UUID
    body: str = Field(min_length=1, max_length=4000)


class ReadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_read_message_id: UUID
