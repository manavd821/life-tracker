from datetime import date

from fastapi import APIRouter, Query

from app.api.dependencies import AnalyticsServiceDep, CurrentUser, DbSession
from app.schemas.analytics import DailyAnalytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/daily", response_model=DailyAnalytics)
async def daily_analytics(
    session: DbSession,
    user: CurrentUser,
    service: AnalyticsServiceDep,
    day: date = Query(..., alias="date"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    return await service.daily(session, user.id, day, tz_offset_minutes)