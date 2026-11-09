"""
Wizard تنظیمات موتور — prompt، topic، زبان، timezone، schedule، categories، criteria، min_score.
هر تغییر بلافاصله در DB ذخیره می‌شود.
"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

(
    SETTINGS_MENU, WAIT_PROMPT, WAIT_TOPIC, WAIT_TIMEZONE,
    WAIT_MIN_SCORE, WAIT_INTERVAL, WAIT_DAILY_CAP, WAIT_SIGNATURE,
    WAIT_HASHTAGS, WAIT_CAT_NAME, WAIT_CAT_KEYWORDS,
) = range(11)


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


async def _get_channel(context):
    channel_id = context.user_data.get("selected_channel_id")
    if not channel_id:
        return None
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        return await ChannelRepository(session).get_by_id(channel_id)


async def _save_settings(context, settings_dict: dict) -> None:
    channel_id = context.user_data.get("selected_channel_id")
    if not channel_id:
        return
    async with _get_session() as session:
        from src.infrastructure.db.repositories.channel_repo import ChannelRepository
        from src.domain.entities.channel import ChannelSettings
        repo = ChannelRepository(session)
        ch = await repo.get_by_id(channel_id)
        if not ch:
            return
        s = ch.settings
        for k, v in settings_dict.items():
            if hasattr(s, k):
                setattr(s, k, v)
        await repo.update_settings(channel_id, s)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query

    # channel_id از callback یا context
    if query and ":" in query.data:
        ch_id = int(query.data.split(":")[1])
        context.user_data["selected_channel_id"] = ch_id

    channel = await _get_channel(context)
    if not channel:
        if query:
            await query.answer()
            await query.edit_message_text(t("error_generic", lang=lang))
        return SETTINGS_MENU

    # ownership check
    if channel.owner_id != user.telegram_id:
        if query:
            await query.answer(t("not_authorized", lang=lang), show_alert=True)
        return SETTINGS_MENU

    s = channel.settings
    mode_label = t("settings_mode_auto", lang=lang) if s.mode == "auto" else t("settings_mode_review", lang=lang)

    keyboard = [
        [InlineKeyboardButton(
            f"{'🤖' if s.mode == 'auto' else '👁️'} حالت: {mode_label}",
            callback_data="set_toggle_mode"
        )],
        [InlineKeyboardButton(t("settings_prompt", lang=lang), callback_data="set_prompt")],
        [InlineKeyboardButton(t("settings_topic", lang=lang), callback_data="set_topic")],
        [InlineKeyboardButton(t("settings_language", lang=lang), callback_data="set_lang_menu")],
        [InlineKeyboardButton(t("settings_timezone", lang=lang), callback_data="set_timezone")],
        [InlineKeyboardButton(t("settings_schedule", lang=lang), callback_data="set_schedule")],
        [InlineKeyboardButton(t("settings_min_score", lang=lang), callback_data="set_min_score")],
        [InlineKeyboardButton(t("settings_categories", lang=lang), callback_data="set_categories")],
        [InlineKeyboardButton("✍️ امضا و هشتگ", callback_data="set_signature")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data=f"ch_select:{channel.id}")],
    ]

    text = (
        f"⚙️ <b>تنظیمات — {channel.title}</b>\n\n"
        f"حالت: {mode_label}\n"
        f"موضوع: {s.topic or '—'}\n"
        f"زبان خروجی: {s.language}\n"
        f"Timezone: {s.timezone}\n"
        f"بازه: هر {s.interval_minutes} دقیقه\n"
        f"سقف روزانه: {s.daily_posts_cap} پست\n"
        f"حداقل امتیاز: {s.min_score}"
    )
    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SETTINGS_MENU


async def toggle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    channel = await _get_channel(context)
    if not channel:
        return SETTINGS_MENU
    new_mode = "review" if channel.settings.mode == "auto" else "auto"
    await _save_settings(context, {"mode": new_mode})
    await query.answer(f"✅ حالت تغییر کرد: {new_mode}", show_alert=False)
    return await settings_menu(update, context)


async def prompt_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("settings_enter_prompt", lang=lang),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("/skip — بدون تغییر", callback_data="set_menu"),
            InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu"),
        ]]),
    )
    return WAIT_PROMPT


async def prompt_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    text = (update.message.text or "").strip()
    if text != "/skip" and text:
        await _save_settings(context, {"prompt": text})
    await update.message.reply_text(t("settings_saved", lang=lang))
    return await _refresh_menu(update, context)


async def topic_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("settings_enter_topic", lang=lang),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")]]),
    )
    return WAIT_TOPIC


async def topic_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    text = (update.message.text or "").strip()
    if text:
        await _save_settings(context, {"topic": text})
    await update.message.reply_text(t("settings_saved", lang=lang))
    return await _refresh_menu(update, context)


async def timezone_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    # لیست timezone‌های رایج
    common_tzs = ["Asia/Tehran", "UTC", "Europe/London", "America/New_York", "Asia/Dubai"]
    keyboard = [[InlineKeyboardButton(tz, callback_data=f"set_tz_quick:{tz}")] for tz in common_tzs]
    keyboard.append([InlineKeyboardButton("✏️ وارد کردن دستی", callback_data="set_tz_manual")])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")])
    await query.edit_message_text(
        t("settings_enter_timezone", lang=lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAIT_TIMEZONE


async def timezone_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    tz = query.data.split(":")[1]
    await _save_settings(context, {"timezone": tz})
    await query.answer(t("settings_saved", lang=lang), show_alert=False)
    return await settings_menu(update, context)


async def timezone_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    tz_name = (update.message.text or "").strip()
    try:
        import pytz
        pytz.timezone(tz_name)
        await _save_settings(context, {"timezone": tz_name})
        await update.message.reply_text(t("settings_saved", lang=lang))
    except Exception:
        await update.message.reply_text(t("settings_invalid_timezone", lang=lang))
    return await _refresh_menu(update, context)


async def min_score_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("0.3 (پایین)", callback_data="set_score_quick:0.3"),
         InlineKeyboardButton("0.5 (متوسط)", callback_data="set_score_quick:0.5")],
        [InlineKeyboardButton("0.7 (بالا)", callback_data="set_score_quick:0.7"),
         InlineKeyboardButton("0.9 (خیلی بالا)", callback_data="set_score_quick:0.9")],
        [InlineKeyboardButton("✏️ دستی", callback_data="set_score_manual")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")],
    ]
    await query.edit_message_text(
        t("settings_enter_min_score", lang=lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAIT_MIN_SCORE


async def score_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    score = float(query.data.split(":")[1])
    await _save_settings(context, {"min_score": score})
    await query.answer(t("settings_saved", lang=lang))
    return await settings_menu(update, context)


async def score_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    try:
        score = float((update.message.text or "").strip())
        if not 0 <= score <= 1:
            raise ValueError
        await _save_settings(context, {"min_score": score})
        await update.message.reply_text(t("settings_saved", lang=lang))
    except ValueError:
        await update.message.reply_text(t("settings_invalid_score", lang=lang))
    return await _refresh_menu(update, context)


async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    channel = await _get_channel(context)
    if not channel:
        return SETTINGS_MENU
    s = channel.settings
    keyboard = [
        [InlineKeyboardButton(f"⏱️ هر {s.interval_minutes} دقیقه", callback_data="set_interval")],
        [InlineKeyboardButton(f"📊 سقف روزانه: {s.daily_posts_cap}", callback_data="set_daily_cap")],
        [InlineKeyboardButton(
            f"🌙 quiet: {s.quiet_start or '—'} تا {s.quiet_end or '—'}",
            callback_data="set_quiet"
        )],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")],
    ]
    await query.edit_message_text(
        f"📅 <b>زمان‌بندی</b>\n\nInterval: {s.interval_minutes} دقیقه\nسقف: {s.daily_posts_cap} پست/روز",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return WAIT_INTERVAL


async def interval_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    intervals = [30, 60, 120, 180, 360, 720]
    keyboard = [[InlineKeyboardButton(f"{i} دقیقه", callback_data=f"set_int_quick:{i}")] for i in intervals]
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="set_schedule")])
    await query.edit_message_text("هر چند دقیقه یک بار اجرا شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_INTERVAL


async def interval_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    minutes = int(query.data.split(":")[1])
    await _save_settings(context, {"interval_minutes": minutes})
    return await settings_menu(update, context)


async def daily_cap_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    caps = [5, 10, 20, 30, 50]
    keyboard = [[InlineKeyboardButton(f"{c} پست/روز", callback_data=f"set_cap_quick:{c}")] for c in caps]
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="set_schedule")])
    await query.edit_message_text("سقف انتشار روزانه:", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_DAILY_CAP


async def daily_cap_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cap = int(query.data.split(":")[1])
    await _save_settings(context, {"daily_posts_cap": cap})
    return await settings_menu(update, context)


async def signature_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    channel = await _get_channel(context)
    s = channel.settings if channel else None
    current_sig = s.signature if s else ""
    current_tags = " ".join(s.hashtags) if s else ""
    await query.edit_message_text(
        f"✍️ امضای فعلی: {current_sig or '—'}\n🏷️ هشتگ‌های فعلی: {current_tags or '—'}\n\nامضای جدید را وارد کنید (یا /skip):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")]]),
    )
    context.user_data["settings_step"] = "signature"
    return WAIT_SIGNATURE


async def signature_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    step = context.user_data.pop("settings_step", "signature")
    text = (update.message.text or "").strip()
    if text != "/skip" and text:
        await _save_settings(context, {"signature": text})
    await update.message.reply_text(
        "🏷️ هشتگ‌ها را وارد کنید (فاصله‌دار، مثال: ai technology فناوری) یا /skip:"
    )
    context.user_data["settings_step"] = "hashtags"
    return WAIT_HASHTAGS


async def hashtags_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    text = (update.message.text or "").strip()
    if text != "/skip" and text:
        tags = [t.strip().lstrip("#") for t in text.split() if t.strip()]
        await _save_settings(context, {"hashtags": tags[:15]})
    await update.message.reply_text(t("settings_saved", lang=lang))
    return await _refresh_menu(update, context)


async def lang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_outlang:fa"),
         InlineKeyboardButton("🇬🇧 English", callback_data="set_outlang:en")],
        [InlineKeyboardButton("🇸🇦 عربی", callback_data="set_outlang:ar"),
         InlineKeyboardButton("🇩🇪 Deutsch", callback_data="set_outlang:de")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="set_menu")],
    ]
    await query.edit_message_text("زبان خروجی محتوا:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SETTINGS_MENU


async def set_output_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    out_lang = query.data.split(":")[1]
    await _save_settings(context, {"language": out_lang})
    return await settings_menu(update, context)


async def _refresh_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بازگشت به settings menu بعد از هر تغییر"""
    # fake callback برای edit
    class FakeQuery:
        data = "set_menu"
        async def answer(self): pass
        async def edit_message_text(self, *a, **kw): pass
        message = update.message

    update.callback_query = FakeQuery()
    return await settings_menu(update, context)


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(settings_menu, pattern=r"^ch_settings:\d+$"),
            CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
        ],
        states={
            SETTINGS_MENU: [
                CallbackQueryHandler(toggle_mode, pattern="^set_toggle_mode$"),
                CallbackQueryHandler(prompt_start, pattern="^set_prompt$"),
                CallbackQueryHandler(topic_start, pattern="^set_topic$"),
                CallbackQueryHandler(lang_menu, pattern="^set_lang_menu$"),
                CallbackQueryHandler(set_output_lang, pattern=r"^set_outlang:"),
                CallbackQueryHandler(timezone_start, pattern="^set_timezone$"),
                CallbackQueryHandler(min_score_start, pattern="^set_min_score$"),
                CallbackQueryHandler(score_quick, pattern=r"^set_score_quick:"),
                CallbackQueryHandler(schedule_menu, pattern="^set_schedule$"),
                CallbackQueryHandler(signature_start, pattern="^set_signature$"),
            ],
            WAIT_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_receive),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topic_receive),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_TIMEZONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, timezone_receive),
                CallbackQueryHandler(timezone_quick, pattern=r"^set_tz_quick:"),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_MIN_SCORE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, score_receive),
                CallbackQueryHandler(score_quick, pattern=r"^set_score_quick:"),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_INTERVAL: [
                CallbackQueryHandler(interval_quick, pattern=r"^set_int_quick:"),
                CallbackQueryHandler(interval_start, pattern="^set_interval$"),
                CallbackQueryHandler(daily_cap_start, pattern="^set_daily_cap$"),
                CallbackQueryHandler(daily_cap_quick, pattern=r"^set_cap_quick:"),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_DAILY_CAP: [
                CallbackQueryHandler(daily_cap_quick, pattern=r"^set_cap_quick:"),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_SIGNATURE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, signature_receive),
                CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            ],
            WAIT_HASHTAGS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, hashtags_receive),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(settings_menu, pattern="^set_menu$"),
            CallbackQueryHandler(settings_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
