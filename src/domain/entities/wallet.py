"""موجودیت کیف پول و دفتر کل — چندارزی"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Wallet:
    """
    کیف پول — یک رکورد به ازای هر (user_id, currency).
    عملیات مالی atomic و با Decimal (نه float).
    """

    def __init__(
        self,
        user_id: int,
        currency: str,         # "IRR" | "USD" | ...
        balance: Decimal = Decimal("0"),
        id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        if balance < 0:
            raise ValueError("موجودی کیف پول نمی‌تواند منفی باشد")
        self.id = id
        self.user_id = user_id
        self.currency = currency
        self.balance = balance
        self.updated_at = updated_at or datetime.utcnow()

    def apply_delta(self, delta: Decimal) -> None:
        """اعمال تغییر موجودی — از overdraft جلوگیری می‌کند"""
        new_balance = self.balance + delta
        if new_balance < Decimal("0"):
            raise ValueError(
                f"موجودی کافی نیست: موجودی={self.balance}, تغییر={delta}"
            )
        self.balance = new_balance
        self.updated_at = datetime.utcnow()


class LedgerEntry:
    """
    دفتر کل — هر تراکنش مالی یک رکورد دارد.
    سوابق حسابداری هرگز حذف نمی‌شوند.
    """

    def __init__(
        self,
        user_id: int,
        currency: str,
        delta: Decimal,
        balance_after: Decimal,
        reason: str,              # "referral_credit" | "plan_payment" | ...
        ref: Optional[str] = None,  # شناسه مرجع
        note: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.currency = currency
        self.delta = delta
        self.balance_after = balance_after
        self.reason = reason
        self.ref = ref
        self.note = note
        self.idempotency_key = idempotency_key
        self.created_at = created_at or datetime.utcnow()
