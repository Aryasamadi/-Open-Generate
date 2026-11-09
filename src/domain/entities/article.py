"""موجودیت مقاله/خبر با state machine کامل"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ArticleStatus(str, Enum):
    """
    چرخه حیات مقاله — هر انتقال باید با دلیل ثبت شود.
    """
    FETCHED = "fetched"               # دریافت‌شده از منبع
    DEDUPED = "deduped"               # بررسی تکراری
    SCORED = "scored"                 # امتیازدهی‌شده
    PENDING_AI = "pending_ai"         # در صف تولید متن AI
    AI_DONE = "ai_done"               # متن AI آماده
    PENDING_REVIEW = "pending_review" # در صف بازبینی انسانی
    APPROVED = "approved"             # تأیید‌شده
    REJECTED = "rejected"             # رد‌شده
    PUBLISHING = "publishing"         # در حال انتشار
    PUBLISHED = "published"           # منتشرشده
    FAILED = "failed"                 # خطا در انتشار
    ARCHIVED = "archived"             # آرشیو‌شده
    DUPLICATE = "duplicate"           # تکراری — منتشر نمی‌شود
    FILTERED = "filtered"             # پالایش‌شده — تبلیغ یا نامرتبط

    @property
    def is_terminal(self) -> bool:
        return self in (
            ArticleStatus.PUBLISHED,
            ArticleStatus.REJECTED,
            ArticleStatus.ARCHIVED,
            ArticleStatus.DUPLICATE,
            ArticleStatus.FILTERED,
        )

    @property
    def can_republish(self) -> bool:
        return self in (ArticleStatus.FAILED, ArticleStatus.ARCHIVED)


class Article:
    """
    یک مقاله/خبر در چرخه پردازش.
    هر مقاله برای هر کانال فقط یک بار موفق منتشر می‌شود (idempotency).
    """

    def __init__(
        self,
        channel_id: int,
        source_id: int,
        url: str,
        canonical_url: str,
        title: str,
        content_hash: str,         # SHA-256 محتوای normalize‌شده
        url_hash: str,             # SHA-256 URL canonical
        status: ArticleStatus = ArticleStatus.FETCHED,
        # --- محتوا ---
        raw_text: Optional[str] = None,
        full_text: Optional[str] = None,  # متن استخراج‌شده از صفحه
        post_html: Optional[str] = None,  # خروجی AI برای تلگرام
        media_url: Optional[str] = None,
        media_type: Optional[str] = None,  # "photo" | "video" | "document"
        # --- زمان ---
        published_at: Optional[datetime] = None,  # زمان منبع
        fetched_at: Optional[datetime] = None,
        # --- امتیازدهی ---
        score: float = 0.0,
        category: Optional[str] = None,
        scoring_detail: Optional[dict[str, Any]] = None,
        # --- AI ---
        ai_model_id: Optional[int] = None,
        ai_prompt_hash: Optional[str] = None,
        ai_retries: int = 0,
        ai_error: Optional[str] = None,
        # --- انتشار ---
        telegram_message_id: Optional[int] = None,
        publish_attempts: int = 0,
        last_publish_error: Optional[str] = None,
        published_at_actual: Optional[datetime] = None,
        # --- مدیریت ---
        reason: Optional[str] = None,  # دلیل آخرین انتقال وضعیت
        reviewed_by: Optional[int] = None,  # telegram_id بازبین
        reviewed_at: Optional[datetime] = None,
        # --- متا ---
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.channel_id = channel_id
        self.source_id = source_id
        self.url = url
        self.canonical_url = canonical_url
        self.title = title
        self.content_hash = content_hash
        self.url_hash = url_hash
        self.status = status
        self.raw_text = raw_text
        self.full_text = full_text
        self.post_html = post_html
        self.media_url = media_url
        self.media_type = media_type
        self.published_at = published_at
        self.fetched_at = fetched_at or datetime.utcnow()
        self.score = score
        self.category = category
        self.scoring_detail = scoring_detail
        self.ai_model_id = ai_model_id
        self.ai_prompt_hash = ai_prompt_hash
        self.ai_retries = ai_retries
        self.ai_error = ai_error
        self.telegram_message_id = telegram_message_id
        self.publish_attempts = publish_attempts
        self.last_publish_error = last_publish_error
        self.published_at_actual = published_at_actual
        self.reason = reason
        self.reviewed_by = reviewed_by
        self.reviewed_at = reviewed_at
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def transition(self, new_status: ArticleStatus, reason: Optional[str] = None) -> None:
        """انتقال وضعیت با ثبت دلیل"""
        self.status = new_status
        self.reason = reason
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"Article(id={self.id}, channel={self.channel_id}, "
            f"status={self.status}, title={self.title[:50]!r})"
        )
