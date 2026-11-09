"""کیف پول — نمایش موجودی، تاریخچه تراکنش‌ها"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

WALLET_MENU = 0

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    if query:
        await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import WalletModel, LedgerModel
        # موجودی‌ها
        result = await session.execute(
            select(WalletModel).where(WalletModel.user_id == user.telegram_id)
        )
        wallets = result.scalars().all()

        # ۱۰ تراکنش اخیر
        result2 = await session.execute(
            select(LedgerModel)
            .where(LedgerModel.user_id == user.telegram_id)
            .order_by(LedgerModel.created_at.desc())
            .limit(10)
        )
        ledger = result2.scalars().all()

    # متن موجودی
    if wallets:
        balance_text = "\n".join(
            t("wallet_balance", lang=lang, balance=f"{w.balance:,.0f}", currency=w.currency)
            for w in wallets
        )
    else:
        balance_text = "موجودی: صفر"

    # تاریخچه
    history = ""
    if ledger:
        history = "\n\n📋 تراکنش‌های اخیر:\n"
        for entry in ledger:
            sign = "+" if entry.delta > 0 else ""
            history += f"{'🟢' if entry.delta > 0 else '🔴'} {sign}{entry.delta:,.0f} {entry.currency} — {entry.reason}\n"

    keyboard = [
        [InlineKeyboardButton("📋 تاریخچه کامل", callback_data="wallet_full_history")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")],
    ]

    text = f"💰 <b>کیف پول</b>\n\n{balance_text}{history}"

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    return WALLET_MENU


async def full_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import LedgerModel
        result = await session.execute(
            select(LedgerModel)
            .where(LedgerModel.user_id == user.telegram_id)
            .order_by(LedgerModel.created_at.desc())
            .limit(50)
        )
        ledger = result.scalars().all()

    if not ledger:
        await query.edit_message_text(
            "📋 هنوز هیچ تراکنشی ثبت نشده است.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang=lang), callback_data="wallet_menu")
            ]]),
        )
        return WALLET_MENU

    lines = []
    for entry in ledger:
        sign = "+" if entry.delta > 0 else ""
        date = entry.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"{'🟢' if entry.delta > 0 else '🔴'} {sign}{entry.delta:,.0f} {entry.currency}\n"
            f"   {entry.reason} | {date}"
        )

    # ارسال به صورت چند پیام اگر طولانی است
    text = "\n".join(lines)
    if len(text) > 3800:
        # تقسیم
        chunks = [lines[i:i+15] for i in range(0, len(lines), 15)]
        await query.edit_message_text(
            "📋 تاریخچه تراکنش‌ها:\n\n" + "\n".join(chunks[0]),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang=lang), callback_data="wallet_menu")
            ]]),
        )
        for chunk in chunks[1:]:
            await query.message.reply_text("\n".join(chunk))
    else:
        await query.edit_message_text(
            "📋 تاریخچه تراکنش‌ها:\n\n" + text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang=lang), callback_data="wallet_menu")
            ]]),
        )

    return WALLET_MENU


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(wallet_menu, pattern="^wallet_menu$")],
        states={
            WALLET_MENU: [
                CallbackQueryHandler(full_history, pattern="^wallet_full_history$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(wallet_menu, pattern="^wallet_menu$"),
            CallbackQueryHandler(wallet_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
