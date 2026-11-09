"""موجودیت درخواست پرداخت"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class PayStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"      # پلن اعمال شد
    NOTIFIED = "notified"    # کاربر مطلع شد
    REFUNDED = "refunded"


class PayRequest:
    """
    درخواست پرداخت — پرداخت دستی نباید صرفاً بر اساس متن کاربر تأیید شود.
    اعمال پلن فقط یک بار انجام می‌شود (idempotency).
    """

    def __init__(
        self,
        user_id: int,
        plan_id: int,
        amount: Decimal,
        currency: str,              # "IRR" | "USD" | ...
        status: PayStatus = PayStatus.PENDING,
        receipt_path: Optional[str] = None,
        receipt_mime: Optional[str] = None,
        receipt_size: Optional[int] = None,
        discount_code: Optional[str] = None,
        discount_applied: Decimal = Decimal("0"),
        note: Optional[str] = None,
        # --- تصمیم ---
        decided_by: Optional[int] = None,   # telegram_id سوپرادمین
        decision_note: Optional[str] = None,
        # --- زمان‌ها ---
        claimed_at: Optional[datetime] = None,
        applied_at: Optional[datetime] = None,
        decided_at: Optional[datetime] = None,
        notified_at: Optional[datetime] = None,
        # --- idempotency ---
        idempotency_key: Optional[str] = None,
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.plan_id = plan_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.receipt_path = receipt_path
        self.receipt_mime = receipt_mime
        self.receipt_size = receipt_size
        self.discount_code = discount_code
        self.discount_applied = discount_applied
        self.note = note
        self.decided_by = decided_by
        self.decision_note = decision_note
        self.claimed_at = claimed_at
        self.applied_at = applied_at
        self.decided_at = decided_at
        self.notified_at = notified_at
        self.idempotency_key = idempotency_key
        self.created_at = created_at or datetime.utcnow()
