"""
Wizard پرداخت — ثبت درخواست، آپلود رسید، بررسی ادمین، اعمال پلن.
پرداخت دستی فقط بر اساس بررسی انسانی تأیید می‌شود.
Idempotency: اعمال پلن فقط یک بار انجام می‌شود.
"""
from __future__ import annotations
from decimal import Decimal
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

(
    PLAN_MENU, PLAN_SELECT, DISCOUNT_INPUT, RECEIPT_UPLOAD, PAY_CONFIRM,
) = range(5)


async def plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    if query:
        await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import PlanModel
        result = await session.execute(
            select(PlanModel).where(PlanModel.is_active == True).order_by(PlanModel.sort)
        )
        plans = result.scalars().all()

    # وضعیت پلن فعلی
    plan_text = t("plan_menu", lang=lang)
    if user and user.plan_id:
        exp = user.plan_expires_at.strftime("%Y-%m-%d") if user.plan_expires_at else "—"
        plan_text += f"\n\n{t('plan_current', lang=lang, name=user.plan_id, expires=exp, daily='—')}"
    elif user and not user.has_active_plan:
        plan_text += f"\n\n⚠️ {t('plan_expired', lang=lang)}"

    keyboard = []
    for p in plans:
        keyboard.append([
            InlineKeyboardButton(
                f"{'🆓 ' if p.is_free else '💎 '}{p.name} — {p.price}",
                callback_data=f"pay_select:{p.id}",
            )
        ])
    keyboard.append([InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")])

    if query:
        await query.edit_message_text(plan_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(plan_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return PLAN_MENU


async def plan_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.split(":")[1])

    async with _get_session() as session:
        from src.infrastructure.db.models import PlanModel
        plan = await session.get(PlanModel, plan_id)

    if not plan:
        await query.edit_message_text(t("error_generic", lang=lang))
        return PLAN_MENU

    # پلن رایگان — مستقیم اعمال
    if plan.is_free:
        await _apply_free_plan(user.telegram_id, plan_id, lang)
        await query.edit_message_text(t("payment_approved", lang=lang, plan=plan.name))
        return PLAN_MENU

    # بررسی درخواست تکراری
    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import PayRequestModel
        result = await session.execute(
            select(PayRequestModel).where(
                PayRequestModel.user_id == user.telegram_id,
                PayRequestModel.status == "pending",
            )
        )
        existing = result.scalar_one_or_none()
    if existing:
        await query.edit_message_text(t("payment_duplicate", lang=lang))
        return PLAN_MENU

    context.user_data["selected_plan"] = {"id": plan_id, "name": plan.name, "price": plan.price, "price_num": str(plan.price_num)}

    keyboard = [
        [InlineKeyboardButton("🏷️ " + t("discount_enter_code", lang=lang), callback_data="pay_has_discount")],
        [InlineKeyboardButton("⏭️ بدون کد تخفیف", callback_data="pay_no_discount")],
        [InlineKeyboardButton(t("cancel", lang=lang), callback_data="plan_menu")],
    ]
    await query.edit_message_text(
        t("plan_selected", lang=lang, name=plan.name, price=plan.price),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return PLAN_SELECT


async def discount_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t("discount_enter_code", lang=lang),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("cancel", lang=lang), callback_data="plan_menu")]
        ]),
    )
    return DISCOUNT_INPUT


async def discount_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    code = (update.message.text or "").strip().upper()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import DiscountModel
        from datetime import datetime
        result = await session.execute(
            select(DiscountModel).where(
                DiscountModel.code == code,
                DiscountModel.is_active == True,
            )
        )
        disc = result.scalar_one_or_none()

    if not disc or not _is_discount_valid(disc):
        await update.message.reply_text(t("discount_invalid", lang=lang))
        return DISCOUNT_INPUT

    plan_info = context.user_data.get("selected_plan", {})
    original = Decimal(plan_info.get("price_num", "0"))
    discounted = (original * (1 - disc.percent / 100)).quantize(Decimal("0.01"))
    context.user_data["discount_code"] = code
    context.user_data["discount_applied"] = str(original - discounted)
    context.user_data["final_price"] = str(discounted)

    await update.message.reply_text(
        t("discount_applied", lang=lang, percent=int(disc.percent)) +
        f"\nمبلغ نهایی: {discounted:,}"
    )
    await _ask_receipt(update, context, lang)
    return RECEIPT_UPLOAD


async def skip_discount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    query = update.callback_query
    await query.answer()
    plan_info = context.user_data.get("selected_plan", {})
    context.user_data["final_price"] = plan_info.get("price_num", "0")
    context.user_data["discount_code"] = None
    context.user_data["discount_applied"] = "0"
    await query.edit_message_text(t("payment_enter_receipt", lang=lang))
    return RECEIPT_UPLOAD


