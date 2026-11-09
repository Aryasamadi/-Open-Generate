"""
سرویس اشتراک — enforcement محدودیت‌های پلن، usage tracking، بررسی انقضا.
تمام محدودیت‌ها در backend enforce می‌شوند؛ پنهان کردن دکمه کافی نیست.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# محدودیت پلن رایگان
FREE_PLAN = {
    "daily_posts": 3,
    "max_sources": 2,
    "max_channels": 1,
    "daily_tests": 2,
}


class SubscriptionService:

    async def get_plan_limits(self, telegram_id: int) -> dict:
        """محدودیت‌های فعلی کاربر — از DB نه از cache"""
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel, PlanModel

            result = await session.execute(
                select(UserModel).where(UserModel.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return FREE_PLAN.copy()

            # انقضا
            if user.plan_expires_at and datetime.utcnow() > user.plan_expires_at:
                return FREE_PLAN.copy()

            if not user.plan_id:
                return FREE_PLAN.copy()

            plan = await session.get(PlanModel, user.plan_id)
            if not plan:
                return FREE_PLAN.copy()

            return {
                "daily_posts": plan.daily_posts,
                "max_sources": plan.max_sources,
                "max_channels": plan.max_channels,
                "daily_tests": plan.daily_tests,
            }

    async def can_add_channel(self, telegram_id: int) -> tuple[bool, str]:
        """آیا کاربر می‌تواند کانال جدید اضافه کند؟"""
        limits = await self.get_plan_limits(telegram_id)
        async with get_session() as session:
            from sqlalchemy import select, func
            from src.infrastructure.db.models import ChannelModel
            count_result = await session.execute(
                select(func.count()).select_from(ChannelModel)
                .where(ChannelModel.owner_id == telegram_id)
            )
            count = count_result.scalar_one()

        max_ch = limits["max_channels"]
        if count >= max_ch:
            return False, f"سقف {max_ch} کانال در پلن شما"
        return True, ""

    async def can_add_source(self, telegram_id: int, channel_id: int) -> tuple[bool, str]:
        limits = await self.get_plan_limits(telegram_id)
        async with get_session() as session:
            from sqlalchemy import select, func
            from src.infrastructure.db.models import SourceModel
            count_result = await session.execute(
                select(func.count()).select_from(SourceModel)
                .where(SourceModel.channel_id == channel_id)
            )
            count = count_result.scalar_one()

        max_src = limits["max_sources"]
        if count >= max_src:
            return False, f"سقف {max_src} منبع در پلن شما"
        return True, ""

    async def can_post_today(self, telegram_id: int, channel_id: int) -> tuple[bool, str]:
        """بررسی سقف پست روزانه"""
        limits = await self.get_plan_limits(telegram_id)
        today = date.today().isoformat()

        async with get_session() as session:
            from sqlalchemy import select, func
            from src.infrastructure.db.models import ArticleModel
            count_result = await session.execute(
                select(func.count()).select_from(ArticleModel)
                .where(
                    ArticleModel.channel_id == channel_id,
                    ArticleModel.status == "published",
                    func.date(ArticleModel.published_at_actual) == today,
                )
            )
            count = count_result.scalar_one()

        max_posts = limits["daily_posts"]
        if count >= max_posts:
            return False, f"سقف {max_posts} پست روزانه"
        return True, ""

    async def track_usage(
        self,
        telegram_id: int,
        posts: int = 0,
        tests: int = 0,
        ai_calls: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """ثبت مصرف — idempotent با upsert"""
        today = date.today().isoformat()

        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import UsageModel

            result = await session.execute(
                select(UsageModel).where(
                    UsageModel.user_id == telegram_id,
                    UsageModel.date == today,
                )
            )
            usage = result.scalar_one_or_none()

            if usage:
                await session.execute(
                    update(UsageModel)
                    .where(
                        UsageModel.user_id == telegram_id,
                        UsageModel.date == today,
                    )
                    .values(
                        posts_count=UsageModel.posts_count + posts,
                        tests_count=UsageModel.tests_count + tests,
                        ai_calls=UsageModel.ai_calls + ai_calls,
                        ai_tokens_in=UsageModel.ai_tokens_in + tokens_in,
                        ai_tokens_out=UsageModel.ai_tokens_out + tokens_out,
                    )
                )
            else:
                session.add(UsageModel(
                    user_id=telegram_id,
                    date=today,
                    posts_count=posts,
                    tests_count=tests,
                    ai_calls=ai_calls,
                    ai_tokens_in=tokens_in,
                    ai_tokens_out=tokens_out,
                ))

    async def check_expiring_plans(self, days_ahead: int = 3) -> list[int]:
        """
        کاربرانی که پلن‌شان طی N روز منقضی می‌شود.
        برای ارسال notification هشدار.
        """
        cutoff = datetime.utcnow() + timedelta(days=days_ahead)
        now = datetime.utcnow()

        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel
            result = await session.execute(
                select(UserModel.telegram_id).where(
                    UserModel.plan_expires_at.between(now, cutoff),
                    UserModel.is_banned == False,
                )
            )
            return [r[0] for r in result.fetchall()]

    async def process_expired_plans(self) -> int:
        """
        بررسی و ثبت وضعیت پلن‌های منقضی‌شده.
        داده‌ها حذف نمی‌شوند — فقط notification ارسال می‌شود.
        """
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel, NotificationModel
            result = await session.execute(
                select(UserModel).where(
                    UserModel.plan_expires_at < datetime.utcnow(),
                    UserModel.plan_id.isnot(None),
                    UserModel.is_banned == False,
                )
            )
            expired_users = result.scalars().all()

        count = 0
        for user in expired_users:
            # بررسی اینکه notification قبلاً ارسال نشده باشد
            async with get_session() as session:
                from sqlalchemy import select
                from src.infrastructure.db.models import NotificationModel
                existing = (await session.execute(
                    select(NotificationModel).where(
                        NotificationModel.user_id == user.telegram_id,
                        NotificationModel.notification_type == "plan_expired",
                        NotificationModel.created_at >= datetime.utcnow() - timedelta(days=1),
                    )
                )).scalar_one_or_none()

                if not existing:
                    session.add(NotificationModel(
                        user_id=user.telegram_id,
                        notification_type="plan_expired",
                        payload={"plan_id": user.plan_id},
                        next_attempt_at=datetime.utcnow(),
                    ))
                    count += 1

        logger.info("expired_plans_processed", count=count)
        return count
