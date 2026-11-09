"""Repository مدل‌های AI"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.ai_model import AIModel, AIProvider
from src.infrastructure.db.models import AIModelModel


def _to_entity(m: AIModelModel) -> AIModel:
    return AIModel(
        id=m.id,
        provider=AIProvider(m.provider),
        display_name=m.display_name,
        base_url=m.base_url,
        model_id=m.model_id,
        api_key_encrypted=m.api_key_encrypted,
        is_global=m.is_global,
        owner_id=m.owner_id,
        temperature=float(m.temperature),
        max_tokens=m.max_tokens,
        priority=m.priority,
        is_active=m.is_active,
        fail_count=m.fail_count,
        last_error=m.last_error,
        last_ok=m.last_ok,
        last_fail=m.last_fail,
        next_try_after=m.next_try_after,
        circuit_open=m.circuit_open,
        created_at=m.created_at,
    )


class AIModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_available_for_channel(self, channel_owner_id: int) -> list[AIModel]:
        """مدل‌های عمومی + شخصی مدیر کانال، مرتب بر اساس priority"""
        result = await self._s.execute(
            select(AIModelModel)
            .where(
                AIModelModel.is_active == True,
                AIModelModel.circuit_open == False,
                or_(
                    AIModelModel.is_global == True,
                    AIModelModel.owner_id == channel_owner_id,
                ),
            )
            .order_by(AIModelModel.priority.desc())
        )
        return [_to_entity(r) for r in result.scalars().all()]

    async def create(self, model: AIModel) -> AIModel:
        m = AIModelModel(
            provider=model.provider.value,
            display_name=model.display_name,
            base_url=model.base_url,
            model_id=model.model_id,
            api_key_encrypted=model.api_key_encrypted,
            is_global=model.is_global,
            owner_id=model.owner_id,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
            priority=model.priority,
            is_active=model.is_active,
        )
        self._s.add(m)
        await self._s.flush()
        model.id = m.id
        return model

    async def update_circuit(
        self,
        model_id: int,
        fail_count: int,
        circuit_open: bool,
        last_error: Optional[str],
        next_try_after: Optional[object],
    ) -> None:
        from sqlalchemy import update as sql_update
        await self._s.execute(
            sql_update(AIModelModel)
            .where(AIModelModel.id == model_id)
            .values(
                fail_count=fail_count,
                circuit_open=circuit_open,
                last_error=last_error,
                next_try_after=next_try_after,
            )
        )
