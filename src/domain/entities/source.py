"""موجودیت منبع محتوا"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    RSS = "rss"
    ATOM = "atom"
    API = "api"       # API اختصاصی با key
    WEB = "web"       # استخراج مستقیم از صفحه


class Source:
    """
    منبع محتوا — RSS، Atom یا API اختصاصی.
    خرابی یک منبع نباید کل چرخه را متوقف کند.
    """

    def __init__(
        self,
        channel_id: int,
        owner_id: int,
        title: str,
        url: str,
        feed_url: Optional[str] = None,
        source_type: SourceType = SourceType.RSS,
        is_active: bool = True,
        # --- API اختصاصی ---
        api_url: Optional[str] = None,
        api_key_encrypted: Optional[str] = None,  # رمزنگاری‌شده
        api_note: Optional[str] = None,
        # --- وضعیت fetch ---
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        last_fetch: Optional[datetime] = None,
        fail_count: int = 0,
        found_total: int = 0,
        last_error: Optional[str] = None,
        next_try_after: Optional[datetime] = None,
        # --- متا ---
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.title = title
        self.url = url
        self.feed_url = feed_url
        self.source_type = source_type
        self.is_active = is_active
        self.api_url = api_url
        self.api_key_encrypted = api_key_encrypted
        self.api_note = api_note
        self.etag = etag
        self.last_modified = last_modified
        self.last_fetch = last_fetch
        self.fail_count = fail_count
        self.found_total = found_total
        self.last_error = last_error
        self.next_try_after = next_try_after
        self.created_at = created_at or datetime.utcnow()

    @property
    def has_custom_api(self) -> bool:
        return bool(self.api_url and self.api_key_encrypted)

    @property
    def is_healthy(self) -> bool:
        return self.fail_count < 5 and self.is_active

    def __repr__(self) -> str:
        return f"Source(id={self.id}, title={self.title!r}, type={self.source_type})"
