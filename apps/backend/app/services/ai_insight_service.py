from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import day_window, range_window, window_minutes
from app.core.errors import InvalidTimeRange
from app.repositories.interfaces.behavior_repository import BehaviorRepositoryInterface
from app.schemas.ai_insights import (
    AIContext,
    AIResponse,
    BehaviorSummary,
    CategoryTotal,
    CategoryTransitionFact,
    CoachingSuggestion,
    ContextAssociationFact,
    Insight,
    Period,
    TaskSummary,
)
from app.services.analytics_service import AnalyticsService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.task_analysis_service import TaskAnalysisService

logger = logging.getLogger(__name__)

AI_SYSTEM_PROMPT = """You are the AI Insight Engine for a deterministic behavior tracking system.

PRINCIPLES:
1. Do not invent facts. Only use the structured information provided in the input.
2. Do not make unsupported causal claims. Say "your recorded X sessions have been longer in Y" instead of "Y makes you X better".
3. Distinguish correlation from causation. Use phrases like "associated with", "observed more often", "appears", or "recorded pattern".
4. Unaccounted time is uncertainty. Never interpret unaccounted time as rest, entertainment, laziness, phone usage, or sleeping unless the data explicitly says so.
5. Coaching must be actionable. Turn verified observations into practical experiments or suggestions.
6. Avoid judgment. Do not shame or morally judge the user.
7. Keep insights and coaching separate: insights answer "what does the data show?"; coaching answers "what could I try?".

OUTPUT:
Return a JSON object matching this exact schema:
{
  "insights": [
    {
      "title": "string",
      "description": "string",
      "supporting_facts": ["string", ...]
    }
  ],
  "coaching": [
    {
      "title": "string",
      "recommendation": "string",
      "reasoning": "string"
    }
  ]
}

Be concise, analytical, and supportive. Use only the provided facts."""


