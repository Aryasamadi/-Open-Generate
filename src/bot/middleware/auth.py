"""
Auth Middleware — هر update با user ID و resource ownership مجدداً authorize می‌شود.
callback_data مجوز محسوب نمی‌شود.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import get_settings
from src.bot.localization.fa import t
from src.infrastructure.db.session import get_session
from src.infrastructure.db.repositories.user_repo import UserRepository
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    قبل از هر handler:
    1. کاربر را پیدا یا ایجاد کن
    2. بررسی ban
    3. آخرین فعالیت را ثبت کن
    4. user را در context ذخیره کن
    """
    if not update.effective_user:
        return

    tg_user = update.effective_user
    settings = get_settings()

    async with get_session() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )

        # Super admin از config
        if tg_user.id in settings.SUPER_ADMIN_IDS:
            from src.domain.entities.user import UserRole
            user.role = UserRole.SUPER_ADMIN

        # به‌روزرسانی آخرین فعالیت
        await repo.update_last_active(user.id)
        await session.commit()

        context.user_data["db_user"] = user
        context.user_data["lang"] = user.language

    # بررسی ban
    if user.is_banned:
        lang = user.language
        if update.message:
            await update.message.reply_text(
                t("banned", lang=lang, reason=user.ban_reason or "")
            )
        elif update.callback_query:
            await update.callback_query.answer(
                t("banned", lang=lang, reason=user.ban_reason or "")[:200],
                show_alert=True,
            )
        return  # توقف پردازش
