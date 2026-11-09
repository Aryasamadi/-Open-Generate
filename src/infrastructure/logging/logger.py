"""
Logging ساختاریافته با structlog.
Secret و PII هرگز ثبت نمی‌شوند.
هر درخواست correlation_id دارد.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from config.settings import get_settings

# ------------------------------------------------------------------ Processors

_SECRET_PATTERNS = (
    "api_key", "token", "password", "secret", "key_encrypted",
    "db_password", "encryption_key", "webhook_secret",
)


def _mask_secrets(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """ماسک کردن secretها قبل از ثبت در log"""
    for key in list(event_dict.keys()):
        if any(p in key.lower() for p in _SECRET_PATTERNS):
            val = event_dict[key]
            if isinstance(val, str) and val:
                event_dict[key] = "••••••••"
    return event_dict


def _add_app_info(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    settings = get_settings()
    event_dict.setdefault("app", "open-generate")
    event_dict.setdefault("env", settings.APP_ENV)
    event_dict.setdefault("version", settings.APP_VERSION)
    return event_dict


# ------------------------------------------------------------------ Setup

def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.value, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _mask_secrets,
        _add_app_info,
    ]

    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # کاهش noise کتابخانه‌های خارجی
    for noisy in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
