"""
سرویس معرفی — اعتبار به معرف پس از اولین خرید معرفی‌شده.
خودارجاعی و ثبت تکراری blocked.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from src.infrastructure.db.session import get_session
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

REFERRAL_CREDIT_AMOUNT = Decimal("50000")
REFERRAL_CURRENCY = "IRR"


class ReferralService:

    async def register_referral(
        self,
        referrer_id: int,
        referred_id: int,
    ) -> bool:
        """ثبت معرفی — یکتا برای هر referred_id"""
        if referrer_id == referred_id:
            logger.warning("self_referral_blocked", user_id=referrer_id)
            return False

        async with get_session() as session:
            from sqlalchemy import select
            from src.infrastructure.db.models import ReferralModel

            # بررسی ثبت قبلی
            result = await session.execute(
                select(ReferralModel).where(ReferralModel.referred_id == referred_id)
            )
            if result.scalar_one_or_none():
                logger.info("referral_already_registered", referred_id=referred_id)
                return False

            session.add(ReferralModel(
                referrer_id=referrer_id,
                referred_id=referred_id,
                credit_amount=REFERRAL_CREDIT_AMOUNT,
                currency=REFERRAL_CURRENCY,
                credited=False,
            ))
            logger.info("referral_registered", referrer=referrer_id, referred=referred_id)
        return True

    async def credit_referrer_on_first_purchase(self, referred_id: int) -> bool:
        """
        پس از اولین خرید معرفی‌شده، اعتبار به معرف اضافه می‌شود.
        Idempotent: اگر قبلاً credit شده، دوباره انجام نمی‌شود.
        """
        async with get_session() as session:
            from sqlalchemy import select, update
            from src.infrastructure.db.models import ReferralModel, WalletModel, LedgerModel
            import uuid

            result = await session.execute(
                select(ReferralModel).where(
                    ReferralModel.referred_id == referred_id,
                    ReferralModel.credited == False,
                )
            )
            referral = result.scalar_one_or_none()
            if not referral:
                return False

            referrer_id = referral.referrer_id
            amount = referral.credit_amount
            currency = referral.currency
            idempotency_key = f"referral_{referral.id}"

            # بررسی idempotency از ledger
            ledger_result = await session.execute(
                select(LedgerModel).where(
                    LedgerModel.idempotency_key == idempotency_key
                )
            )
            if ledger_result.scalar_one_or_none():
                logger.info("referral_already_credited", referral_id=referral.id)
                return True

            # واکشی یا ایجاد wallet
            wallet_result = await session.execute(
                select(WalletModel).where(
                    WalletModel.user_id == referrer_id,
                    WalletModel.currency == currency,
                )
            )
            wallet = wallet_result.scalar_one_or_none()
            if not wallet:
                wallet = WalletModel(
                    user_id=referrer_id,
                    currency=currency,
                    balance=Decimal("0"),
                )
                session.add(wallet)
                await session.flush()

            new_balance = wallet.balance + amount
            await session.execute(
                update(WalletModel)
                .where(
                    WalletModel.user_id == referrer_id,
                    WalletModel.currency == currency,
                )
                .values(balance=new_balance, updated_at=datetime.utcnow())
            )

            # ثبت ledger
            session.add(LedgerModel(
                user_id=referrer_id,
                currency=currency,
                delta=amount,
                balance_after=new_balance,
                reason="referral_credit",
                ref=str(referral.id),
                idempotency_key=idempotency_key,
            ))

            # علامت‌گذاری referral
            await session.execute(
                update(ReferralModel)
                .where(ReferralModel.id == referral.id)
                .values(credited=True, credited_at=datetime.utcnow())
            )

            # notification
            session.add(__import__(
                "src.infrastructure.db.models", fromlist=["NotificationModel"]
            ).NotificationModel(
                user_id=referrer_id,
                notification_type="referral_credited",
                payload={"amount": str(amount), "currency": currency},
                next_attempt_at=datetime.utcnow(),
            ))

            logger.info(
                "referral_credited",
                referrer=referrer_id,
                amount=str(amount),
                currency=currency,
            )
        return True
