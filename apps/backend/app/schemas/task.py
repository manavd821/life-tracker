from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import PrimaryCategory


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start_time: datetime
    end_time: datetime
    primary_category: PrimaryCategory
    activity_label_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    context_tag_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class CreateTask(TaskBase):
    pass


class UpdateTask(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    start_time: datetime | None = None
    end_time: datetime | None = None
    primary_category: PrimaryCategory | None = None
    activity_label_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    context_tag_ids: list[uuid.UUID] | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class TaskContextTagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    behavior_context_tag_id: uuid.UUID
    primary_category: PrimaryCategory
    context_tag: str


class TaskActivityLabelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_label_id: uuid.UUID
    primary_category: PrimaryCategory
    activity_label: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    primary_category: PrimaryCategory
    activity_label: TaskActivityLabelSummary | None = None
    context_tags: list[TaskContextTagSummary] = Field(default_factory=list)
    start_time: datetime
    end_time: datetime
    planned_minutes: int
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class BehaviorContribution(BaseModel):
    behavior_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    primary_category: str
    activity_label: str | None = None
    overlap_minutes: int
    match_score: float
    effective_minutes: float
    matched_context_tags: list[str] = Field(default_factory=list)


class TaskAnalysis(BaseModel):
    task_id: uuid.UUID
    planned_minutes: int
    effective_minutes: float
    completion_rate: float


class TaskAnalysisDetail(TaskAnalysis):
    contributions: list[BehaviorContribution] = Field(default_factory=list)


class TaskAnalysisTotals(BaseModel):
    count: int
    planned_minutes: int
    effective_minutes: float
    completion_rate: float