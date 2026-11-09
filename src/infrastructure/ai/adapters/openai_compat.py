"""
OpenAI-compatible Adapter.
پوشش: OpenAI، OpenRouter، Groq، DeepSeek، Together، Mistral، xAI، Ollama، LM Studio و هر endpoint هم‌قرارداد.
"""
from __future__ import annotations

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, RateLimitError
from openai.types.chat import ChatCompletion

from src.infrastructure.ai.adapters.base import AIProviderAdapter, AIResponse, ModelInfo
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class OpenAICompatAdapter(AIProviderAdapter):
    """
    تمام endpointهای OpenAI-compatible را پوشش می‌دهد.
    API key هرگز در log ثبت نمی‌شود.
    """

    _INJECT_FENCE = (
        "\n\n---CONTENT-START---\n",
        "\n---CONTENT-END---\n",
    )

    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        model_id: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """
        محتوای وب در fence جداگانه قرار می‌گیرد تا prompt injection ممکن نباشد.
        """
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # محتوای وب را با fence جدا می‌کنیم
        safe_content = (
            f"{self._INJECT_FENCE[0]}{user_content}{self._INJECT_FENCE[1]}"
        )

        try:
            response: ChatCompletion = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": safe_content},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            choice = response.choices[0]
            text = choice.message.content or ""
            usage = response.usage

            return AIResponse(
                text=text,
                model_id=model_id,
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
                finish_reason=choice.finish_reason or "stop",
            )

        except RateLimitError as exc:
            raise RuntimeError(f"rate limit provider: {exc.status_code}") from exc
        except APIStatusError as exc:
            raise RuntimeError(
                f"API error {exc.status_code}: {exc.message[:200]}"
            ) from exc
        except APIConnectionError as exc:
            raise ConnectionError(f"اتصال به AI ناموفق") from exc

    async def list_models(self, api_key: str, base_url: str) -> list[ModelInfo]:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            models = await client.models.list()
            return [
                ModelInfo(id=m.id, display_name=m.id)
                for m in models.data
            ]
        except Exception as exc:
            raise NotImplementedError(
                f"این provider کشف مدل را پشتیبانی نمی‌کند: {exc}"
            ) from exc

    async def test_connection(
        self, api_key: str, base_url: str, model_id: str
    ) -> bool:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception as exc:
            logger.warning("ai_test_failed", model=model_id, error=str(exc)[:100])
            return False
