from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from ai_dating.config import Settings
from ai_dating.events.clickhouse import ClickHouseSink
from ai_dating.events.fake_sink import FakeSink
from ai_dating.events.sink import InsertResult
from tests.events.contracts.test_schemas import VALID


def test_fake_sink_success_and_retry():
    sink = FakeSink()
    payload = dict(VALID["impression"])
    payload["event_id"] = str(uuid4())
    assert sink.insert([payload]) is InsertResult.SUCCESS
    sink.retry_ids.add(payload["event_id"])
    assert sink.insert([payload]) is InsertResult.RETRYABLE


def test_clickhouse_timeout_is_retryable(monkeypatch):
    settings = Settings(clickhouse_url="http://127.0.0.1:8123")
    sink = ClickHouseSink(settings)

    def boom(*_args, **_kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(sink._client, "post", boom)
    assert sink.insert([dict(VALID["impression"])]) is InsertResult.RETRYABLE


@pytest.mark.integration
def test_clickhouse_duplicate_event_id_inserts():
    settings = Settings(clickhouse_url="http://127.0.0.1:8123")
    sink = ClickHouseSink(settings)
    if not sink.ping():
        pytest.skip("ClickHouse is not running")
    sink.ensure_schema()
    payload = dict(VALID["impression"])
    payload["event_id"] = str(uuid4())
    assert sink.insert([payload]) is InsertResult.SUCCESS
    assert sink.insert([payload]) is InsertResult.SUCCESS
