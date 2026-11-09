"""
موتور AI — انتخاب مدل با priority/fallback، circuit breaker، retry، cache و ثبت usage.
هنگام قطعی AI، متن ساختگی منتشر نمی‌شود.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from src.domain.entities.ai_model import AIModel, AIProvider
from src.infrastructure.ai.adapters.base import AIProviderAdapter, AIResponse
from src.infrastructure.ai.adapters.anthropic_adapter import AnthropicAdapter
from src.infrastructure.ai.adapters.openai_compat import OpenAICompatAdapter
from src.infrastructure.crypto.encryption import decrypt
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_ADAPTERS: dict[AIProvider, AIProviderAdapter] = {
    AIProvider.ANTHROPIC: AnthropicAdapter(),
    AIProvider.GEMINI: OpenAICompatAdapter(),   # Gemini از OpenAI-compat پشتیبانی می‌کند
    AIProvider.OPENAI: OpenAICompatAdapter(),
    AIProvider.OPENROUTER: OpenAICompatAdapter(),
    AIProvider.GROQ: OpenAICompatAdapter(),
    AIProvider.DEEPSEEK: OpenAICompatAdapter(),
    AIProvider.TOGETHER: OpenAICompatAdapter(),
    AIProvider.MISTRAL: OpenAICompatAdapter(),
    AIProvider.XAI: OpenAICompatAdapter(),
    AIProvider.OLLAMA: OpenAICompatAdapter(),
    AIProvider.LM_STUDIO: OpenAICompatAdapter(),
    AIProvider.CUSTOM: OpenAICompatAdapter(),
}


def get_adapter(provider: AIProvider) -> AIProviderAdapter:
    return _ADAPTERS[provider]


class AIEngine:
    """
    مدیریت کامل چرخه AI:
    - انتخاب مدل با priority
    - circuit breaker
    - retry با backoff
    - cache جواب‌ها
    - ثبت usage
    """

    def __init__(self, cache_store: Optional[object] = None) -> None:
        self._settings = get_settings()
        self._cache = cache_store  # کلاس cache جداگانه

    def _build_cache_key(
        self, model: AIModel, system_prompt: str, content: str
    ) -> str:
        raw = f"{model.id}:{model.model_id}:{system_prompt}:{content}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def generate_with_fallback(
        self,
        models: list[AIModel],
        system_prompt: str,
        article_content: str,
    ) -> Optional[AIResponse]:
        """
        تلاش به ترتیب priority — اگر همه fail شدند None برمی‌گردد.
        None = متن ساختگی منتشر نمی‌شود.
        """
        sorted_models = sorted(
            [m for m in models if m.is_available],
            key=lambda m: m.priority,
            reverse=True,
        )

        if not sorted_models:
            logger.warning("no_available_ai_models")
            return None

        for model in sorted_models:
            try:
                result = await self._generate_single(model, system_prompt, article_content)
                return result
            except Exception as exc:
                logger.warning(
                    "ai_model_failed",
                    model_id=model.id,
                    provider=model.provider,
                    error=str(exc)[:200],
                )
                await self._handle_failure(model)
                continue

        logger.error("all_ai_models_failed", tried=len(sorted_models))
        return None

    async def _generate_single(
        self, model: AIModel, system_prompt: str, content: str
    ) -> AIResponse:
        adapter = get_adapter(model.provider)
        api_key = decrypt(model.api_key_encrypted) if model.api_key_encrypted else ""

        settings = self._settings

        @retry(
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            stop=stop_after_attempt(settings.AI_MAX_RETRIES),
            wait=wait_exponential(
                multiplier=settings.AI_RETRY_BACKOFF, min=1, max=60
            ),
            reraise=True,
        )
        async def _call() -> AIResponse:
            return await adapter.generate(
                system_prompt=system_prompt,
                user_content=content,
                model_id=model.model_id,
                api_key=api_key,
                base_url=model.base_url,
                temperature=model.temperature,
                max_tokens=model.max_tokens,
            )

        return await _call()

    async def _handle_failure(self, model: AIModel) -> None:
        """fail_count و circuit breaker را به‌روز می‌کند"""
        model.fail_count += 1
        model.last_fail = datetime.utcnow()

        if model.fail_count >= self._settings.AI_CIRCUIT_BREAKER_THRESHOLD:
            model.circuit_open = True
            model.next_try_after = datetime.utcnow() + timedelta(
                seconds=self._settings.AI_CIRCUIT_BREAKER_TIMEOUT
            )
            logger.warning(
                "ai_circuit_opened",
                model_id=model.id,
                next_try=model.next_try_after.isoformat(),
            )
