"""
Scheduler — با APScheduler، timezone/DST صحیح، heartbeat واقعی، قفل کانال.
هر کانال فقط یک pipeline متعارض هم‌زمان دارد.
lock با lease/expiry و recovery پس از crash.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import get_settings
from src.application.content.pipeline import ContentPipeline
from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_WORKER_ID = str(uuid.uuid4())[:8]


class ChannelLock:
    """قفل کانال با lease — مقابله با اجرای موازی و crash recovery"""

    def __init__(self) -> None:
        self._locks: dict[int, datetime] = {}  # channel_id → expires_at

    def acquire(self, channel_id: int, ttl: int) -> bool:
        now = datetime.utcnow()
        if channel_id in self._locks:
            if now < self._locks[channel_id]:
                return False  # قفل فعال
        self._locks[channel_id] = now + timedelta(seconds=ttl)
        return True

    def release(self, channel_id: int) -> None:
        self._locks.pop(channel_id, None)

    def cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired = [k for k, v in self._locks.items() if now >= v]
        for k in expired:
            del self._locks[k]
            logger.warning("channel_lock_expired", channel_id=k)


class Scheduler:
    """
    Scheduler اصلی — هر tick کانال‌های آماده را انتخاب و pipeline اجرا می‌کند.
    quiet hours با timezone IANA و DST صحیح بررسی می‌شوند.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._pipeline = ContentPipeline()
        self._lock = ChannelLock()
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False

    def start(self) -> None:
        tick = self._settings.SCHEDULER_TICK_SECONDS
        hb_interval = self._settings.SCHEDULER_HEARTBEAT_INTERVAL

        self._scheduler.add_job(
            self._tick,
            trigger=IntervalTrigger(seconds=tick),
            id="scheduler_tick",
            replace_existing=True,
            misfire_grace_time=tick // 2,
        )
        self._scheduler.add_job(
            self._heartbeat,
            trigger=IntervalTrigger(seconds=hb_interval),
            id="scheduler_heartbeat",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("scheduler_started", worker_id=_WORKER_ID, tick_seconds=tick)

    def stop(self) -> None:
        self._scheduler.shutdown(wait=True)
        self._running = False
        logger.info("scheduler_stopped")

    async def _heartbeat(self) -> None:
        """heartbeat واقعی — صرف اتصال DB کافی نیست"""
        async with get_session() as session:
            from sqlalchemy import insert
            from src.infrastructure.db.models import SchedulerHeartbeatModel
            session.add(
                SchedulerHeartbeatModel(
                    beat_at=datetime.utcnow(),
                    worker_id=_WORKER_ID,
                )
            )
        logger.debug("scheduler_heartbeat", worker_id=_WORKER_ID)

    async def _tick(self) -> None:
        self._lock.cleanup_expired()
        settings = self._settings

        async with get_session() as session:
            from src.infrastructure.db.repositories.channel_repo import ChannelRepository
            repo = ChannelRepository(session)
            channels = await repo.list_ready_for_scheduler()

        if not channels:
            return

        semaphore = asyncio.Semaphore(settings.SCHEDULER_MAX_CONCURRENT_CHANNELS)
        tasks = []
        for channel in channels:
            if self._should_run(channel):
                tasks.append(self._run_channel(channel, semaphore))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _should_run(self, channel: object) -> bool:
        """بررسی interval و quiet hours با timezone صحیح"""
        s = getattr(channel, "settings", None)
        if not s:
            return False

        # بررسی interval
        last_run = s.last_run
        interval = s.interval_minutes
        if last_run:
            next_run = last_run + timedelta(minutes=interval)
            if datetime.utcnow() < next_run:
                return False

        # بررسی quiet hours با DST
        if s.quiet_start and s.quiet_end:
            try:
                tz = pytz.timezone(s.timezone)
                now_local = datetime.now(tz)
                now_time = now_local.strftime("%H:%M")

                start = s.quiet_start
                end = s.quiet_end

                if start <= end:
                    # بازه ساده: 23:00 - 06:00 نیست
                    if start <= now_time <= end:
                        return False
                else:
                    # از نیمه‌شب عبور می‌کند
                    if now_time >= start or now_time <= end:
                        return False
            except Exception as exc:
                logger.warning("timezone_error", tz=s.timezone, error=str(exc))

        return True

    async def _run_channel(self, channel: object, semaphore: asyncio.Semaphore) -> None:
        channel_id = getattr(channel, "id", 0) or 0
        ttl = self._settings.SCHEDULER_CHANNEL_LOCK_TTL

        if not self._lock.acquire(channel_id, ttl):
            logger.debug("channel_locked_skip", channel_id=channel_id)
            return

        async with semaphore:
            try:
                await self._pipeline.run(channel)
            except Exception as exc:
                logger.error(
                    "channel_pipeline_error",
                    channel_id=channel_id,
                    error=str(exc),
                )
            finally:
                self._lock.release(channel_id)
