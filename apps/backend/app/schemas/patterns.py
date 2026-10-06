from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import PrimaryCategory


class PatternWindow(BaseModel):
    start_date: str
    end_date: str
    behavior_count: int


class CategoryTransition(BaseModel):
    type: Literal["category_transition"] = "category_transition"
    from_category: PrimaryCategory
    to_category: PrimaryCategory
    count: int
    probability: float
    transitions_from_source: int


class ActivityTransition(BaseModel):
    type: Literal["activity_transition"] = "activity_transition"
    from_category: PrimaryCategory
    from_activity: str
    to_category: PrimaryCategory
    to_activity: str
    count: int
    probability: float
    transitions_from_source: int


class TransitionPatterns(BaseModel):
    window: PatternWindow
    minimum_transition_count: int
    category_transitions: list[CategoryTransition] = Field(default_factory=list)
    activity_transitions: list[ActivityTransition] = Field(default_factory=list)


class ContextStat(BaseModel):
    type: Literal["context_stat"] = "context_stat"
    category: PrimaryCategory
    activity_label: str | None
    dimension: str
    context: str
    session_count: int
    total_duration_minutes: int
    average_duration_minutes: float


class ContextAssociation(BaseModel):
    type: Literal["context_association"] = "context_association"
    category: PrimaryCategory
    activity_label: str | None
    dimension: str
    context_a: str
    context_b: str
    average_duration_a: float
    average_duration_b: float
    sample_a: int
    sample_b: int
    difference_minutes: float
    ratio: float


class ContextPatterns(BaseModel):
    window: PatternWindow
    minimum_context_sessions: int
    context_stats: list[ContextStat] = Field(default_factory=list)
    associations: list[ContextAssociation] = Field(default_factory=list)
