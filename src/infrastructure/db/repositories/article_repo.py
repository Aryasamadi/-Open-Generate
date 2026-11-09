"""Repository مقالات"""
from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.article import Article, ArticleStatus
from src.infrastructure.db.models import ArticleModel, DedupModel


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def is_duplicate(self, channel_id: int, content_hash: str, url_hash: str) -> bool:
        result = await self._s.execute(
            select(func.count()).select_from(ArticleModel).where(
                ArticleModel.channel_id == channel_id,
                (ArticleModel.content_hash == content_hash) | (ArticleModel.url_hash == url_hash),
            )
        )
        return result.scalar_one() > 0

    async def create(self, article: Article) -> Article:
        m = ArticleModel(
            channel_id=article.channel_id,
            source_id=article.source_id,
            url=article.url,
            canonical_url=article.canonical_url,
            title=article.title,
            content_hash=article.content_hash,
            url_hash=article.url_hash,
            status=article.status.value,
            raw_text=article.raw_text,
            post_html=article.post_html,
            media_url=article.media_url,
            published_at=article.published_at,
            score=article.score,
            category=article.category,
            scoring_detail=article.scoring_detail,
            reason=article.reason,
        )
        self._s.add(m)
        await self._s.flush()
        article.id = m.id

        # ثبت در dedup
        self._s.add(DedupModel(channel_id=article.channel_id, hash=article.content_hash))
        self._s.add(DedupModel(channel_id=article.channel_id, hash=article.url_hash))
        return article

    async def count_published_today(self, channel_id: int) -> int:
        today = date.today().isoformat()
        result = await self._s.execute(
            select(func.count()).select_from(ArticleModel).where(
                ArticleModel.channel_id == channel_id,
                ArticleModel.status == ArticleStatus.PUBLISHED.value,
                func.date(ArticleModel.published_at_actual) == today,
            )
        )
        return result.scalar_one()

    async def list_pending_review(self, channel_id: int, limit: int = 10) -> list[Article]:
        result = await self._s.execute(
            select(ArticleModel).where(
                ArticleModel.channel_id == channel_id,
                ArticleModel.status == ArticleStatus.PENDING_REVIEW.value,
            ).order_by(ArticleModel.score.desc()).limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def update_status(
        self,
        article_id: int,
        status: ArticleStatus,
        reason: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
    ) -> None:
        from sqlalchemy import update
        values: dict = {"status": status.value, "updated_at": datetime.utcnow()}
        if reason:
            values["reason"] = reason
        if telegram_message_id:
            values["telegram_message_id"] = telegram_message_id
            values["published_at_actual"] = datetime.utcnow()
        await self._s.execute(
            update(ArticleModel).where(ArticleModel.id == article_id).values(**values)
        )

    def _to_entity(self, m: ArticleModel) -> Article:
        return Article(
            id=m.id,
            channel_id=m.channel_id,
            source_id=m.source_id or 0,
            url=m.url,
            canonical_url=m.canonical_url,
            title=m.title,
            content_hash=m.content_hash,
            url_hash=m.url_hash,
            status=ArticleStatus(m.status),
            raw_text=m.raw_text,
            post_html=m.post_html,
            media_url=m.media_url,
            published_at=m.published_at,
            score=float(m.score or 0),
            category=m.category,
            telegram_message_id=m.telegram_message_id,
            reason=m.reason,
            created_at=m.created_at,
        )
