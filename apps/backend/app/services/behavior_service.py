from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from psycopg.errors import ExclusionViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.day import day_window
from app.core.errors import BehaviorOverlapError, InvalidTimeRange, ResourceNotFound
from app.models.behavior import Behavior
from app.models.enums import BehaviorSource, PrimaryCategory
from app.repositories.interfaces.activity_label_repository import (
    ActivityLabelRepositoryInterface,
)
from app.repositories.interfaces.behavior_repository import BehaviorRepositoryInterface
from app.repositories.interfaces.context_tag_repository import (
    ContextTagRepositoryInterface,
)
from app.schemas.behavior import BehaviorResponse, CreateBehavior, UpdateBehavior
from app.schemas.timeline import TimelineResponse, UnaccountedPeriod

logger = logging.getLogger(__name__)


def _describe(behavior: Behavior) -> str:
    label = behavior.activity_label.activity_label if behavior.activity_label else None
    parts = [_value(behavior.primary_category)]
    if label:
        parts.append(label)
    window = f"{behavior.start_time:%H:%M}-{behavior.end_time:%H:%M}"
    return f"{' · '.join(parts)} · {window}"


class BehaviorService:
    def __init__(
        self,
        behaviors: BehaviorRepositoryInterface,
        activity_labels: ActivityLabelRepositoryInterface,
        context_tags: ContextTagRepositoryInterface,
    ) -> None:
        self._behaviors = behaviors
        self._activity_labels = activity_labels
        self._context_tags = context_tags

    async def create(
        self, session: AsyncSession, user_id: uuid.UUID, payload: CreateBehavior
    ) -> BehaviorResponse:
        self._validate_range(payload.start_time, payload.end_time)
        activity_label_id = await self._validate_activity_label(
            session, user_id, payload.primary_category, payload.activity_label_id
        )
        tags = await self._validate_context_tags(
            session, user_id, payload.primary_category, payload.context_tag_ids
        )
        await self._reject_overlap(
            session, user_id, payload.start_time, payload.end_time
        )

        behavior = await self._behaviors.add(
            session,
            user_id=user_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            primary_category=payload.primary_category.value,
            activity_label_id=activity_label_id,
            energy_level=_value(payload.energy_level),
            emotion_state=_value(payload.emotion_state),
            focus_state=_value(payload.focus_state),
            environment=_value(payload.environment),
            precision=payload.precision.value,
            notes=payload.notes,
            source=BehaviorSource.manual.value,
        )
        await _set_tags(session, behavior, tags)
        await self._commit(session)
        return await self._response(
            await self._behaviors.get(session, behavior.behavior_id)
        )

    async def timeline(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        day: date,
        tz_offset_minutes: int = 0,
    ) -> TimelineResponse:
        day_start, day_end = day_window(day, tz_offset_minutes)
        behaviors = await self._behaviors.list_for_day(
            session, user_id, day_start, day_end
        )
        responses = [await self._response(b) for b in behaviors]
        gaps = self._gaps(behaviors, day_start, day_end)
        return TimelineResponse(
            date=day.isoformat(),
            behaviors=responses,
            unaccounted=gaps,
            total_tracked_minutes=sum(b.duration_minutes for b in behaviors),
            total_unaccounted_minutes=sum(g.duration_minutes for g in gaps),
            total_behaviors=len(behaviors),
        )

    async def get(
        self, session: AsyncSession, user_id: uuid.UUID, behavior_id: uuid.UUID
    ) -> BehaviorResponse:
        return await self._response(await self._owned(session, user_id, behavior_id))

    async def update(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        behavior_id: uuid.UUID,
        payload: UpdateBehavior,
    ) -> BehaviorResponse:
        existing = await self._owned(session, user_id, behavior_id)

        start_time = payload.start_time or existing.start_time
        end_time = payload.end_time or existing.end_time
        self._validate_range(start_time, end_time)

        category = payload.primary_category or existing.primary_category
        activity_label_id = (
            payload.activity_label_id
            if payload.activity_label_id is not None
            else existing.activity_label_id
        )
        validated_label = await self._validate_activity_label(
            session, user_id, category, activity_label_id
        )

        if payload.context_tag_ids is not None:
            tags = await self._validate_context_tags(
                session, user_id, category, payload.context_tag_ids
            )
        else:
            tags = list(existing.context_tags)

        await self._reject_overlap(
            session,
            user_id,
            start_time,
            end_time,
            exclude_behavior_id=behavior_id,
        )

        changes: dict[str, object] = {
            "start_time": start_time,
            "end_time": end_time,
            "primary_category": category.value,
            "activity_label_id": validated_label,
            "precision": (
                payload.precision.value
                if payload.precision is not None
                else existing.precision.value
            ),
            "source": BehaviorSource.edit.value,
        }
        for name in (
            "energy_level",
            "emotion_state",
            "focus_state",
            "environment",
            "notes",
        ):
            if name in payload.model_fields_set:
                changes[name] = _value(getattr(payload, name))

        await self._behaviors.update(session, behavior_id, **changes)
        behavior = await self._owned(session, user_id, behavior_id)
        await _set_tags(session, behavior, tags)
        await self._commit(session)
        return await self._response(await self._owned(session, user_id, behavior_id))

    async def delete(
        self, session: AsyncSession, user_id: uuid.UUID, behavior_id: uuid.UUID
    ) -> None:
        await self._owned(session, user_id, behavior_id)
        await self._behaviors.soft_delete(session, behavior_id, datetime.now(timezone.utc))
        await session.commit()

    async def _owned(
        self, session: AsyncSession, user_id: uuid.UUID, behavior_id: uuid.UUID
    ) -> Behavior:
        behavior = await self._behaviors.get(session, behavior_id)
        if behavior is None or behavior.user_id != user_id:
            raise ResourceNotFound("Behavior not found")
        return behavior

    @staticmethod
    def _validate_range(start_time: datetime, end_time: datetime) -> None:
        if start_time >= end_time:
            raise InvalidTimeRange("start_time must be before end_time")

    async def _validate_activity_label(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        category: PrimaryCategory,
        activity_label_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if activity_label_id is None:
            return None
        label = await self._activity_labels.get(session, activity_label_id)
        if label is None or label.user_id != user_id:
            raise ResourceNotFound("Activity label not found")
        if label.primary_category != category:
            raise InvalidTimeRange(
                f"Activity label '{label.activity_label}' belongs to "
                f"{_value(label.primary_category)}, not {category.value}",
                code="activity_label_category_mismatch",
            )
        return activity_label_id

    async def _validate_context_tags(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        category: PrimaryCategory,
        tag_ids: list[uuid.UUID],
    ) -> list:
        if not tag_ids:
            return []
        unique_ids = list(dict.fromkeys(tag_ids))
        tags = await self._context_tags.get_many_for_user(session, user_id, unique_ids)
        found = {t.behavior_context_tag_id for t in tags}
        if len(found) != len(unique_ids):
            raise ResourceNotFound("One or more context tags not found")
        for tag in tags:
            if tag.primary_category != category:
                raise InvalidTimeRange(
                    f"Context tag '{tag.context_tag}' belongs to "
                    f"{_value(tag.primary_category)}, not {category.value}",
                    code="context_tag_category_mismatch",
                )
        return tags

    async def _reject_overlap(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        exclude_behavior_id: uuid.UUID | None = None,
    ) -> None:
        clashes = await self._behaviors.list_overlapping(
            session, user_id, start_time, end_time, exclude_behavior_id
        )
        if clashes:
            raise BehaviorOverlapError(
                "Time overlap detected",
                details={"conflicts": [_describe(b) for b in clashes]},
            )

    async def _commit(self, session: AsyncSession) -> None:
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            if isinstance(exc.orig, ExclusionViolation) or "ex_behaviors_no_overlap" in str(
                exc.orig
            ):
                raise BehaviorOverlapError(
                    "Time overlap detected", details={"conflicts": []}
                ) from exc
            raise

    async def _response(self, behavior: Behavior) -> BehaviorResponse:
        return BehaviorResponse.model_validate(behavior)

    @staticmethod
    def _gaps(
        behaviors: list[Behavior], day_start: datetime, day_end: datetime
    ) -> list[UnaccountedPeriod]:
        gaps: list[UnaccountedPeriod] = []
        cursor = day_start
        for behavior in behaviors:
            if behavior.start_time > cursor:
                gaps.append(_period(cursor, behavior.start_time))
            cursor = max(cursor, behavior.end_time)
        if cursor < day_end:
            gaps.append(_period(cursor, day_end))
        return gaps


async def _set_tags(session: AsyncSession, behavior: Behavior, tags: list) -> None:
    await session.run_sync(lambda _: setattr(behavior, "context_tags", tags))


def _period(start: datetime, end: datetime) -> UnaccountedPeriod:
    return UnaccountedPeriod(
        start_time=start,
        end_time=end,
        duration_minutes=int((end - start).total_seconds() // 60),
    )


def _value(enum_member) -> str | None:
    if enum_member is None:
        return None
    return getattr(enum_member, "value", enum_member)