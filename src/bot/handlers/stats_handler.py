"""آمار کانال و مصرف کاربر"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

STATS_MENU = 0

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    # آمار کانال خاص یا همه کانال‌ها
    if ":" in query.data:
        channel_id = int(query.data.split(":")[1])
        await _channel_stats(query, context, channel_id, lang, user)
    else:
        await _user_stats(query, context, lang, user)

    return STATS_MENU


async def _channel_stats(query, context, channel_id: int, lang: str, user) -> None:
    from src.application.channel.service import ChannelService
    svc = ChannelService(context.bot)
    stats = await svc.get_stats(channel_id)

    # ownership check
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        ch = await ChannelRepository(session).get_by_id(channel_id)
    if not ch or ch.owner_id != user.telegram_id:
        await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("🔄 اجرای دستی pipeline", callback_data=f"ch_run_pipeline:{channel_id}")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel_id}")],
    ]

    await query.edit_message_text(
        f"📊 <b>آمار — {ch.title}</b>\n\n"
        f"امروز منتشرشده: {stats['today_published']}\n"
        f"کل منتشرشده: {stats['total_published']}\n"
        f"در صف بازبینی: {stats['pending_review']}\n"
        f"پالایش‌شده/رد‌شده: {stats['filtered']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def _user_stats(query, context, lang: str, user) -> None:
    from datetime import date
    today = date.today().isoformat()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import UsageModel
        result = await session.execute(
            select(UsageModel).where(
                UsageModel.user_id == user.telegram_id,
                UsageModel.date == today,
            )
        )
        usage = result.scalar_one_or_none()

    posts = usage.posts_count if usage else 0
    tests = usage.tests_count if usage else 0
    ai_calls = usage.ai_calls if usage else 0
    tokens_in = usage.ai_tokens_in if usage else 0
    tokens_out = usage.ai_tokens_out if usage else 0

    keyboard = [[InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")]]

    await query.edit_message_text(
        f"📊 <b>آمار امروز</b>\n\n"
        f"{t('stats_today', lang=lang, posts=posts, tests=tests, ai_calls=ai_calls)}\n"
        f"{t('stats_tokens', lang=lang, tokens_in=f'{tokens_in:,}', tokens_out=f'{tokens_out:,}')}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def run_pipeline_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer("⏳ در حال اجرا...")

    channel_id = int(query.data.split(":")[1])

    # ownership
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        ch = await ChannelRepository(session).get_by_id(channel_id)
    if not ch or ch.owner_id != user.telegram_id:
        await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return STATS_MENU

    from src.application.channel.service import ChannelService
    svc = ChannelService(context.bot)
    result = await svc.trigger_pipeline(channel_id)

    await query.edit_message_text(
        f"✅ Pipeline اجرا شد:\n\n"
        f"دریافت‌شده: {result.get('fetched', 0)}\n"
        f"منتشرشده: {result.get('published', 0)}\n"
        f"در صف بازبینی: {result.get('queued_review', 0)}\n"
        f"خطاها: {result.get('errors', 0)}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel_id}")
        ]]),
    )
    return STATS_MENU


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(stats_menu, pattern="^stats_menu$"),
            CallbackQueryHandler(stats_menu, pattern=r"^ch_stats:\d+$"),
            CallbackQueryHandler(run_pipeline_manual, pattern=r"^ch_run_pipeline:\d+$"),
        ],
        states={
            STATS_MENU: [
                CallbackQueryHandler(run_pipeline_manual, pattern=r"^ch_run_pipeline:\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(stats_menu, pattern="^stats_menu$"),
            CallbackQueryHandler(stats_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
