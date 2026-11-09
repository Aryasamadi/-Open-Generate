"""Repository کاربران"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User, UserRole
from src.infrastructure.db.models import UserModel


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        telegram_id=m.telegram_id,
        username=m.username,
        first_name=m.first_name,
        last_name=m.last_name,
        language=m.language,
        role=UserRole(m.role),
        plan_id=m.plan_id,
        plan_expires_at=m.plan_expires_at,
        next_plan_id=m.next_plan_id,
        next_plan_starts_at=m.next_plan_starts_at,
        is_banned=m.is_banned,
        ban_reason=m.ban_reason,
        free_quota_used=m.free_quota_used,
        created_at=m.created_at,
        last_active_at=m.last_active_at,
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self._s.execute(
            select(UserModel).where(UserModel.telegram_id == telegram_id)
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str],
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            # به‌روزرسانی اطلاعات پروفایل
            await self._s.execute(
                update(UserModel)
                .where(UserModel.telegram_id == telegram_id)
                .values(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
            )
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            return user

        model = UserModel(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language="fa",
            role="user",
        )
        self._s.add(model)
        await self._s.flush()
        return _to_entity(model)

    async def update_last_active(self, user_id: int) -> None:
        await self._s.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_active_at=datetime.utcnow())
        )

    async def ban(self, telegram_id: int, reason: str, by: int) -> None:
        await self._s.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(is_banned=True, ban_reason=reason)
        )

    async def unban(self, telegram_id: int) -> None:
        await self._s.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(is_banned=False, ban_reason=None)
        )

    async def set_language(self, telegram_id: int, language: str) -> None:
        await self._s.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(language=language)
        )

    async def count_all(self) -> int:
        from sqlalchemy import func
        result = await self._s.execute(
            select(func.count()).select_from(UserModel)
        )
        return result.scalar_one()
