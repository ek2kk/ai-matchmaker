from typing import Annotated, Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

type AppEnv = Literal["local", "staging", "production"]

_LOCAL_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
    )

    app_env: AppEnv = "local"
    release_id: str = "dev"
    cors_origins: Annotated[tuple[str, ...], NoDecode] = _LOCAL_ORIGINS
    database_url: str | None = None
    database_direct_url: str | None = None
    clickhouse_url: str | None = None
    clickhouse_database: str = "ai_dating"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_timeout_seconds: float = 5
    outbox_batch_size: int = 50
    outbox_lease_seconds: int = 30
    bind_host: str = "127.0.0.1"
    session_ttl_seconds: int = 86400
    telegram_bot_token: str | None = None
    telegram_init_data_ttl_seconds: int = 300
    telegram_admission_open: bool = True
    telegram_admission_cohort_limit: int = 100
    dslab_api_key: str | None = None
    dslab_model: str = "gemini-2.5-flash-lite"
    extraction_prompt_version: str = "extract-facts-v4"
    extraction_timeout_seconds: float = 8
    extraction_max_attempts: int = 3
    embedding_model: str = "gte-base"
    embedding_timeout_seconds: float = 15
    job_lease_seconds: int = 30
    worker_poll_seconds: float = 1
    object_storage_backend: Literal["local", "s3"] = "local"
    object_storage_path: str = ""
    object_storage_endpoint: str | None = None
    object_storage_bucket: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_region: str = "ru-central1"
    media_signing_secret: str = "local-media-signing"
    media_auto_approve: bool = True
    message_auto_approve: bool = True
    message_rate_per_minute: int = 20
    message_rate_per_day: int = 200
    photo_max_bytes: int = 10 * 1024 * 1024
    photo_max_edge: int = 2048
    photo_uploads_per_day: int = 10
    upload_intent_ttl_seconds: int = 900
    media_url_ttl_seconds: int = 300
    rerank_enabled: bool = False
    rerank_timeout_seconds: float = 3
    rerank_max_input_tokens: int = 8000
    rerank_max_output_tokens: int = 800
    rerank_max_cost_rub: float = 0.50
    rerank_daily_cost_rub: float = 500
    rerank_prompt_version: str = "rerank-v1"
    rerank_projection_version: str = "rerank-proj-v1"
    rerank_manifest_path: str = ""
    rerank_input_price_per_1k_rub: float = 0.40
    rerank_output_price_per_1k_rub: float = 0.80

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator(
        "database_url",
        "database_direct_url",
        "clickhouse_url",
        "dslab_api_key",
        "telegram_bot_token",
        "object_storage_endpoint",
        "object_storage_bucket",
        "object_storage_access_key",
        "object_storage_secret_key",
        mode="before",
    )
    @classmethod
    def empty_url_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("database_url", "database_direct_url")
    @classmethod
    def postgres_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.lower()
        if lowered.startswith("sqlite") or not lowered.startswith("postgresql"):
            raise ValueError("must be a PostgreSQL URL; SQLite is not supported")
        return value

    @model_validator(mode="after")
    def cors_not_wildcard(self) -> Self:
        if "*" in self.cors_origins:
            raise ValueError("CORS origins must be an explicit allowlist")
        return self

    @model_validator(mode="after")
    def session_ttl_positive(self) -> Self:
        if self.session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be positive")
        if self.telegram_init_data_ttl_seconds <= 0:
            raise ValueError("telegram_init_data_ttl_seconds must be positive")
        if self.telegram_admission_cohort_limit < 1:
            raise ValueError("telegram_admission_cohort_limit must be at least 1")
        if self.extraction_timeout_seconds <= 0:
            raise ValueError("extraction_timeout_seconds must be positive")
        if self.extraction_max_attempts < 1:
            raise ValueError("extraction_max_attempts must be at least 1")
        if self.embedding_timeout_seconds <= 0:
            raise ValueError("embedding_timeout_seconds must be positive")
        if self.job_lease_seconds <= 0:
            raise ValueError("job_lease_seconds must be positive")
        if self.media_auto_approve and self.app_env != "local":
            raise ValueError("media_auto_approve is allowed only when APP_ENV=local")
        if self.message_auto_approve and self.app_env != "local":
            raise ValueError("message_auto_approve is allowed only when APP_ENV=local")
        if self.app_env != "local" and not self.dslab_api_key:
            raise ValueError("DSLAB_API_KEY is required outside local")
        if self.app_env != "local" and not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required outside local")
        if self.message_rate_per_minute < 1:
            raise ValueError("message_rate_per_minute must be at least 1")
        if self.message_rate_per_day < 1:
            raise ValueError("message_rate_per_day must be at least 1")
        if self.photo_max_bytes <= 0:
            raise ValueError("photo_max_bytes must be positive")
        if self.upload_intent_ttl_seconds <= 0:
            raise ValueError("upload_intent_ttl_seconds must be positive")
        if self.media_url_ttl_seconds <= 0:
            raise ValueError("media_url_ttl_seconds must be positive")
        if self.object_storage_backend == "s3" and (
            not self.object_storage_endpoint
            or not self.object_storage_bucket
            or not self.object_storage_access_key
            or not self.object_storage_secret_key
        ):
            raise ValueError("s3 object storage requires endpoint, bucket and keys")
        if self.rerank_timeout_seconds <= 0:
            raise ValueError("rerank_timeout_seconds must be positive")
        if self.rerank_enabled:
            from ai_dating.ai.manifest import load_manifest, manifest_allows
            from ai_dating.ai.rerank import (
                RERANK_PROJECTION_VERSION,
                RERANK_PROMPT_VERSION,
            )

            model = self.dslab_model
            if self.rerank_prompt_version != RERANK_PROMPT_VERSION:
                raise ValueError("rerank_prompt_version does not match code")
            if self.rerank_projection_version != RERANK_PROJECTION_VERSION:
                raise ValueError("rerank_projection_version does not match code")
            if not manifest_allows(
                load_manifest(self.rerank_manifest_path),
                prompt_version=self.rerank_prompt_version,
                model_version=model,
                projection_version=self.rerank_projection_version,
            ):
                raise ValueError(
                    "rerank_enabled requires a passing evaluation manifest "
                    "matching prompt, model and projection versions"
                )
        return self


def is_loopback(host: str) -> bool:
    return host in _LOOPBACK


def load_settings() -> Settings:
    return Settings()


def is_ready(settings: Settings, *, clickhouse_ok: bool | None = None) -> bool:
    if settings.app_env == "local":
        ready = bool(settings.cors_origins)
    else:
        ready = bool(
            settings.database_url
            and settings.database_direct_url
            and settings.cors_origins
            and settings.release_id
        )
    if settings.clickhouse_url and clickhouse_ok is False:
        return False
    return ready


def require_startup(settings: Settings) -> None:
    if settings.app_env == "local":
        if not is_loopback(settings.bind_host):
            raise RuntimeError("local-password auth requires a loopback bind")
        return
    if not is_ready(settings):
        raise RuntimeError("Missing required configuration for this environment")
