"""
سرویس کیف پول — واریز/برداشت atomic با دفتر کل.
هر تراکنش idempotency_key دارد تا تکرار مشکل نسازد.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class WalletService:

    async def credit(
        self,
        user_id: int,
        amount: Decimal,
        currency: str,
        reason: str,
        ref: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> bool:
        """واریز به کیف پول — idempotent"""
        if amount <= Decimal("0"):
            raise ValueError("مبلغ باید مثبت باشد")

        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import WalletModel, LedgerModel

            # بررسی idempotency
            if idempotency_key:
                existing = (await session.execute(
                    select(LedgerModel).where(LedgerModel.idempotency_key == idempotency_key)
                )).scalar_one_or_none()
                if existing:
                    logger.info("wallet_credit_idempotent", key=idempotency_key)
                    return True

            # واکشی یا ایجاد wallet
            wallet = (await session.execute(
                select(WalletModel).where(
                    WalletModel.user_id == user_id,
                    WalletModel.currency == currency,
                )
            )).scalar_one_or_none()

            if not wallet:
                wallet = WalletModel(
                    user_id=user_id,
                    currency=currency,
                    balance=Decimal("0"),
                )
                session.add(wallet)
                await session.flush()

            new_balance = wallet.balance + amount
            await session.execute(
                update(WalletModel)
                .where(
                    WalletModel.user_id == user_id,
                    WalletModel.currency == currency,
                )
                .values(balance=new_balance, updated_at=datetime.utcnow())
            )

            session.add(LedgerModel(
                user_id=user_id,
                currency=currency,
                delta=amount,
                balance_after=new_balance,
                reason=reason,
                ref=ref,
                idempotency_key=idempotency_key,
            ))

            logger.info(
                "wallet_credited",
                user=user_id,
                amount=str(amount),
                currency=currency,
                reason=reason,
            )
        return True

    async def debit(
        self,
        user_id: int,
        amount: Decimal,
        currency: str,
        reason: str,
        ref: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> bool:
        """برداشت از کیف پول — بررسی موجودی"""
        if amount <= Decimal("0"):
            raise ValueError("مبلغ باید مثبت باشد")

        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import WalletModel, LedgerModel

            if idempotency_key:
                existing = (await session.execute(
                    select(LedgerModel).where(LedgerModel.idempotency_key == idempotency_key)
                )).scalar_one_or_none()
                if existing:
                    return True

            wallet = (await session.execute(
                select(WalletModel).where(
                    WalletModel.user_id == user_id,
                    WalletModel.currency == currency,
                )
            )).scalar_one_or_none()

            if not wallet or wallet.balance < amount:
                logger.warning("wallet_insufficient", user=user_id, amount=str(amount))
                return False

            new_balance = wallet.balance - amount
            await session.execute(
                update(WalletModel)
                .where(
                    WalletModel.user_id == user_id,
                    WalletModel.currency == currency,
                )
                .values(balance=new_balance, updated_at=datetime.utcnow())
            )

            session.add(LedgerModel(
                user_id=user_id,
                currency=currency,
                delta=-amount,
                balance_after=new_balance,
                reason=reason,
                ref=ref,
                idempotency_key=idempotency_key,
            ))

        return True

    async def get_balance(self, user_id: int, currency: str) -> Decimal:
        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import WalletModel
            wallet = (await session.execute(
                select(WalletModel).where(
                    WalletModel.user_id == user_id,
                    WalletModel.currency == currency,
                )
            )).scalar_one_or_none()
        return wallet.balance if wallet else Decimal("0")


# import circular را جلوگیری می‌کنیم
from src.infrastructure.db.models import LedgerModel  # noqa: E402, F401
