from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_label import ActivityLabel


class ActivityLabelRepositoryInterface(Protocol):
    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[ActivityLabel]: ...

    async def get(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> ActivityLabel | None: ...

    async def get_many_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        activity_label_ids: list[uuid.UUID],
    ) -> list[ActivityLabel]: ...

    async def exists_in_category(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        activity_label: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool: ...

    async def add(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        activity_label: str,
    ) -> ActivityLabel: ...

    async def update(
        self,
        session: AsyncSession,
        activity_label_id: uuid.UUID,
        primary_category: str | None = None,
        activity_label: str | None = None,
    ) -> ActivityLabel: ...

    async def delete(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> None: ...

    async def count_behaviors_using(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> int: ...

    async def count_behaviors_outside_category(
        self,
        session: AsyncSession,
        activity_label_id: uuid.UUID,
        primary_category: str,
    ) -> int: ...