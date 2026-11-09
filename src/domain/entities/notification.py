"""موجودیت اعلان دائمی"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class NotificationType(str, Enum):
    PAYMENT_APPROVED = "payment_approved"
    PAYMENT_REJECTED = "payment_rejected"
    PLAN_EXPIRING = "plan_expiring"
    PLAN_EXPIRED = "plan_expired"
    PUBLISH_ERROR = "publish_error"
    AI_PROVIDER_FAIL = "ai_provider_fail"
    CHANNEL_BOT_REMOVED = "channel_bot_removed"
    SYSTEM_ALERT = "system_alert"
    SUPPORT_REPLY = "support_reply"
    REFERRAL_CREDITED = "referral_credited"


class Notification:
    """
    اعلان durable — با retry/backoff/dead-letter.
    شکست تحویل باید قابل بازیابی باشد.
    """

    def __init__(
        self,
        user_id: int,
        notification_type: NotificationType,
        payload: dict[str, Any],
        attempts: int = 0,
        max_attempts: int = 5,
        next_attempt_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
        is_dead: bool = False,
        last_error: Optional[str] = None,
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.notification_type = notification_type
        self.payload = payload
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.next_attempt_at = next_attempt_at or datetime.utcnow()
        self.delivered_at = delivered_at
        self.is_dead = is_dead
        self.last_error = last_error
        self.created_at = created_at or datetime.utcnow()

    @property
    def is_delivered(self) -> bool:
        return self.delivered_at is not None

    @property
    def should_retry(self) -> bool:
        return (
            not self.is_delivered
            and not self.is_dead
            and self.attempts < self.max_attempts
        )
