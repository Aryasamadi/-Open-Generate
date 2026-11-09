"""
سرویس ادمین — مدیریت کاربران، پلن‌ها، broadcast، آمار کلی.
تمام عملیات audit log دارند.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AdminService:

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    # ------------------------------------------------------------------ پلن
    async def assign_plan(
        self,
        target_telegram_id: int,
        plan_id: int,
        assigned_by: int,
        reason: Optional[str] = None,
        days_override: Optional[int] = None,
    ) -> bool:
        """اختصاص پلن دستی — با audit log"""
        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import UserModel, PlanModel, PlanChangeModel

            user = (await session.execute(
                select(UserModel).where(UserModel.telegram_id == target_telegram_id)
            )).scalar_one_or_none()
            if not user:
                return False

            plan = await session.get(PlanModel, plan_id)
            if not plan:
                return False

            days = days_override or plan.days
            expires = datetime.utcnow() + timedelta(days=days) if days else None

            old_plan = user.plan_id
            await session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == target_telegram_id)
                .values(plan_id=plan_id, plan_expires_at=expires)
            )
            session.add(PlanChangeModel(
                user_id=target_telegram_id,
                old_plan_id=old_plan,
                new_plan_id=plan_id,
                changed_by=assigned_by,
                reason=reason or "admin_manual_assign",
            ))

            logger.info(
                "plan_assigned",
                target=target_telegram_id,
                plan=plan.name,
                by=assigned_by,
                expires=expires.isoformat() if expires else "never",
            )
        return True

    # ------------------------------------------------------------------ broadcast
    async def broadcast(
        self,
        text: str,
        sent_by: int,
        only_active: bool = True,
        parse_mode: str = "HTML",
    ) -> dict[str, int]:
        """ارسال همگانی — بدون block شدن، با آمار"""
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import UserModel

            query = select(UserModel.telegram_id).where(UserModel.is_banned == False)
            if only_active:
                cutoff = datetime.utcnow() - timedelta(days=90)
                query = query.where(UserModel.last_active_at >= cutoff)

            result = await session.execute(query)
            telegram_ids = [r[0] for r in result.fetchall()]

        ok = fail = 0
        BATCH_SIZE = 25
        DELAY_BETWEEN_BATCHES = 1.0  # second

        for i in range(0, len(telegram_ids), BATCH_SIZE):
            batch = telegram_ids[i : i + BATCH_SIZE]
            tasks = [self._send_one(uid, text, parse_mode) for uid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if r is True:
                    ok += 1
                else:
                    fail += 1
            if i + BATCH_SIZE < len(telegram_ids):
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

        logger.info("broadcast_done", ok=ok, fail=fail, by=sent_by)
        return {"ok": ok, "fail": fail, "total": len(telegram_ids)}

    async def _send_one(self, user_id: int, text: str, parse_mode: str) -> bool:
        try:
            await self._bot.send_message(
                chat_id=user_id, text=text, parse_mode=parse_mode
            )
            return True
        except TelegramError:
            return False

    # ------------------------------------------------------------------ آمار
    async def global_stats(self) -> dict:
        async with get_session() as session:
            from sqlalchemy import select, func
            from src.infrastructure.db.models import (
                UserModel, ChannelModel, ArticleModel, PayRequestModel
            )
            from datetime import date

            today = date.today().isoformat()

            users = (await session.execute(select(func.count()).select_from(UserModel))).scalar_one()
            channels = (await session.execute(select(func.count()).select_from(ChannelModel).where(ChannelModel.is_active == True))).scalar_one()
            published_today = (await session.execute(
                select(func.count()).select_from(ArticleModel)
                .where(
                    ArticleModel.status == "published",
                    func.date(ArticleModel.published_at_actual) == today,
                )
            )).scalar_one()
            pending_payments = (await session.execute(
                select(func.count()).select_from(PayRequestModel)
                .where(PayRequestModel.status == "pending")
            )).scalar_one()
            banned_users = (await session.execute(
                select(func.count()).select_from(UserModel).where(UserModel.is_banned == True)
            )).scalar_one()

        return {
            "total_users": users,
            "active_channels": channels,
            "published_today": published_today,
            "pending_payments": pending_payments,
            "banned_users": banned_users,
        }

    # ------------------------------------------------------------------ کاربر
    async def search_users(self, query: str, limit: int = 10) -> list[dict]:
        async with get_session() as session:
            from sqlalchemy import select, or_
            from src.infrastructure.db.models import UserModel

            try:
                tg_id = int(query)
                result = await session.execute(
                    select(UserModel).where(UserModel.telegram_id == tg_id).limit(limit)
                )
            except ValueError:
                uname = query.lstrip("@")
                result = await session.execute(
                    select(UserModel).where(UserModel.username.ilike(f"%{uname}%")).limit(limit)
                )
            users = result.scalars().all()

        return [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "first_name": u.first_name,
                "role": u.role,
                "plan_id": u.plan_id,
                "is_banned": u.is_banned,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]

    # ------------------------------------------------------------------ discount
    async def create_discount(
        self,
        code: str,
        percent: Decimal,
        max_uses: int,
        expires_in_days: Optional[int],
        created_by: int,
    ) -> bool:
        async with get_session() as session:
            from src.infrastructure.db.models import DiscountModel
            expires = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
            session.add(DiscountModel(
                code=code.upper().strip(),
                percent=percent,
                max_uses=max_uses,
                expires_at=expires,
                is_active=True,
            ))
            logger.info("discount_created", code=code, percent=str(percent), by=created_by)
        return True
