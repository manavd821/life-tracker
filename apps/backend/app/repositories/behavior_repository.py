from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity_label import ActivityLabel
from app.models.behavior import Behavior
from app.repositories.interfaces.behavior_repository import (
    CONTEXT_DIMENSIONS,
    ContextDurationRow,
)


def in_window_minutes(start, end):
    clipped = func.least(Behavior.end_time, end) - func.greatest(Behavior.start_time, start)
    return func.floor(func.extract("epoch", clipped) / 60)


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

    def _in_window(self, user_id: uuid.UUID, day_start, day_end):
        return (
            Behavior.user_id == user_id,
            Behavior.deleted_at.is_(None),
            Behavior.start_time < day_end,
            Behavior.end_time > day_start,
        )

    async def list_for_range(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        window_start,
        window_end,
    ) -> list[Behavior]:
        stmt = (
            select(Behavior)
            .options(selectinload(Behavior.activity_label))
            .where(*self._in_window(user_id, window_start, window_end))
            .order_by(Behavior.start_time, Behavior.behavior_id)
        )
        return list((await session.scalars(stmt)).all())

    async def get_context_duration_totals(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        window_start,
        window_end,
    ) -> list[ContextDurationRow]:
        minutes = in_window_minutes(window_start, window_end)
        where = (*self._in_window(user_id, window_start, window_end),)
        rows: list[ContextDurationRow] = []

        for dimension in CONTEXT_DIMENSIONS:
            column = getattr(Behavior, dimension)
            result = await session.execute(
                select(
                    Behavior.primary_category,
                    ActivityLabel.activity_label,
                    column,
                    func.count(Behavior.behavior_id),
                    func.coalesce(func.sum(minutes), 0),
                )
                .select_from(Behavior)
                .outerjoin(
                    ActivityLabel,
                    Behavior.activity_label_id == ActivityLabel.activity_label_id,
                )
                .where(*where, column.is_not(None))
                .group_by(Behavior.primary_category, ActivityLabel.activity_label, column)
            )
            for category, label, context, count, total in result:
                rows.append(
                    ContextDurationRow(
                        dimension=dimension,
                        category=category,
                        activity_label=label,
                        context=context,
                        session_count=int(count),
                        total_duration_minutes=int(total),
                    )
                )
        return rows

    async def get_day_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start, day_end
    ) -> tuple[int, int]:
        minutes = in_window_minutes(day_start, day_end)
        row = (
            await session.execute(
                select(
                    func.count(Behavior.behavior_id),
                    func.coalesce(func.sum(minutes), 0),
                ).where(*self._in_window(user_id, day_start, day_end))
            )
        ).one()
        return int(row[0]), int(row[1])

    async def get_category_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start, day_end
    ) -> list[tuple[str, int]]:
        minutes = in_window_minutes(day_start, day_end)
        rows = await session.execute(
            select(Behavior.primary_category, func.sum(minutes))
            .where(*self._in_window(user_id, day_start, day_end))
            .group_by(Behavior.primary_category)
            .order_by(func.sum(minutes).desc())
        )
        return [(row[0], int(row[1])) for row in rows]

    async def get_activity_totals(
        self, session: AsyncSession, user_id: uuid.UUID, day_start, day_end
    ) -> list[tuple[str, str | None, int]]:
        minutes = in_window_minutes(day_start, day_end)
        rows = await session.execute(
            select(
                Behavior.primary_category,
                ActivityLabel.activity_label,
                func.sum(minutes),
            )
            .select_from(Behavior)
            .outerjoin(
                ActivityLabel,
                Behavior.activity_label_id == ActivityLabel.activity_label_id,
            )
            .where(*self._in_window(user_id, day_start, day_end))
            .group_by(Behavior.primary_category, ActivityLabel.activity_label)
            .order_by(Behavior.primary_category, func.sum(minutes).desc())
        )
        return [(row[0], row[1], int(row[2])) for row in rows]