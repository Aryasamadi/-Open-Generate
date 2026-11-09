"""Repository منابع"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.source import Source, SourceType
from src.infrastructure.db.models import SourceModel


def _to_entity(m: SourceModel) -> Source:
    return Source(
        id=m.id,
        channel_id=m.channel_id,
        owner_id=m.owner_id,
        title=m.title,
        url=m.url,
        feed_url=m.feed_url,
        source_type=SourceType(m.source_type),
        is_active=m.is_active,
        api_url=m.api_url,
        api_key_encrypted=m.api_key_encrypted,
        api_note=m.api_note,
        etag=m.etag,
        last_modified=m.last_modified,
        last_fetch=m.last_fetch,
        fail_count=m.fail_count,
        found_total=m.found_total,
        last_error=m.last_error,
        next_try_after=m.next_try_after,
        created_at=m.created_at,
    )


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_active_by_channel(self, channel_id: int) -> list[Source]:
        result = await self._s.execute(
            select(SourceModel)
            .where(SourceModel.channel_id == channel_id, SourceModel.is_active == True)
            .order_by(SourceModel.created_at)
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def count_by_channel(self, channel_id: int) -> int:
        from sqlalchemy import func
        result = await self._s.execute(
            select(func.count()).select_from(SourceModel)
            .where(SourceModel.channel_id == channel_id)
        )
        return result.scalar_one()

    async def create(self, source: Source) -> Source:
        model = SourceModel(
            channel_id=source.channel_id,
            owner_id=source.owner_id,
            title=source.title,
            url=source.url,
            feed_url=source.feed_url,
            source_type=source.source_type.value,
            is_active=source.is_active,
            api_url=source.api_url,
            api_key_encrypted=source.api_key_encrypted,
            api_note=source.api_note,
        )
        self._s.add(model)
        await self._s.flush()
        source.id = model.id
        return source

    async def update_fetch_state(
        self,
        source_id: int,
        etag: Optional[str],
        last_modified: Optional[str],
        fail_count: int,
        last_error: Optional[str],
    ) -> None:
        from datetime import datetime
        await self._s.execute(
            update(SourceModel)
            .where(SourceModel.id == source_id)
            .values(
                etag=etag,
                last_modified=last_modified,
                fail_count=fail_count,
                last_error=last_error,
                last_fetch=datetime.utcnow(),
            )
        )
