from __future__ import annotations

import signal
import time

import structlog
from sqlalchemy.orm import Session

from ai_dating.config import load_settings, require_startup
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.clickhouse import ClickHouseSink
from ai_dating.events.relay import run_once
from ai_dating.logging import configure_logging

log = structlog.get_logger("ai_dating.relay")
_stop = False


def _handle_stop(_signum: int, _frame: object) -> None:
    global _stop
    _stop = True


def main() -> None:
    settings = load_settings()
    require_startup(settings)
    configure_logging(settings, service_process="relay")
    if not settings.database_url and not settings.database_direct_url:
        raise SystemExit("DATABASE_URL is required for the outbox relay")
    sink = ClickHouseSink(settings)
    sink.ensure_schema()
    engine = create_sync_engine(settings)
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    while not _stop:
        with Session(engine) as session:
            run_once(
                session,
                sink,
                limit=settings.outbox_batch_size,
                lease_seconds=settings.outbox_lease_seconds,
            )
        if _stop:
            break
        time.sleep(1)
    log.info("relay_shutdown")
