from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ResourceConflict, ResourceNotFound
from app.repositories.interfaces.context_tag_repository import (
    ContextTagRepositoryInterface,
)
from app.schemas.context_tag import (
    ContextTagResponse,
    CreateContextTag,
    UpdateContextTag,
)


class ContextTagService:
    def __init__(self, tags: ContextTagRepositoryInterface) -> None:
        self._tags = tags

    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[ContextTagResponse]:
        tags = await self._tags.list_for_user(session, user_id)
        return [ContextTagResponse.model_validate(t) for t in tags]

    async def create(
        self, session: AsyncSession, user_id: uuid.UUID, payload: CreateContextTag
    ) -> ContextTagResponse:
        await self._reject_duplicate(
            session, user_id, payload.primary_category.value, payload.context_tag.strip()
        )
        tag = await self._tags.add(
            session, user_id, payload.primary_category.value, payload.context_tag.strip()
        )
        await session.commit()
        return ContextTagResponse.model_validate(tag)

    async def update(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        behavior_context_tag_id: uuid.UUID,
        payload: UpdateContextTag,
    ) -> ContextTagResponse:
        await self._owned(session, user_id, behavior_context_tag_id)
        category = (
            payload.primary_category.value
            if payload.primary_category is not None
            else None
        )
        name = payload.context_tag.strip() if payload.context_tag else None
        if category is not None or name is not None:
            current = await self._tags.get(session, behavior_context_tag_id)
            await self._reject_duplicate(
                session,
                user_id,
                category or current.primary_category.value,
                name or current.context_tag,
                exclude_id=behavior_context_tag_id,
            )
        tag = await self._tags.update(
            session, behavior_context_tag_id, category, name
        )
        await session.commit()
        return ContextTagResponse.model_validate(tag)

    async def delete(
        self, session: AsyncSession, user_id: uuid.UUID, behavior_context_tag_id: uuid.UUID
    ) -> None:
        await self._owned(session, user_id, behavior_context_tag_id)
        await self._tags.delete(session, behavior_context_tag_id)
        await session.commit()

    async def _owned(
        self, session: AsyncSession, user_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        tag = await self._tags.get(session, tag_id)
        if tag is None or tag.user_id != user_id:
            raise ResourceNotFound("Context tag not found")

    async def _reject_duplicate(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        context_tag: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if await self._tags.exists_in_category(
            session, user_id, primary_category, context_tag, exclude_id
        ):
            raise ResourceConflict(
                f"Context tag '{context_tag}' already exists in {primary_category}"
            )