class AIInsightService:
    def __init__(
        self,
        behaviors: BehaviorRepositoryInterface,
        analytics: AnalyticsService,
        task_analysis: TaskAnalysisService,
        pattern_detection: PatternDetectionService,
        client: Any | None = None,
    ) -> None:
        self._behaviors = behaviors
        self._analytics = analytics
        self._task_analysis = task_analysis
        self._pattern_detection = pattern_detection
        self._client = client

    def _resolve_window(
        self,
        start_date: date | None,
        end_date: date | None,
        tz_offset_minutes: int,
    ) -> tuple[datetime, datetime, date, date]:
        start = start_date or date.today()
        end = end_date or start
        if end < start:
            raise InvalidTimeRange(
                "end_date must be on or after start_date",
                code="invalid_insight_range",
            )
        return (*range_window(start, end, tz_offset_minutes), start, end)

    async def build_context(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        tz_offset_minutes: int = 0,
    ) -> AIContext:
        import uuid

        window_start, window_end, start, end = self._resolve_window(
            start_date, end_date, tz_offset_minutes
        )
        if start == end:
            day_start, day_end = day_window(start, tz_offset_minutes)
            window_start, window_end = day_start, day_end

        analytics = await self._analytics.daily(session, user_id, start, tz_offset_minutes) if start == end else None

        if analytics is None:
            behavior_count, tracked = await self._behaviors.get_day_totals(
                session, user_id, window_start, window_end
            )
            categories = await self._behaviors.get_category_totals(
                session, user_id, window_start, window_end
            )
            activities = await self._behaviors.get_activity_totals(
                session, user_id, window_start, window_end
            )
            analyses = await self._task_analysis.analyze_tasks_for_date(
                session, user_id, window_start, window_end
            )
            day_total = window_minutes(window_start, window_end)
            behavior_summary = BehaviorSummary(
                tracked_minutes=tracked,
                unaccounted_minutes=day_total - tracked,
                category_totals=[
                    CategoryTotal(category=category, minutes=minutes)
                    for category, minutes in categories
                ],
                day_minutes=day_total,
                behavior_count=behavior_count,
            )
            task_summary = TaskSummary(
                planned_minutes=sum(a.planned_minutes for a in analyses),
                effective_minutes=round(sum(a.effective_minutes for a in analyses), 2),
                completion_rate=round(
                    (sum(a.effective_minutes for a in analyses) / sum(a.planned_minutes for a in analyses) * 100)
                    if sum(a.planned_minutes for a in analyses) > 0
                    else 0.0,
                    2,
                ),
                count=len(analyses),
            )
        else:
            behavior_summary = BehaviorSummary(
                tracked_minutes=analytics.summary.tracked_minutes,
                unaccounted_minutes=analytics.summary.unaccounted_minutes,
                category_totals=[
                    CategoryTotal(category=c.category, minutes=c.duration_minutes)
                    for c in analytics.categories
                ],
                day_minutes=analytics.summary.day_minutes,
                behavior_count=analytics.summary.behavior_count,
            )
            task_summary = TaskSummary(
                planned_minutes=analytics.tasks.planned_minutes,
                effective_minutes=analytics.tasks.effective_minutes,
                completion_rate=analytics.tasks.completion_rate,
                count=analytics.tasks.count,
            )

        transitions = await self._pattern_detection.transitions(
            session, user_id, start, end, tz_offset_minutes
        )
        context_patterns = await self._pattern_detection.context(
            session, user_id, start, end, tz_offset_minutes
        )

        patterns: list[Any] = []
        for p in transitions.category_transitions:
            patterns.append(
                CategoryTransitionFact(
                    from_category=p.from_category.value,
                    to_category=p.to_category.value,
                    count=p.count,
                    probability=p.probability,
                )
            )
        for p in transitions.activity_transitions:
            patterns.append(
                CategoryTransitionFact(
                    type="activity_transition",
                    from_category=p.from_category.value,
                    from_activity=p.from_activity,
                    to_category=p.to_category.value,
                    to_activity=p.to_activity,
                    count=p.count,
                    probability=p.probability,
                )
            )
        for p in context_patterns.associations:
            patterns.append(
                ContextAssociationFact(
                    category=p.category.value,
                    activity_label=p.activity_label,
                    dimension=p.dimension,
                    context_a=p.context_a,
                    context_b=p.context_b,
                    average_duration_a=p.average_duration_a,
                    average_duration_b=p.average_duration_b,
                    sample_a=p.sample_a,
                    sample_b=p.sample_b,
                    difference_minutes=p.difference_minutes,
                )
            )

        return AIContext(
            period=Period(start=start.isoformat(), end=end.isoformat()),
            behavior_summary=behavior_summary,
            task_summary=task_summary,
            patterns=patterns,
        )

    async def generate_insights(
        self,
        context: AIContext,
        api_key: str | None = None,
        model: str | None = None,
    ) -> AIResponse:
        if self._client is not None:
            return await self._generate_with_client(context)
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            model_name = model or "gemini-2.5-flash"
            response = client.models.generate_content(
                model=model_name,
                contents=json.dumps(context.model_dump(mode="json"), indent=2),
                config=types.GenerateContentConfig(
                    system_instruction=AI_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            text = response.text if hasattr(response, "text") else ""
            if not text:
                raise ValueError("Empty response from Gemini")
            data = json.loads(text)
            return AIResponse.model_validate(data)
        except ValidationError:
            logger.exception("Gemini returned invalid structured response")
            raise
        except Exception as exc:
            logger.exception("Failed to generate insights via Gemini")
            raise RuntimeError(f"Gemini API error: {exc}") from exc

    async def _generate_with_client(self, context: AIContext) -> AIResponse:
        client = self._client
        model_name = getattr(client, "_model", "gemini-2.5-flash")
        system_prompt = AI_SYSTEM_PROMPT
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=json.dumps(context.model_dump(mode="json"), indent=2),
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            )
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Empty response")
            data = json.loads(text)
            return AIResponse.model_validate(data)
        except ValidationError:
            logger.exception("Gemini returned invalid structured response")
            raise
        except Exception as exc:
            logger.exception("Failed to generate insights")
            raise RuntimeError(f"Gemini API error: {exc}") from exc


import uuid  # noqa: E402
