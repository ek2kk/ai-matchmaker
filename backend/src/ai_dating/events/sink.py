from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class InsertResult(StrEnum):
    SUCCESS = "success"
    RETRYABLE = "retryable"
    REJECTED = "rejected"


class EventSink(Protocol):
    def insert(self, payloads: list[dict]) -> InsertResult: ...

    def ping(self) -> bool: ...
