from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import day_window
from app.repositories.interfaces.task_repository import TaskRepositoryInterface
from app.schemas.ai_chat import (
    ChatActivityTotal,
    ChatAnalytics,
    ChatCategoryTotal,
    ChatContext,
    ChatTaskFact,
    ChatTaskTotals,
)
from app.schemas.ai_insights import (
    ActivityTransitionFact,
    CategoryTransitionFact,
    ContextAssociationFact,
    Period,
)
from app.services.analytics_service import AnalyticsService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.task_analysis_service import TaskAnalysisService


class AIContextBuilder:
    """Builds the verified context for one chat request.

    It only orchestrates the existing deterministic engines:

    - AnalyticsService        -> tracked/unaccounted minutes, categories, activities
    - TaskAnalysisService     -> planned vs effective minutes, completion rate
    - PatternDetectionService -> transitions and context associations
    - TaskRepository          -> task titles for the selected date (presentation only)

    It never computes a statistic itself, never passes SQLAlchemy models or
    repository objects onward, and is always scoped to a single user id that
    comes from authentication, never from the request body.
    """

    def __init__(
        self,
        analytics: AnalyticsService,
        task_analysis: TaskAnalysisService,
        tasks: TaskRepositoryInterface,
        pattern_detection: PatternDetectionService,
    ) -> None:
        self._analytics = analytics
        self._task_analysis = task_analysis
        self._tasks = tasks
        self._pattern_detection = pattern_detection

    async def build(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day: date,
        tz_offset_minutes: int = 0,
    ) -> ChatContext:
        window_start, window_end = day_window(day, tz_offset_minutes)

        daily = await self._analytics.daily(session, user_id, day, tz_offset_minutes)

        task_rows = await self._tasks.get_tasks_for_date(
            session, user_id, window_start, window_end
        )
        analyses = await self._task_analysis.analyze_tasks_for_date(
            session, user_id, window_start, window_end
        )
        analysis_by_id = {analysis.task_id: analysis for analysis in analyses}

        task_facts: list[ChatTaskFact] = []
        for task in task_rows:
            analysis = analysis_by_id.get(task.task_id)
            task_facts.append(
                ChatTaskFact(
                    title=task.title,
                    category=getattr(task.primary_category, "value", task.primary_category),
                    activity_label=(
                        task.activity_label.activity_label if task.activity_label else None
                    ),
                    planned_minutes=(
                        analysis.planned_minutes if analysis else task.planned_minutes
                    ),
                    effective_minutes=analysis.effective_minutes if analysis else 0.0,
                    completion_rate=analysis.completion_rate if analysis else 0.0,
                )
            )

        transitions = await self._pattern_detection.transitions(
            session, user_id, day, day, tz_offset_minutes
        )
        context_patterns = await self._pattern_detection.context(
            session, user_id, day, day, tz_offset_minutes
        )

        return ChatContext(
            period=Period(start=day.isoformat(), end=day.isoformat()),
            analytics=ChatAnalytics(
                day_minutes=daily.summary.day_minutes,
                tracked_minutes=daily.summary.tracked_minutes,
                unaccounted_minutes=daily.summary.unaccounted_minutes,
                behavior_count=daily.summary.behavior_count,
                categories=[
                    ChatCategoryTotal(
                        category=getattr(category.category, "value", category.category),
                        minutes=category.duration_minutes,
                    )
                    for category in daily.categories
                ],
                activities=[
                    ChatActivityTotal(
                        category=getattr(activity.category, "value", activity.category),
                        activity_label=activity.activity_label,
                        minutes=activity.duration_minutes,
                    )
                    for activity in daily.activities
                ],
                task_totals=ChatTaskTotals(**daily.tasks.model_dump()),
            ),
            tasks=task_facts,
            patterns=self._pattern_facts(transitions, context_patterns),
        )

    @staticmethod
    def _pattern_facts(transitions, context_patterns) -> list:
        facts: list = []
        for pattern in transitions.category_transitions:
            facts.append(
                CategoryTransitionFact(
                    from_category=getattr(pattern.from_category, "value", pattern.from_category),
                    to_category=getattr(pattern.to_category, "value", pattern.to_category),
                    count=pattern.count,
                    probability=pattern.probability,
                )
            )
        for pattern in transitions.activity_transitions:
            facts.append(
                ActivityTransitionFact(
                    from_category=getattr(pattern.from_category, "value", pattern.from_category),
                    from_activity=pattern.from_activity,
                    to_category=getattr(pattern.to_category, "value", pattern.to_category),
                    to_activity=pattern.to_activity,
                    count=pattern.count,
                    probability=pattern.probability,
                )
            )
        for pattern in context_patterns.associations:
            facts.append(
                ContextAssociationFact(
                    category=getattr(pattern.category, "value", pattern.category),
                    activity_label=pattern.activity_label,
                    dimension=pattern.dimension,
                    context_a=pattern.context_a,
                    context_b=pattern.context_b,
                    average_duration_a=pattern.average_duration_a,
                    average_duration_b=pattern.average_duration_b,
                    sample_a=pattern.sample_a,
                    sample_b=pattern.sample_b,
                    difference_minutes=pattern.difference_minutes,
                )
            )
        return facts


