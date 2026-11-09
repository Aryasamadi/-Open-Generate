"""
Worker — Scheduler + Jobs + Publish Worker + Notification Dispatcher.
همه چیز در یک process، با graceful shutdown.
"""
from __future__ import annotations

import asyncio
import signal
import sys

from config.settings import get_settings
from src.infrastructure.logging.logger import get_logger, setup_logging
from src.infrastructure.scheduler.scheduler import Scheduler
from src.infrastructure.scheduler.jobs import register_jobs
from src.infrastructure.scheduler.publish_worker import PublishWorker
from src.runtime.health import start_health_server

logger = get_logger(__name__)

_scheduler: Scheduler | None = None
_publish_worker: PublishWorker | None = None


async def _notification_loop(bot) -> None:
    from src.application.notification.dispatcher import NotificationDispatcher
    dispatcher = NotificationDispatcher(bot)
    while True:
        try:
            stats = await dispatcher.dispatch_pending(limit=20)
            if stats["delivered"] > 0 or stats["dead"] > 0:
                logger.info("notification_cycle", **stats)
        except Exception as exc:
            logger.error("notification_loop_error", error=str(exc))
        await asyncio.sleep(30)


async def main_async() -> None:
    global _scheduler, _publish_worker

    setup_logging()
    settings = get_settings()

    from telegram import Bot
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN.get_secret_value())

    # اطمینان از DB
    from sqlalchemy import text
    from src.infrastructure.db.session import get_engine
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("worker_db_connected")

    start_health_server()

    # Scheduler + Jobs
    _scheduler = Scheduler()
    register_jobs(_scheduler._scheduler, bot)
    _scheduler.start()

    # Publish Worker
    _publish_worker = PublishWorker(bot)

    logger.info("worker_started", env=settings.APP_ENV, version=settings.APP_VERSION)

    await asyncio.gather(
        _publish_worker.run_forever(),
        _notification_loop(bot),
        return_exceptions=True,
    )


def _shutdown(signum: int, frame: object) -> None:
    logger.info("worker_shutdown_signal", signal=signum)
    if _scheduler:
        _scheduler.stop()
    if _publish_worker:
        _publish_worker.stop()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
