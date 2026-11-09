"""سرویس کاربر — ثبت‌نام، پروفایل، referral اولیه"""
from __future__ import annotations

from typing import Optional

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class UserService:

    async def handle_new_user(
        self,
        telegram_id: int,
        referred_by: Optional[int] = None,
    ) -> None:
        """
        اولین ورود کاربر:
        1. ثبت referral اگر وجود داشت
        2. اختصاص پلن رایگان
        """
        if referred_by and referred_by != telegram_id:
            from src.application.referral.service import ReferralService
            await ReferralService().register_referral(
                referrer_id=referred_by,
                referred_id=telegram_id,
            )

        # پلن رایگان پیش‌فرض
        await self._assign_free_plan(telegram_id)

    async def _assign_free_plan(self, telegram_id: int) -> None:
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel, PlanModel

            user = (await session.execute(
                select(UserModel).where(UserModel.telegram_id == telegram_id)
            )).scalar_one_or_none()

            if not user or user.plan_id is not None:
                return  # پلن قبلاً اختصاص یافته

            free_plan = (await session.execute(
                select(PlanModel).where(PlanModel.is_free == True, PlanModel.is_active == True)
                .order_by(PlanModel.sort)
                .limit(1)
            )).scalar_one_or_none()

            if free_plan:
                from sqlalchemy import update
                await session.execute(
                    update(UserModel)
                    .where(UserModel.telegram_id == telegram_id)
                    .values(plan_id=free_plan.id, plan_expires_at=None)
                )
                logger.info("free_plan_assigned", user=telegram_id, plan=free_plan.name)

    async def get_profile(self, telegram_id: int) -> Optional[dict]:
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel, PlanModel
            user = (await session.execute(
                select(UserModel).where(UserModel.telegram_id == telegram_id)
            )).scalar_one_or_none()

            if not user:
                return None

            plan_name = None
            if user.plan_id:
                plan = await session.get(PlanModel, user.plan_id)
                plan_name = plan.name if plan else None

        return {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "role": user.role,
            "plan": plan_name,
            "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
            "is_banned": user.is_banned,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
