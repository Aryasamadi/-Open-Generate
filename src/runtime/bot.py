"""
نقطه ورود ربات — راه‌اندازی PTB، ثبت تمام handlerها، health server.
"""
from __future__ import annotations
import sys
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, MessageHandler, filters
from config.settings import BotMode, get_settings
from src.infrastructure.db.session import close_engine, get_engine
from src.infrastructure.logging.logger import get_logger, setup_logging
from src.runtime.health import start_health_server

logger = get_logger(__name__)


async def on_startup(app: Application) -> None:
    settings = get_settings()
    logger.info("bot_starting", env=settings.APP_ENV, version=settings.APP_VERSION)
    from sqlalchemy import text
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("db_connected")
    start_health_server()


async def on_shutdown(app: Application) -> None:
    logger.info("bot_shutting_down")
    await close_engine()


def build_application() -> Application:
    settings = get_settings()
    builder = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN.get_secret_value())
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .concurrent_updates(True)
        .build()
    )
    _register_handlers(builder)
    return builder


def _register_handlers(app: Application) -> None:
    from src.bot.handlers import (
        admin_handler, ai_handler, channel_handler, language_handler,
        payment_handler, referral_handler, review_handler, settings_handler,
        source_handler, start_handler, stats_handler, support_handler, wallet_handler,
    )
    from src.bot.middleware.auth import auth_middleware

    app.add_handler(MessageHandler(filters.ALL, auth_middleware), group=-2)
    app.add_handler(CallbackQueryHandler(auth_middleware), group=-2)

    app.add_handler(start_handler.build_handler())
    app.add_handler(channel_handler.build_handler())
    app.add_handler(source_handler.build_handler())
    app.add_handler(ai_handler.build_handler())
    app.add_handler(settings_handler.build_handler())
    app.add_handler(payment_handler.build_handler())
    app.add_handler(wallet_handler.build_handler())
    app.add_handler(referral_handler.build_handler())
    app.add_handler(support_handler.build_handler())
    app.add_handler(review_handler.build_handler())
    app.add_handler(stats_handler.build_handler())
    app.add_handler(language_handler.build_handler())
    app.add_handler(admin_handler.build_handler())
    app.add_error_handler(_error_handler)
    logger.info("all_handlers_registered")


async def _error_handler(update: object, context: object) -> None:
    import traceback
    exc = getattr(context, "error", None)
    if exc:
        logger.error("unhandled_bot_error", error=str(exc), tb=traceback.format_exc()[:300])


def main() -> None:
    setup_logging()
    settings = get_settings()
    app = build_application()
    if settings.BOT_MODE == BotMode.WEBHOOK:
        app.run_webhook(
            listen="0.0.0.0",
            port=settings.WEBHOOK_PORT,
            url_path=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
            webhook_url=str(settings.WEBHOOK_URL),
            secret_token=(settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None),
        )
    else:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
