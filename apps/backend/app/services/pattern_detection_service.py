from __future__ import annotations

import uuid
from datetime import date, datetime
from itertools import pairwise

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import range_window
from app.core.errors import InvalidTimeRange
from app.models.behavior import Behavior
from app.repositories.interfaces.behavior_repository import (
    BehaviorRepositoryInterface,
    ContextDurationRow,
)
from app.schemas.patterns import (
    ActivityTransition,
    CategoryTransition,
    ContextAssociation,
    ContextPatterns,
    ContextStat,
    PatternWindow,
    TransitionPatterns,
)


class PatternDetectionService:
    """Deterministic statistics over recorded behaviors.

    Detects category and activity transitions and describes activity/context
    duration associations. Every figure is derived by counting or averaging
    observed records: nothing is inferred, no gap is bridged, and no causal or
    coaching statement is produced.
    """

    def __init__(
        self,
        behaviors: BehaviorRepositoryInterface,
        *,
        min_transition_count: int = 5,
        min_context_sessions: int = 3,
    ) -> None:
        self._behaviors = behaviors
        self._min_transition_count = max(1, min_transition_count)
        self._min_context_sessions = max(1, min_context_sessions)

    async def transitions(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        tz_offset_minutes: int = 0,
    ) -> TransitionPatterns:
        window_start, window_end, start, end = self._resolve_window(
            start_date, end_date, tz_offset_minutes
        )
        behaviors = await self._behaviors.list_for_range(
            session, user_id, window_start, window_end
        )

        category_counts: dict[tuple[str, str], int] = {}
        activity_counts: dict[tuple[str, str, str, str], int] = {}

        for chain in self._contiguous_chains(behaviors):
            for from_category, to_category in self._category_sequence(chain):
                key = (from_category, to_category)
                category_counts[key] = category_counts.get(key, 0) + 1

            for source, target in self._activity_sequences(chain):
                key = (*source, *target)
                activity_counts[key] = activity_counts.get(key, 0) + 1

        return TransitionPatterns(
            window=PatternWindow(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                behavior_count=len(behaviors),
            ),
            minimum_transition_count=self._min_transition_count,
            category_transitions=self._category_patterns(category_counts),
            activity_transitions=self._activity_patterns(activity_counts),
        )

    async def context(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        tz_offset_minutes: int = 0,
    ) -> ContextPatterns:
        window_start, window_end, start, end = self._resolve_window(
            start_date, end_date, tz_offset_minutes
        )
        rows = await self._behaviors.get_context_duration_totals(
            session, user_id, window_start, window_end
        )
        stats = [self._stat(row) for row in rows]
        behaviors = await self._behaviors.list_for_range(
            session, user_id, window_start, window_end
        )

        return ContextPatterns(
            window=PatternWindow(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                behavior_count=len(behaviors),
            ),
            minimum_context_sessions=self._min_context_sessions,
            context_stats=sorted(
                stats,
                key=lambda s: (
                    s.dimension,
                    s.category.value,
                    s.activity_label or "",
                    s.context,
                ),
            ),
            associations=self._associations(stats),
        )

    # ---------- window ----------

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
                code="invalid_pattern_range",
            )
        return (*range_window(start, end, tz_offset_minutes), start, end)

    # ---------- transitions ----------

    @staticmethod
    def _contiguous_chains(behaviors: list[Behavior]) -> list[list[Behavior]]:
        """Split an ordered timeline wherever unaccounted time separates two
        behaviors. A transition is only ever counted inside one chain, so a gap
        is never bridged."""
        chains: list[list[Behavior]] = []
        current: list[Behavior] = []

        for behavior in sorted(behaviors, key=lambda b: (b.start_time, b.behavior_id)):
            if current and current[-1].end_time == behavior.start_time:
                current.append(behavior)
            else:
                if current:
                    chains.append(current)
                current = [behavior]

        if current:
            chains.append(current)
        return chains

    @staticmethod
    def _category_sequence(chain: list[Behavior]) -> list[tuple[str, str]]:
        """Collapse consecutive same-category behaviors so that
        Study/DSA -> Study/CN yields a single Study step and never Study -> Study."""
        collapsed: list[str] = []
        for behavior in chain:
            category = _value(behavior.primary_category)
            if not collapsed or collapsed[-1] != category:
                collapsed.append(category)

        return list(pairwise(collapsed))

    @staticmethod
    def _activity_sequences(
        chain: list[Behavior],
    ) -> list[tuple[tuple[str, str], tuple[str, str]]]:
        """Pairs of consecutive labelled behaviors. A behavior without an
        activity label breaks the activity chain instead of being given an
        invented name."""
        pairs: list[tuple[tuple[str, str], tuple[str, str]]] = []
        previous: tuple[str, str] | None = None

        for behavior in chain:
            label = (
                behavior.activity_label.activity_label
                if behavior.activity_label is not None
                else None
            )
            if label is None:
                previous = None
                continue
            current = (_value(behavior.primary_category), label)
            if previous is not None and previous != current:
                pairs.append((previous, current))
            previous = current
        return pairs

    def _category_patterns(
        self, counts: dict[tuple[str, str], int]
    ) -> list[CategoryTransition]:
        totals = self._totals(counts, lambda key: key[0])
        patterns = [
            CategoryTransition(
                from_category=from_category,
                to_category=to_category,
                count=count,
                probability=self._probability(count, totals[from_category]),
                transitions_from_source=totals[from_category],
            )
            for (from_category, to_category), count in counts.items()
            if count >= self._min_transition_count
        ]
        return sorted(patterns, key=lambda p: (-p.count, p.from_category.value, p.to_category.value))

    def _activity_patterns(
        self, counts: dict[tuple[str, str, str, str], int]
    ) -> list[ActivityTransition]:
        totals = self._totals(counts, lambda key: key[:2])
        patterns = [
            ActivityTransition(
                from_category=from_category,
                from_activity=from_activity,
                to_category=to_category,
                to_activity=to_activity,
                count=count,
                probability=self._probability(count, totals[(from_category, from_activity)]),
                transitions_from_source=totals[(from_category, from_activity)],
            )
            for (from_category, from_activity, to_category, to_activity), count in counts.items()
            if count >= self._min_transition_count
        ]
        return sorted(
            patterns,
            key=lambda p: (-p.count, p.from_category.value, p.from_activity, p.to_category.value, p.to_activity),
        )

    @staticmethod
    def _totals(counts: dict, key_of) -> dict:
        totals: dict = {}
        for key, count in counts.items():
            bucket = key_of(key)
            totals[bucket] = totals.get(bucket, 0) + count
        return totals

    @staticmethod
    def _probability(count: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round(count / total, 4)

    # ---------- context ----------

    @staticmethod
    def _stat(row: ContextDurationRow) -> ContextStat:
        return ContextStat(
            category=row.category,
            activity_label=row.activity_label,
            dimension=row.dimension,
            context=row.context,
            session_count=row.session_count,
            total_duration_minutes=row.total_duration_minutes,
            average_duration_minutes=round(
                row.total_duration_minutes / row.session_count, 2
            )
            if row.session_count
            else 0.0,
        )

    def _associations(self, stats: list[ContextStat]) -> list[ContextAssociation]:
        """Longest and shortest average session per activity/context dimension.

        Only the observed association is reported: not why it happens and not
        what the user should do about it."""
        groups: dict[tuple[str, str, str], list[ContextStat]] = {}
        for stat in stats:
            if stat.session_count < self._min_context_sessions:
                continue
            key = (stat.dimension, stat.category.value, stat.activity_label or "")
            groups.setdefault(key, []).append(stat)

        associations: list[ContextAssociation] = []
        for (dimension, _, _), bucket in groups.items():
            if len(bucket) < 2:
                continue
            longest = max(bucket, key=lambda s: (s.average_duration_minutes, s.context))
            shortest = min(bucket, key=lambda s: (s.average_duration_minutes, s.context))
            if longest.average_duration_minutes <= shortest.average_duration_minutes:
                continue
            associations.append(
                ContextAssociation(
                    category=longest.category,
                    activity_label=longest.activity_label,
                    dimension=dimension,
                    context_a=longest.context,
                    context_b=shortest.context,
                    average_duration_a=longest.average_duration_minutes,
                    average_duration_b=shortest.average_duration_minutes,
                    sample_a=longest.session_count,
                    sample_b=shortest.session_count,
                    difference_minutes=round(
                        longest.average_duration_minutes
                        - shortest.average_duration_minutes,
                        2,
                    ),
                    ratio=round(
                        longest.average_duration_minutes
                        / shortest.average_duration_minutes,
                        2,
                    )
                    if shortest.average_duration_minutes
                    else 0.0,
                )
            )
        return sorted(
            associations,
            key=lambda a: (-a.difference_minutes, a.dimension, a.activity_label or ""),
        )


def _value(enum_member) -> str:
    return getattr(enum_member, "value", enum_member)
