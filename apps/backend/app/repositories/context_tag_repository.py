from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.context_tag import BehaviorContextTag


class ContextTagRepository:
    async def list_for_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[BehaviorContextTag]:
        stmt = (
            select(BehaviorContextTag)
            .where(BehaviorContextTag.user_id == user_id)
            .order_by(
                BehaviorContextTag.primary_category, BehaviorContextTag.context_tag
            )
        )
        return list((await session.scalars(stmt)).all())

    async def get(
        self, session: AsyncSession, behavior_context_tag_id: uuid.UUID
    ) -> BehaviorContextTag | None:
        return await session.scalar(
            select(BehaviorContextTag).where(
                BehaviorContextTag.behavior_context_tag_id == behavior_context_tag_id
            )
        )

    async def get_many_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
    ) -> list[BehaviorContextTag]:
        if not tag_ids:
            return []
        stmt = select(BehaviorContextTag).where(
            BehaviorContextTag.user_id == user_id,
            BehaviorContextTag.behavior_context_tag_id.in_(tag_ids),
        )
        return list((await session.scalars(stmt)).all())

    async def exists_in_category(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        context_tag: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = (
            select(BehaviorContextTag.behavior_context_tag_id)
            .where(
                BehaviorContextTag.user_id == user_id,
                BehaviorContextTag.primary_category == primary_category,
                BehaviorContextTag.context_tag == context_tag,
            )
            .limit(1)
        )
        if exclude_id is not None:
            stmt = stmt.where(
                BehaviorContextTag.behavior_context_tag_id != exclude_id
            )
        return (await session.scalar(stmt)) is not None

    async def add(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        primary_category: str,
        context_tag: str,
    ) -> BehaviorContextTag:
        tag = BehaviorContextTag(
            user_id=user_id, primary_category=primary_category, context_tag=context_tag
        )
        session.add(tag)
        await session.flush()
        return tag

    async def update(
        self,
        session: AsyncSession,
        behavior_context_tag_id: uuid.UUID,
        primary_category: str | None = None,
        context_tag: str | None = None,
    ) -> BehaviorContextTag | None:
        changes: dict[str, object] = {}
        if primary_category is not None:
            changes["primary_category"] = primary_category
        if context_tag is not None:
            changes["context_tag"] = context_tag
        if changes:
            await session.execute(
                update(BehaviorContextTag)
                .where(
                    BehaviorContextTag.behavior_context_tag_id
                    == behavior_context_tag_id
                )
                .values(**changes)
            )
            await session.flush()
        return await self.get(session, behavior_context_tag_id)

    async def delete(
        self, session: AsyncSession, behavior_context_tag_id: uuid.UUID
    ) -> None:
        await session.delete(
            await session.get(BehaviorContextTag, behavior_context_tag_id)
        )