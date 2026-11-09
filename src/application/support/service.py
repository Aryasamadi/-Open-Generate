"""سرویس پشتیبانی — مدیریت تیکت‌ها، پاسخ ادمین"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class SupportService:

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def reply_to_ticket(
        self,
        ticket_id: int,
        admin_id: int,
        message: str,
        file_id: Optional[str] = None,
    ) -> bool:
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import (
                SupportTicketModel, SupportMessageModel, NotificationModel
            )

            ticket = await session.get(SupportTicketModel, ticket_id)
            if not ticket or ticket.status == "closed":
                return False

            # ثبت پیام ادمین
            session.add(SupportMessageModel(
                ticket_id=ticket_id,
                sender_id=admin_id,
                is_admin=True,
                text=message,
                file_id=file_id,
            ))

            # notification برای کاربر
            session.add(NotificationModel(
                user_id=ticket.user_id,
                notification_type="support_reply",
                payload={"ticket_id": ticket_id, "message": message[:300]},
                next_attempt_at=datetime.utcnow(),
            ))

            logger.info("support_reply_sent", ticket_id=ticket_id, by=admin_id)
        return True

    async def close_ticket(self, ticket_id: int, closed_by: int) -> bool:
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import SupportTicketModel
            ticket = await session.get(SupportTicketModel, ticket_id)
            if not ticket:
                return False
            await session.execute(
                update(SupportTicketModel)
                .where(SupportTicketModel.id == ticket_id)
                .values(status="closed", closed_at=datetime.utcnow())
            )
            logger.info("ticket_closed", ticket_id=ticket_id, by=closed_by)
        return True

    async def list_open_tickets(self, limit: int = 50) -> list[dict]:
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import SupportTicketModel, UserModel
            result = await session.execute(
                select(SupportTicketModel)
                .where(SupportTicketModel.status == "open")
                .order_by(SupportTicketModel.created_at)
                .limit(limit)
            )
            tickets = result.scalars().all()

        return [
            {
                "id": t.id,
                "user_id": t.user_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]
