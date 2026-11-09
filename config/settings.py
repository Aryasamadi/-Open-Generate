"""
تنظیمات مرکزی برنامه — Typed & Validated via Pydantic Settings
هیچ secret نباید در Git ثبت شود؛ همه از env یا .env.secret خوانده می‌شوند.
"""
from __future__ import annotations

import secrets
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseDriver(str, Enum):
    POSTGRES = "postgresql+asyncpg"
    SQLITE = "sqlite+aiosqlite"


class BotMode(str, Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.secret"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ Core
    APP_ENV: Literal["development", "staging", "production"] = "production"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_FORMAT: Literal["json", "console"] = "json"

    # ------------------------------------------------------------------ Telegram
    TELEGRAM_BOT_TOKEN: SecretStr
    BOT_MODE: BotMode = BotMode.POLLING
    WEBHOOK_URL: AnyHttpUrl | None = None
    WEBHOOK_SECRET: SecretStr | None = None
    WEBHOOK_PORT: int = Field(default=8443, ge=1, le=65535)
    SUPER_ADMIN_IDS: list[int] = Field(default_factory=list)

    @field_validator("SUPER_ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            # pydantic-settings گاهی یک عدد تکی را decode می‌کند نه list
            # list(123) → TypeError؛ باید صریح handle شود
            return [v]
        # list یا tuple یا هر iterable دیگر
        return [int(x) for x in v]  # type: ignore[union-attr]

    # ------------------------------------------------------------------ Database
    DB_DRIVER: DatabaseDriver = DatabaseDriver.POSTGRES
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "opengenerate"
    DB_USER: str = "og_user"
    DB_PASSWORD: SecretStr = SecretStr("changeme")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # SQLite alternative (only used when DB_DRIVER = sqlite)
    SQLITE_PATH: Path = Path("/data/db/opengenerate.db")

    @property
    def database_url(self) -> str:
        if self.DB_DRIVER == DatabaseDriver.SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        pwd = self.DB_PASSWORD.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        برای Alembic که sync driver می‌خواهد.
        postgresql+asyncpg → postgresql+psycopg2 (نه فقط postgresql://)
        چون "postgresql://" بدون driver بخش به psycopg2 fallback می‌کند،
        اما صریح بودن بهتر است و از ابهام جلوگیری می‌کند.
        """
        url = self.database_url
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
            "sqlite+aiosqlite://", "sqlite://"
        )

    # ------------------------------------------------------------------ Encryption
    # کلید رمزنگاری API keyها — باید 32 بایت hex باشد
    ENCRYPTION_KEY: SecretStr

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if len(raw) < 32:
            raise ValueError("ENCRYPTION_KEY باید حداقل ۳۲ کاراکتر باشد")
        return v

    # ------------------------------------------------------------------ AI
    AI_DEFAULT_TIMEOUT: int = 60       # seconds
    AI_MAX_RETRIES: int = 3
    AI_RETRY_BACKOFF: float = 2.0
    AI_CIRCUIT_BREAKER_THRESHOLD: int = 5
    AI_CIRCUIT_BREAKER_TIMEOUT: int = 300  # seconds
    AI_CACHE_TTL: int = 3600           # seconds
    AI_CONCURRENCY_CAP: int = 10

    # ------------------------------------------------------------------ Fetcher
    FETCHER_TIMEOUT: int = 30
    FETCHER_MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10MB
    FETCHER_MAX_REDIRECTS: int = 5
    FETCHER_CONCURRENCY: int = 20
    FETCHER_USER_AGENT: str = "OpenGenerate/1.0 (+https://github.com/Aryasamadi/-Open-Generate)"

    # ------------------------------------------------------------------ Scheduler
    SCHEDULER_TICK_SECONDS: int = 60
    SCHEDULER_MAX_CONCURRENT_CHANNELS: int = 10
    SCHEDULER_CHANNEL_LOCK_TTL: int = 600  # 10 minutes
    SCHEDULER_HEARTBEAT_INTERVAL: int = 30
    SCHEDULER_STALE_THRESHOLD: int = 120   # alert if no heartbeat for 2 min

    # ------------------------------------------------------------------ Queue
    QUEUE_MAX_RETRIES: int = 5
    QUEUE_RETRY_BACKOFF_BASE: int = 60    # seconds
    QUEUE_DEAD_LETTER_AFTER: int = 5
    QUEUE_CONCURRENCY: int = 5

    # ------------------------------------------------------------------ Rate Limits
    RATE_LIMIT_USER_PER_MINUTE: int = 30
    RATE_LIMIT_GLOBAL_PER_SECOND: int = 30  # Telegram Bot API limit
    RATE_LIMIT_AI_PER_USER_PER_DAY: int = 100

    # ------------------------------------------------------------------ Storage
    DATA_DIR: Path = Path("/data")
    RECEIPTS_DIR: Path = Path("/data/receipts")
    BACKUP_STAGING_DIR: Path = Path("/data/backups")
    LOGS_DIR: Path = Path("/data/logs")
    MAX_RECEIPT_SIZE_BYTES: int = 20 * 1024 * 1024  # 20MB
    ALLOWED_RECEIPT_MIME_TYPES: list[str] = Field(
        default=["image/jpeg", "image/png", "image/webp", "application/pdf"]
    )

    # ------------------------------------------------------------------ Health
    HEALTH_PORT: int = Field(default=9090, ge=1, le=65535)

    # ------------------------------------------------------------------ Metrics
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = Field(default=9091, ge=1, le=65535)

    # ------------------------------------------------------------------ Notifications
    NOTIFICATION_MAX_RETRIES: int = 5
    NOTIFICATION_RETRY_BACKOFF: int = 60
    NOTIFICATION_DEAD_AFTER: int = 5

    # ------------------------------------------------------------------ Backup
    BACKUP_ENCRYPTION_KEY: SecretStr | None = None
    BACKUP_OFFSITE_ENABLED: bool = False
    BACKUP_OFFSITE_S3_BUCKET: str | None = None
    BACKUP_OFFSITE_S3_KEY: SecretStr | None = None
    BACKUP_OFFSITE_S3_SECRET: SecretStr | None = None
    BACKUP_OFFSITE_S3_ENDPOINT: AnyHttpUrl | None = None
    BACKUP_RETENTION_DAILY: int = 7
    BACKUP_RETENTION_WEEKLY: int = 4
    BACKUP_RETENTION_MONTHLY: int = 6

    # ------------------------------------------------------------------ Misc
    DEFAULT_LANGUAGE: Literal["fa", "en"] = "fa"
    CLAIM_TOKEN_TTL_SECONDS: int = 3600   # 1 hour
    DEEPLINK_TTL_SECONDS: int = 86400     # 24 hours

    @model_validator(mode="after")
    def validate_webhook_config(self) -> "Settings":
        if self.BOT_MODE == BotMode.WEBHOOK:
            if not self.WEBHOOK_URL:
                raise ValueError("WEBHOOK_URL الزامی است وقتی BOT_MODE=webhook")
            if not self.WEBHOOK_SECRET:
                raise ValueError("WEBHOOK_SECRET الزامی است وقتی BOT_MODE=webhook")
        return self

    @model_validator(mode="after")
    def validate_super_admins(self) -> "Settings":
        if self.APP_ENV == "production" and not self.SUPER_ADMIN_IDS:
            raise ValueError("SUPER_ADMIN_IDS باید در production تنظیم شود")
        return self


def get_settings() -> Settings:
    """Singleton settings — cached after first call"""
    return _settings_instance


# --- Initialize once at import time; will raise if env is misconfigured ---
try:
    _settings_instance = Settings()  # type: ignore[call-arg]
except Exception as exc:
    import sys
    print(f"❌ خطا در بارگذاری تنظیمات: {exc}", file=sys.stderr)
    raise
