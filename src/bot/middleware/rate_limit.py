"""Rate limit middleware — محدودیت per-user و global"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import get_settings
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# In-memory rate limit (در production از Redis یا DB استفاده کن)
_user_counts: dict[int, list[datetime]] = defaultdict(list)


async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return

    settings = get_settings()
    user_id = update.effective_user.id
    now = datetime.utcnow()
    window = timedelta(minutes=1)
    limit = settings.RATE_LIMIT_USER_PER_MINUTE

    # پاکسازی timestamps قدیمی
    _user_counts[user_id] = [
        t for t in _user_counts[user_id] if now - t < window
    ]

    if len(_user_counts[user_id]) >= limit:
        logger.warning("rate_limit_exceeded", user_id=user_id)
        if update.callback_query:
            await update.callback_query.answer(
                "⚠️ درخواست زیادی ارسال کردید. لطفاً کمی صبر کنید.",
                show_alert=True,
            )
        return

    _user_counts[user_id].append(now)
