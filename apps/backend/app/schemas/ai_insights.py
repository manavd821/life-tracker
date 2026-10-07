from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Period(BaseModel):
    start: str
    end: str


class CategoryTotal(BaseModel):
    category: str
    minutes: int


class BehaviorSummary(BaseModel):
    tracked_minutes: int
    unaccounted_minutes: int
    category_totals: list[CategoryTotal] = Field(default_factory=list)
    day_minutes: int | None = None
    behavior_count: int | None = None


class TaskSummary(BaseModel):
    planned_minutes: int | None = None
    effective_minutes: float | None = None
    completion_rate: float | None = None
    count: int | None = None


class CategoryTransitionFact(BaseModel):
    type: Literal["category_transition"] = "category_transition"
    from_category: str
    to_category: str
    count: int
    probability: float


class ActivityTransitionFact(BaseModel):
    type: Literal["activity_transition"] = "activity_transition"
    from_category: str
    from_activity: str
    to_category: str
    to_activity: str
    count: int
    probability: float


class ContextAssociationFact(BaseModel):
    type: Literal["context_association"] = "context_association"
    category: str
    activity_label: str | None
    dimension: str
    context_a: str
    context_b: str
    average_duration_a: float
    average_duration_b: float
    sample_a: int
    sample_b: int
    difference_minutes: float


class AIContext(BaseModel):
    period: Period
    behavior_summary: BehaviorSummary
    task_summary: TaskSummary | None = None
    patterns: list[
        CategoryTransitionFact | ActivityTransitionFact | ContextAssociationFact
    ] = Field(default_factory=list)


class Insight(BaseModel):
    title: str
    description: str
    supporting_facts: list[str] = Field(default_factory=list)


class CoachingSuggestion(BaseModel):
    title: str
    recommendation: str
    reasoning: str


class AIResponse(BaseModel):
    insights: list[Insight] = Field(default_factory=list)
    coaching: list[CoachingSuggestion] = Field(default_factory=list)
