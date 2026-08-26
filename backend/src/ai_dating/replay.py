from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.replay import replay_events
from ai_dating.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay outbox events without changing event_id"
    )
    parser.add_argument("--event-id", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--owner", default="local")
    parser.add_argument("--reason", default="manual_replay")
    args = parser.parse_args()
    settings = load_settings()
    configure_logging(settings, service_process="replay")
    engine = create_sync_engine(settings)
    ids = [UUID(value) for value in args.event_id]
    with Session(engine) as session:
        count = replay_events(
            session,
            ids,
            owner=args.owner,
            reason=args.reason,
            dry_run=args.dry_run,
        )
    print(count)
