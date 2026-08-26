from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog

from ai_dating.config import Settings
from ai_dating.events.sink import InsertResult

log = structlog.get_logger("ai_dating.clickhouse")
DDL_PATH = Path(__file__).resolve().parents[3] / "clickhouse" / "raw_events.sql"


def _occurred_at(value: object) -> str:
    text = str(value).replace("T", " ").replace("Z", "")
    if "." in text:
        head, frac = text.split(".", 1)
        return f"{head}.{frac[:3]}"
    return text


def _row(payload: dict) -> dict:
    occurred = _occurred_at(payload["occurred_at"])
    return {
        "event_id": payload["event_id"],
        "event_name": payload["event_name"],
        "schema_version": payload["schema_version"],
        "occurred_at": occurred,
        "producer": payload["producer"],
        "owner": payload["owner"],
        "actor_account_id": payload["actor_account_id"],
        "subject_account_id": payload["subject_account_id"],
        "recommendation_batch_id": payload["recommendation_batch_id"],
        "recommendation_item_id": payload["recommendation_item_id"],
        "match_id": payload["match_id"],
        "conversation_id": payload["conversation_id"],
        "request_id": payload["request_id"],
        "experiment_assignments": json.dumps(payload["experiment_assignments"]),
        "privacy_classification": payload["privacy_classification"],
        "properties": json.dumps(payload["properties"]),
    }


class ClickHouseSink:
    def __init__(self, settings: Settings) -> None:
        if not settings.clickhouse_url:
            raise RuntimeError("CLICKHOUSE_URL is not configured")
        self._url = settings.clickhouse_url.rstrip("/")
        self._database = settings.clickhouse_database
        self._client = httpx.Client(
            timeout=settings.clickhouse_timeout_seconds,
            auth=(settings.clickhouse_user, settings.clickhouse_password),
        )

    def ping(self) -> bool:
        try:
            response = self._client.get(self._url, params={"query": "SELECT 1"})
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def close(self) -> None:
        self._client.close()

    def ensure_schema(self) -> None:
        statements = [
            part.strip()
            for part in DDL_PATH.read_text().split(";")
            if part.strip() and not part.strip().startswith("--")
        ]
        for statement in statements:
            response = self._client.post(self._url, content=f"{statement};".encode())
            if response.status_code >= 400:
                raise RuntimeError("clickhouse schema init failed")

    def insert(self, payloads: list[dict]) -> InsertResult:
        if not payloads:
            return InsertResult.SUCCESS
        body = "\n".join(json.dumps(_row(item)) for item in payloads)
        query = f"INSERT INTO {self._database}.raw_events FORMAT JSONEachRow"
        try:
            response = self._client.post(
                self._url,
                params={"query": query},
                content=body.encode(),
            )
        except httpx.TimeoutException:
            log.info("clickhouse_insert", error_code="sink_timeout")
            return InsertResult.RETRYABLE
        except httpx.HTTPError:
            log.info("clickhouse_insert", error_code="sink_unavailable")
            return InsertResult.RETRYABLE
        if response.status_code >= 500:
            log.info("clickhouse_insert", error_code="sink_unavailable")
            return InsertResult.RETRYABLE
        if response.status_code >= 400:
            log.info("clickhouse_insert", error_code="sink_rejected")
            return InsertResult.REJECTED
        return InsertResult.SUCCESS
