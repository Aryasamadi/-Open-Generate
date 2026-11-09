"""تست‌های واحد — domain entities و business rules"""
from __future__ import annotations

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore[assignment]
from decimal import Decimal
from datetime import datetime, timedelta

from src.domain.entities.user import User, UserRole
from src.domain.entities.wallet import Wallet, LedgerEntry
from src.domain.entities.discount import Discount
from src.domain.entities.referral import Referral
from src.domain.entities.article import Article, ArticleStatus
from src.domain.entities.ai_model import AIModel, AIProvider


class TestUser:
    def test_banned_user_cannot_access(self):
        user = User(1, "test", "Test", None, is_banned=True)
        assert not user.can_access(UserRole.USER)

    def test_super_admin_can_access_all(self):
        user = User(1, "admin", "Admin", None, role=UserRole.SUPER_ADMIN)
        assert user.can_access(UserRole.USER)
        assert user.can_access(UserRole.ADMIN)
        assert user.can_access(UserRole.SUPER_ADMIN)

    def test_regular_user_cannot_access_admin(self):
        user = User(1, "u", "User", None, role=UserRole.USER)
        assert user.can_access(UserRole.USER)
        assert not user.can_access(UserRole.ADMIN)

    def test_plan_expired(self):
        past = datetime.utcnow() - timedelta(days=1)
        user = User(1, "u", "User", None, plan_expires_at=past)
        assert user.plan_is_expired

    def test_plan_active(self):
        future = datetime.utcnow() + timedelta(days=30)
        user = User(1, "u", "User", None, plan_expires_at=future)
        assert user.has_active_plan


class TestWallet:
    def test_overdraft_prevented(self):
        wallet = Wallet(user_id=1, currency="IRR", balance=Decimal("100"))
        with pytest.raises(ValueError, match="موجودی کافی"):
            wallet.apply_delta(Decimal("-200"))

    def test_valid_debit(self):
        wallet = Wallet(user_id=1, currency="IRR", balance=Decimal("500"))
        wallet.apply_delta(Decimal("-100"))
        assert wallet.balance == Decimal("400")

    def test_credit(self):
        wallet = Wallet(user_id=1, currency="IRR", balance=Decimal("0"))
        wallet.apply_delta(Decimal("1000"))
        assert wallet.balance == Decimal("1000")

    def test_negative_initial_balance_rejected(self):
        with pytest.raises(ValueError):
            Wallet(user_id=1, currency="IRR", balance=Decimal("-1"))

    def test_no_float_allowed(self):
        # Decimal باید استفاده شود، نه float
        wallet = Wallet(user_id=1, currency="USD", balance=Decimal("0"))
        wallet.apply_delta(Decimal("0.01"))
        assert isinstance(wallet.balance, Decimal)


class TestDiscount:
    def test_valid_discount(self):
        future = datetime.utcnow() + timedelta(days=30)
        d = Discount(code="SAVE10", percent=Decimal("10"), expires_at=future, max_uses=100)
        assert d.is_valid()
        result = d.apply_to(Decimal("1000"))
        assert result == Decimal("900.00")

    def test_expired_discount_invalid(self):
        past = datetime.utcnow() - timedelta(days=1)
        d = Discount(code="OLD", percent=Decimal("10"), expires_at=past, max_uses=100)
        assert not d.is_valid()

    def test_used_up_discount_invalid(self):
        future = datetime.utcnow() + timedelta(days=30)
        d = Discount(code="FULL", percent=Decimal("10"), expires_at=future, max_uses=5, used=5)
        assert not d.is_valid()

    def test_invalid_percent(self):
        with pytest.raises(ValueError):
            Discount(code="BAD", percent=Decimal("150"), expires_at=None, max_uses=10)


class TestReferral:
    def test_self_referral_blocked(self):
        with pytest.raises(ValueError, match="خودارجاعی"):
            Referral(referrer_id=1, referred_id=1, credit_amount=Decimal("10"), currency="IRR")

    def test_valid_referral(self):
        r = Referral(referrer_id=1, referred_id=2, credit_amount=Decimal("50000"), currency="IRR")
        assert r.referrer_id != r.referred_id


class TestArticleStateMachine:
    def _make_article(self) -> Article:
        return Article(
            channel_id=1, source_id=1,
            url="https://example.com/article",
            canonical_url="https://example.com/article",
            title="Test Article",
            content_hash="abc123",
            url_hash="def456",
        )

    def test_initial_status(self):
        a = self._make_article()
        assert a.status == ArticleStatus.FETCHED

    def test_transition_records_reason(self):
        a = self._make_article()
        a.transition(ArticleStatus.REJECTED, reason="low_score")
        assert a.status == ArticleStatus.REJECTED
        assert a.reason == "low_score"

    def test_terminal_states(self):
        assert ArticleStatus.PUBLISHED.is_terminal
        assert ArticleStatus.REJECTED.is_terminal
        assert not ArticleStatus.PENDING_REVIEW.is_terminal


class TestAIModel:
    def test_global_model_cannot_have_owner(self):
        with pytest.raises(ValueError):
            AIModel(
                provider=AIProvider.OPENAI,
                display_name="Test",
                base_url="https://api.openai.com",
                model_id="gpt-4",
                is_global=True,
                owner_id=123,
            )

    def test_personal_model_must_have_owner(self):
        with pytest.raises(ValueError):
            AIModel(
                provider=AIProvider.OPENAI,
                display_name="Test",
                base_url="https://api.openai.com",
                model_id="gpt-4",
                is_global=False,
                owner_id=None,
            )

    def test_circuit_open_model_unavailable(self):
        m = AIModel(
            provider=AIProvider.OPENAI,
            display_name="Test",
            base_url="https://api.openai.com",
            model_id="gpt-4",
            is_global=False,
            owner_id=1,
            circuit_open=True,
        )
        assert not m.is_available
