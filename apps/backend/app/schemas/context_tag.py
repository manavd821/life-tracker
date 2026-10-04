from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrimaryCategory


class ContextTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    behavior_context_tag_id: uuid.UUID
    primary_category: PrimaryCategory
    context_tag: str
    created_at: datetime


class CreateContextTag(BaseModel):
    primary_category: PrimaryCategory
    context_tag: str = Field(min_length=1, max_length=120)


class UpdateContextTag(BaseModel):
    primary_category: PrimaryCategory | None = None
    context_tag: str | None = Field(default=None, min_length=1, max_length=120)