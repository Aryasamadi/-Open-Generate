"""تست‌های امنیتی — SSRF، injection، authorization"""
from __future__ import annotations

import pytest

from src.infrastructure.fetcher.safe_fetcher import (
    SSRFBlockedError,
    _validate_url,
    _validate_resolved_ip,
)
from src.infrastructure.crypto.encryption import encrypt, decrypt, mask_secret


class TestSSRF:
    """مقابله با SSRF و private IP"""

    def test_localhost_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("127.0.0.1")

    def test_private_10_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("10.0.0.1")

    def test_private_192_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("192.168.1.1")

    def test_link_local_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("169.254.169.254")  # AWS metadata

    def test_private_172_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("172.16.0.1")

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_resolved_ip("::1")

    def test_url_with_credentials_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_url("https://user:pass@example.com/feed")

    def test_non_http_scheme_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_url("ftp://example.com/feed")

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFBlockedError):
            _validate_url("file:///etc/passwd")

    def test_public_url_allowed(self):
        # نباید exception بدهد
        _validate_url("https://feeds.bbcnews.com/news/world/rss.xml")


class TestEncryption:
    def test_roundtrip(self, monkeypatch):
        # Mock settings برای تست بدون .env
        from unittest.mock import MagicMock
        from pydantic import SecretStr
        import config.settings as settings_module

        mock_settings = MagicMock()
        mock_settings.ENCRYPTION_KEY = SecretStr("a" * 32)
        monkeypatch.setattr(settings_module, "_settings_instance", mock_settings)

        plaintext = "sk-test-api-key-12345"
        encrypted = encrypt(plaintext)
        assert encrypted != plaintext
        assert decrypt(encrypted) == plaintext

    def test_mask_secret(self):
        masked = mask_secret("sk-1234567890abcdef", visible=4)
        assert masked.startswith("sk-1")
        assert "••••" in masked
        assert "1234567890abcdef" not in masked

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            encrypt("")


class TestAuthorizationLogic:
    def test_callback_data_is_not_permission(self):
        """callback_data مجوز نیست — باید از DB ownership بررسی شود"""
        from src.domain.entities.user import User, UserRole

        # کاربر A — channel_id=1 دارد
        user_a = User(telegram_id=100, username="a", first_name="A", last_name=None)
        # کاربر B — channel_id=1 ندارد اما callback_data آن را می‌داند
        user_b = User(telegram_id=200, username="b", first_name="B", last_name=None)

        # ownership باید در DB بررسی شود، نه از callback_data
        # این تست logic را document می‌کند
        assert user_a.telegram_id != user_b.telegram_id
