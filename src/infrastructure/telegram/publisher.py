"""
Publisher تلگرام — Rich Message با HTML واقعی، عکس الزامی، محتوای بلند چندبخشی.

قوانین:
1. اگر media_url دارد → send_photo + caption است، الزامی
2. اگر caption از 1024 بیشتر شد → caption فشرده + پیام‌های ادامه‌دار
3. شکست واکشی/ارسال عکس → تلاش دوباره با URL مستقیم → اگر باز هم شکست خورد → خطا ثبت،
   بدون بی‌سروصدا تبدیل شدن به متن ساده (پیام متنی فقط وقتی اصلاً media_url نباشد)
4. HTML معتبر تلگرام — تگ‌های غیرمجاز حذف، جداول تبدیل، heading‌ها تبدیل
5. محتوای بلند → split + پیام‌های ادامه‌دار linked به عنوان reply
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from telegram import Bot, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.error import (
    BadRequest,
    Forbidden,
    NetworkError,
    RetryAfter,
    TelegramError,
    TimedOut,
)

from src.domain.entities.article import Article
from src.infrastructure.logging.logger import get_logger
from src.infrastructure.telegram.html_formatter import build_post_structure

logger = get_logger(__name__)

PERMANENT_ERRORS = frozenset({
    "bot was kicked",
    "chat not found",
    "bot is not a member",
    "have no rights to send",
    "not enough rights",
    "bot was blocked by the user",
    "wrong file identifier",
    "wrong type of the web page content",
})

# تعداد تلاش برای واکشی عکس
_PHOTO_MAX_ATTEMPTS = 2
# تأخیر بین ارسال پیام‌های ادامه‌دار (رعایت rate limit)
_CONTINUATION_DELAY = 0.3  # ثانیه


class PublishResult:
    __slots__ = ("success", "message_id", "error", "is_permanent", "extra_message_ids")

    def __init__(
        self,
        success: bool,
        message_id: Optional[int] = None,
        error: Optional[str] = None,
        is_permanent: bool = False,
        extra_message_ids: Optional[list[int]] = None,
    ) -> None:
        self.success = success
        self.message_id = message_id
        self.error = error
        self.is_permanent = is_permanent
        self.extra_message_ids = extra_message_ids or []


class TelegramPublisher:
    """
    انتشار Rich Message در کانال.
    هر مقاله برای هر کانال فقط یک بار موفق منتشر می‌شود (idempotency).
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def publish(
        self,
        article: Article,
        channel_telegram_id: int,
        settings: object,
    ) -> PublishResult:
        """نقطه ورود اصلی — idempotent"""
        if article.telegram_message_id:
            return PublishResult(success=True, message_id=article.telegram_message_id)

        # ساختار پست با formatter
        media_url: Optional[str] = (
            article.media_url
            if getattr(settings, "include_media", True)
            else None
        )

        post_struct = build_post_structure(
            post_html=article.post_html or "",
            title=article.title or "",
            source_url=article.url or "",
            media_url=media_url,
            hashtags=list(getattr(settings, "hashtags", []) or []),
            signature=str(getattr(settings, "signature", "") or ""),
            include_link=bool(getattr(settings, "include_link", True)),
            include_media=bool(getattr(settings, "include_media", True)),
            language=str(getattr(settings, "language", "fa") or "fa"),
        )

        try:
            if post_struct.has_media and post_struct.media_url:
                return await self._send_with_photo(
                    article, channel_telegram_id, post_struct
                )
            else:
                return await self._send_text_only(
                    article, channel_telegram_id, post_struct
                )

        except RetryAfter as exc:
            return PublishResult(
                success=False,
                error=f"rate_limit:{exc.retry_after}",
                is_permanent=False,
            )
        except (Forbidden, BadRequest) as exc:
            err = str(exc).lower()
            is_perm = any(p in err for p in PERMANENT_ERRORS)
            logger.warning(
                "publish_error",
                article_id=article.id,
                channel=channel_telegram_id,
                permanent=is_perm,
                error=str(exc)[:300],
            )
            return PublishResult(
                success=False,
                error=_translate_error(str(exc)),
                is_permanent=is_perm,
            )
        except (NetworkError, TimedOut) as exc:
            return PublishResult(success=False, error=str(exc)[:200], is_permanent=False)

    # ------------------------------------------------------------------ photo
    async def _send_with_photo(
        self,
        article: Article,
        channel_id: int,
        post_struct: object,
    ) -> PublishResult:
        """
        ارسال عکس + caption.
        شکست ارسال عکس → خطا ثبت می‌شود، به متن ساده تبدیل نمی‌شود.
        (اگر مدیر می‌خواهد متن ساده منتشر شود، باید media_url را خالی بگذارد)
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, _PHOTO_MAX_ATTEMPTS + 1):
            try:
                msg = await self._bot.send_photo(
                    chat_id=channel_id,
                    photo=post_struct.media_url,
                    caption=post_struct.caption,
                    parse_mode=ParseMode.HTML,
                )
                extra_ids = await self._send_continuations(
                    channel_id, post_struct.continuation_chunks, reply_to=msg.message_id
                )
                logger.info(
                    "article_published_with_photo",
                    article_id=article.id,
                    channel=channel_id,
                    message_id=msg.message_id,
                    continuations=len(extra_ids),
                )
                return PublishResult(
                    success=True,
                    message_id=msg.message_id,
                    extra_message_ids=extra_ids,
                )
            except (BadRequest, TelegramError) as exc:
                err_str = str(exc).lower()
                # اگر خطا مربوط به عکس است (نه حقوق/کانال)، retry معنا ندارد
                photo_errors = {
                    "wrong file identifier", "wrong type of the web page content",
                    "failed to get http url content", "url host is empty",
                    "bad request: wrong file identifier"
                }
                if any(p in err_str for p in photo_errors):
                    last_exc = exc
                    logger.warning(
                        "photo_fetch_failed",
                        article_id=article.id,
                        attempt=attempt,
                        error=str(exc)[:200],
                    )
                    break  # retry با همان URL بی‌فایده است
                raise  # خطاهای کانال/حقوق → بالاتر handle می‌شود

        # عکس قابل ارسال نبود — این یک خطا است، نه fallback آرام
        error_msg = f"photo_unavailable: {last_exc!s:.200}" if last_exc else "photo_send_failed"
        logger.error(
            "photo_publish_failed_no_fallback",
            article_id=article.id,
            channel=channel_id,
            media_url=post_struct.media_url[:100] if post_struct.media_url else "",
            error=error_msg,
        )
        return PublishResult(
            success=False,
            error=error_msg,
            is_permanent=False,  # می‌توان بعداً retry کرد یا ادمین می‌تواند media_url را پاک کند
        )

    # ------------------------------------------------------------------ text-only
    async def _send_text_only(
        self,
        article: Article,
        channel_id: int,
        post_struct: object,
    ) -> PublishResult:
        """ارسال بدون عکس — همه محتوا در پیام‌های متنی"""
        msg = await self._bot.send_message(
            chat_id=channel_id,
            text=post_struct.caption,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
        extra_ids = await self._send_continuations(
            channel_id, post_struct.continuation_chunks, reply_to=msg.message_id
        )
        logger.info(
            "article_published_text",
            article_id=article.id,
            channel=channel_id,
            message_id=msg.message_id,
            continuations=len(extra_ids),
        )
        return PublishResult(
            success=True,
            message_id=msg.message_id,
            extra_message_ids=extra_ids,
        )

    # ------------------------------------------------------------------ continuation
    async def _send_continuations(
        self,
        channel_id: int,
        chunks: list[str],
        reply_to: Optional[int],
    ) -> list[int]:
        """ارسال پیام‌های ادامه‌دار به‌عنوان reply به پیام اول"""
        ids: list[int] = []
        current_reply = reply_to
        for chunk in chunks:
            if not chunk.strip():
                continue
            await asyncio.sleep(_CONTINUATION_DELAY)
            try:
                msg = await self._bot.send_message(
                    chat_id=channel_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=current_reply,
                    disable_web_page_preview=True,
                )
                ids.append(msg.message_id)
                current_reply = msg.message_id
            except TelegramError as exc:
                logger.warning(
                    "continuation_send_failed",
                    channel=channel_id,
                    error=str(exc)[:200],
                )
                # اگر یک chunk شکست خورد، ادامه می‌دهیم
        return ids


# ——————————————————————————————————————————————————————————
def _translate_error(error: str) -> str:
    err = error.lower()
    if "not a member" in err or "was kicked" in err:
        return "ربات از کانال خارج شده — لطفاً ربات را مجدداً ادمین کنید"
    if "chat not found" in err:
        return "کانال یافت نشد — شناسه کانال را بررسی کنید"
    if "rights" in err or "rights to send" in err:
        return "ربات مجوز ارسال ندارد — دسترسی admin را بررسی کنید"
    if "wrong file identifier" in err or "web page content" in err:
        return "URL عکس نامعتبر یا غیرقابل دسترس است"
    return error[:200]
