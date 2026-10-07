from datetime import date
import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import (
    AIInsightServiceDep,
    ChatServiceDep,
    CurrentUser,
    DbSession,
    SettingsDep,
)
from app.core.errors import AIUnavailable, DomainError
from app.schemas.ai_insights import AIResponse
from app.schemas.ai_chat import ChatRequest, ChatResponse
from app.services.ai_chat_service import CHAT_UNAVAILABLE_MESSAGE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/daily", response_model=AIResponse)
async def daily_insights(
    session: DbSession,
    user: CurrentUser,
    service: AIInsightServiceDep,
    settings: SettingsDep,
    day: date = Query(..., alias="date"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
) -> AIResponse:
    try:
        context = await service.build_context(
            session,
            user.id,
            start_date=day,
            end_date=day,
            tz_offset_minutes=tz_offset_minutes,
        )
        return await service.generate_insights(
            context,
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    except DomainError:
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "insights_unavailable",
                    "message": "Insights are temporarily unavailable. Your behavior and analytics data are still available.",
                }
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "insights_unavailable",
                    "message": "Insights are temporarily unavailable. Your behavior and analytics data are still available.",
                }
            },
        ) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(
    session: DbSession,
    user: CurrentUser,
    service: ChatServiceDep,
    request: ChatRequest,
) -> ChatResponse:
    """Context-aware chat. The user always comes from authentication; the
    request only carries the message, the selected date, and recent history."""
    try:
        return await service.chat(session, user.id, request)
    except DomainError:
        raise
    except Exception as exc:
        logger.exception("Chat request failed")
        raise AIUnavailable(
            CHAT_UNAVAILABLE_MESSAGE, code="chat_unavailable"
        ) from exc
