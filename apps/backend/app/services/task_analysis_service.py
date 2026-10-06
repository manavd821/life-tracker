from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ResourceNotFound
from app.models.behavior import Behavior
from app.models.task import Task
from app.repositories.interfaces.behavior_repository import BehaviorRepositoryInterface
from app.repositories.interfaces.task_repository import TaskRepositoryInterface
from app.schemas.task import (
    BehaviorContribution,
    TaskAnalysis,
    TaskAnalysisDetail,
    TaskAnalysisTotals,
)

EXACT_ACTIVITY_SCORE = 1.0
CATEGORY_ONLY_SCORE = 0.5
CONTEXT_BONUS = 0.25
MAX_SCORE = 1.0


class TaskAnalysisService:
    def __init__(
        self,
        tasks: TaskRepositoryInterface,
        behaviors: BehaviorRepositoryInterface,
    ) -> None:
        self._tasks = tasks
        self._behaviors = behaviors

    async def analyze(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> TaskAnalysisDetail:
        task = await self._owned_task(session, user_id, task_id)
        behaviors = await self._behaviors.list_overlapping(
            session, user_id, task.start_time, task.end_time
        )
        contributions = self._score(task, behaviors)
        planned = task.planned_minutes
        effective = round(sum(c.effective_minutes for c in contributions), 2)
        return TaskAnalysisDetail(
            task_id=task.task_id,
            planned_minutes=planned,
            effective_minutes=effective,
            completion_rate=self._rate(effective, planned),
            contributions=contributions,
        )

    async def analyze_many_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[TaskAnalysis]:
        tasks = await self._tasks.list_for_user(session, user_id)
        return await self._analyze(session, user_id, tasks)

    async def analyze_tasks_for_date(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> list[TaskAnalysis]:
        tasks = await self._tasks.get_tasks_for_date(
            session, user_id, day_start, day_end
        )
        return await self._analyze(session, user_id, tasks)

    async def _analyze(
        self, session: AsyncSession, user_id: uuid.UUID, tasks: list[Task]
    ) -> list[TaskAnalysis]:
        if not tasks:
            return []

        window_start = min(t.start_time for t in tasks)
        window_end = max(t.end_time for t in tasks)
        behaviors = await self._behaviors.list_overlapping(
            session, user_id, window_start, window_end
        )
        by_id = {b.behavior_id: b for b in behaviors}

        results = []
        for task in tasks:
            overlapping = [
                b
                for b in by_id.values()
                if b.start_time < task.end_time and b.end_time > task.start_time
            ]
            contributions = self._score(task, overlapping)
            planned = task.planned_minutes
            effective = round(sum(c.effective_minutes for c in contributions), 2)
            results.append(
                TaskAnalysis(
                    task_id=task.task_id,
                    planned_minutes=planned,
                    effective_minutes=effective,
                    completion_rate=self._rate(effective, planned),
                )
            )
        return results

    async def _owned_task(
        self, session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
    ) -> Task:
        task = await self._tasks.get(session, task_id)
        if task is None or task.user_id != user_id:
            raise ResourceNotFound("Task not found")
        return task

    def _score(
        self, task: Task, behaviors: list[Behavior]
    ) -> list[BehaviorContribution]:
        task_tag_ids = {t.behavior_context_tag_id for t in task.context_tags}
        contributions: list[BehaviorContribution] = []

        for behavior in sorted(behaviors, key=lambda b: b.start_time):
            score, matched_tags = self._match_score(task, behavior, task_tag_ids)
            if score <= 0:
                continue

            overlap_start = max(task.start_time, behavior.start_time)
            overlap_end = min(task.end_time, behavior.end_time)
            overlap_minutes = int(
                (overlap_end - overlap_start).total_seconds() // 60
            )
            if overlap_minutes <= 0:
                continue

            contributions.append(
                BehaviorContribution(
                    behavior_id=behavior.behavior_id,
                    start_time=behavior.start_time,
                    end_time=behavior.end_time,
                    primary_category=_value(behavior.primary_category),
                    activity_label=(
                        behavior.activity_label.activity_label
                        if behavior.activity_label
                        else None
                    ),
                    overlap_minutes=overlap_minutes,
                    match_score=score,
                    effective_minutes=round(overlap_minutes * score, 2),
                    matched_context_tags=matched_tags,
                )
            )
        return contributions

    @staticmethod
    def _match_score(
        task: Task, behavior: Behavior, task_tag_ids: set[uuid.UUID]
    ) -> tuple[float, list[str]]:
        if behavior.primary_category != task.primary_category:
            return 0.0, []

        if task.activity_label_id and behavior.activity_label_id == task.activity_label_id:
            score = EXACT_ACTIVITY_SCORE
        else:
            score = CATEGORY_ONLY_SCORE

        matched = [
            tag.context_tag
            for tag in behavior.context_tags
            if tag.behavior_context_tag_id in task_tag_ids
        ]
        if matched:
            score = min(MAX_SCORE, score + CONTEXT_BONUS)

        return round(score, 2), matched

    @staticmethod
    def _rate(effective_minutes: float, planned_minutes: int) -> float:
        if planned_minutes <= 0:
            return 0.0
        return round(effective_minutes / planned_minutes * 100, 2)

    @classmethod
    def summarize(cls, analyses: list[TaskAnalysis]) -> TaskAnalysisTotals:
        planned = sum(a.planned_minutes for a in analyses)
        effective = round(sum(a.effective_minutes for a in analyses), 2)
        return TaskAnalysisTotals(
            count=len(analyses),
            planned_minutes=planned,
            effective_minutes=effective,
            completion_rate=cls._rate(effective, planned),
        )


def _value(enum_member) -> str | None:
    if enum_member is None:
        return None
    return getattr(enum_member, "value", enum_member)