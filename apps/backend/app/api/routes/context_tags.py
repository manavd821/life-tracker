import uuid

from fastapi import APIRouter, status

from app.api.dependencies import ContextTagServiceDep, CurrentUser, DbSession
from app.schemas.context_tag import (
    ContextTagResponse,
    CreateContextTag,
    UpdateContextTag,
)

router = APIRouter(prefix="/context-tags", tags=["context-tags"])


@router.get("", response_model=list[ContextTagResponse])
async def list_context_tags(session: DbSession, user: CurrentUser, service: ContextTagServiceDep):
    return await service.list_for_user(session, user.id)


@router.post("", response_model=ContextTagResponse, status_code=status.HTTP_201_CREATED)
async def create_context_tag(
    payload: CreateContextTag, session: DbSession, user: CurrentUser, service: ContextTagServiceDep
):
    return await service.create(session, user.id, payload)


@router.patch("/{behavior_context_tag_id}", response_model=ContextTagResponse)
async def update_context_tag(
    behavior_context_tag_id: uuid.UUID,
    payload: UpdateContextTag,
    session: DbSession,
    user: CurrentUser,
    service: ContextTagServiceDep,
):
    return await service.update(session, user.id, behavior_context_tag_id, payload)


@router.delete("/{behavior_context_tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context_tag(
    behavior_context_tag_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    service: ContextTagServiceDep,
):
    await service.delete(session, user.id, behavior_context_tag_id)