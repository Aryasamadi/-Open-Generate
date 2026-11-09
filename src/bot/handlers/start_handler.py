"""
Handler /start با deep link کامل:
- ref_<telegram_id>  → ثبت referral
- claim_<token>      → انتقال مالکیت کانال
- پیش‌نمایش منو اصلی
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

from src.bot.localization.fa import t
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = context.user_data.get("db_user")
    lang = context.user_data.get("lang", "fa")
    tg_user = update.effective_user

    # deep link
    args = context.args or []
    if args:
        token = args[0]
        handled = await _handle_deeplink(update, context, token, lang, user)
        if handled:
            return

    # پلن رایگان برای کاربر جدید
    if user:
        from src.application.user.service import UserService
        await UserService().handle_new_user(tg_user.id)

    name = tg_user.first_name
    text = t("welcome", lang=lang, name=name)
    keyboard = _main_menu_keyboard(lang, user)
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def _handle_deeplink(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    token: str,
    lang: str,
    user: object,
) -> bool:
    """
    برگرداندن True اگر deep link پردازش شد.
    """
    tg_user = update.effective_user

    # --- referral: ref_<telegram_id>
    if token.startswith("ref_"):
        try:
            referrer_id = int(token[4:])
        except ValueError:
            return False

        if referrer_id != tg_user.id:
            from src.application.user.service import UserService
            await UserService().handle_new_user(tg_user.id, referred_by=referrer_id)
            logger.info("referral_deeplink", referrer=referrer_id, referred=tg_user.id)
        else:
            logger.warning("self_referral_deeplink_blocked", user_id=tg_user.id)

        # ادامه به منوی اصلی
        return False

    # --- channel claim: claim_<token>
    if token.startswith("claim_"):
        claim_token = token[6:]
        await _handle_channel_claim(update, context, claim_token, lang, user)
        return True

    # --- deeplink عمومی از DB
    from datetime import datetime
    async with _get_session() as session:
        from sqlalchemy import select, update as sql_update
        from src.infrastructure.db.models import DeeplinkModel
        result = await session.execute(
            select(DeeplinkModel).where(
                DeeplinkModel.token == token,
                DeeplinkModel.used_at.is_(None),
                DeeplinkModel.expires_at > datetime.utcnow(),
            )
        )
        deeplink = result.scalar_one_or_none()

        if not deeplink:
            await update.message.reply_text("🔗 لینک نامعتبر یا منقضی شده است.")
            return True

        # mark used
        await session.execute(
            sql_update(DeeplinkModel)
            .where(DeeplinkModel.id == deeplink.id)
            .values(used_at=datetime.utcnow(), used_by=tg_user.id)
        )

    action = deeplink.action
    payload = deeplink.payload

    if action == "plan_promo":
        plan_id = payload.get("plan_id")
        await update.message.reply_text(
            f"🎁 لینک تخفیف پلن دریافت شد!\nبرای خرید /start را بزنید."
        )
        return True

    return False


async def _handle_channel_claim(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    claim_token: str,
    lang: str,
    user: object,
) -> None:
    """انتقال مالکیت کانال با توکن"""
    if not user:
        await update.message.reply_text(t("error_generic", lang=lang))
        return

    from datetime import datetime
    async with _get_session() as session:
        from sqlalchemy import select, update as sql_update
        from src.infrastructure.db.models import ChannelTokenModel, ChannelModel

        result = await session.execute(
            select(ChannelTokenModel).where(
                ChannelTokenModel.token == claim_token,
                ChannelTokenModel.used == False,
                ChannelTokenModel.expires_at > datetime.utcnow(),
            )
        )
        ch_token = result.scalar_one_or_none()

        if not ch_token:
            await update.message.reply_text("🔗 توکن نامعتبر یا منقضی شده است.")
            return

        # انتقال مالکیت
        await session.execute(
            sql_update(ChannelModel)
            .where(ChannelModel.id == ch_token.channel_id)
            .values(owner_id=user.telegram_id)
        )
        await session.execute(
            sql_update(ChannelTokenModel)
            .where(ChannelTokenModel.id == ch_token.id)
            .values(used=True, claimed_by=user.telegram_id)
        )

    logger.info(
        "channel_claimed",
        channel_id=ch_token.channel_id,
        new_owner=user.telegram_id,
    )
    await update.message.reply_text("✅ مالکیت کانال با موفقیت منتقل شد.")


def _main_menu_keyboard(lang: str, user: object) -> list[list[InlineKeyboardButton]]:
    from src.domain.entities.user import UserRole
    role = getattr(user, "role", UserRole.USER) if user else UserRole.USER

    rows = [
        [InlineKeyboardButton("📢 " + t("channel_menu", lang=lang), callback_data="channel_menu")],
        [InlineKeyboardButton("🤖 " + t("ai_menu", lang=lang), callback_data="ai_menu")],
        [InlineKeyboardButton("💎 " + t("plan_menu", lang=lang), callback_data="plan_menu")],
        [InlineKeyboardButton("💰 " + t("wallet_menu", lang=lang), callback_data="wallet_menu")],
        [InlineKeyboardButton("📊 " + t("stats_menu", lang=lang), callback_data="stats_menu")],
        [InlineKeyboardButton("🎁 " + t("referral_menu", lang=lang), callback_data="referral_menu")],
        [InlineKeyboardButton("🆘 " + t("support_menu", lang=lang), callback_data="support_menu")],
        [InlineKeyboardButton("🌐 " + t("language_menu", lang=lang), callback_data="language_menu")],
    ]
    if role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        rows.append(
            [InlineKeyboardButton("👑 " + t("admin_menu", lang=lang), callback_data="admin_menu")]
        )
    return rows


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def build_handler() -> CommandHandler:
    return CommandHandler("start", start_command)
