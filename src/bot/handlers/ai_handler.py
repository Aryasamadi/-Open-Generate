"""Wizard مدیریت مدل‌های AI"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.domain.entities.ai_model import AIProvider

AI_MENU, AI_SELECT_PROVIDER, AI_ENTER_BASE_URL, AI_ENTER_API_KEY, AI_ENTER_MODEL_ID, AI_ENTER_NAME, AI_CONFIRM = range(7)

PROVIDER_BUTTONS = [
    [InlineKeyboardButton("Anthropic (Claude)", callback_data="aip:anthropic"),
     InlineKeyboardButton("OpenAI / Compatible", callback_data="aip:openai")],
    [InlineKeyboardButton("Gemini", callback_data="aip:gemini"),
     InlineKeyboardButton("Groq", callback_data="aip:groq")],
    [InlineKeyboardButton("DeepSeek", callback_data="aip:deepseek"),
     InlineKeyboardButton("Mistral", callback_data="aip:mistral")],
    [InlineKeyboardButton("Ollama (Local)", callback_data="aip:ollama"),
     InlineKeyboardButton("Custom", callback_data="aip:custom")],
]

PROVIDER_DEFAULTS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}

async def ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    async with _get_session() as session:
        from src.infrastructure.db.repositories.ai_model_repo import AIModelRepository
        models = await AIModelRepository(session).list_available_for_channel(user.telegram_id)
    keyboard = []
    for m in models:
        keyboard.append([InlineKeyboardButton(f"🤖 {m.display_name}", callback_data=f"ai_sel:{m.id}")])
    keyboard.append([InlineKeyboardButton(t("ai_add", lang=lang), callback_data="ai_add")])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")])
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(t("ai_menu", lang=lang), reply_markup=InlineKeyboardMarkup(keyboard))
    return AI_MENU

async def ai_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("ai_enter_provider", lang=lang),
        reply_markup=InlineKeyboardMarkup(PROVIDER_BUTTONS + [[InlineKeyboardButton(t("cancel", lang=lang), callback_data="ai_menu")]]),
    )
    return AI_SELECT_PROVIDER

async def ai_select_provider(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    provider = query.data.split(":")[1]
    context.user_data["new_ai"] = {"provider": provider}
    default_url = PROVIDER_DEFAULTS.get(provider, "")
    if default_url:
        context.user_data["new_ai"]["base_url"] = default_url
        await query.edit_message_text(
            f"✅ Provider: {provider}\n🔗 Base URL: {default_url}\n\n" + t("ai_enter_api_key", lang=lang),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="ai_menu")]]),
        )
        return AI_ENTER_API_KEY
    await query.edit_message_text(
        t("ai_enter_base_url", lang=lang),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="ai_menu")]]),
    )
    return AI_ENTER_BASE_URL

async def ai_receive_base_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    url = (update.message.text or "").strip()
    context.user_data.setdefault("new_ai", {})["base_url"] = url
    await update.message.reply_text(t("ai_enter_api_key", lang=lang))
    return AI_ENTER_API_KEY

async def ai_receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    key = (update.message.text or "").strip()
    try: await update.message.delete()
    except Exception: pass
    from src.infrastructure.crypto.encryption import encrypt, mask_secret
    encrypted = encrypt(key)
    context.user_data.setdefault("new_ai", {})["api_key_encrypted"] = encrypted
    masked = mask_secret(key)
    await update.message.reply_text(t("ai_key_masked", lang=lang, masked=masked))
    await update.message.reply_text(t("ai_enter_model_id", lang=lang))
    return AI_ENTER_MODEL_ID

async def ai_receive_model_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    model_id = (update.message.text or "").strip()
    context.user_data.setdefault("new_ai", {})["model_id"] = model_id
    await update.message.reply_text(t("ai_enter_display_name", lang=lang))
    return AI_ENTER_NAME

async def ai_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    name = (update.message.text or "").strip()
    new_ai = context.user_data.pop("new_ai", {})
    new_ai["display_name"] = name

    await update.message.reply_text(t("ai_testing", lang=lang))
    from src.infrastructure.crypto.encryption import decrypt
    from src.infrastructure.ai.engine import get_adapter
    provider = AIProvider(new_ai["provider"])
    adapter = get_adapter(provider)
    api_key = decrypt(new_ai["api_key_encrypted"])
    ok = await adapter.test_connection(api_key, new_ai["base_url"], new_ai["model_id"])

    if not ok:
        await update.message.reply_text(t("ai_test_failed", lang=lang, error="اتصال ناموفق"))
        return AI_MENU

    async with _get_session() as session:
        from src.infrastructure.db.repositories.ai_model_repo import AIModelRepository
        from src.domain.entities.ai_model import AIModel
        model = AIModel(
            provider=provider,
            display_name=name,
            base_url=new_ai["base_url"],
            model_id=new_ai["model_id"],
            api_key_encrypted=new_ai["api_key_encrypted"],
            is_global=False,
            owner_id=user.telegram_id,
        )
        await AIModelRepository(session).create(model)

    await update.message.reply_text(t("ai_added", lang=lang, name=name))
    return AI_MENU

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()

def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(ai_menu, pattern="^ai_menu$")],
        states={
            AI_MENU: [CallbackQueryHandler(ai_add_start, pattern="^ai_add$")],
            AI_SELECT_PROVIDER: [CallbackQueryHandler(ai_select_provider, pattern=r"^aip:")],
            AI_ENTER_BASE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_receive_base_url)],
            AI_ENTER_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_receive_api_key)],
            AI_ENTER_MODEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_receive_model_id)],
            AI_ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_receive_name)],
        },
        fallbacks=[CallbackQueryHandler(ai_menu, pattern="^ai_menu$")],
        per_user=True, per_chat=True, allow_reentry=True,
    )
