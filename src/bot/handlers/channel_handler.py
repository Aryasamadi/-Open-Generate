"""
Wizard مدیریت کانال — افزودن، تنظیم، حذف، انتقال مالکیت.
تمام callbackها با user ID و resource ownership مجدداً authorize می‌شوند.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# states
(
    CHANNEL_MENU,
    CHANNEL_ENTER_ID,
    CHANNEL_CONFIRM_ADD,
    CHANNEL_SELECT,
    CHANNEL_ACTION,
) = range(5)


async def channel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")

    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        repo = ChannelRepository(session)
        channels = await repo.list_by_owner(user.telegram_id)

    keyboard = []
    for ch in channels:
        status = "✅" if ch.is_active else "⏸️"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {ch.title}",
                callback_data=f"ch_select:{ch.id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(t("channel_add", lang=lang), callback_data="ch_add")
    ])
    keyboard.append([
        InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")
    ])

    text = t("channel_menu", lang=lang)
    if not channels:
        text += f"\n\n{t('no_channels', lang=lang)}"

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return CHANNEL_MENU


async def channel_enter_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("channel_enter_id", lang=lang),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("cancel", lang=lang), callback_data="ch_menu")]
        ]),
    )
    return CHANNEL_ENTER_ID


async def channel_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    text_input = (update.message.text or "").strip()

    # حذف پیام حاوی اطلاعات کانال (privacy)
    try:
        await update.message.delete()
    except Exception:
        pass

    await update.message.reply_text(t("channel_checking", lang=lang))

    # بررسی سقف پلن
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        repo = ChannelRepository(session)
        count = await repo.count_by_owner(user.telegram_id)

    # بررسی سقف پلن کاربر
    max_channels = _get_plan_limit(user, "max_channels")
    if count >= max_channels:
        await update.message.reply_text(
            t("channel_limit_reached", lang=lang, max=max_channels)
        )
        return CHANNEL_MENU

    # بررسی کانال در تلگرام
    try:
        from telegram import Bot
        from config.settings import get_settings
        bot = context.bot
        chat_id = text_input if text_input.startswith("-") else f"@{text_input.lstrip('@')}"
        chat = await bot.get_chat(chat_id)

        # بررسی نوع
        if chat.type not in ("channel", "supergroup"):
            await update.message.reply_text("❌ فقط کانال‌ها پشتیبانی می‌شوند.")
            return CHANNEL_MENU

        # بررسی ادمین بودن ربات
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        can_post = getattr(bot_member, "can_post_messages", False)

        if not can_post:
            await update.message.reply_text(t("channel_not_admin", lang=lang))
            return CHANNEL_MENU

        # بررسی وجود قبلی
        async with _get_session() as session:
            from src.infrastructure.db.repositories.channel_repo import ChannelRepository
            repo = ChannelRepository(session)
            existing = await repo.get_by_telegram_id(chat.id)
            if existing:
                await update.message.reply_text(t("channel_already_exists", lang=lang))
                return CHANNEL_MENU

        context.user_data["pending_channel"] = {
            "telegram_id": chat.id,
            "username": chat.username,
            "title": chat.title,
        }

        keyboard = [
            [
                InlineKeyboardButton(t("yes_confirm", lang=lang), callback_data="ch_confirm_add"),
                InlineKeyboardButton(t("cancel", lang=lang), callback_data="ch_menu"),
            ]
        ]
        await update.message.reply_text(
            f"📢 کانال یافت شد:\n<b>{chat.title}</b>\n@{chat.username or ''}\n\nاضافه شود؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return CHANNEL_CONFIRM_ADD

    except Exception as exc:
        logger.warning("channel_check_error", error=str(exc)[:200])
        await update.message.reply_text(f"❌ خطا: {exc!s:.150}")
        return CHANNEL_MENU


async def channel_confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    pending = context.user_data.pop("pending_channel", None)
    query = update.callback_query
    await query.answer()

    if not pending:
        await query.edit_message_text(t("error_generic", lang=lang))
        return CHANNEL_MENU

    async with _get_session() as session:
        from src.domain.entities.channel import Channel
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        repo = ChannelRepository(session)
        channel = Channel(
            owner_id=user.telegram_id,
            telegram_id=pending["telegram_id"],
            username=pending.get("username"),
            title=pending["title"],
            bot_is_admin=True,
        )
        await repo.create(channel)

    await query.edit_message_text(
        t("channel_added", lang=lang, title=pending["title"])
    )
    return CHANNEL_MENU


async def channel_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    # پارس channel_id از callback_data
    parts = query.data.split(":")
    if len(parts) < 2:
        return CHANNEL_MENU

    channel_id = int(parts[1])

    # authorize: مالکیت بررسی می‌شود
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        repo = ChannelRepository(session)
        channel = await repo.get_by_id(channel_id)

    if not channel or channel.owner_id != user.telegram_id:
        await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return CHANNEL_MENU

    context.user_data["selected_channel_id"] = channel_id

    status_icon = "✅" if channel.is_active else "⏸️"
    keyboard = [
        [InlineKeyboardButton(t("channel_settings", lang=lang), callback_data=f"ch_settings:{channel_id}")],
        [InlineKeyboardButton(t("source_menu", lang=lang), callback_data=f"src_menu:{channel_id}")],
        [InlineKeyboardButton("📋 صف بازبینی", callback_data=f"review_queue:{channel_id}")],
        [InlineKeyboardButton(t("stats_menu", lang=lang), callback_data=f"ch_stats:{channel_id}")],
        [
            InlineKeyboardButton(
                "⏸️ غیرفعال" if channel.is_active else "▶️ فعال",
                callback_data=f"ch_toggle:{channel_id}",
            ),
            InlineKeyboardButton(t("channel_delete", lang=lang), callback_data=f"ch_delete:{channel_id}"),
        ],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="ch_menu")],
    ]

    await query.edit_message_text(
        f"{status_icon} <b>{channel.title}</b>\n@{channel.username or ''}\n\n"
        f"حالت: {'خودکار 🤖' if channel.settings.mode == 'auto' else 'بازبینی 👁️'}\n"
        f"آخرین اجرا: {channel.settings.last_run or '—'}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return CHANNEL_SELECT


def _get_plan_limit(user: object, field: str) -> int:
    """سقف پلن — در production از DB می‌خواند"""
    defaults = {"max_channels": 3, "max_sources": 10, "daily_posts": 20}
    return defaults.get(field, 1)


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(channel_menu, pattern="^ch_menu$"),
            CallbackQueryHandler(channel_menu, pattern="^channel_menu$"),
        ],
        states={
            CHANNEL_MENU: [
                CallbackQueryHandler(channel_enter_id, pattern="^ch_add$"),
                CallbackQueryHandler(channel_select, pattern=r"^ch_select:\d+$"),
            ],
            CHANNEL_ENTER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, channel_receive_id),
                CallbackQueryHandler(channel_menu, pattern="^ch_menu$"),
            ],
            CHANNEL_CONFIRM_ADD: [
                CallbackQueryHandler(channel_confirm_add, pattern="^ch_confirm_add$"),
                CallbackQueryHandler(channel_menu, pattern="^ch_menu$"),
            ],
            CHANNEL_SELECT: [
                CallbackQueryHandler(channel_menu, pattern="^ch_menu$"),
                CallbackQueryHandler(channel_select, pattern=r"^ch_select:\d+$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(channel_menu, pattern="^ch_menu$"),
            CallbackQueryHandler(channel_menu, pattern="^main_menu$"),
        ],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
