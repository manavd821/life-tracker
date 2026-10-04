from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrimaryCategory


class ActivityLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    activity_label_id: uuid.UUID
    primary_category: PrimaryCategory
    activity_label: str
    created_at: datetime


class CreateActivityLabel(BaseModel):
    primary_category: PrimaryCategory
    activity_label: str = Field(min_length=1, max_length=120)


class UpdateActivityLabel(BaseModel):
    primary_category: PrimaryCategory | None = None
    activity_label: str | None = Field(default=None, min_length=1, max_length=120)