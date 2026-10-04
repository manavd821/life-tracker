import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError
from svix.webhooks import Webhook, WebhookVerificationError

from app.api.dependencies import UserServiceDep
from app.core.config import get_settings
from app.schemas.user import ClerkUser, ClerkWebhookEvent

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/clerk")
async def clerk_webhook(
    request: Request, user_service: UserServiceDep
) -> dict[str, str]:
    body = await request.body()
    settings = get_settings()
    try:
        Webhook(settings.CLERK_WEBHOOK_SECRET).verify(body, dict(request.headers))
    except WebhookVerificationError:
        logger.warning("Rejected Clerk webhook with an invalid signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    try:
        event = ClerkWebhookEvent.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed Clerk webhook payload",
        ) from exc

    if event.type != "user.created":
        logger.info(f"Ignoring unsupported Clerk event {event.type}")
        return {"status": "ignored"}

    try:
        clerk_user = ClerkUser.model_validate(event.data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed Clerk user payload",
        ) from exc

    await user_service.create_user_from_clerk(clerk_user)
    return {"status": "ok"}
