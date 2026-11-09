"""pytest configuration"""
from __future__ import annotations

import os
import sys

import pytest

# اضافه کردن root به path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# متغیرهای محیطی برای تست
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "0:test_token_for_testing")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-chars-min")
os.environ.setdefault("DB_DRIVER", "sqlite+aiosqlite")
os.environ.setdefault("SQLITE_PATH", ":memory:")
os.environ.setdefault("SUPER_ADMIN_IDS", "123456789")
os.environ.setdefault("DB_PASSWORD", "test_password")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
