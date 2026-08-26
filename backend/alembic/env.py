from alembic import context
from alembic.util import CommandError
from sqlalchemy import create_engine, pool

from ai_dating.accounts import models as _accounts  # noqa: F401
from ai_dating.ai import models as _ai  # noqa: F401
from ai_dating.auth import models as _auth  # noqa: F401
from ai_dating.config import load_settings
from ai_dating.database.base import Base
from ai_dating.database.engine import as_sync_url
from ai_dating.events import audit as _audit  # noqa: F401
from ai_dating.events import models as _models  # noqa: F401
from ai_dating.matching import models as _matching  # noqa: F401
from ai_dating.media import models as _media  # noqa: F401
from ai_dating.messaging import models as _messaging  # noqa: F401
from ai_dating.onboarding import models as _onboarding  # noqa: F401
from ai_dating.privacy import models as _privacy  # noqa: F401
from ai_dating.profiles import models as _profiles  # noqa: F401
from ai_dating.recommendations import models as _recommendations  # noqa: F401
from ai_dating.safety import models as _safety  # noqa: F401

target_metadata = Base.metadata


def _direct_url() -> str:
    settings = load_settings()
    if not settings.database_direct_url:
        raise CommandError(
            "DATABASE_DIRECT_URL is not set. Copy backend/.env.example to "
            "backend/.env and point it at PostgreSQL. Local API/healthz does "
            "not need a database."
        )
    return as_sync_url(settings.database_direct_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_direct_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_direct_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
