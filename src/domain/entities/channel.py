"""موجودیت کانال تلگرام و تنظیمات آن"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CategoryConfig:
    name: str
    name_en: str
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0
    enabled: bool = True


@dataclass
class CriterionConfig:
    name: str
    name_en: str
    weight: float = 1.0
    description: str = ""


@dataclass
class ChannelSettings:
    """
    تمام تنظیمات مستقل هر کانال.
    همه فیلدها باید ذخیره، بازیابی و از UI قابل ویرایش باشند.
    """
    # حالت کار
    enabled: bool = True
    mode: str = "auto"           # "auto" | "review"

    # محتوا
    prompt: str = ""
    topic: str = ""
    language: str = "fa"         # زبان خروجی محتوا

    # دسته‌بندی و معیار
    categories: list[CategoryConfig] = field(default_factory=list)
    criteria: list[CriterionConfig] = field(default_factory=list)
    min_score: float = 0.5

    # بازه زمانی محتوا
    lookback_hours: int = 24
    allow_undated: bool = False

    # زمان‌بندی انتشار
    quiet_start: Optional[str] = None   # "HH:MM" در timezone کانال
    quiet_end: Optional[str] = None     # "HH:MM"
    timezone: str = "Asia/Tehran"
    interval_minutes: int = 60
    posts_per_cycle: int = 1
    daily_posts_cap: int = 10

    # قالب‌بندی پست
    include_media: bool = True
    include_link: bool = True
    signature: str = ""
    max_words: int = 500
    post_limit: int = 4096           # Telegram text limit
    hashtags: list[str] = field(default_factory=list)

    # پالایش
    strict_ads: bool = True

    # آخرین اجرا — فقط برای خواندن
    last_run: Optional[datetime] = None
    last_end: Optional[datetime] = None
    last_result: Optional[str] = None
    diagnostic: Optional[dict[str, Any]] = None
    last_notified_diagnostic: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelSettings":
        cats = [CategoryConfig(**c) for c in data.pop("categories", [])]
        crits = [CriterionConfig(**c) for c in data.pop("criteria", [])]
        return cls(categories=cats, criteria=crits, **data)


class Channel:
    """کانال تلگرام متعلق به یک کاربر/مدیر"""

    def __init__(
        self,
        owner_id: int,            # telegram_id مالک
        telegram_id: int,         # شناسه عددی کانال
        username: Optional[str],
        title: str,
        settings: Optional[ChannelSettings] = None,
        is_active: bool = True,
        bot_is_admin: bool = False,
        verified_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id
        self.owner_id = owner_id
        self.telegram_id = telegram_id
        self.username = username
        self.title = title
        self.settings = settings or ChannelSettings()
        self.is_active = is_active
        self.bot_is_admin = bot_is_admin
        self.verified_at = verified_at
        self.created_at = created_at or datetime.utcnow()

    @property
    def is_ready(self) -> bool:
        """آیا کانال آماده انتشار است؟"""
        return (
            self.is_active
            and self.bot_is_admin
            and self.settings.enabled
        )

    def __repr__(self) -> str:
        return (
            f"Channel(id={self.id}, telegram_id={self.telegram_id}, "
            f"title={self.title!r}, owner={self.owner_id})"
        )
