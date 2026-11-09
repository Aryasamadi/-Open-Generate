"""
سرویس منابع — کشف feed، اعتبارسنجی، بررسی سلامت.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from src.infrastructure.db.session import get_session
from src.infrastructure.fetcher.safe_fetcher import SafeFetcher, FetchError, SSRFBlockedError
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_fetcher = SafeFetcher()


class SourceService:

    async def discover_feed(self, url: str) -> Optional[str]:
        """
        کشف آدرس RSS/Atom از URL صفحه.
        اگر URL خودش feed باشد، همان برگردانده می‌شود.
        """
        try:
            result = await _fetcher.fetch(url)
        except (FetchError, SSRFBlockedError) as exc:
            logger.warning("feed_discovery_failed", url=url, error=str(exc)[:100])
            return None

        content_type = result.content_type.lower()
        if any(t in content_type for t in ("rss", "atom", "xml", "feed")):
            return url

        # جستجو در HTML برای link rel="alternate"
        try:
            content = result.content.decode("utf-8", errors="ignore")
            import re
            patterns = [
                r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
            ]
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    feed_url = match.group(1)
                    # relative URL را resolve کنیم
                    if feed_url.startswith("http"):
                        return feed_url
                    from urllib.parse import urljoin
                    return urljoin(url, feed_url)
        except Exception as exc:
            logger.debug("feed_html_parse_failed", error=str(exc)[:100])

        return None

    async def validate_feed(self, feed_url: str) -> dict:
        """اعتبارسنجی feed — تعداد entry، آخرین تاریخ، عنوان"""
        try:
            result = await _fetcher.fetch(feed_url)
        except (FetchError, SSRFBlockedError) as exc:
            return {"valid": False, "error": str(exc)[:200]}

        try:
            import feedparser
            feed = feedparser.parse(result.content)
            entries = feed.entries
            feed_title = feed.feed.get("title", "")

            return {
                "valid": True,
                "feed_title": feed_title,
                "entry_count": len(entries),
                "latest_title": entries[0].get("title", "") if entries else "",
            }
        except Exception as exc:
            return {"valid": False, "error": f"parse error: {exc!s:.100}"}

    async def reset_failed_sources(self, fail_threshold: int = 5) -> int:
        """
        منابعی که بیش از N بار fail شده‌اند را پس از TTL reset می‌کند.
        برای جلوگیری از قفل شدن دائمی یک منبع.
        """
        threshold_time = datetime.utcnow() - timedelta(hours=24)
        async with get_session() as session:
            from sqlalchemy import update, select
            from src.infrastructure.db.models import SourceModel
            result = await session.execute(
                select(SourceModel).where(
                    SourceModel.fail_count >= fail_threshold,
                    SourceModel.last_fetch < threshold_time,
                    SourceModel.is_active == True,
                )
            )
            sources = result.scalars().all()

            for src in sources:
                await session.execute(
                    update(SourceModel)
                    .where(SourceModel.id == src.id)
                    .values(
                        fail_count=0,
                        last_error=None,
                        next_try_after=None,
                    )
                )
                logger.info("source_reset", source_id=src.id, title=src.title)

        return len(sources)

    async def get_source_health(self, channel_id: int) -> list[dict]:
        """آمار سلامت منابع یک کانال"""
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import SourceModel
            result = await session.execute(
                select(SourceModel).where(SourceModel.channel_id == channel_id)
            )
            sources = result.scalars().all()

        return [
            {
                "id": s.id,
                "title": s.title,
                "is_active": s.is_active,
                "fail_count": s.fail_count,
                "last_fetch": s.last_fetch.isoformat() if s.last_fetch else None,
                "last_error": s.last_error,
                "found_total": s.found_total,
                "healthy": s.fail_count < 5 and s.is_active,
            }
            for s in sources
        ]
