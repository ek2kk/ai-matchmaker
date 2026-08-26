from sqlalchemy import Engine, NullPool, create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_dating.config import Settings


def as_sync_url(url: str) -> str:
    parsed = make_url(url).set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def as_async_url(url: str) -> str:
    parsed = make_url(url).set(drivername="postgresql+psycopg_async")
    return parsed.render_as_string(hide_password=False)


def create_runtime_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_async_engine(as_async_url(settings.database_url), pool_pre_ping=True)


def create_migration_engine(settings: Settings) -> Engine:
    if not settings.database_direct_url:
        raise RuntimeError("DATABASE_DIRECT_URL is not configured")
    return create_engine(as_sync_url(settings.database_direct_url), poolclass=NullPool)


def create_sync_engine(settings: Settings) -> Engine:
    url = settings.database_url or settings.database_direct_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(as_sync_url(url), pool_pre_ping=True)


def session_maker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine)
