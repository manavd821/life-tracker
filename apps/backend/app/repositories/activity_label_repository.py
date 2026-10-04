from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_label import ActivityLabel
from app.models.behavior import Behavior


class ActivityLabelRepository:
    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[ActivityLabel]:
        stmt = (
            select(ActivityLabel)
            .where(ActivityLabel.user_id == user_id)
            .order_by(
                ActivityLabel.primary_category, ActivityLabel.activity_label
            )
        )
        return list((await session.scalars(stmt)).all())

    async def get(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> ActivityLabel | None:
        return await session.scalar(
            select(ActivityLabel).where(
                ActivityLabel.activity_label_id == activity_label_id
            )
        )

    async def get_many_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        activity_label_ids: list[uuid.UUID],
    ) -> list[ActivityLabel]:
        if not activity_label_ids:
            return []
        stmt = select(ActivityLabel).where(
            ActivityLabel.user_id == user_id,
            ActivityLabel.activity_label_id.in_(activity_label_ids),
        )
        return list((await session.scalars(stmt)).all())

    async def exists_in_category(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        activity_label: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = (
            select(ActivityLabel.activity_label_id)
            .where(
                ActivityLabel.user_id == user_id,
                ActivityLabel.primary_category == primary_category,
                ActivityLabel.activity_label == activity_label,
            )
            .limit(1)
        )
        if exclude_id is not None:
            stmt = stmt.where(ActivityLabel.activity_label_id != exclude_id)
        return (await session.scalar(stmt)) is not None

    async def add(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        activity_label: str,
    ) -> ActivityLabel:
        label = ActivityLabel(
            user_id=user_id,
            primary_category=primary_category,
            activity_label=activity_label,
        )
        session.add(label)
        await session.flush()
        return label

    async def update(
        self,
        session: AsyncSession,
        activity_label_id: uuid.UUID,
        primary_category: str | None = None,
        activity_label: str | None = None,
    ) -> ActivityLabel | None:
        changes: dict[str, object] = {}
        if primary_category is not None:
            changes["primary_category"] = primary_category
        if activity_label is not None:
            changes["activity_label"] = activity_label
        if changes:
            await session.execute(
                update(ActivityLabel)
                .where(
                    ActivityLabel.activity_label_id == activity_label_id
                )
                .values(**changes)
            )
            await session.flush()
        return await self.get(session, activity_label_id)

    async def delete(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> None:
        await session.delete(
            await session.get(ActivityLabel, activity_label_id)
        )

    async def count_behaviors_using(
        self, session: AsyncSession, activity_label_id: uuid.UUID
    ) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(Behavior)
                .where(
                    Behavior.activity_label_id == activity_label_id,
                    Behavior.deleted_at.is_(None),
                )
            )
        ) or 0

    async def count_behaviors_outside_category(
        self,
        session: AsyncSession,
        activity_label_id: uuid.UUID,
        primary_category: str,
    ) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(Behavior)
                .where(
                    Behavior.activity_label_id == activity_label_id,
                    Behavior.primary_category != primary_category,
                    Behavior.deleted_at.is_(None),
                )
            )
        ) or 0