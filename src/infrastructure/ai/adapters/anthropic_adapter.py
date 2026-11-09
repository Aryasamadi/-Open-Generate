"""Anthropic (Claude) Adapter"""
from __future__ import annotations

import anthropic

from src.infrastructure.ai.adapters.base import AIProviderAdapter, AIResponse, ModelInfo
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_INJECT_FENCE_START = "\n\n<article_content>\n"
_INJECT_FENCE_END = "\n</article_content>\n"


class AnthropicAdapter(AIProviderAdapter):

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
        client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url or None)

        safe_content = f"{_INJECT_FENCE_START}{user_content}{_INJECT_FENCE_END}"

        try:
            msg = await client.messages.create(
                model=model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": safe_content}],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            text = "".join(
                block.text for block in msg.content if hasattr(block, "text")
            )

            return AIResponse(
                text=text,
                model_id=model_id,
                tokens_in=msg.usage.input_tokens,
                tokens_out=msg.usage.output_tokens,
                finish_reason=msg.stop_reason or "stop",
            )

        except anthropic.RateLimitError as exc:
            raise RuntimeError("rate limit Anthropic") from exc
        except anthropic.APIStatusError as exc:
            raise RuntimeError(f"Anthropic API error {exc.status_code}") from exc

    async def list_models(self, api_key: str, base_url: str) -> list[ModelInfo]:
        # Anthropic مدل‌ها را از API expose نمی‌کند؛ لیست ثابت
        return [
            ModelInfo(id="claude-opus-4-5", display_name="Claude Opus 4.5"),
            ModelInfo(id="claude-sonnet-4-5", display_name="Claude Sonnet 4.5"),
            ModelInfo(id="claude-haiku-3-5", display_name="Claude Haiku 3.5"),
        ]

    async def test_connection(self, api_key: str, base_url: str, model_id: str) -> bool:
        client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url or None)
        try:
            await client.messages.create(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception as exc:
            logger.warning("anthropic_test_failed", error=str(exc)[:100])
            return False
