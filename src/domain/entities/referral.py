"""موجودیت معرفی (Referral)"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional


class Referral:
    """
    referred یکتا است — هر کاربر فقط یک بار معرفی می‌شود.
    خودارجاعی و سوءاستفاده ممنوع است.
    """

    def __init__(
        self,
        referrer_id: int,       # telegram_id معرف
        referred_id: int,       # telegram_id معرفی‌شده
        credit_amount: Decimal,
        currency: str,
        credited: bool = False,
        credited_at: Optional[datetime] = None,
        note: Optional[str] = None,
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        if referrer_id == referred_id:
            raise ValueError("خودارجاعی مجاز نیست")
        self.id = id
        self.referrer_id = referrer_id
        self.referred_id = referred_id
        self.credit_amount = credit_amount
        self.currency = currency
        self.credited = credited
        self.credited_at = credited_at
        self.note = note
        self.created_at = created_at or datetime.utcnow()