async def _ask_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    await update.message.reply_text(
        t("payment_enter_receipt", lang=lang),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("cancel", lang=lang), callback_data="plan_menu")]
        ]),
    )


async def receipt_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")

    # قبول: عکس یا document
    file_obj = None
    mime = None
    if update.message.photo:
        file_obj = update.message.photo[-1]
        mime = "image/jpeg"
    elif update.message.document:
        doc = update.message.document
        mime = doc.mime_type or "application/octet-stream"
        if mime not in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
            await update.message.reply_text("❌ فقط تصویر یا PDF قبول می‌شود.")
            return RECEIPT_UPLOAD
        file_obj = doc
    else:
        await update.message.reply_text(t("payment_enter_receipt", lang=lang))
        return RECEIPT_UPLOAD

    # اندازه فایل
    file_size = getattr(file_obj, "file_size", 0) or 0
    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ حجم فایل بیش از ۲۰ مگابایت است.")
        return RECEIPT_UPLOAD

    # ذخیره فایل
    import os, secrets
    from pathlib import Path
    from config.settings import get_settings
    settings = get_settings()
    receipts_dir = settings.RECEIPTS_DIR
    Path(receipts_dir).mkdir(parents=True, exist_ok=True)

    tg_file = await file_obj.get_file()
    ext = ".pdf" if mime == "application/pdf" else ".jpg"
    filename = f"{user.telegram_id}_{secrets.token_hex(8)}{ext}"
    save_path = str(Path(receipts_dir) / filename)
    await tg_file.download_to_drive(save_path)

    plan_info = context.user_data.get("selected_plan", {})

    async with _get_session() as session:
        import uuid
        from src.infrastructure.db.models import PayRequestModel
        from decimal import Decimal as D
        pay = PayRequestModel(
            user_id=user.telegram_id,
            plan_id=plan_info["id"],
            amount=D(context.user_data.get("final_price", plan_info.get("price_num", "0"))),
            currency="IRR",
            status="pending",
            receipt_path=save_path,
            receipt_mime=mime,
            receipt_size=file_size,
            discount_code=context.user_data.get("discount_code"),
            discount_applied=D(context.user_data.get("discount_applied", "0")),
            idempotency_key=str(uuid.uuid4()),
        )
        session.add(pay)
        await session.flush()
        pay_id = pay.id

    # اطلاع‌رسانی به سوپرادمین‌ها
    await _notify_admins_new_payment(context, pay_id, user, plan_info)

    await update.message.reply_text(t("payment_submitted", lang=lang, id=pay_id))

    # پاکسازی context
    for k in ("selected_plan", "discount_code", "discount_applied", "final_price"):
        context.user_data.pop(k, None)

    return PLAN_MENU


async def _notify_admins_new_payment(
    context: ContextTypes.DEFAULT_TYPE,
    pay_id: int,
    user: object,
    plan_info: dict,
) -> None:
    from config.settings import get_settings
    settings = get_settings()
    text = (
        f"💳 درخواست پرداخت جدید\n"
        f"کاربر: {getattr(user, 'telegram_id', '?')} (@{getattr(user, 'username', '?') or '—'})\n"
        f"پلن: {plan_info.get('name', '?')}\n"
        f"ID: #{pay_id}"
    )
    for admin_id in settings.SUPER_ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass


async def _apply_free_plan(telegram_id: int, plan_id: int, lang: str) -> None:
    from datetime import datetime, timedelta
    async with _get_session() as session:
        from sqlalchemy import update
        from src.infrastructure.db.models import UserModel, PlanModel
        plan = await session.get(PlanModel, plan_id)
        if not plan:
            return
        expires = datetime.utcnow() + timedelta(days=plan.days) if plan.days else None
        await session.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(plan_id=plan_id, plan_expires_at=expires)
        )


def _is_discount_valid(disc: object) -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    if not disc.is_active:
        return False
    if disc.expires_at and now > disc.expires_at:
        return False
    if disc.used >= disc.max_uses:
        return False
    return True


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(plan_menu, pattern="^plan_menu$"),
            CallbackQueryHandler(plan_menu, pattern="^pay_plan_menu$"),
        ],
        states={
            PLAN_MENU: [
                CallbackQueryHandler(plan_select, pattern=r"^pay_select:\d+$"),
            ],
            PLAN_SELECT: [
                CallbackQueryHandler(discount_prompt, pattern="^pay_has_discount$"),
                CallbackQueryHandler(skip_discount, pattern="^pay_no_discount$"),
            ],
            DISCOUNT_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, discount_receive),
                CallbackQueryHandler(plan_menu, pattern="^plan_menu$"),
            ],
            RECEIPT_UPLOAD: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receipt_receive),
                CallbackQueryHandler(plan_menu, pattern="^plan_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(plan_menu, pattern="^plan_menu$"),
            CallbackQueryHandler(plan_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
