"""
Callback‌های تأیید/رد پرداخت برای ادمین.
تأیید از طریق PaymentService با idempotency کامل.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.application.payment.service import PaymentService
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_payment_service = PaymentService()


async def admin_pay_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    pay_id = int(query.data.split(":")[1])

    # تأیید با دوم
    keyboard = [
        [
            InlineKeyboardButton("✅ بله، تأیید می‌کنم", callback_data=f"adm_pay_approve_final:{pay_id}"),
            InlineKeyboardButton("❌ انصراف", callback_data="adm_payments"),
        ]
    ]
    await query.edit_message_text(
        f"⚠️ تأیید پرداخت #{pay_id}?\n\nاین عمل پلن کاربر را فعال می‌کند.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return 7  # ADMIN_PAYMENT_DECISION


async def admin_pay_approve_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    pay_id = int(query.data.split(":")[1])

    ok = await _payment_service.approve(
        pay_id=pay_id,
        decided_by=admin.telegram_id,
        note="admin_approved_via_bot",
    )

    if ok:
        logger.info("admin_approved_payment", pay_id=pay_id, admin=admin.telegram_id)
        await query.edit_message_text(f"✅ پرداخت #{pay_id} تأیید و پلن فعال شد.")
    else:
        await query.edit_message_text(f"❌ خطا در تأیید پرداخت #{pay_id}")

    return 7  # ADMIN_PAYMENT_DECISION


async def admin_pay_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    pay_id = int(query.data.split(":")[1])
    context.user_data["reject_pay_id"] = pay_id

    await query.edit_message_text(
        f"❌ دلیل رد پرداخت #{pay_id} را بنویسید:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ انصراف", callback_data="adm_payments")
        ]]),
    )
    return 8  # ADMIN_PAYMENT_DECISION — waiting text


async def admin_pay_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    pay_id = context.user_data.pop("reject_pay_id", None)
    reason = (update.message.text or "").strip()

    if not pay_id:
        return 7

    ok = await _payment_service.reject(
        pay_id=pay_id,
        decided_by=admin.telegram_id,
        reason=reason,
    )

    if ok:
        await update.message.reply_text(f"✅ پرداخت #{pay_id} رد شد.")
    else:
        await update.message.reply_text(f"❌ خطا در رد پرداخت #{pay_id}")

    return 7
