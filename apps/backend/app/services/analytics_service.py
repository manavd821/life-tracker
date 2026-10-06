from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import day_window, window_minutes
from app.repositories.interfaces.behavior_repository import BehaviorRepositoryInterface
from app.schemas.analytics import (
    ActivityTotal,
    CategoryTotal,
    DailyAnalytics,
    DaySummary,
)
from app.services.task_analysis_service import TaskAnalysisService


class AnalyticsService:
    def __init__(
        self,
        behaviors: BehaviorRepositoryInterface,
        task_analysis: TaskAnalysisService,
    ) -> None:
        self._behaviors = behaviors
        self._task_analysis = task_analysis

    async def daily(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day: date,
        tz_offset_minutes: int = 0,
    ) -> DailyAnalytics:
        day_start, day_end = day_window(day, tz_offset_minutes)
        day_total = window_minutes(day_start, day_end)

        behavior_count, tracked = await self._behaviors.get_day_totals(
            session, user_id, day_start, day_end
        )
        categories = await self._behaviors.get_category_totals(
            session, user_id, day_start, day_end
        )
        activities = await self._behaviors.get_activity_totals(
            session, user_id, day_start, day_end
        )
        analyses = await self._task_analysis.analyze_tasks_for_date(
            session, user_id, day_start, day_end
        )

        return DailyAnalytics(
            date=day.isoformat(),
            summary=DaySummary(
                day_minutes=day_total,
                tracked_minutes=tracked,
                unaccounted_minutes=day_total - tracked,
                behavior_count=behavior_count,
            ),
            categories=[
                CategoryTotal(category=category, duration_minutes=minutes)
                for category, minutes in categories
            ],
            activities=[
                ActivityTotal(
                    category=category,
                    activity_label=label,
                    duration_minutes=minutes,
                )
                for category, label, minutes in activities
            ],
            tasks=TaskAnalysisService.summarize(analyses),
        )