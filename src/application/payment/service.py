"""
سرویس پرداخت — تأیید/رد با idempotency کامل.
اعمال پلن فقط یک بار انجام می‌شود.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PaymentService:

    async def approve(
        self,
        pay_id: int,
        decided_by: int,
        note: Optional[str] = None,
    ) -> bool:
        """
        تأیید پرداخت — idempotent:
        اگر قبلاً approved/applied شده، دوباره پلن اعمال نمی‌شود.
        """
        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import PayRequestModel, PlanModel, UserModel, PlanChangeModel

            pay = await session.get(PayRequestModel, pay_id)
            if not pay:
                logger.error("payment_not_found", pay_id=pay_id)
                return False

            # Idempotency guard
            if pay.status in ("approved", "applied"):
                logger.info("payment_already_approved", pay_id=pay_id, status=pay.status)
                return True

            if pay.status != "pending":
                logger.warning("payment_wrong_state", pay_id=pay_id, status=pay.status)
                return False

            # 1) تأیید
            await session.execute(
                update(PayRequestModel)
                .where(PayRequestModel.id == pay_id)
                .values(
                    status="approved",
                    decided_by=decided_by,
                    decision_note=note,
                    decided_at=datetime.utcnow(),
                )
            )

            # 2) واکشی پلن
            plan = await session.get(PlanModel, pay.plan_id)
            if not plan:
                logger.error("plan_not_found_for_payment", pay_id=pay_id, plan_id=pay.plan_id)
                return False

            # 3) اعمال پلن
            expires = datetime.utcnow() + timedelta(days=plan.days) if plan.days else None
            await session.execute(
                update(UserModel)
                .where(UserModel.telegram_id == pay.user_id)
                .values(plan_id=plan.id, plan_expires_at=expires)
            )

            # 4) ثبت audit log
            session.add(PlanChangeModel(
                user_id=pay.user_id,
                new_plan_id=plan.id,
                changed_by=decided_by,
                reason=f"payment_approved:#{pay_id}",
                pay_request_id=pay_id,
            ))

            # 5) applied
            await session.execute(
                update(PayRequestModel)
                .where(PayRequestModel.id == pay_id)
                .values(status="applied", applied_at=datetime.utcnow())
            )

            logger.info(
                "payment_approved_and_applied",
                pay_id=pay_id,
                user=pay.user_id,
                plan=plan.name,
                by=decided_by,
            )

        # 6) ایجاد notification
        await self._queue_approval_notification(pay.user_id, pay_id, plan.name)
        return True

    async def reject(
        self,
        pay_id: int,
        decided_by: int,
        reason: str,
    ) -> bool:
        async with get_session() as session:
            from sqlalchemy import update
            from src.infrastructure.db.models import PayRequestModel

            pay = await session.get(PayRequestModel, pay_id)
            if not pay or pay.status != "pending":
                return False

            await session.execute(
                update(PayRequestModel)
                .where(PayRequestModel.id == pay_id)
                .values(
                    status="rejected",
                    decided_by=decided_by,
                    decision_note=reason,
                    decided_at=datetime.utcnow(),
                )
            )
            logger.info("payment_rejected", pay_id=pay_id, by=decided_by, reason=reason)

        await self._queue_rejection_notification(pay.user_id, pay_id, reason)
        return True

    async def _queue_approval_notification(
        self, user_id: int, pay_id: int, plan_name: str
    ) -> None:
        async with get_session() as session:
            from src.infrastructure.db.models import NotificationModel
            session.add(NotificationModel(
                user_id=user_id,
                notification_type="payment_approved",
                payload={"pay_id": pay_id, "plan_name": plan_name},
                next_attempt_at=datetime.utcnow(),
            ))

    async def _queue_rejection_notification(
        self, user_id: int, pay_id: int, reason: str
    ) -> None:
        async with get_session() as session:
            from src.infrastructure.db.models import NotificationModel
            session.add(NotificationModel(
                user_id=user_id,
                notification_type="payment_rejected",
                payload={"pay_id": pay_id, "reason": reason},
                next_attempt_at=datetime.utcnow(),
            ))
