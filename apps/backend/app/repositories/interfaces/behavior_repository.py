from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.behavior import Behavior

CONTEXT_DIMENSIONS = ("environment", "energy_level", "focus_state", "emotion_state")


@dataclass(frozen=True)
class ContextDurationRow:
    """One behavior context bucket, e.g. Study / CN / Library."""

    dimension: str
    category: str
    activity_label: str | None
    context: str
    session_count: int
    total_duration_minutes: int


class BehaviorRepositoryInterface(Protocol):
    async def add(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        primary_category: str,
        activity_label_id: uuid.UUID | None,
        energy_level: str | None,
        emotion_state: str | None,
        focus_state: str | None,
        environment: str | None,
        precision: str,
        notes: str | None,
        source: str,
    ) -> Behavior: ...

    async def get(
        self, session: AsyncSession, behavior_id: uuid.UUID
    ) -> Behavior | None: ...

    async def list_overlapping(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_behavior_id: uuid.UUID | None = None,
    ) -> list[Behavior]: ...

    async def list_for_day(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Behavior]: ...

    async def list_for_range(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> list[Behavior]: ...

    async def get_context_duration_totals(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> list[ContextDurationRow]: ...

    async def get_day_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start: datetime, day_end: datetime
    ) -> tuple[int, int]: ...

    async def get_category_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start: datetime, day_end: datetime
    ) -> list[tuple[str, int]]: ...

    async def get_activity_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start: datetime, day_end: datetime
    ) -> list[tuple[str, str | None, int]]: ...

    async def update(
        self, session: AsyncSession, behavior_id: uuid.UUID, **changes: object
    ) -> Behavior | None: ...

    async def soft_delete(
        self, session: AsyncSession, behavior_id: uuid.UUID, deleted_at: datetime
    ) -> None: ...