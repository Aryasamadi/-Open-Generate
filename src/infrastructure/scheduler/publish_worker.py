"""
Publish Worker — هر N ثانیه مقالات approved را از DB می‌خواند و publish می‌کند.
Idempotency: اگر telegram_message_id دارد، دوباره ارسال نمی‌شود.
Quiet hours: بررسی می‌شود.
Daily cap: بررسی می‌شود.
Rate limit: حداکثر ۳۰ msg/s به تلگرام.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from telegram import Bot

logger = get_logger(__name__)

_PUBLISH_INTERVAL = 15      # ثانیه
_BATCH_PER_CYCLE  = 10      # حداکثر مقاله در هر دور
_TG_DELAY         = 0.05    # 50ms بین پیام‌ها → ~20/s well under 30/s limit


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


class PublishWorker:

    def __init__(self, bot: "Bot") -> None:
        self._bot = bot
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        logger.info("publish_worker_started")
        while self._running:
            try:
                await self._cycle()
            except Exception as exc:
                logger.error("publish_worker_cycle_error", error=str(exc))
            await asyncio.sleep(_PUBLISH_INTERVAL)

    def stop(self) -> None:
        self._running = False

    async def _cycle(self) -> None:
        """یک دور کامل: واکشی → بررسی → ارسال → ثبت"""
        async with _get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import ArticleModel, ChannelModel
            # مقالات approved که هنوز publish نشدند
            result = await session.execute(
                select(ArticleModel)
                .where(
                    ArticleModel.status == "approved",
                    ArticleModel.telegram_message_id.is_(None),
                )
                .order_by(ArticleModel.score.desc(), ArticleModel.created_at)
                .limit(_BATCH_PER_CYCLE)
            )
            articles = result.scalars().all()

        if not articles:
            return

        logger.debug("publish_cycle", batch=len(articles))

        for article in articles:
            try:
                await self._publish_one(article)
                await asyncio.sleep(_TG_DELAY)
            except Exception as exc:
                logger.error("publish_one_error", article_id=article.id, error=str(exc)[:200])

    async def _publish_one(self, article) -> None:
        """ارسال یک مقاله — با بررسی کامل constraints"""
        channel_id = article.channel_id

        # واکشی کانال و تنظیمات
        async with _get_session() as session:
            from src.infrastructure.db.repositories.channel_repo import ChannelRepository
            channel = await ChannelRepository(session).get_by_id(channel_id)

        if not channel or not channel.is_ready:
            await self._fail_article(article.id, "channel_not_ready", permanent=False)
            return

        s = channel.settings

        # quiet hours
        if self._in_quiet_hours(s):
            logger.debug("quiet_hours_skip", channel_id=channel_id)
            return

        # daily cap
        from src.application.subscription.service import SubscriptionService
        can_post, reason = await SubscriptionService().can_post_today(
            channel.owner_id, channel_id
        )
        if not can_post:
            logger.debug("daily_cap_reached", channel_id=channel_id, reason=reason)
            return

        # post_html نباشد و title هم خالی باشد → رد
        if not (article.post_html or article.title or "").strip():
            await self._fail_article(article.id, "empty_post_html", permanent=True)
            return

        # ارسال از طریق publisher جدید (Rich Message با html_formatter)
        from src.infrastructure.telegram.publisher import TelegramPublisher
        publisher = TelegramPublisher(self._bot)
        result = await publisher.publish(article, channel.telegram_id, s)

        if result.success:
            await self._mark_published(
                article.id, result.message_id, channel.owner_id,
                extra_ids=result.extra_message_ids,
            )
        elif result.is_permanent:
            await self._fail_article(article.id, result.error or "permanent_error", permanent=True)
            if result.error and any(w in result.error for w in ("ادمین", "admin", "removed")):
                await self._notify_bot_removed(channel)
        else:
            # موقت — retry بعداً
            await self._increment_attempts(article.id, result.error or "")

    async def _mark_published(
        self, article_id: int, message_id: int, owner_id: int,
        extra_ids: list[int] | None = None,
    ) -> None:
        async with _get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import ArticleModel, PubJournalModel
            await session.execute(
                update(ArticleModel).where(ArticleModel.id == article_id).values(
                    status="published",
                    telegram_message_id=message_id,
                    published_at_actual=datetime.utcnow(),
                    publish_attempts=ArticleModel.publish_attempts + 1,
                )
            )
            async with _get_session() as s2:
                art = await s2.get(ArticleModel, article_id)
                s2.add(PubJournalModel(
                    article_id=article_id,
                    channel_id=art.channel_id if art else 0,
                    attempt=(art.publish_attempts if art else 1),
                    status="published",
                    telegram_message_id=message_id,
                ))

        # usage tracking
        from src.application.subscription.service import SubscriptionService
        await SubscriptionService().track_usage(owner_id, posts=1)
        logger.info(
            "article_published_ok",
            article_id=article_id,
            msg_id=message_id,
            continuations=len(extra_ids or []),
        )

    async def _fail_article(self, article_id: int, error: str, permanent: bool) -> None:
        async with _get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import ArticleModel
            new_status = "failed" if permanent else "approved"  # approved بماند برای retry
            values = {
                "last_publish_error": error[:500],
                "publish_attempts": ArticleModel.publish_attempts + 1,
            }
            if permanent:
                values["status"] = "failed"
            await session.execute(
                update(ArticleModel).where(ArticleModel.id == article_id).values(**values)
            )
        logger.warning("article_publish_failed", article_id=article_id, permanent=permanent, error=error[:100])

    async def _increment_attempts(self, article_id: int, error: str) -> None:
        async with _get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import ArticleModel
            # بعد از ۵ تلاش → failed
            art = await session.get(ArticleModel, article_id)
            if art and art.publish_attempts >= 5:
                await session.execute(
                    update(ArticleModel).where(ArticleModel.id == article_id)
                    .values(status="failed", last_publish_error=error[:500])
                )
            else:
                await session.execute(
                    update(ArticleModel).where(ArticleModel.id == article_id)
                    .values(
                        publish_attempts=ArticleModel.publish_attempts + 1,
                        last_publish_error=error[:500],
                    )
                )

    async def _notify_bot_removed(self, channel) -> None:
        async with _get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import ChannelModel, NotificationModel
            await session.execute(
                update(ChannelModel).where(ChannelModel.id == channel.id)
                .values(bot_is_admin=False)
            )
            session.add(NotificationModel(
                user_id=channel.owner_id,
                notification_type="channel_bot_removed",
                payload={"channel_title": channel.title, "channel_id": channel.id},
                next_attempt_at=datetime.utcnow(),
            ))

    def _in_quiet_hours(self, settings) -> bool:
        """بررسی quiet hours با timezone صحیح"""
        if not (settings.quiet_start and settings.quiet_end):
            return False
        try:
            import pytz
            tz = pytz.timezone(settings.timezone or "UTC")
            now_local = datetime.now(tz).strftime("%H:%M")
            start, end = settings.quiet_start, settings.quiet_end
            if start <= end:
                return start <= now_local <= end
            return now_local >= start or now_local <= end
        except Exception:
            return False
