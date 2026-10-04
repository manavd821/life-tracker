import uuid

from fastapi import APIRouter, status

from app.api.dependencies import ActivityLabelServiceDep, CurrentUser, DbSession
from app.schemas.activity_label import (
    ActivityLabelResponse,
    CreateActivityLabel,
    UpdateActivityLabel,
)

router = APIRouter(prefix="/activity-labels", tags=["activity-labels"])


@router.get("", response_model=list[ActivityLabelResponse])
async def list_activity_labels(session: DbSession, user: CurrentUser, service: ActivityLabelServiceDep):
    return await service.list_for_user(session, user.id)


@router.post("", response_model=ActivityLabelResponse, status_code=status.HTTP_201_CREATED)
async def create_activity_label(
    payload: CreateActivityLabel, session: DbSession, user: CurrentUser, service: ActivityLabelServiceDep
):
    return await service.create(session, user.id, payload)


@router.patch("/{activity_label_id}", response_model=ActivityLabelResponse)
async def update_activity_label(
    activity_label_id: uuid.UUID,
    payload: UpdateActivityLabel,
    session: DbSession,
    user: CurrentUser,
    service: ActivityLabelServiceDep,
):
    return await service.update(session, user.id, activity_label_id, payload)


@router.delete("/{activity_label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity_label(
    activity_label_id: uuid.UUID, session: DbSession, user: CurrentUser, service: ActivityLabelServiceDep
):
    await service.delete(session, user.id, activity_label_id)