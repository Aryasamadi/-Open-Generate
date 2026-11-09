"""موجودیت مدل هوش مصنوعی"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional


class AIProvider(str, Enum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENAI = "openai"              # و سازگارها
    OPENROUTER = "openrouter"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    TOGETHER = "together"
    MISTRAL = "mistral"
    XAI = "xai"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    CUSTOM = "custom"              # endpoint سفارشی


class AIModel:
    """
    مدل AI — عمومی (Super Admin) یا شخصی (مدیر کانال).
    API key رمزنگاری‌شده ذخیره می‌شود؛ هرگز در log یا UI کامل نمایش داده نمی‌شود.
    """

    def __init__(
        self,
        provider: AIProvider,
        display_name: str,
        base_url: str,
        model_id: str,
        api_key_encrypted: Optional[str] = None,
        is_global: bool = False,
        owner_id: Optional[int] = None,  # None = global
        temperature: float = 0.7,
        max_tokens: int = 1024,
        priority: int = 0,
        is_active: bool = True,
        # --- وضعیت ---
        fail_count: int = 0,
        last_error: Optional[str] = None,
        last_ok: Optional[datetime] = None,
        last_fail: Optional[datetime] = None,
        next_try_after: Optional[datetime] = None,
        circuit_open: bool = False,
        # --- متا ---
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        if is_global and owner_id is not None:
            raise ValueError("مدل global نمی‌تواند owner داشته باشد")
        if not is_global and owner_id is None:
            raise ValueError("مدل شخصی باید owner داشته باشد")

        self.id = id
        self.provider = provider
        self.display_name = display_name
        self.base_url = base_url
        self.model_id = model_id
        self.api_key_encrypted = api_key_encrypted
        self.is_global = is_global
        self.owner_id = owner_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.priority = priority
        self.is_active = is_active
        self.fail_count = fail_count
        self.last_error = last_error
        self.last_ok = last_ok
        self.last_fail = last_fail
        self.next_try_after = next_try_after
        self.circuit_open = circuit_open
        self.created_at = created_at or datetime.utcnow()

    @property
    def is_available(self) -> bool:
        if not self.is_active or self.circuit_open:
            return False
        if self.next_try_after and datetime.utcnow() < self.next_try_after:
            return False
        return True

    def masked_api_key(self) -> str:
        """نمایش ماسک‌شده API key"""
        if not self.api_key_encrypted:
            return "—"
        return "••••••••"

    def __repr__(self) -> str:
        return (
            f"AIModel(id={self.id}, provider={self.provider}, "
            f"name={self.display_name!r}, global={self.is_global})"
        )
