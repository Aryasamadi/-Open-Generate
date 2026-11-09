"""
پنل سوپرادمین کامل — کاربران، پلن، پرداخت، broadcast، discount، آمار، سلامت.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters,
)
from src.bot.localization.fa import t
from src.domain.entities.user import UserRole
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

(
    ADMIN_MENU, ADMIN_USER_SEARCH, ADMIN_USER_ACTION, ADMIN_BAN_REASON,
    ADMIN_BROADCAST_MSG, ADMIN_BROADCAST_CONFIRM, ADMIN_PLAN_MENU,
    ADMIN_PAYMENT_REVIEW, ADMIN_PAYMENT_DECISION, ADMIN_PAYMENT_REJECT_REASON,
    ADMIN_DISCOUNT_CODE, ADMIN_DISCOUNT_PERCENT, ADMIN_DISCOUNT_USES,
    ADMIN_ASSIGN_PLAN_SELECT, ADMIN_GLOBAL_AI,
) = range(15)


def _require_super(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = context.user_data.get("db_user")
        lang = context.user_data.get("lang", "fa")
        if not user or not user.is_super_admin:
            q = update.callback_query
            if q:
                await q.answer(t("not_authorized", lang=lang), show_alert=True)
            else:
                await update.message.reply_text(t("not_authorized", lang=lang))
            return ADMIN_MENU
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


def _gs():
    from src.infrastructure.db.session import get_session
    return get_session()


# ───────────────────────── MENU ─────────────────────────
@_require_super
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query
    if q: await q.answer()

    from src.application.admin.service import AdminService
    svc = AdminService(context.bot)
    stats = await svc.global_stats()

    kb = [
        [InlineKeyboardButton("👥 کاربران", callback_data="adm_users"),
         InlineKeyboardButton("💳 پرداخت‌ها", callback_data="adm_payments")],
        [InlineKeyboardButton("💎 پلن‌ها", callback_data="adm_plans"),
         InlineKeyboardButton("🤖 AI عمومی", callback_data="adm_global_ai")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="adm_broadcast"),
         InlineKeyboardButton("🏷️ کد تخفیف", callback_data="adm_discount")],
        [InlineKeyboardButton("💊 سلامت سیستم", callback_data="adm_health")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")],
    ]
    text = (
        f"👑 <b>پنل سوپرادمین</b>\n\n"
        f"👥 کاربران: {stats['total_users']}\n"
        f"📢 کانال‌های فعال: {stats['active_channels']}\n"
        f"📰 منتشر امروز: {stats['published_today']}\n"
        f"💳 پرداخت منتظر: {stats['pending_payments']}\n"
        f"🚫 مسدود: {stats['banned_users']}"
    )
    if q:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return ADMIN_MENU


# ───────────────────────── USER SEARCH ─────────────────────────
@_require_super
async def admin_user_search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🔍 شناسه عددی یا @username کاربر را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")]]),
    )
    return ADMIN_USER_SEARCH


@_require_super
async def admin_user_search_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    from src.application.admin.service import AdminService
    users = await AdminService(context.bot).search_users(update.message.text.strip())

    if not users:
        await update.message.reply_text("❌ کاربری پیدا نشد.")
        return ADMIN_USER_SEARCH

    for u in users[:5]:
        status = "🚫 مسدود" if u["is_banned"] else "✅ فعال"
        kb = [[
            InlineKeyboardButton(
                "🚫 مسدود" if not u["is_banned"] else "✅ رفع مسدودیت",
                callback_data=f"adm_ban:{u['telegram_id']}" if not u["is_banned"] else f"adm_unban:{u['telegram_id']}",
            ),
            InlineKeyboardButton("💎 تغییر پلن", callback_data=f"adm_assign_plan:{u['telegram_id']}"),
        ]]
        await update.message.reply_text(
            f"👤 <b>{u['first_name']}</b>\n"
            f"🆔 {u['telegram_id']} | @{u['username'] or '—'}\n"
            f"نقش: {u['role']} | پلن: {u['plan_id'] or 'رایگان'}\n"
            f"وضعیت: {status}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML",
        )
    return ADMIN_USER_SEARCH


# ───────────────────────── BAN ─────────────────────────
@_require_super
async def admin_ban_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    context.user_data["ban_target"] = int(q.data.split(":")[1])
    await q.edit_message_text(
        t("admin_ban_reason", lang=lang),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_menu")]]),
    )
    return ADMIN_BAN_REASON


@_require_super
async def admin_ban_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    target = context.user_data.pop("ban_target", None)
    reason = (update.message.text or "").strip()
    if target:
        async with _gs() as s:
            from src.infrastructure.db.repositories.user_repo import UserRepository
            await UserRepository(s).ban(target, reason, by=admin.telegram_id)
        logger.info("admin_banned_user", target=target, by=admin.telegram_id)
        await update.message.reply_text(t("admin_banned", lang=lang, id=target))
    return ADMIN_MENU


@_require_super
async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    q = update.callback_query; await q.answer()
    target = int(q.data.split(":")[1])
    async with _gs() as s:
        from src.infrastructure.db.repositories.user_repo import UserRepository
        await UserRepository(s).unban(target)
    logger.info("admin_unbanned_user", target=target, by=admin.telegram_id)
    await q.edit_message_text(t("admin_unbanned", lang=lang, id=target))
    return ADMIN_MENU


# ───────────────────────── PLAN ASSIGN ─────────────────────────
@_require_super
async def admin_assign_plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    target_id = int(q.data.split(":")[1])
    context.user_data["assign_plan_target"] = target_id

    async with _gs() as s:
        from sqlalchemy import select
        from src.infrastructure.db.models import PlanModel
        result = await s.execute(select(PlanModel).where(PlanModel.is_active == True).order_by(PlanModel.sort))
        plans = result.scalars().all()

    kb = [[InlineKeyboardButton(f"{'🆓' if p.is_free else '💎'} {p.name}", callback_data=f"adm_do_assign:{p.id}")] for p in plans]
    kb.append([InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_menu")])
    await q.edit_message_text(f"💎 انتخاب پلن برای کاربر {target_id}:", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_ASSIGN_PLAN_SELECT


@_require_super
async def admin_do_assign_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    q = update.callback_query; await q.answer()
    plan_id = int(q.data.split(":")[1])
    target = context.user_data.pop("assign_plan_target", None)
    if target:
        from src.application.admin.service import AdminService
        ok = await AdminService(context.bot).assign_plan(target, plan_id, admin.telegram_id)
        await q.edit_message_text(f"{'✅ پلن اختصاص یافت.' if ok else '❌ خطا.'}")
    return ADMIN_MENU


# ───────────────────────── PAYMENTS ─────────────────────────
@_require_super
async def admin_payment_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()

    async with _gs() as s:
        from sqlalchemy import select
        from src.infrastructure.db.models import PayRequestModel
        result = await s.execute(
            select(PayRequestModel).where(PayRequestModel.status == "pending")
            .order_by(PayRequestModel.created_at).limit(15)
        )
        pays = result.scalars().all()

    if not pays:
        await q.edit_message_text(
            "✅ هیچ پرداخت منتظری وجود ندارد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")]]),
        )
        return ADMIN_MENU

    kb = [[InlineKeyboardButton(
        f"#{p.id} — {p.user_id} — {p.amount:,.0f} {p.currency}",
        callback_data=f"adm_pay_view:{p.id}",
    )] for p in pays]
    kb.append([InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")])
    await q.edit_message_text(
        f"💳 <b>پرداخت‌های منتظر ({len(pays)})</b>",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML",
    )
    return ADMIN_PAYMENT_REVIEW


@_require_super
async def admin_pay_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    pay_id = int(q.data.split(":")[1])

    async with _gs() as s:
        from src.infrastructure.db.models import PayRequestModel, PlanModel
        pay = await s.get(PayRequestModel, pay_id)
        plan = await s.get(PlanModel, pay.plan_id) if pay else None

    if not pay:
        await q.edit_message_text(t("error_generic", lang=lang)); return ADMIN_MENU

    context.user_data["review_pay_id"] = pay_id
    kb = [
        [InlineKeyboardButton("✅ تأیید", callback_data=f"adm_pay_approve:{pay_id}"),
         InlineKeyboardButton("❌ رد", callback_data=f"adm_pay_reject:{pay_id}")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="adm_payments")],
    ]
    text = (
        f"💳 درخواست <b>#{pay_id}</b>\n"
        f"کاربر: {pay.user_id}\n"
        f"پلن: {plan.name if plan else '?'}\n"
        f"مبلغ: {pay.amount:,.0f} {pay.currency}\n"
        f"تاریخ: {pay.created_at.strftime('%Y-%m-%d %H:%M') if pay.created_at else '—'}\n"
        f"رسید: {'✅ دارد' if pay.receipt_path else '❌ ندارد'}"
    )

    # ارسال رسید اگر وجود دارد
    if pay.receipt_path:
        try:
            import os
            if os.path.exists(pay.receipt_path):
                await q.message.reply_document(
                    document=open(pay.receipt_path, "rb"),
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="HTML",
                )
                return ADMIN_PAYMENT_DECISION
        except Exception:
            pass

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return ADMIN_PAYMENT_DECISION


@_require_super
async def admin_pay_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    q = update.callback_query; await q.answer()
    pay_id = int(q.data.split(":")[1])

    # double-confirm
    kb = [
        [InlineKeyboardButton("✅ بله، تأیید می‌کنم", callback_data=f"adm_pay_approve_final:{pay_id}"),
         InlineKeyboardButton("❌ انصراف", callback_data="adm_payments")],
    ]
    await q.edit_message_text(
        f"⚠️ تأیید پرداخت #{pay_id}؟\nاین عمل پلن کاربر را فعال می‌کند.",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ADMIN_PAYMENT_DECISION


@_require_super
async def admin_pay_approve_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    q = update.callback_query; await q.answer()
    pay_id = int(q.data.split(":")[1])

    from src.application.payment.service import PaymentService
    ok = await PaymentService().approve(pay_id, admin.telegram_id)
    # referral credit پس از اولین خرید
    if ok:
        async with _gs() as s:
            from src.infrastructure.db.models import PayRequestModel
            pay = await s.get(PayRequestModel, pay_id)
            if pay:
                from src.application.referral.service import ReferralService
                await ReferralService().credit_referrer_on_first_purchase(pay.user_id)

    await q.edit_message_text(f"{'✅ پرداخت تأیید و پلن فعال شد.' if ok else '❌ خطا.'}")
    return ADMIN_MENU


@_require_super
async def admin_pay_reject_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    pay_id = int(q.data.split(":")[1])
    context.user_data["reject_pay_id"] = pay_id
    await q.edit_message_text(
        f"❌ دلیل رد درخواست #{pay_id}:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_payments")]]),
    )
    return ADMIN_PAYMENT_REJECT_REASON


@_require_super
async def admin_pay_reject_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    pay_id = context.user_data.pop("reject_pay_id", None)
    reason = (update.message.text or "").strip()
    if pay_id:
        from src.application.payment.service import PaymentService
        await PaymentService().reject(pay_id, admin.telegram_id, reason)
        await update.message.reply_text(f"✅ پرداخت #{pay_id} رد شد.")
    return ADMIN_MENU


# ───────────────────────── BROADCAST ─────────────────────────
@_require_super
async def admin_broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        t("admin_broadcast_message", lang=lang),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_menu")]]),
    )
    return ADMIN_BROADCAST_MSG


@_require_super
async def admin_broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    text = (update.message.text or "").strip()
    if not text:
        return ADMIN_BROADCAST_MSG

    # شمارش کاربران
    async with _gs() as s:
        from sqlalchemy import select, func
        from src.infrastructure.db.models import UserModel
        count = (await s.execute(select(func.count()).select_from(UserModel).where(UserModel.is_banned == False))).scalar_one()

    context.user_data["broadcast_text"] = text
    kb = [
        [InlineKeyboardButton(t("admin_broadcast_confirm", lang=lang), callback_data="adm_broadcast_confirm"),
         InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_menu")],
    ]
    await update.message.reply_text(
        t("admin_broadcast_preview", lang=lang, text=text[:300], count=count),
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML",
    )
    return ADMIN_BROADCAST_CONFIRM


@_require_super
async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    q = update.callback_query; await q.answer("⏳ در حال ارسال...")
    text = context.user_data.pop("broadcast_text", "")

    from src.application.admin.service import AdminService
    result = await AdminService(context.bot).broadcast(text, sent_by=admin.telegram_id)
    await q.edit_message_text(
        t("admin_broadcast_sent", lang=lang, ok=result["ok"], fail=result["fail"])
    )
    return ADMIN_MENU


# ───────────────────────── DISCOUNT ─────────────────────────
@_require_super
async def admin_discount_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()

    async with _gs() as s:
        from sqlalchemy import select
        from src.infrastructure.db.models import DiscountModel
        result = await s.execute(select(DiscountModel).where(DiscountModel.is_active == True).order_by(DiscountModel.id.desc()).limit(10))
        discs = result.scalars().all()

    lines = [f"🏷️ <b>کدهای تخفیف فعال</b>\n"]
    for d in discs:
        exp = d.expires_at.strftime("%Y-%m-%d") if d.expires_at else "بدون انقضا"
        lines.append(f"<code>{d.code}</code> — {d.percent}٪ — {d.used}/{d.max_uses} بار — تا {exp}")

    kb = [
        [InlineKeyboardButton("➕ ایجاد کد تخفیف", callback_data="adm_discount_new")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")],
    ]
    await q.edit_message_text("\n".join(lines) or "هیچ کدی وجود ندارد.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return ADMIN_MENU


@_require_super
async def admin_discount_new_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🏷️ کد تخفیف جدید را وارد کنید (فقط حروف و اعداد، مثال: SAVE20):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("cancel", lang=lang), callback_data="adm_discount")]]),
    )
    context.user_data["discount_step"] = "code"
    return ADMIN_DISCOUNT_CODE


@_require_super
async def admin_discount_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    admin = context.user_data.get("db_user")
    step = context.user_data.get("discount_step")
    text = (update.message.text or "").strip()

    if step == "code":
        context.user_data["new_disc_code"] = text.upper()
        await update.message.reply_text("💯 درصد تخفیف را وارد کنید (مثال: 20):")
        context.user_data["discount_step"] = "percent"
        return ADMIN_DISCOUNT_PERCENT
    elif step == "percent":
        try:
            pct = float(text)
            assert 0 < pct <= 100
        except (ValueError, AssertionError):
            await update.message.reply_text("❌ عدد معتبر بین ۱ تا ۱۰۰ وارد کنید.")
            return ADMIN_DISCOUNT_PERCENT
        context.user_data["new_disc_percent"] = pct
        await update.message.reply_text("🔢 حداکثر تعداد استفاده (مثال: 50):")
        context.user_data["discount_step"] = "uses"
        return ADMIN_DISCOUNT_USES
    elif step == "uses":
        try:
            uses = int(text); assert uses > 0
        except (ValueError, AssertionError):
            await update.message.reply_text("❌ عدد صحیح مثبت وارد کنید.")
            return ADMIN_DISCOUNT_USES

        from decimal import Decimal
        from src.application.admin.service import AdminService
        ok = await AdminService(context.bot).create_discount(
            code=context.user_data.pop("new_disc_code"),
            percent=Decimal(str(context.user_data.pop("new_disc_percent"))),
            max_uses=uses,
            expires_in_days=30,
            created_by=admin.telegram_id,
        )
        context.user_data.pop("discount_step", None)
        await update.message.reply_text("✅ کد تخفیف ایجاد شد." if ok else "❌ خطا.")
        return ADMIN_MENU
    return ADMIN_MENU


# ───────────────────────── GLOBAL AI ─────────────────────────
@_require_super
async def admin_global_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()

    async with _gs() as s:
        from sqlalchemy import select
        from src.infrastructure.db.models import AIModelModel
        result = await s.execute(select(AIModelModel).where(AIModelModel.is_global == True).order_by(AIModelModel.priority.desc()))
        models = result.scalars().all()

    lines = ["🤖 <b>مدل‌های AI عمومی</b>\n"]
    for m in models:
        circuit = "🔴 circuit open" if m.circuit_open else "🟢"
        lines.append(f"{circuit} {m.display_name} | {m.provider} | priority={m.priority}")

    kb = [
        [InlineKeyboardButton("➕ افزودن مدل عمومی", callback_data="adm_add_global_ai")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")],
    ]
    await q.edit_message_text("\n".join(lines) or "هیچ مدلی تعریف نشده.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return ADMIN_GLOBAL_AI


# ───────────────────────── HEALTH ─────────────────────────
@_require_super
async def admin_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    q = update.callback_query; await q.answer()

    from src.runtime.health import get_health
    data = await get_health()
    overall = "✅" if data["status"] == "ok" else "⚠️"
    sched = data["checks"]["scheduler"]
    db    = data["checks"]["db"]

    text = (
        f"💊 <b>وضعیت سیستم</b> {overall}\n\n"
        f"DB: {'✅' if db['status'] == 'ok' else '❌ ' + db.get('detail', '')}\n"
        f"Scheduler: {'✅ ' + str(sched.get('age_seconds', '?')) + 's' if sched['status'] == 'ok' else '❌ ' + sched['status']}\n"
        f"UTC: {data['timestamp']}"
    )
    kb = [
        [InlineKeyboardButton("🔄 بررسی مجدد", callback_data="adm_health"),
         InlineKeyboardButton(t("back", lang=lang), callback_data="adm_menu")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return ADMIN_MENU


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_menu, pattern="^(admin_menu|adm_menu)$"),
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_user_search_prompt, pattern="^adm_users$"),
                CallbackQueryHandler(admin_payment_list,       pattern="^adm_payments$"),
                CallbackQueryHandler(admin_broadcast_prompt,   pattern="^adm_broadcast$"),
                CallbackQueryHandler(admin_discount_menu,      pattern="^adm_discount$"),
                CallbackQueryHandler(admin_global_ai,          pattern="^adm_global_ai$"),
                CallbackQueryHandler(admin_health,             pattern="^adm_health$"),
                CallbackQueryHandler(admin_ban_prompt,         pattern=r"^adm_ban:\d+$"),
                CallbackQueryHandler(admin_unban,              pattern=r"^adm_unban:\d+$"),
                CallbackQueryHandler(admin_assign_plan_menu,   pattern=r"^adm_assign_plan:\d+$"),
                CallbackQueryHandler(admin_menu,               pattern="^adm_plans$"),
            ],
            ADMIN_USER_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_user_search_receive),
                CallbackQueryHandler(admin_menu, pattern="^adm_menu$"),
            ],
            ADMIN_BAN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_receive),
                CallbackQueryHandler(admin_menu, pattern="^adm_menu$"),
            ],
            ADMIN_BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_receive),
                CallbackQueryHandler(admin_menu, pattern="^adm_menu$"),
            ],
            ADMIN_BROADCAST_CONFIRM: [
                CallbackQueryHandler(admin_broadcast_confirm, pattern="^adm_broadcast_confirm$"),
                CallbackQueryHandler(admin_menu,              pattern="^adm_menu$"),
            ],
            ADMIN_ASSIGN_PLAN_SELECT: [
                CallbackQueryHandler(admin_do_assign_plan, pattern=r"^adm_do_assign:\d+$"),
                CallbackQueryHandler(admin_menu,           pattern="^adm_menu$"),
            ],
            ADMIN_PAYMENT_REVIEW: [
                CallbackQueryHandler(admin_pay_view,    pattern=r"^adm_pay_view:\d+$"),
                CallbackQueryHandler(admin_menu,        pattern="^adm_menu$"),
            ],
            ADMIN_PAYMENT_DECISION: [
                CallbackQueryHandler(admin_pay_approve,       pattern=r"^adm_pay_approve:\d+$"),
                CallbackQueryHandler(admin_pay_approve_final, pattern=r"^adm_pay_approve_final:\d+$"),
                CallbackQueryHandler(admin_pay_reject_prompt, pattern=r"^adm_pay_reject:\d+$"),
                CallbackQueryHandler(admin_payment_list,      pattern="^adm_payments$"),
                CallbackQueryHandler(admin_menu,              pattern="^adm_menu$"),
            ],
            ADMIN_PAYMENT_REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_pay_reject_receive),
                CallbackQueryHandler(admin_payment_list, pattern="^adm_payments$"),
            ],
            ADMIN_DISCOUNT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_step),
                CallbackQueryHandler(admin_discount_menu, pattern="^adm_discount$"),
            ],
            ADMIN_DISCOUNT_PERCENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_step),
            ],
            ADMIN_DISCOUNT_USES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_discount_step),
            ],
            ADMIN_GLOBAL_AI: [
                CallbackQueryHandler(admin_menu, pattern="^adm_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_menu, pattern="^(admin_menu|adm_menu|main_menu)$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
