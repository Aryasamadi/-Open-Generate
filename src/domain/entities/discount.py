"""موجودیت کد تخفیف"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Discount:
    def __init__(
        self,
        code: str,
        percent: Decimal,           # ۰ تا ۱۰۰
        expires_at: Optional[datetime],
        max_uses: int,
        used: int = 0,
        is_active: bool = True,
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        if not (Decimal("0") <= percent <= Decimal("100")):
            raise ValueError("درصد تخفیف باید بین ۰ و ۱۰۰ باشد")
        self.id = id
        self.code = code.upper().strip()
        self.percent = percent
        self.expires_at = expires_at
        self.max_uses = max_uses
        self.used = used
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        if not self.is_active:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        if self.used >= self.max_uses:
            return False
        return True

    def apply_to(self, amount: Decimal) -> Decimal:
        """مبلغ تخفیف‌خورده را برمی‌گرداند"""
        discount_amount = (amount * self.percent / Decimal("100")).quantize(Decimal("0.01"))
        return max(Decimal("0"), amount - discount_amount)
