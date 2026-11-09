"""
Scheduled jobs — وظایف دوره‌ای مستقل از pipeline.
هر job اگر fail شود، بقیه متأثر نمی‌شوند.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.infrastructure.logging.logger import get_logger

if TYPE_CHECKING:
    from telegram import Bot

logger = get_logger(__name__)


async def job_check_expiring_plans(bot: "Bot") -> None:
    """هر ۶ ساعت — notification برای پلن‌های در حال انقضا"""
    try:
        from src.application.subscription.service import SubscriptionService
        svc = SubscriptionService()

        # هشدار ۳ روز مانده
        expiring = await svc.check_expiring_plans(days_ahead=3)
        for user_id in expiring:
            async with _get_session() as session:
                from src.infrastructure.db.models import NotificationModel
                from sqlalchemy import select
                # بررسی notification تکراری (۲۴ ساعت)
                existing = (await session.execute(
                    select(NotificationModel).where(
                        NotificationModel.user_id == user_id,
                        NotificationModel.notification_type == "plan_expiring",
                        NotificationModel.created_at >= datetime.utcnow() - timedelta(days=1),
                    )
                )).scalar_one_or_none()
                if not existing:
                    session.add(NotificationModel(
                        user_id=user_id,
                        notification_type="plan_expiring",
                        payload={"days": 3},
                        next_attempt_at=datetime.utcnow(),
                    ))

        # پردازش پلن‌های منقضی‌شده
        expired_count = await svc.process_expired_plans()

        logger.info(
            "job_expiry_check",
            expiring_notified=len(expiring),
            expired_processed=expired_count,
        )
    except Exception as exc:
        logger.error("job_check_expiring_plans_failed", error=str(exc))


async def job_reset_failed_sources() -> None:
    """هر ۱۲ ساعت — reset منابعی که بیش از ۲۴ ساعت fail بودند"""
    try:
        from src.application.source.service import SourceService
        count = await SourceService().reset_failed_sources(fail_threshold=5)
        logger.info("job_source_reset", count=count)
    except Exception as exc:
        logger.error("job_reset_failed_sources_error", error=str(exc))


async def job_cleanup_dedup(days: int = 7) -> None:
    """هر روز — پاکسازی dedup قدیمی‌تر از N روز"""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with _get_session() as session:
            from sqlalchemy import delete
            from src.infrastructure.db.models import DedupModel
            result = await session.execute(
                delete(DedupModel).where(DedupModel.seen_at < cutoff)
            )
            deleted = result.rowcount
        logger.info("job_dedup_cleanup", deleted=deleted, cutoff=cutoff.isoformat())
    except Exception as exc:
        logger.error("job_cleanup_dedup_error", error=str(exc))


async def job_cleanup_kv_cache() -> None:
    """هر ساعت — پاکسازی kv_cache منقضی"""
    try:
        async with _get_session() as session:
            from sqlalchemy import delete
            from src.infrastructure.db.models import KVCacheModel
            result = await session.execute(
                delete(KVCacheModel).where(
                    KVCacheModel.expires_at < datetime.utcnow(),
                    KVCacheModel.expires_at.isnot(None),
                )
            )
        logger.debug("job_kv_cache_cleanup", deleted=result.rowcount)
    except Exception as exc:
        logger.error("job_kv_cache_cleanup_error", error=str(exc))


async def job_check_bot_admin_status(bot: "Bot") -> None:
    """هر ۲ ساعت — بررسی مجوز ادمین ربات در همه کانال‌ها"""
    try:
        from src.application.channel.service import ChannelService
        svc = ChannelService(bot)
        issues = await svc.check_all_channels_bot_status()
        if issues:
            logger.warning("bot_removed_from_channels", count=len(issues), channels=[i["channel_id"] for i in issues])
    except Exception as exc:
        logger.error("job_bot_admin_check_error", error=str(exc))


async def job_cleanup_old_heartbeats() -> None:
    """هر روز — پاکسازی heartbeat‌های قدیمی (نگه‌داری ۱ هفته)"""
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        async with _get_session() as session:
            from sqlalchemy import delete
            from src.infrastructure.db.models import SchedulerHeartbeatModel
            await session.execute(
                delete(SchedulerHeartbeatModel).where(
                    SchedulerHeartbeatModel.beat_at < cutoff
                )
            )
    except Exception as exc:
        logger.error("job_heartbeat_cleanup_error", error=str(exc))


async def job_cleanup_old_articles(days: int = 90) -> None:
    """هر هفته — آرشیو مقالات قدیمی (نه حذف — تغییر status)"""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with _get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import ArticleModel
            result = await session.execute(
                update(ArticleModel)
                .where(
                    ArticleModel.created_at < cutoff,
                    ArticleModel.status.in_(["published", "rejected", "filtered", "duplicate"]),
                )
                .values(status="archived")
            )
        logger.info("job_article_archive", archived=result.rowcount)
    except Exception as exc:
        logger.error("job_cleanup_articles_error", error=str(exc))


def _get_session():
    from src.infrastructure.db.session import get_session
    return get_session()


def register_jobs(scheduler: object, bot: "Bot") -> None:
    """ثبت تمام jobها در APScheduler"""
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger

    sched = scheduler

    sched.add_job(
        lambda: asyncio.create_task(job_check_expiring_plans(bot)),
        trigger=IntervalTrigger(hours=6),
        id="job_expiry_check",
        replace_existing=True,
        misfire_grace_time=600,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_reset_failed_sources()),
        trigger=IntervalTrigger(hours=12),
        id="job_source_reset",
        replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_cleanup_dedup()),
        trigger=CronTrigger(hour=3, minute=0),  # ۳ شب UTC
        id="job_dedup_cleanup",
        replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_cleanup_kv_cache()),
        trigger=IntervalTrigger(hours=1),
        id="job_kv_cleanup",
        replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_check_bot_admin_status(bot)),
        trigger=IntervalTrigger(hours=2),
        id="job_bot_admin_check",
        replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_cleanup_old_heartbeats()),
        trigger=CronTrigger(hour=4, minute=0),
        id="job_heartbeat_cleanup",
        replace_existing=True,
    )
    sched.add_job(
        lambda: asyncio.create_task(job_cleanup_old_articles()),
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="job_article_archive",
        replace_existing=True,
    )

    logger.info("scheduled_jobs_registered", count=7)
