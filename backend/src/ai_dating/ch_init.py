from ai_dating.config import load_settings
from ai_dating.events.clickhouse import ClickHouseSink


def main() -> None:
    settings = load_settings()
    sink = ClickHouseSink(settings)
    sink.ensure_schema()
