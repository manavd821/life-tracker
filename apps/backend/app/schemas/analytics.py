from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import PrimaryCategory
from app.schemas.task import TaskAnalysisTotals


class DaySummary(BaseModel):
    day_minutes: int
    tracked_minutes: int
    unaccounted_minutes: int
    behavior_count: int


class CategoryTotal(BaseModel):
    category: PrimaryCategory
    duration_minutes: int


class ActivityTotal(BaseModel):
    category: PrimaryCategory
    activity_label: str | None
    duration_minutes: int


class DailyAnalytics(BaseModel):
    date: str
    summary: DaySummary
    categories: list[CategoryTotal] = Field(default_factory=list)
    activities: list[ActivityTotal] = Field(default_factory=list)
    tasks: TaskAnalysisTotals