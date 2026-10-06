from datetime import date

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession, PatternDetectionServiceDep
from app.schemas.patterns import ContextPatterns, TransitionPatterns

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/transitions", response_model=TransitionPatterns)
async def transition_patterns(
    session: DbSession,
    user: CurrentUser,
    service: PatternDetectionServiceDep,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
) -> TransitionPatterns:
    return await service.transitions(
        session, user.id, start_date, end_date, tz_offset_minutes
    )


@router.get("/context", response_model=ContextPatterns)
async def context_patterns(
    session: DbSession,
    user: CurrentUser,
    service: PatternDetectionServiceDep,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
) -> ContextPatterns:
    return await service.context(
        session, user.id, start_date, end_date, tz_offset_minutes
    )
