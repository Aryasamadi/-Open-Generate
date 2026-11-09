"""
پشتیبانی — ایجاد تیکت، تاریخچه مکالمه، پاسخ ادمین.
پیام‌های پشتیبانی به سوپرادمین‌ها forward می‌شوند.
"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

SUPPORT_MENU, WAIT_MESSAGE, TICKET_VIEW = range(3)

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    if query:
        await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import SupportTicketModel
        result = await session.execute(
            select(SupportTicketModel)
            .where(SupportTicketModel.user_id == user.telegram_id)
            .order_by(SupportTicketModel.created_at.desc())
            .limit(10)
        )
        tickets = result.scalars().all()

    keyboard = []
    for ticket in tickets:
        icon = "🟢" if ticket.status == "open" else "⬛"
        date = ticket.created_at.strftime("%m/%d")
        keyboard.append([
            InlineKeyboardButton(
                f"{icon} تیکت #{ticket.id} — {date}",
                callback_data=f"sup_view:{ticket.id}",
            )
        ])
    keyboard.append([InlineKeyboardButton(t("support_new", lang=lang), callback_data="sup_new")])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")])

    text = f"🆘 <b>پشتیبانی</b>\n\nتعداد تیکت‌های باز: {sum(1 for t in tickets if t.status == 'open')}"

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SUPPORT_MENU


async def new_ticket_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("support_enter_message", lang=lang),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("cancel", lang=lang), callback_data="support_menu")
        ]]),
    )
    return WAIT_MESSAGE


async def new_ticket_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    text_msg = (update.message.text or "").strip()

    if not text_msg:
        await update.message.reply_text("پیام نمی‌تواند خالی باشد.")
        return WAIT_MESSAGE

    async with _get_session() as session:
        from src.infrastructure.db.models import SupportTicketModel, SupportMessageModel
        ticket = SupportTicketModel(
            user_id=user.telegram_id,
            status="open",
        )
        session.add(ticket)
        await session.flush()

        msg = SupportMessageModel(
            ticket_id=ticket.id,
            sender_id=user.telegram_id,
            is_admin=False,
            text=text_msg,
        )
        session.add(msg)
        ticket_id = ticket.id

    # اطلاع‌رسانی به سوپرادمین‌ها
    from config.settings import get_settings
    settings = get_settings()
    admin_text = (
        f"🆘 تیکت جدید #{ticket_id}\n"
        f"کاربر: {user.telegram_id} (@{user.username or '—'})\n\n"
        f"{text_msg[:500]}\n\n"
        f"برای پاسخ: /reply_{ticket_id}"
    )
    for admin_id in settings.SUPER_ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_text)
        except Exception:
            pass

    await update.message.reply_text(t("support_submitted", lang=lang, id=ticket_id))
    return SUPPORT_MENU


async def ticket_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    ticket_id = int(query.data.split(":")[1])

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import SupportTicketModel, SupportMessageModel
        ticket = await session.get(SupportTicketModel, ticket_id)
        if not ticket or ticket.user_id != user.telegram_id:
            await query.answer(t("not_authorized", lang=lang), show_alert=True)
            return SUPPORT_MENU

        result = await session.execute(
            select(SupportMessageModel)
            .where(SupportMessageModel.ticket_id == ticket_id)
            .order_by(SupportMessageModel.created_at)
        )
        messages = result.scalars().all()

    lines = [f"🎫 <b>تیکت #{ticket_id}</b>\nوضعیت: {'🟢 باز' if ticket.status == 'open' else '⬛ بسته'}\n\n"]
    for m in messages:
        prefix = "👤 شما" if not m.is_admin else "🎧 پشتیبانی"
        date = m.created_at.strftime("%m/%d %H:%M")
        lines.append(f"<b>{prefix}</b> ({date}):\n{m.text or '[فایل]'}\n")

    keyboard = [[InlineKeyboardButton(t("back", lang=lang), callback_data="support_menu")]]

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return TICKET_VIEW


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(support_menu, pattern="^support_menu$")],
        states={
            SUPPORT_MENU: [
                CallbackQueryHandler(new_ticket_prompt, pattern="^sup_new$"),
                CallbackQueryHandler(ticket_view, pattern=r"^sup_view:\d+$"),
            ],
            WAIT_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, new_ticket_receive),
                CallbackQueryHandler(support_menu, pattern="^support_menu$"),
            ],
            TICKET_VIEW: [
                CallbackQueryHandler(support_menu, pattern="^support_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(support_menu, pattern="^support_menu$"),
            CallbackQueryHandler(support_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
