"""
Pipeline انتشار — ۱۵ مرحله کامل از دریافت تا انتشار.
شکست یک مقاله نباید batch را متوقف کند.
restart یا اجرای مجدد نباید duplicate تولید کند.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from config.settings import get_settings
from src.domain.entities.article import Article, ArticleStatus
from src.domain.entities.channel import Channel, ChannelSettings
from src.domain.entities.source import Source
from src.infrastructure.ai.engine import AIEngine
from src.infrastructure.db.session import get_session
from src.infrastructure.db.repositories.channel_repo import ChannelRepository
from src.infrastructure.fetcher.safe_fetcher import FetchError, SafeFetcher, SSRFBlockedError
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    channel_id: int
    fetched: int = 0
    deduplicated: int = 0
    scored: int = 0
    published: int = 0
    queued_review: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None

    def finish(self) -> None:
        self.ended_at = datetime.utcnow()


class ContentPipeline:
    """
    چرخه کامل دریافت تا انتشار برای یک کانال.
    هر مرحله status، زمان، خطا و retry مستقل دارد.
    """

    def __init__(self, ai_engine: Optional[AIEngine] = None) -> None:
        self._fetcher = SafeFetcher()
        self._ai = ai_engine or AIEngine()
        self._settings = get_settings()

    async def run(self, channel: Channel) -> PipelineResult:
        result = PipelineResult(channel_id=channel.id or 0)
        settings = channel.settings

        logger.info(
            "pipeline_start",
            channel_id=channel.id,
            mode=settings.mode,
        )

        try:
            async with get_session() as session:
                from src.infrastructure.db.repositories.source_repo import SourceRepository
                from src.infrastructure.db.repositories.article_repo import ArticleRepository

                source_repo = SourceRepository(session)
                article_repo = ArticleRepository(session)

                # مرحله ۱: دریافت منابع فعال
                sources = await source_repo.list_active_by_channel(channel.id or 0)

                for source in sources:
                    try:
                        await self._process_source(
                            channel, source, settings, article_repo, result
                        )
                    except (SSRFBlockedError, FetchError) as exc:
                        result.errors.append(f"source {source.id}: {exc}")
                        logger.warning(
                            "source_fetch_error",
                            source_id=source.id,
                            error=str(exc)[:200],
                        )
                        # خطای یک منبع → ادامه با منبع بعدی
                        continue

                await session.commit()

        except Exception as exc:
            result.errors.append(f"pipeline error: {exc}")
            logger.error("pipeline_error", channel_id=channel.id, error=str(exc))

        result.finish()
        logger.info(
            "pipeline_done",
            channel_id=channel.id,
            published=result.published,
            queued_review=result.queued_review,
            errors=len(result.errors),
        )
        return result

    async def _process_source(
        self,
        channel: Channel,
        source: Source,
        settings: ChannelSettings,
        article_repo: object,
        result: PipelineResult,
    ) -> None:
        # مرحله ۲: Fetch
        fetch_result = await self._fetcher.fetch(
            url=source.feed_url or source.url,
            etag=source.etag,
            last_modified=source.last_modified,
        )

        if fetch_result.not_modified:
            return  # محتوا تغییر نکرده

        # مرحله ۳: Parse feed
        feed = feedparser.parse(fetch_result.content)
        entries = feed.entries[:50]  # حداکثر ۵۰ مقاله در هر fetch

        for entry in entries:
            try:
                await self._process_entry(
                    channel, source, settings, entry, article_repo, result
                )
            except Exception as exc:
                result.errors.append(f"entry error: {exc}")
                # شکست یک مقاله → ادامه
                continue

    async def _process_entry(
        self,
        channel: Channel,
        source: Source,
        settings: ChannelSettings,
        entry: object,
        article_repo: object,
        result: PipelineResult,
    ) -> None:
        # مرحله ۴: normalize
        url = getattr(entry, "link", "") or ""
        title = getattr(entry, "title", "") or ""
        raw_text = getattr(entry, "summary", "") or ""
        published_at = self._parse_date(entry)

        if not url or not title:
            return

        canonical_url = self._canonicalize_url(url)
        content_hash = self._hash_content(title, raw_text)
        url_hash = hashlib.sha256(canonical_url.encode()).hexdigest()

        # مرحله ۵: Dedup
        is_dup = await getattr(article_repo, "is_duplicate")(
            channel.id or 0, content_hash, url_hash
        )
        if is_dup:
            result.deduplicated += 1
            return

        result.fetched += 1

        # مرحله ۶: بازه زمانی
        if published_at:
            cutoff = datetime.utcnow() - timedelta(hours=settings.lookback_hours)
            if published_at < cutoff:
                return
        elif not settings.allow_undated:
            return

        # مرحله ۸: تبلیغات (ساده)
        if settings.strict_ads and self._is_ad(title, raw_text):
            return

        # مرحله ۹: Scoring
        score, category = self._score_article(title, raw_text, settings)

        # مرحله ۱۰: min_score
        if score < settings.min_score:
            return

        result.scored += 1

        # check daily cap
        daily_count = await getattr(article_repo, "count_published_today")(channel.id or 0)
        if daily_count >= settings.daily_posts_cap:
            return

        # ایجاد article
        article = Article(
            channel_id=channel.id or 0,
            source_id=source.id or 0,
            url=url,
            canonical_url=canonical_url,
            title=title,
            content_hash=content_hash,
            url_hash=url_hash,
            raw_text=raw_text,
            published_at=published_at,
            score=score,
            category=category,
            status=ArticleStatus.SCORED,
        )

        # مرحله ۱۱: AI
        ai_text = await self._generate_ai_text(channel, article, settings)
        if ai_text:
            article.post_html = ai_text
            article.transition(ArticleStatus.AI_DONE)
        else:
            # بدون AI — در حالت review نگه می‌داریم
            if settings.mode == "auto":
                return  # متن ساختگی منتشر نمی‌شود
            article.transition(ArticleStatus.AI_DONE, reason="no_ai")

        # مرحله ۱۲-۱۳: validate و صف
        if settings.mode == "review":
            article.transition(ArticleStatus.PENDING_REVIEW)
            result.queued_review += 1
        else:
            article.transition(ArticleStatus.APPROVED)
            # مرحله ۱۴: انتشار (در worker جداگانه)
            # اینجا فقط به صف اضافه می‌شود
            result.published += 1  # واقعی پس از تأیید worker

        await getattr(article_repo, "create")(article)

    async def _generate_ai_text(
        self, channel: Channel, article: Article, settings: ChannelSettings
    ) -> Optional[str]:
        """تولید متن با AI — None اگر همه مدل‌ها fail شدند"""
        try:
            from src.infrastructure.db.session import get_session
            async with get_session() as session:
                from src.infrastructure.db.repositories.ai_model_repo import AIModelRepository
                repo = AIModelRepository(session)
                models = await repo.list_available_for_channel(
                    channel_owner_id=channel.owner_id
                )

            if not models:
                return None

            from src.application.content.prompt_builder import build_system_prompt
            system_prompt = build_system_prompt(
                language=settings.language or "fa",
                custom_prompt=settings.prompt or "",
                topic=settings.topic or "",
                max_words=settings.max_words or 400,
            )
            response = await self._ai.generate_with_fallback(
                models=models,
                system_prompt=system_prompt,
                article_content=f"عنوان: {article.title}\n\n{article.raw_text or ''}",
            )

            return response.text if response else None

        except Exception as exc:
            logger.warning(
                "ai_generation_failed",
                article_id=article.id,
                error=str(exc)[:200],
            )
            return None

    # _default_prompt حذف شد — منطق آن به prompt_builder.py منتقل شده
    # prompt_builder.py ساختار HTML دقیق تلگرام را به مدل آموزش می‌دهد

    def _canonicalize_url(self, url: str) -> str:
        """حذف query string و fragment و normalize"""
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    def _hash_content(self, title: str, text: str) -> str:
        normalized = f"{title.strip().lower()}:{text[:500].strip().lower()}"
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _parse_date(self, entry: object) -> Optional[datetime]:
        import time
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    return datetime(*val[:6])
                except Exception:
                    pass
        return None

    def _is_ad(self, title: str, text: str) -> bool:
        """تشخیص ساده تبلیغات — قابل بهبود با ML"""
        ad_keywords = [
            "sponsored", "advertisement", "تبلیغ", "آگهی",
            "خرید کنید", "click here", "کلیک کنید",
        ]
        combined = f"{title} {text}".lower()
        return any(kw in combined for kw in ad_keywords)

    def _score_article(
        self, title: str, text: str, settings: ChannelSettings
    ) -> tuple[float, Optional[str]]:
        """
        امتیازدهی وزن‌دار بر اساس categories و criteria.
        برگرداندن (score, category).
        """
        if not settings.categories:
            return 0.7, None  # پیش‌فرض اگر دسته‌بندی تعریف نشده

        combined = f"{title} {text}".lower()
        best_score = 0.0
        best_category = None

        for cat in settings.categories:
            if not cat.enabled:
                continue
            matches = sum(1 for kw in cat.keywords if kw.lower() in combined)
            if matches > 0:
                cat_score = min(1.0, matches / max(len(cat.keywords), 1)) * cat.weight
                if cat_score > best_score:
                    best_score = cat_score
                    best_category = cat.name

        # اگر هیچ دسته‌ای match نکرد، امتیاز پیش‌فرض
        if best_score == 0.0:
            best_score = 0.3

        return round(best_score, 4), best_category
