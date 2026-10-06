from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import day_window
from app.core.errors import InvalidTimeRange, ResourceNotFound
from app.models.enums import PrimaryCategory
from app.models.task import Task
from app.repositories.interfaces.activity_label_repository import (
    ActivityLabelRepositoryInterface,
)
from app.repositories.interfaces.context_tag_repository import (
    ContextTagRepositoryInterface,
)
from app.repositories.interfaces.task_repository import TaskRepositoryInterface
from app.schemas.task import CreateTask, TaskResponse, UpdateTask


class TaskService:
    def __init__(
        self,
        tasks: TaskRepositoryInterface,
        activity_labels: ActivityLabelRepositoryInterface,
        context_tags: ContextTagRepositoryInterface,
    ) -> None:
        self._tasks = tasks
        self._activity_labels = activity_labels
        self._context_tags = context_tags

    async def list_for_day(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day: date | None,
        tz_offset_minutes: int = 0,
    ) -> list[TaskResponse]:
        if day is None:
            tasks = await self._tasks.list_for_user(session, user_id)
        else:
            day_start, day_end = day_window(day, tz_offset_minutes)
            tasks = await self._tasks.get_tasks_for_date(
                session, user_id, day_start, day_end
            )
        return [TaskResponse.model_validate(task) for task in tasks]

    async def create(
        self, session: AsyncSession, user_id: uuid.UUID, payload: CreateTask
    ) -> TaskResponse:
        self._validate_range(payload.start_time, payload.end_time)
        activity_label_id = await self._validate_activity_label(
            session, user_id, payload.primary_category, payload.activity_label_id
        )
        tags = await self._validate_context_tags(
            session, user_id, payload.primary_category, payload.context_tag_ids
        )

        task = await self._tasks.add(
            session,
            user_id=user_id,
            title=payload.title.strip(),
            primary_category=payload.primary_category.value,
            activity_label_id=activity_label_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            description=payload.description,
        )
        await _set_tags(session, task, tags)
        await session.commit()
        return TaskResponse.model_validate(
            await self._tasks.get(session, task.task_id)
        )

    async def get(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> TaskResponse:
        return TaskResponse.model_validate(
            await self._owned(session, user_id, task_id)
        )

    async def update(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: UpdateTask,
    ) -> TaskResponse:
        existing = await self._owned(session, user_id, task_id)

        start_time = payload.start_time or existing.start_time
        end_time = payload.end_time or existing.end_time
        self._validate_range(start_time, end_time)

        category = payload.primary_category or existing.primary_category
        activity_label_id = (
            payload.activity_label_id
            if payload.activity_label_id is not None
            else existing.activity_label_id
        )
        validated_label = await self._validate_activity_label(
            session, user_id, category, activity_label_id
        )

        tags = (
            await self._validate_context_tags(
                session, user_id, category, payload.context_tag_ids
            )
            if payload.context_tag_ids is not None
            else list(existing.context_tags)
        )

        changes: dict[str, object] = {
            "title": payload.title.strip() if payload.title else existing.title,
            "start_time": start_time,
            "end_time": end_time,
            "primary_category": category.value,
            "activity_label_id": validated_label,
        }
        if "description" in payload.model_fields_set:
            changes["description"] = payload.description

        await self._tasks.update(session, task_id, **changes)
        task = await self._owned(session, user_id, task_id)
        await _set_tags(session, task, tags)
        await session.commit()
        return TaskResponse.model_validate(
            await self._tasks.get(session, task_id)
        )

    async def delete(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> None:
        await self._owned(session, user_id, task_id)
        await self._tasks.delete(session, task_id)
        await session.commit()

    async def _owned(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> Task:
        task = await self._tasks.get(session, task_id)
        if task is None or task.user_id != user_id:
            raise ResourceNotFound("Task not found")
        return task

    @staticmethod
    def _validate_range(start_time: datetime, end_time: datetime) -> None:
        if start_time >= end_time:
            raise InvalidTimeRange("start_time must be before end_time")

    async def _validate_activity_label(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        category: PrimaryCategory,
        activity_label_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if activity_label_id is None:
            return None
        label = await self._activity_labels.get(session, activity_label_id)
        if label is None or label.user_id != user_id:
            raise ResourceNotFound("Activity label not found")
        if label.primary_category != category:
            raise InvalidTimeRange(
                f"Activity label '{label.activity_label}' belongs to "
                f"{getattr(label.primary_category, 'value', label.primary_category)}, "
                f"not {category.value}",
                code="activity_label_category_mismatch",
            )
        return activity_label_id

    async def _validate_context_tags(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        category: PrimaryCategory,
        tag_ids: list[uuid.UUID],
    ) -> list:
        if not tag_ids:
            return []
        unique_ids = list(dict.fromkeys(tag_ids))
        tags = await self._context_tags.get_many_for_user(session, user_id, unique_ids)
        if len({t.behavior_context_tag_id for t in tags}) != len(unique_ids):
            raise ResourceNotFound("One or more context tags not found")
        for tag in tags:
            if tag.primary_category != category:
                raise InvalidTimeRange(
                    f"Context tag '{tag.context_tag}' belongs to "
                    f"{getattr(tag.primary_category, 'value', tag.primary_category)}, "
                    f"not {category.value}",
                    code="context_tag_category_mismatch",
                )
        return tags


async def _set_tags(session: AsyncSession, task: Task, tags: list) -> None:
    await session.run_sync(lambda _: setattr(task, "context_tags", tags))