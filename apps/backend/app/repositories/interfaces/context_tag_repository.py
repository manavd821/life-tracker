from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.context_tag import BehaviorContextTag


class ContextTagRepositoryInterface(Protocol):
    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[BehaviorContextTag]: ...

    async def get(
        self, session: AsyncSession, behavior_context_tag_id: uuid.UUID
    ) -> BehaviorContextTag | None: ...

    async def get_many_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
    ) -> list[BehaviorContextTag]: ...

    async def exists_in_category(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        context_tag: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def add(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        context_tag: str,
    ) -> BehaviorContextTag: ...

    async def update(
        self,
        session: AsyncSession,
        behavior_context_tag_id: uuid.UUID,
        primary_category: str | None = None,
        context_tag: str | None = None,
    ) -> BehaviorContextTag: ...

    async def delete(
        self, session: AsyncSession, behavior_context_tag_id: uuid.UUID
    ) -> None: ...