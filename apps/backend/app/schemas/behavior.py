from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    BehaviorSource,
    EmotionState,
    EnergyLevel,
    Environment,
    FocusState,
    Precision,
    PrimaryCategory,
)


class BehaviorBase(BaseModel):
    start_time: datetime
    end_time: datetime
    primary_category: PrimaryCategory
    activity_label_id: uuid.UUID | None = None
    energy_level: EnergyLevel | None = None
    emotion_state: EmotionState | None = None
    focus_state: FocusState | None = None
    environment: Environment | None = None
    notes: str | None = Field(default=None, max_length=2000)
    precision: Precision = Precision.HIGH

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class CreateBehavior(BehaviorBase):
    context_tag_ids: list[uuid.UUID] = Field(default_factory=list)


class UpdateBehavior(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    primary_category: PrimaryCategory | None = None
    activity_label_id: uuid.UUID | None = None
    energy_level: EnergyLevel | None = None
    emotion_state: EmotionState | None = None
    focus_state: FocusState | None = None
    environment: Environment | None = None
    notes: str | None = Field(default=None, max_length=2000)
    precision: Precision | None = None
    context_tag_ids: list[uuid.UUID] | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class ContextTagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    behavior_context_tag_id: uuid.UUID
    primary_category: PrimaryCategory
    context_tag: str


class ActivityLabelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_label_id: uuid.UUID
    primary_category: PrimaryCategory
    activity_label: str


class BehaviorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    behavior_id: uuid.UUID
    user_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    primary_category: PrimaryCategory
    activity_label: ActivityLabelSummary | None = None
    energy_level: EnergyLevel | None = None
    emotion_state: EmotionState | None = None
    focus_state: FocusState | None = None
    environment: Environment | None = None
    precision: Precision
    source: BehaviorSource
    notes: str | None = None
    context_tags: list[ContextTagSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime