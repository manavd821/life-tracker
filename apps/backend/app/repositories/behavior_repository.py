from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.behavior import Behavior


class BehaviorRepository:
    _LOADED = (selectinload(Behavior.activity_label), selectinload(Behavior.context_tags))

    async def add(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        start_time,
        end_time,
        primary_category: str,
        activity_label_id: uuid.UUID | None,
        energy_level: str | None,
        emotion_state: str | None,
        focus_state: str | None,
        environment: str | None,
        precision: str,
        notes: str | None,
        source: str,
    ) -> Behavior:
        behavior = Behavior(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            primary_category=primary_category,
            activity_label_id=activity_label_id,
            energy_level=energy_level,
            emotion_state=emotion_state,
            focus_state=focus_state,
            environment=environment,
            precision=precision,
            notes=notes,
            source=source,
        )
        session.add(behavior)
        await session.flush()
        return behavior

    async def get(
        self, session: AsyncSession, behavior_id: uuid.UUID
    ) -> Behavior | None:
        return await session.scalar(
            select(Behavior)
            .options(*self._LOADED)
            .where(Behavior.behavior_id == behavior_id, Behavior.deleted_at.is_(None))
        )

    async def list_overlapping(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time,
        end_time,
        exclude_behavior_id: uuid.UUID | None = None,
    ) -> list[Behavior]:
        stmt = (
            select(Behavior)
            .options(*self._LOADED)
            .where(
                Behavior.user_id == user_id,
                Behavior.deleted_at.is_(None),
                Behavior.start_time < end_time,
                Behavior.end_time > start_time,
            )
            .order_by(Behavior.start_time)
        )
        if exclude_behavior_id is not None:
            stmt = stmt.where(Behavior.behavior_id != exclude_behavior_id)
        return list((await session.scalars(stmt)).all())

    async def list_for_day(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day_start,
        day_end,
    ) -> list[Behavior]:
        stmt = (
            select(Behavior)
            .options(*self._LOADED)
            .where(
                Behavior.user_id == user_id,
                Behavior.deleted_at.is_(None),
                Behavior.start_time >= day_start,
                Behavior.start_time < day_end,
            )
            .order_by(Behavior.start_time)
        )
        return list((await session.scalars(stmt)).all())

    async def update(
        self, session: AsyncSession, behavior_id: uuid.UUID, **changes: object
    ) -> Behavior | None:
        if not changes:
            return await self.get(session, behavior_id)
        await session.execute(
            update(Behavior)
            .where(Behavior.behavior_id == behavior_id, Behavior.deleted_at.is_(None))
            .values(**changes, updated_at=func.now())
        )
        await session.flush()
        return await self.get(session, behavior_id)

    async def soft_delete(
        self, session: AsyncSession, behavior_id: uuid.UUID, deleted_at
    ) -> None:
        await session.execute(
            update(Behavior)
            .where(Behavior.behavior_id == behavior_id, Behavior.deleted_at.is_(None))
            .values(deleted_at=deleted_at, updated_at=func.now())
        )