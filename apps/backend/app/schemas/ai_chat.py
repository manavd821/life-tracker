from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai_insights import (
    ActivityTransitionFact,
    CategoryTransitionFact,
    ContextAssociationFact,
    Period,
)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 20

ChatRole = Literal["user", "assistant"]

PatternFact = CategoryTransitionFact | ActivityTransitionFact | ContextAssociationFact


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    date: datetime.date | None = None
    tz_offset_minutes: int = Field(default=0, ge=-840, le=840)
    history: list[ChatMessage] = Field(
        default_factory=list, max_length=MAX_HISTORY_MESSAGES
    )


class ChatResponse(BaseModel):
    reply: str
    date: str


class ChatCategoryTotal(BaseModel):
    category: str
    minutes: int


class ChatActivityTotal(BaseModel):
    category: str
    activity_label: str | None = None
    minutes: int


class ChatTaskTotals(BaseModel):
    count: int
    planned_minutes: int
    effective_minutes: float
    completion_rate: float


class ChatAnalytics(BaseModel):
    day_minutes: int
    tracked_minutes: int
    unaccounted_minutes: int
    behavior_count: int
    categories: list[ChatCategoryTotal] = Field(default_factory=list)
    activities: list[ChatActivityTotal] = Field(default_factory=list)
    task_totals: ChatTaskTotals


class ChatTaskFact(BaseModel):
    title: str
    category: str
    activity_label: str | None = None
    planned_minutes: int
    effective_minutes: float
    completion_rate: float


class ChatContext(BaseModel):
    """Verified, user-scoped facts handed to the chat model.

    Every value is computed by a deterministic engine (Analytics, Task
    Analysis, Pattern Detection) before it reaches this structure. Nothing
    here is derived by the LLM, and no SQLAlchemy/repository object is ever
    part of it.
    """

    period: Period
    analytics: ChatAnalytics
    tasks: list[ChatTaskFact] = Field(default_factory=list)
    patterns: list[PatternFact] = Field(default_factory=list)
