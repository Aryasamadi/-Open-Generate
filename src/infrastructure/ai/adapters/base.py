"""
AI Provider Adapter — interface مشترک برای همه providerها.
هر provider adapter مستقل دارد.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AIResponse:
    text: str
    model_id: str
    tokens_in: int
    tokens_out: int
    finish_reason: str  # "stop" | "length" | "error"


@dataclass
class ModelInfo:
    id: str
    display_name: str


class AIProviderAdapter(ABC):
    """
    Interface مشترک — هر provider باید این را پیاده کند.
    prompt injection: محتوای وب داده غیرقابل اعتماد است، نه دستور سیستمی.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_content: str,  # محتوای وب — داده، نه دستور
        model_id: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """تولید متن — secret هرگز در log نمی‌آید"""
        ...

    @abstractmethod
    async def list_models(
        self,
        api_key: str,
        base_url: str,
    ) -> list[ModelInfo]:
        """کشف مدل‌ها — اگر provider پشتیبانی نکند NotImplementedError"""
        ...

    @abstractmethod
    async def test_connection(
        self,
        api_key: str,
        base_url: str,
        model_id: str,
    ) -> bool:
        """تست اتصال و اعتبار API key"""
        ...
