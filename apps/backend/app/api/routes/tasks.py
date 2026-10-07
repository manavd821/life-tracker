import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.dependencies import (
    CurrentUser,
    DbSession,
    TaskAnalysisServiceDep,
    TaskServiceDep,
)
from app.core.day import day_window
from app.schemas.task import (
    CreateTask,
    TaskAnalysis,
    TaskAnalysisDetail,
    TaskResponse,
    UpdateTask,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    session: DbSession,
    user: CurrentUser,
    service: TaskServiceDep,
    date_: date | None = Query(default=None, alias="date"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    return await service.list_for_day(session, user.id, date_, tz_offset_minutes)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: CreateTask, session: DbSession, user: CurrentUser, service: TaskServiceDep
):
    return await service.create(session, user.id, payload)


@router.get("/analysis", response_model=list[TaskAnalysis])
async def list_task_analysis(
    session: DbSession,
    user: CurrentUser,
    analysis: TaskAnalysisServiceDep,
    date_: date | None = Query(default=None, alias="date"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    if date_ is None:
        return await analysis.analyze_many_for_user(session, user.id)
    day_start, day_end = day_window(date_, tz_offset_minutes)
    return await analysis.analyze_tasks_in_window(session, user.id, day_start, day_end)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID, session: DbSession, user: CurrentUser, service: TaskServiceDep
):
    return await service.get(session, user.id, task_id)


@router.get("/{task_id}/analysis", response_model=TaskAnalysisDetail)
async def get_task_analysis(
    task_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
    analysis: TaskAnalysisServiceDep,
):
    return await analysis.analyze(session, user.id, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: UpdateTask,
    session: DbSession,
    user: CurrentUser,
    service: TaskServiceDep,
):
    return await service.update(session, user.id, task_id, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID, session: DbSession, user: CurrentUser, service: TaskServiceDep
):
    await service.delete(session, user.id, task_id)