def render_chat_context(context: ChatContext) -> str:
    """Deterministic, readable rendering of the verified context.

    The same ChatContext always produces the same text: no dict dumps, no
    repository objects, no internal identifiers.
    """
    start = date.fromisoformat(context.period.start)
    end = date.fromisoformat(context.period.end)
    period = (
        f"{start.strftime('%B')} {start.day}, {start.year}"
        if start == end
        else f"{start.isoformat()} to {end.isoformat()}"
    )

    analytics = context.analytics
    lines: list[str] = ["<life_tracker_context>", f"Period: {period}", "", "Analytics:"]
    lines.append(f"- Day length: {analytics.day_minutes} minutes")
    lines.append(f"- Tracked: {analytics.tracked_minutes} minutes")
    lines.append(
        f"- Unaccounted: {analytics.unaccounted_minutes} minutes "
        "(unknown time; never assume what it contains)"
    )
    lines.append(f"- Behaviors recorded: {analytics.behavior_count}")
    lines.append(
        "- Categories: "
        + (
            "; ".join(f"{c.category} {c.minutes} min" for c in analytics.categories)
            if analytics.categories
            else "none recorded"
        )
    )
    lines.append(
        "- Activities: "
        + (
            "; ".join(
                f"{a.category}/{a.activity_label or 'unlabelled'} {a.minutes} min"
                for a in analytics.activities
            )
            if analytics.activities
            else "none recorded"
        )
    )
    totals = analytics.task_totals
    lines.append(
        f"- Task totals: {totals.count} task(s), planned {totals.planned_minutes} min, "
        f"effective {_num(totals.effective_minutes)} min, "
        f"completion {_num(totals.completion_rate)}%"
    )

    lines.append("")
    lines.append("Tasks:")
    if context.tasks:
        for task in context.tasks:
            label = f"{task.category}/{task.activity_label}" if task.activity_label else task.category
            lines.append(
                f'- "{task.title}" [{label}]: planned {task.planned_minutes} min, '
                f"effective {_num(task.effective_minutes)} min, "
                f"completion {_num(task.completion_rate)}%"
            )
    else:
        lines.append("- (no tasks scheduled for this date)")

    lines.append("")
    lines.append(
        "Patterns (deterministic detections for this period; patterns below "
        "minimum sample thresholds are not reported):"
    )
    if context.patterns:
        lines.extend(_render_pattern(pattern) for pattern in context.patterns)
    else:
        lines.append("- (no patterns detected for this date)")

    lines.append("</life_tracker_context>")
    return "\n".join(lines)


def _render_pattern(pattern) -> str:
    kind = pattern.type
    if kind == "category_transition":
        return (
            f"- category_transition: {pattern.from_category} -> {pattern.to_category}, "
            f"{pattern.count} transition(s), {_num(pattern.probability * 100)}% of "
            f"transitions out of {pattern.from_category}"
        )
    if kind == "activity_transition":
        return (
            f"- activity_transition: {pattern.from_category}/{pattern.from_activity} -> "
            f"{pattern.to_category}/{pattern.to_activity}, {pattern.count} transition(s), "
            f"{_num(pattern.probability * 100)}% of transitions out of that source"
        )
    return (
        f"- context_association: {pattern.category}/{pattern.activity_label or 'unlabelled'}, "
        f"dimension={pattern.dimension}: {pattern.context_a} "
        f"{_num(pattern.average_duration_a)} min average over {pattern.sample_a} session(s) "
        f"vs {pattern.context_b} {_num(pattern.average_duration_b)} min average over "
        f"{pattern.sample_b} session(s) (difference {_num(pattern.difference_minutes)} min)"
    )


def _num(value: float) -> str:
    return f"{value:g}"
