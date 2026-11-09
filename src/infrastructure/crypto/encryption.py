"""
رمزنگاری API keyها و secretها در حالت سکون.
نبود کلید در production = fail closed؛ plaintext fallback ممنوع.
کلید رمزنگاری هرگز داخل DB یا backup DB نباشد.
"""
from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config.settings import get_settings


def _get_fernet() -> Fernet:
    """
    ساخت Fernet از ENCRYPTION_KEY.
    کلید 32+ کاراکتر → PBKDF2 → Fernet key.
    """
    settings = get_settings()
    raw_key = settings.ENCRYPTION_KEY.get_secret_value().encode()

    # PBKDF2 با salt ثابت (کلید ما deterministic باشد)
    # salt از app_version + constant برای versioning
    salt = b"opengenerate-v1-salt"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(raw_key))
    return Fernet(derived)


def encrypt(plaintext: str) -> str:
    """رمزنگاری رشته — خروجی base64 URL-safe"""
    if not plaintext:
        raise ValueError("رمزنگاری رشته خالی مجاز نیست")
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """رمزگشایی — در صورت خرابی token، ValueError می‌دهد"""
    if not ciphertext:
        raise ValueError("رمزگشایی رشته خالی مجاز نیست")
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("رمزگشایی ناموفق — token نامعتبر یا کلید اشتباه") from exc


def mask_secret(value: str, visible: int = 4) -> str:
    """نمایش ماسک‌شده secret در UI — هرگز کامل نمایش نده"""
    if len(value) <= visible:
        return "••••"
    return value[:visible] + "••••••••"
