"""Wizard مدیریت منابع RSS/API"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

SOURCE_MENU, SOURCE_ENTER_URL, SOURCE_ENTER_TITLE, SOURCE_ENTER_API = range(4)


async def source_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    channel_id = context.user_data.get("selected_channel_id")

    async with _get_session() as session:
        from src.infrastructure.db.repositories.source_repo import SourceRepository
        sources = await SourceRepository(session).list_active_by_channel(channel_id or 0)

    keyboard = []
    for src in sources:
        icon = "✅" if src.is_active else "⏸️"
        keyboard.append([
            InlineKeyboardButton(f"{icon} {src.title}", callback_data=f"src_select:{src.id}")
        ])
    keyboard.append([InlineKeyboardButton(t("source_add", lang=lang), callback_data="src_add")])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel_id}")])

    query = update.callback_query
    if query:
        await query.answer()
        # channel_id از callback data
        if ":" in query.data:
            channel_id = int(query.data.split(":")[1])
            context.user_data["selected_channel_id"] = channel_id
        await query.edit_message_text(
            t("source_menu", lang=lang) + (f"\n\n{t('no_sources', lang=lang)}" if not sources else ""),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    return SOURCE_MENU


async def source_enter_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("source_enter_url", lang=lang),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang=lang), callback_data="src_menu")
        ]]),
    )
    return SOURCE_ENTER_URL


async def source_receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    url = (update.message.text or "").strip()

    # اعتبارسنجی URL
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await update.message.reply_text(t("source_invalid_url", lang=lang))
        return SOURCE_ENTER_URL

    # بررسی SSRF
    try:
        from src.infrastructure.fetcher.safe_fetcher import _validate_url, _validate_resolved_ip
        _validate_url(url)
        _validate_resolved_ip(parsed.hostname or "")
    except Exception:
        await update.message.reply_text(t("source_ssrf_blocked", lang=lang))
        return SOURCE_ENTER_URL

    context.user_data["pending_source_url"] = url
    await update.message.reply_text(t("source_enter_title", lang=lang))
    return SOURCE_ENTER_TITLE


async def source_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    channel_id = context.user_data.get("selected_channel_id")
    title = (update.message.text or "").strip()
    url = context.user_data.pop("pending_source_url", "")

    async with _get_session() as session:
        from src.infrastructure.db.repositories.source_repo import SourceRepository
        from src.domain.entities.source import Source, SourceType
        repo = SourceRepository(session)
        count = await repo.count_by_channel(channel_id or 0)

    max_sources = 10  # از پلن
    if count >= max_sources:
        await update.message.reply_text(t("source_limit_reached", lang=lang, max=max_sources))
        return SOURCE_MENU

    async with _get_session() as session:
        from src.infrastructure.db.repositories.source_repo import SourceRepository
        from src.domain.entities.source import Source, SourceType
        source = Source(
            channel_id=channel_id or 0,
            owner_id=user.telegram_id,
            title=title,
            url=url,
            feed_url=url,
            source_type=SourceType.RSS,
        )
        await SourceRepository(session).create(source)

    await update.message.reply_text(t("source_added", lang=lang, title=title))
    return SOURCE_MENU


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(source_menu, pattern=r"^src_menu(:\d+)?$"),
        ],
        states={
            SOURCE_MENU: [
                CallbackQueryHandler(source_enter_url, pattern="^src_add$"),
            ],
            SOURCE_ENTER_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, source_receive_url),
                CallbackQueryHandler(source_menu, pattern="^src_menu$"),
            ],
            SOURCE_ENTER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, source_receive_title),
            ],
        },
        fallbacks=[CallbackQueryHandler(source_menu, pattern="^src_menu$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
