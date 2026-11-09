"""
Integration tests — نیاز به DB دارند.
با SQLite in-memory اجرا می‌شوند.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

# env برای tests
os.environ.update({
    "APP_ENV": "development",
    "TELEGRAM_BOT_TOKEN": "0:test",
    "ENCRYPTION_KEY": "test-encryption-key-32-chars-min-xx",
    "DB_PASSWORD": "test",
    "SUPER_ADMIN_IDS": "123",
    "DB_DRIVER": "sqlite+aiosqlite",
    "SQLITE_PATH": ":memory:",
})

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
async def db_engine():
    """ایجاد جداول در SQLite in-memory"""
    from src.infrastructure.db.session import get_engine
    from src.infrastructure.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(db_engine):
    from src.infrastructure.db.session import get_session
    async with get_session() as s:
        yield s


class TestUserRepository:
    async def test_get_or_create_new(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        async with get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(
                telegram_id=111111111,
                username="testuser1",
                first_name="Test",
                last_name=None,
            )
        assert user.telegram_id == 111111111
        assert user.username == "testuser1"

    async def test_get_or_create_existing(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        # ایجاد اول
        async with get_session() as session:
            repo = UserRepository(session)
            await repo.get_or_create(
                telegram_id=222222222, username="u2", first_name="A", last_name=None
            )
        # بار دوم — نباید duplicate ایجاد شود
        async with get_session() as session:
            repo = UserRepository(session)
            user = await repo.get_or_create(
                telegram_id=222222222, username="u2_updated", first_name="A", last_name=None
            )
        assert user.username == "u2_updated"


class TestWalletService:
    async def test_credit_and_debit(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        # کاربر اول بساز
        async with get_session() as session:
            await UserRepository(session).get_or_create(
                telegram_id=333333333, username="wallet_test", first_name="W", last_name=None
            )

        from src.application.wallet.service import WalletService
        svc = WalletService()

        ok = await svc.credit(
            user_id=333333333,
            amount=Decimal("1000"),
            currency="IRR",
            reason="test_credit",
            idempotency_key="test-credit-001",
        )
        assert ok is True

        balance = await svc.get_balance(333333333, "IRR")
        assert balance == Decimal("1000")

        ok = await svc.debit(
            user_id=333333333,
            amount=Decimal("300"),
            currency="IRR",
            reason="test_debit",
        )
        assert ok is True

        balance = await svc.get_balance(333333333, "IRR")
        assert balance == Decimal("700")

    async def test_overdraft_prevented(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        async with get_session() as session:
            await UserRepository(session).get_or_create(
                telegram_id=444444444, username="overdraft_test", first_name="O", last_name=None
            )

        from src.application.wallet.service import WalletService
        svc = WalletService()
        ok = await svc.debit(
            user_id=444444444,
            amount=Decimal("99999"),
            currency="IRR",
            reason="test_overdraft",
        )
        assert ok is False

    async def test_idempotency(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        async with get_session() as session:
            await UserRepository(session).get_or_create(
                telegram_id=555555555, username="idem_test", first_name="I", last_name=None
            )

        from src.application.wallet.service import WalletService
        svc = WalletService()
        key = "idempotency-test-key-xyz"

        await svc.credit(555555555, Decimal("500"), "IRR", "test", idempotency_key=key)
        await svc.credit(555555555, Decimal("500"), "IRR", "test", idempotency_key=key)  # تکرار

        balance = await svc.get_balance(555555555, "IRR")
        assert balance == Decimal("500"), f"Expected 500, got {balance}"


class TestSubscriptionService:
    async def test_free_plan_limits(self, db_engine):
        from src.application.subscription.service import SubscriptionService, FREE_PLAN
        svc = SubscriptionService()
        # کاربر بدون پلن → پلن رایگان
        limits = await svc.get_plan_limits(999999999)
        assert limits == FREE_PLAN

    async def test_track_usage(self, db_engine):
        from src.infrastructure.db.session import get_session
        from src.infrastructure.db.repositories.user_repo import UserRepository
        async with get_session() as session:
            await UserRepository(session).get_or_create(
                telegram_id=666666666, username="usage_test", first_name="U", last_name=None
            )

        from src.application.subscription.service import SubscriptionService
        svc = SubscriptionService()

        await svc.track_usage(666666666, posts=2, ai_calls=3, tokens_in=100, tokens_out=50)

        from src.infrastructure.db.session import get_session
        from sqlalchemy import select
        from src.infrastructure.db.models import UsageModel
        from datetime import date
        today = date.today().isoformat()
        async with get_session() as session:
            result = await session.execute(
                select(UsageModel).where(
                    UsageModel.user_id == 666666666,
                    UsageModel.date == today,
                )
            )
            usage = result.scalar_one_or_none()
        assert usage is not None
        assert usage.posts_count == 2
        assert usage.ai_calls == 3
