from __future__ import annotations

from collections.abc import Callable

from ai_dating.events.sink import InsertResult


class FakeSink:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.retry_ids: set[str] = set()
        self.reject_ids: set[str] = set()
        self.calls = 0
        self.before_return: Callable[[list[dict]], None] | None = None

    def ping(self) -> bool:
        return True

    def insert(self, payloads: list[dict]) -> InsertResult:
        self.calls += 1
        ids = [str(item["event_id"]) for item in payloads]
        if any(item_id in self.reject_ids for item_id in ids):
            return InsertResult.REJECTED
        if any(item_id in self.retry_ids for item_id in ids):
            return InsertResult.RETRYABLE
        self.rows.extend(payloads)
        if self.before_return is not None:
            self.before_return(payloads)
        return InsertResult.SUCCESS
