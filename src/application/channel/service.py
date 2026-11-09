"""
سرویس کانال — verify، trigger pipeline، آمار روزانه.
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from src.application.content.pipeline import ContentPipeline
from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ChannelService:

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._pipeline = ContentPipeline()

    async def verify_bot_admin(self, channel_telegram_id: int) -> bool:
        """بررسی واقعی مجوز ادمین ربات در کانال"""
        try:
            bot_user = await self._bot.get_me()
            member = await self._bot.get_chat_member(channel_telegram_id, bot_user.id)
            return getattr(member, "can_post_messages", False)
        except TelegramError as exc:
            logger.warning(
                "channel_verify_failed",
                channel_id=channel_telegram_id,
                error=str(exc)[:200],
            )
            return False

    async def trigger_pipeline(self, channel_id: int) -> dict:
        """اجرای دستی pipeline برای یک کانال"""
        async with get_session() as session:
            from src.infrastructure.db.repositories.channel_repo import ChannelRepository
            channel = await ChannelRepository(session).get_by_id(channel_id)

        if not channel or not channel.is_ready:
            return {"error": "کانال آماده نیست"}

        result = await self._pipeline.run(channel)
        return {
            "fetched": result.fetched,
            "published": result.published,
            "queued_review": result.queued_review,
            "errors": len(result.errors),
        }

    async def get_stats(self, channel_id: int) -> dict:
        """آمار امروز و کلی کانال"""
        today = date.today().isoformat()

        async with get_session() as session:
            from sqlalchemy import select, func
            from src.infrastructure.db.models import ArticleModel

            # پست‌های منتشرشده امروز
            result = await session.execute(
                select(func.count()).select_from(ArticleModel).where(
                    ArticleModel.channel_id == channel_id,
                    ArticleModel.status == "published",
                    func.date(ArticleModel.published_at_actual) == today,
                )
            )
            today_published = result.scalar_one()

            # کل منتشرشده
            result2 = await session.execute(
                select(func.count()).select_from(ArticleModel).where(
                    ArticleModel.channel_id == channel_id,
                    ArticleModel.status == "published",
                )
            )
            total_published = result2.scalar_one()

            # در صف بازبینی
            result3 = await session.execute(
                select(func.count()).select_from(ArticleModel).where(
                    ArticleModel.channel_id == channel_id,
                    ArticleModel.status == "pending_review",
                )
            )
            pending_review = result3.scalar_one()

            # مقالات رد‌شده
            result4 = await session.execute(
                select(func.count()).select_from(ArticleModel).where(
                    ArticleModel.channel_id == channel_id,
                    ArticleModel.status.in_(["rejected", "filtered", "duplicate"]),
                )
            )
            filtered = result4.scalar_one()

        return {
            "today_published": today_published,
            "total_published": total_published,
            "pending_review": pending_review,
            "filtered": filtered,
        }

    async def check_all_channels_bot_status(self) -> list[dict]:
        """بررسی دوره‌ای مجوز ادمین ربات در همه کانال‌ها"""
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import ChannelModel
            result = await session.execute(
                select(ChannelModel).where(ChannelModel.is_active == True)
            )
            channels = result.scalars().all()

        issues = []
        for ch in channels:
            is_admin = await self.verify_bot_admin(ch.telegram_id)
            if not is_admin and ch.bot_is_admin:
                # ربات از کانال خارج شده — به‌روزرسانی و notification
                async with get_session() as session:
                    from sqlalchemy import update
                    from src.infrastructure.db.models import ChannelModel, NotificationModel
                    await session.execute(
                        update(ChannelModel)
                        .where(ChannelModel.id == ch.id)
                        .values(bot_is_admin=False)
                    )
                    session.add(NotificationModel(
                        user_id=ch.owner_id,
                        notification_type="channel_bot_removed",
                        payload={"channel_title": ch.title, "channel_id": ch.id},
                        next_attempt_at=datetime.utcnow(),
                    ))
                issues.append({"channel_id": ch.id, "title": ch.title})
                logger.warning("bot_removed_from_channel", channel_id=ch.id)

        return issues
