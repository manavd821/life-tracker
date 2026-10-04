from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.behavior import BehaviorResponse


class UnaccountedPeriod(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_minutes: int


class TimelineResponse(BaseModel):
    date: str
    behaviors: list[BehaviorResponse] = Field(default_factory=list)
    unaccounted: list[UnaccountedPeriod] = Field(default_factory=list)
    total_tracked_minutes: int
    total_unaccounted_minutes: int
    total_behaviors: int