"""تغییر زبان رابط کاربری"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler
from src.bot.localization.fa import t

LANGUAGE_MENU = 0

async def language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    if query:
        await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_ui_lang:fa"),
            InlineKeyboardButton("🇬🇧 English", callback_data="set_ui_lang:en"),
        ],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")],
    ]

    text = t("language_menu", lang=lang)
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return LANGUAGE_MENU


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    new_lang = query.data.split(":")[1]

    user = context.user_data.get("db_user")
    context.user_data["lang"] = new_lang

    async with _get_session() as session:
        from src.infrastructure.db.repositories.user_repo import UserRepository
        await UserRepository(session).set_language(user.telegram_id, new_lang)

    await query.edit_message_text(t("language_set", lang=new_lang))
    return LANGUAGE_MENU


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(language_menu, pattern="^language_menu$")],
        states={
            LANGUAGE_MENU: [
                CallbackQueryHandler(set_language, pattern=r"^set_ui_lang:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(language_menu, pattern="^language_menu$"),
            CallbackQueryHandler(language_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
