from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Task


class TaskRepository:
    _LOADED = (selectinload(Task.activity_label), selectinload(Task.context_tags))

    async def add(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        title: str,
        primary_category: str,
        activity_label_id: uuid.UUID | None,
        start_time,
        end_time,
        description: str | None,
    ) -> Task:
        task = Task(
            user_id=user_id,
            title=title,
            primary_category=primary_category,
            activity_label_id=activity_label_id,
            start_time=start_time,
            end_time=end_time,
            description=description,
        )
        session.add(task)
        await session.flush()
        return task

    async def get(self, session: AsyncSession, task_id: uuid.UUID) -> Task | None:
        return await session.scalar(
            select(Task)
            .options(*self._LOADED)
            .where(Task.task_id == task_id)
        )

    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(*self._LOADED)
            .where(Task.user_id == user_id)
            .order_by(Task.start_time)
        )
        return list((await session.scalars(stmt)).all())

    async def get_tasks_for_date(
        self, session: AsyncSession, user_id: uuid.UUID, day_start, day_end
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(*self._LOADED)
            .where(
                Task.user_id == user_id,
                Task.start_time >= day_start,
                Task.start_time < day_end,
            )
            .order_by(Task.start_time)
        )
        return list((await session.scalars(stmt)).all())

    async def list_overlapping_window(
        self, session: AsyncSession, user_id: uuid.UUID, start, end
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(*self._LOADED)
            .where(
                Task.user_id == user_id,
                Task.start_time < end,
                Task.end_time > start,
            )
            .order_by(Task.start_time)
        )
        return list((await session.scalars(stmt)).all())

    async def update(
        self, session: AsyncSession, task_id: uuid.UUID, **changes: object
    ) -> Task | None:
        if changes:
            await session.execute(
                update(Task)
                .where(Task.task_id == task_id)
                .values(**changes, updated_at=func.now())
            )
            await session.flush()
        return await self.get(session, task_id)

    async def delete(self, session: AsyncSession, task_id: uuid.UUID) -> None:
        await session.delete(await session.get(Task, task_id))