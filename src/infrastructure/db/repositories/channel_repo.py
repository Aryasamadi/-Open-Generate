"""Repository کانال‌ها"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.channel import Channel, ChannelSettings
from src.infrastructure.db.models import ChannelModel


def _to_entity(m: ChannelModel) -> Channel:
    settings = ChannelSettings.from_dict(dict(m.settings_json)) if m.settings_json else ChannelSettings()
    return Channel(
        id=m.id,
        owner_id=m.owner_id,
        telegram_id=m.telegram_id,
        username=m.username,
        title=m.title,
        settings=settings,
        is_active=m.is_active,
        bot_is_admin=m.bot_is_admin,
        verified_at=m.verified_at,
        created_at=m.created_at,
    )


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, channel_id: int) -> Optional[Channel]:
        result = await self._s.execute(
            select(ChannelModel).where(ChannelModel.id == channel_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Channel]:
        result = await self._s.execute(
            select(ChannelModel).where(ChannelModel.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_by_owner(self, owner_id: int) -> list[Channel]:
        result = await self._s.execute(
            select(ChannelModel)
            .where(ChannelModel.owner_id == owner_id)
            .order_by(ChannelModel.created_at)
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def count_by_owner(self, owner_id: int) -> int:
        from sqlalchemy import func
        result = await self._s.execute(
            select(func.count()).select_from(ChannelModel)
            .where(ChannelModel.owner_id == owner_id)
        )
        return result.scalar_one()

    async def create(self, channel: Channel) -> Channel:
        model = ChannelModel(
            owner_id=channel.owner_id,
            telegram_id=channel.telegram_id,
            username=channel.username,
            title=channel.title,
            is_active=channel.is_active,
            bot_is_admin=channel.bot_is_admin,
            settings_json=channel.settings.to_dict(),
        )
        self._s.add(model)
        await self._s.flush()
        channel.id = model.id
        return channel

    async def update_settings(self, channel_id: int, settings: ChannelSettings) -> None:
        await self._s.execute(
            update(ChannelModel)
            .where(ChannelModel.id == channel_id)
            .values(settings_json=settings.to_dict())
        )

    async def set_active(self, channel_id: int, active: bool) -> None:
        await self._s.execute(
            update(ChannelModel)
            .where(ChannelModel.id == channel_id)
            .values(is_active=active)
        )

    async def set_bot_admin(self, channel_id: int, is_admin: bool) -> None:
        await self._s.execute(
            update(ChannelModel)
            .where(ChannelModel.id == channel_id)
            .values(bot_is_admin=is_admin)
        )

    async def list_ready_for_scheduler(self) -> list[Channel]:
        """کانال‌های آماده برای اجرای pipeline"""
        result = await self._s.execute(
            select(ChannelModel)
            .where(
                ChannelModel.is_active == True,
                ChannelModel.bot_is_admin == True,
            )
        )
        channels = [_to_entity(r) for r in result.scalars().all()]
        return [c for c in channels if c.settings.enabled]
