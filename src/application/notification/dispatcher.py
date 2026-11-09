"""
Dispatcher اعلان‌ها — durable، retry با exponential backoff، dead-letter.
شکست تحویل باید قابل بازیابی باشد.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from telegram import Bot
from telegram.error import Forbidden, TelegramError

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class NotificationDispatcher:

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def dispatch_pending(self, limit: int = 20) -> dict[str, int]:
        """ارسال اعلان‌های معوق — باید در loop اجرا شود"""
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import NotificationModel
            result = await session.execute(
                select(NotificationModel).where(
                    NotificationModel.delivered_at.is_(None),
                    NotificationModel.is_dead == False,
                    NotificationModel.next_attempt_at <= datetime.utcnow(),
                ).limit(limit)
            )
            notifications = result.scalars().all()

        stats = {"delivered": 0, "failed": 0, "dead": 0}

        for notif in notifications:
            success = await self._deliver(notif)
            if success:
                stats["delivered"] += 1
            elif notif.attempts >= notif.max_attempts:
                await self._mark_dead(notif.id)
                stats["dead"] += 1
            else:
                stats["failed"] += 1

        return stats

    async def _deliver(self, notif: object) -> bool:
        notif_type = notif.notification_type
        payload = notif.payload
        user_id = notif.user_id

        try:
            text = self._build_message(notif_type, payload)
            if not text:
                logger.warning("unknown_notification_type", type=notif_type)
                await self._mark_delivered(notif.id)
                return True

            await self._bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
            )
            await self._mark_delivered(notif.id)
            logger.info("notification_delivered", notif_id=notif.id, type=notif_type)
            return True

        except Forbidden:
            # کاربر ربات را block کرده — dead letter
            logger.warning("notification_user_blocked", notif_id=notif.id, user_id=user_id)
            await self._mark_dead(notif.id)
            return False

        except TelegramError as exc:
            logger.warning(
                "notification_delivery_failed",
                notif_id=notif.id,
                error=str(exc)[:200],
            )
            await self._mark_retry(notif.id, notif.attempts + 1)
            return False

        except Exception as exc:
            logger.error("notification_unexpected_error", notif_id=notif.id, error=str(exc))
            await self._mark_retry(notif.id, notif.attempts + 1)
            return False

    def _build_message(self, notif_type: str, payload: dict) -> Optional[str]:
        """تبدیل type + payload به متن قابل ارسال"""
        if notif_type == "payment_approved":
            return (
                f"✅ <b>پرداخت تأیید شد</b>\n\n"
                f"پلن <b>{payload.get('plan_name', '?')}</b> فعال شد.\n"
                f"کد پیگیری: #{payload.get('pay_id', '?')}"
            )
        elif notif_type == "payment_rejected":
            return (
                f"❌ <b>پرداخت رد شد</b>\n\n"
                f"کد پیگیری: #{payload.get('pay_id', '?')}\n"
                f"دلیل: {payload.get('reason', '—')}"
            )
        elif notif_type == "plan_expiring":
            return (
                f"⏰ <b>پلن شما در حال انقضاست</b>\n\n"
                f"پلن شما {payload.get('days', '?')} روز دیگر منقضی می‌شود.\n"
                f"برای تمدید /start را بزنید."
            )
        elif notif_type == "plan_expired":
            return (
                "⚠️ <b>پلن شما منقضی شد</b>\n\n"
                "برای خرید پلن جدید /start را بزنید."
            )
        elif notif_type == "referral_credited":
            amount = payload.get("amount", "0")
            currency = payload.get("currency", "IRR")
            return (
                f"🎁 <b>اعتبار معرفی واریز شد</b>\n\n"
                f"مبلغ {int(float(amount)):,} {currency} به کیف پول شما اضافه شد."
            )
        elif notif_type == "support_reply":
            return (
                f"💬 <b>پاسخ تیکت #{payload.get('ticket_id', '?')}</b>\n\n"
                f"{payload.get('message', '—')}"
            )
        elif notif_type == "channel_bot_removed":
            return (
                f"⚠️ <b>ربات از کانال خارج شد</b>\n\n"
                f"کانال <b>{payload.get('channel_title', '?')}</b>\n"
                f"لطفاً ربات را دوباره ادمین کنید."
            )
        elif notif_type == "ai_provider_fail":
            return (
                f"🤖 <b>خطا در AI</b>\n\n"
                f"مدل «{payload.get('model_name', '?')}» پاسخ نداد.\n"
                f"لطفاً API key را بررسی کنید."
            )
        elif notif_type == "system_alert":
            return (
                f"🚨 <b>هشدار سیستمی</b>\n\n"
                f"{payload.get('message', '—')}"
            )
        return None

    async def _mark_delivered(self, notif_id: int) -> None:
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import NotificationModel
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notif_id)
                .values(
                    delivered_at=datetime.utcnow(),
                    attempts=NotificationModel.attempts + 1,
                )
            )

    async def _mark_retry(self, notif_id: int, attempt: int) -> None:
        """backoff: 1min، 2min، 4min، 8min، 16min..."""
        backoff_seconds = min(60 * (2 ** (attempt - 1)), 3600)
        next_try = datetime.utcnow() + timedelta(seconds=backoff_seconds)
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import NotificationModel
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notif_id)
                .values(attempts=attempt, next_attempt_at=next_try)
            )

    async def _mark_dead(self, notif_id: int) -> None:
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import NotificationModel
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notif_id)
                .values(is_dead=True)
            )
        logger.warning("notification_dead_lettered", notif_id=notif_id)
