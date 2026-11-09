"""معرفی دوستان — لینک، آمار، اعتبار"""
from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler
from src.bot.localization.fa import t

REFERRAL_MENU = 0

def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    if query:
        await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select, func
        from src.infrastructure.db.models import ReferralModel, WalletModel

        # تعداد معرفی‌شدگان
        result = await session.execute(
            select(func.count()).select_from(ReferralModel)
            .where(ReferralModel.referrer_id == user.telegram_id)
        )
        ref_count = result.scalar_one()

        # مجموع اعتبار کسب‌شده
        result2 = await session.execute(
            select(func.sum(ReferralModel.credit_amount))
            .where(
                ReferralModel.referrer_id == user.telegram_id,
                ReferralModel.credited == True,
            )
        )
        total_earned = result2.scalar_one() or 0

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user.telegram_id}"

    text = (
        f"🎁 <b>معرفی دوستان</b>\n\n"
        f"{t('referral_link', lang=lang, link=ref_link)}\n\n"
        f"{t('referral_count', lang=lang, count=ref_count)}\n"
        f"{t('referral_earned', lang=lang, amount=f'{total_earned:,.0f}', currency='IRR')}\n\n"
        f"💡 به ازای هر کاربری که با لینک شما ثبت‌نام کند و اولین خرید را انجام دهد، اعتبار دریافت می‌کنید."
    )

    keyboard = [
        [InlineKeyboardButton("📋 لیست معرفی‌شدگان", callback_data="ref_list")],
        [InlineKeyboardButton(t("back", lang=lang), callback_data="main_menu")],
    ]

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return REFERRAL_MENU


async def referral_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data.get("lang", "fa")
    user = context.user_data.get("db_user")
    query = update.callback_query
    await query.answer()

    async with _get_session() as session:
        from sqlalchemy import select
        from src.infrastructure.db.models import ReferralModel, UserModel
        result = await session.execute(
            select(ReferralModel)
            .where(ReferralModel.referrer_id == user.telegram_id)
            .order_by(ReferralModel.created_at.desc())
            .limit(20)
        )
        refs = result.scalars().all()

    if not refs:
        await query.edit_message_text(
            "هنوز کسی را معرفی نکرده‌اید.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(t("back", lang=lang), callback_data="referral_menu")
            ]]),
        )
        return REFERRAL_MENU

    lines = []
    for r in refs:
        status = "✅ اعتبار پرداخت‌شده" if r.credited else "⏳ منتظر خرید"
        date = r.created_at.strftime("%Y-%m-%d")
        lines.append(f"👤 کاربر {r.referred_id} | {status} | {date}")

    await query.edit_message_text(
        "📋 لیست معرفی‌شدگان:\n\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t("back", lang=lang), callback_data="referral_menu")
        ]]),
    )
    return REFERRAL_MENU


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(referral_menu, pattern="^referral_menu$")],
        states={
            REFERRAL_MENU: [
                CallbackQueryHandler(referral_list, pattern="^ref_list$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(referral_menu, pattern="^referral_menu$"),
            CallbackQueryHandler(referral_menu, pattern="^main_menu$"),
        ],
        per_user=True, per_chat=True, allow_reentry=True,
    )
