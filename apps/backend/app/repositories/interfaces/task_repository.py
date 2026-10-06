from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


class TaskRepositoryInterface(Protocol):
    async def add(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        title: str,
        primary_category: str,
        activity_label_id: uuid.UUID | None,
        start_time: datetime,
        end_time: datetime,
        description: str | None,
    ) -> Task: ...

    async def get(
        self, session: AsyncSession, task_id: uuid.UUID
    ) -> Task | None: ...

    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[Task]: ...

    async def get_tasks_for_date(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Task]: ...

    async def list_overlapping_window(
        self, session: AsyncSession, user_id: uuid.UUID, start: datetime, end: datetime
    ) -> list[Task]: ...

    async def update(
        self, session: AsyncSession, task_id: uuid.UUID, **changes: object
    ) -> Task | None: ...

    async def delete(self, session: AsyncSession, task_id: uuid.UUID) -> None: ...