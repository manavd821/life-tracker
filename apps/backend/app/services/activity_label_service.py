from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ResourceConflict,
    ResourceNotFound,
)
from app.repositories.interfaces.activity_label_repository import (
    ActivityLabelRepositoryInterface,
)
from app.schemas.activity_label import (
    ActivityLabelResponse,
    CreateActivityLabel,
    UpdateActivityLabel,
)


class ActivityLabelService:
    def __init__(self, labels: ActivityLabelRepositoryInterface) -> None:
        self._labels = labels

    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[ActivityLabelResponse]:
        labels = await self._labels.list_for_user(session, user_id)
        return [ActivityLabelResponse.model_validate(x) for x in labels]

    async def create(
        self, session: AsyncSession, user_id: uuid.UUID, payload: CreateActivityLabel
    ) -> ActivityLabelResponse:
        await self._reject_duplicate(
            session,
            user_id,
            payload.primary_category.value,
            payload.activity_label.strip(),
        )
        label = await self._labels.add(
            session, user_id, payload.primary_category.value, payload.activity_label.strip()
        )
        await session.commit()
        return ActivityLabelResponse.model_validate(label)

    async def update(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        activity_label_id: uuid.UUID,
        payload: UpdateActivityLabel,
    ) -> ActivityLabelResponse:
        await self._owned(session, user_id, activity_label_id)
        category = (
            payload.primary_category.value
            if payload.primary_category is not None
            else None
        )
        name = payload.activity_label.strip() if payload.activity_label else None
        if category is not None or name is not None:
            current = await self._labels.get(session, activity_label_id)
            await self._reject_duplicate(
                session,
                user_id,
                category or current.primary_category.value,
                name or current.activity_label,
                exclude_id=activity_label_id,
            )
        if category is not None:
            await self._reject_category_change(session, user_id, activity_label_id, category)
        label = await self._labels.update(
            session, activity_label_id, category, name
        )
        await session.commit()
        return ActivityLabelResponse.model_validate(label)

    async def delete(
        self, session: AsyncSession, user_id: uuid.UUID, activity_label_id: uuid.UUID
    ) -> None:
        await self._owned(session, user_id, activity_label_id)
        in_use = await self._labels.count_behaviors_using(session, activity_label_id)
        if in_use:
            raise ResourceConflict(
                f"Activity label is used by {in_use} behavior(s). "
                "Remove it from those behaviors first.",
                code="activity_label_in_use",
            )
        await self._labels.delete(session, activity_label_id)
        await session.commit()

    async def _reject_category_change(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        activity_label_id: uuid.UUID,
        new_category: str,
    ) -> None:
        affected = await self._labels.count_behaviors_outside_category(
            session, activity_label_id, new_category
        )
        if affected:
            raise ResourceConflict(
                f"Category change would invalidate {affected} behavior(s)",
                code="activity_label_category_in_use",
            )

    async def _owned(
        self, session: AsyncSession, user_id: uuid.UUID, activity_label_id: uuid.UUID
    ) -> None:
        label = await self._labels.get(session, activity_label_id)
        if label is None or label.user_id != user_id:
            raise ResourceNotFound("Activity label not found")

    async def _reject_duplicate(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        activity_label: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if await self._labels.exists_in_category(
            session, user_id, primary_category, activity_label, exclude_id
        ):
            raise ResourceConflict(
                f"Activity label '{activity_label}' already exists in {primary_category}"
            )