"""
بازبینی مقالات — نمایش، تأیید، رد، ویرایش.
بررسی مالکیت کانال قبل از هر action.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

REVIEW_MENU, REVIEW_ARTICLE, WAIT_EDIT = range(3)

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


async def review_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    channel_id = int(query.data.split(":")[1])
    context.user_data["selected_channel_id"] = channel_id

    # ownership check
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        channel = await ChannelRepository(session).get_by_id(channel_id)

    if not channel or channel.owner_id != user.telegram_id:
        await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return REVIEW_MENU

    async with _get_session() as session:
        from src.infrastructure.db.repositories.article_repo import ArticleRepository
        articles = await ArticleRepository(session).list_pending_review(channel_id, limit=10)

    if not articles:
        await query.edit_message_text(
            t("review_empty", lang=lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel_id}")
            ]]),
        )
        return REVIEW_MENU

    keyboard = []
    for art in articles:
        score_str = f"{art.score:.2f}"
        keyboard.append([
            InlineKeyboardButton(
                f"⭐{score_str} {art.title[:40]}",
                callback_data=f"rev_view:{art.id}",
            )
        ])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel_id}")])

    await query.edit_message_text(
        t("review_queue", lang=lang, count=len(articles)),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return REVIEW_MENU


async def review_article_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    article_id = int(query.data.split(":")[1])

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import ArticleModel, SourceModel
        article = await session.get(ArticleModel, article_id)

        if not article:
            await query.answer(t("error_generic", lang=lang), show_alert=True)
            return REVIEW_MENU

        # ownership از طریق channel
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        channel = await ChannelRepository(session).get_by_id(article.channel_id)

    if not channel or channel.owner_id != user.telegram_id:
        await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return REVIEW_MENU

    context.user_data["review_article_id"] = article_id

    post_text = article.post_html or article.raw_text or "(متن موجود نیست)"
    score = f"{float(article.score):.2f}" if article.score else "—"

    # نمایش preview متن
    preview = post_text[:600] + ("..." if len(post_text) > 600 else "")

    keyboard = [
        [
            InlineKeyboardButton(t("review_approve", lang=lang), callback_data=f"rev_approve:{article_id}"),
            InlineKeyboardButton(t("review_reject", lang=lang), callback_data=f"rev_reject:{article_id}"),
        ],
        [InlineKeyboardButton(t("review_edit", lang=lang), callback_data=f"rev_edit:{article_id}")],
        [InlineKeyboardButton("🔗 لینک منبع", url=article.url)],
        [InlineKeyboardButton(t("back", lang=lang), callback_data=f"review_queue:{article.channel_id}")],
    ]

    await query.edit_message_text(
        f"📄 <b>{article.title[:100]}</b>\n\n"
        f"⭐ امتیاز: {score} | دسته: {article.category or '—'}\n\n"
        f"{preview}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return REVIEW_ARTICLE


async def review_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    article_id = int(query.data.split(":")[1])

    async with _get_session() as session:
        from src.infrastructure.db.repositories.article_repo import ArticleRepository
        from src.domain.entities.article import ArticleStatus
        repo = ArticleRepository(session)
        # ownership re-check
        from sqlalchemy import select
        from src.infrastructure.db.models import ArticleModel
        art = await session.get(ArticleModel, article_id)
        if not art:
            return REVIEW_MENU
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        ch = await ChannelRepository(session).get_by_id(art.channel_id)
        if not ch or ch.owner_id != user.telegram_id:
            await query.answer(t("not_authorized", lang=lang), show_alert=True)
            return REVIEW_MENU

        await repo.update_status(
            article_id,
            ArticleStatus.APPROVED,
            reason=f"approved_by:{user.telegram_id}",
        )
        # mark reviewed
        from sqlalchemy import update as sql_update
        from src.infrastructure.db.models import ArticleModel as AM
        from datetime import datetime
        await session.execute(
            sql_update(AM).where(AM.id == article_id)
            .values(reviewed_by=user.telegram_id, reviewed_at=datetime.utcnow())
        )

    await query.edit_message_text(t("review_approved", lang=lang))
    return REVIEW_MENU


async def review_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    article_id = int(query.data.split(":")[1])

    async with _get_session() as session:
        from src.infrastructure.db.repositories.article_repo import ArticleRepository
        from src.domain.entities.article import ArticleStatus
        repo = ArticleRepository(session)
        from src.infrastructure.db.models import ArticleModel
        art = await session.get(ArticleModel, article_id)
        if not art:
            return REVIEW_MENU
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        ch = await ChannelRepository(session).get_by_id(art.channel_id)
        if not ch or ch.owner_id != user.telegram_id:
            await query.answer(t("not_authorized", lang=lang), show_alert=True)
            return REVIEW_MENU

        await repo.update_status(
            article_id, ArticleStatus.REJECTED,
            reason=f"rejected_by:{user.telegram_id}",
        )

    await query.edit_message_text(t("review_rejected", lang=lang))
    return REVIEW_MENU


async def review_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    article_id = int(query.data.split(":")[1])
    context.user_data["edit_article_id"] = article_id

    await query.edit_message_text(
        "✏️ متن جدید پست را وارد کنید (HTML تلگرام):\n\n"
        "تگ‌های مجاز: &lt;b&gt; &lt;i&gt; &lt;code&gt; &lt;a href=...&gt;",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang=lang), callback_data=f"rev_view:{article_id}")
        ]]),
    )
    return WAIT_EDIT


async def review_edit_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    article_id = context.user_data.pop("edit_article_id", None)
    new_text = (update.message.text or "").strip()

    if not article_id or not new_text:
        return REVIEW_MENU

    async with _get_session() as session:
        from sqlalchemy import update as sql_update
        from src.infrastructure.db.models import ArticleModel
        art = await session.get(ArticleModel, article_id)
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        ch = await ChannelRepository(session).get_by_id(art.channel_id)
        if not ch or ch.owner_id != user.telegram_id:
            await update.message.reply_text(t("not_authorized", lang=lang))
            return REVIEW_MENU

        await session.execute(
            sql_update(ArticleModel).where(ArticleModel.id == article_id)
            .values(post_html=new_text[:4096])
        )

    await update.message.reply_text("✅ متن ویرایش شد. اکنون می‌توانید تأیید کنید.")
    return REVIEW_MENU


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(review_queue, pattern=r"^review_queue:\d+$"),
        ],
        states={
            REVIEW_MENU: [
                CallbackQueryHandler(review_article_view, pattern=r"^rev_view:\d+$"),
            ],
            REVIEW_ARTICLE: [
                CallbackQueryHandler(review_approve, pattern=r"^rev_approve:\d+$"),
                CallbackQueryHandler(review_reject, pattern=r"^rev_reject:\d+$"),
                CallbackQueryHandler(review_edit_start, pattern=r"^rev_edit:\d+$"),
                CallbackQueryHandler(review_queue, pattern=r"^review_queue:\d+$"),
            ],
            WAIT_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, review_edit_receive),
                CallbackQueryHandler(review_article_view, pattern=r"^rev_view:\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(review_queue, pattern=r"^review_queue:\d+$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
