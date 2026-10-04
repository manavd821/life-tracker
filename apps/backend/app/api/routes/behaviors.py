import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.dependencies import BehaviorServiceDep, CurrentUser, DbSession
from app.models.user import User
from app.schemas.behavior import BehaviorResponse, CreateBehavior, UpdateBehavior
from app.schemas.timeline import TimelineResponse

router = APIRouter(prefix="/behaviors", tags=["behaviors"])


@router.post("", response_model=BehaviorResponse, status_code=status.HTTP_201_CREATED)
async def create_behavior(
    payload: CreateBehavior, session: DbSession, user: CurrentUser, service: BehaviorServiceDep
) -> BehaviorResponse:
    return await service.create(session, user.id, payload)


@router.get("", response_model=TimelineResponse)
async def get_timeline(
    session: DbSession,
    user: CurrentUser,
    service: BehaviorServiceDep,
    date_: date = Query(alias="date"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
) -> TimelineResponse:
    return await service.timeline(session, user.id, date_, tz_offset_minutes)


@router.get("/{behavior_id}", response_model=BehaviorResponse)
async def get_behavior(
    behavior_id: uuid.UUID, session: DbSession, user: CurrentUser, service: BehaviorServiceDep
) -> BehaviorResponse:
    return await service.get(session, user.id, behavior_id)


@router.patch("/{behavior_id}", response_model=BehaviorResponse)
async def update_behavior(
    behavior_id: uuid.UUID,
    payload: UpdateBehavior,
    session: DbSession,
    user: CurrentUser,
    service: BehaviorServiceDep,
) -> BehaviorResponse:
    return await service.update(session, user.id, behavior_id, payload)


@router.delete("/{behavior_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_behavior(
    behavior_id: uuid.UUID, session: DbSession, user: CurrentUser, service: BehaviorServiceDep
) -> None:
    await service.delete(session, user.id, behavior_id)