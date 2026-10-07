from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AIUnavailable
from app.schemas.ai_chat import ChatContext, ChatMessage, ChatRequest, ChatResponse
from app.services.ai_context_builder import AIContextBuilder, render_chat_context
from app.services.ai_provider import AIProvider

logger = logging.getLogger(__name__)

CHAT_UNAVAILABLE_MESSAGE = (
    "I couldn't generate a response right now. "
    "Your recorded data is still available."
)

# Only the most recent messages are sent so prompts stay small.
MAX_HISTORY_MESSAGES = 10

CHAT_SYSTEM_PROMPT = """You are the Life Tracker AI assistant for a deterministic behavior tracking app.

You receive a verified <life_tracker_context> block built by the app's analytics, task analysis, and pattern detection engines, a short <conversation> history, and the <user_question>.

RULES:

1. DATA RULE
Only make factual claims that are supported by the provided context. The context is the single source of truth for anything about the user.

2. NO FABRICATION
If the context does not contain enough information to answer, say so plainly. Do not invent behaviors, durations, tasks, completion rates, emotions, causes, locations, or patterns. Never guess a number that is not in the context.

3. UNACCOUNTED TIME
Unaccounted time is unknown time. Never describe it as rest, entertainment, sleep, phone usage, distraction, laziness, or anything else unless the context explicitly states it.

4. CAUSALITY
Never claim causation from observational data.
Bad: "The library makes you study better."
Good: "Your recorded CN sessions have been longer in the library."

5. PERIOD SCOPE
The context covers one selected day. If asked about a broader period (for example a week or month) that is not in the context, say that only the selected day is available instead of inventing aggregates.

6. COACHING
When appropriate, frame suggestions as experiments rather than prescriptions, for example "You could experiment with scheduling longer CN sessions in the library."

7. CONVERSATION
Answer the user's actual question first. Keep answers concise, then add the relevant evidence from the context. Do not dump the whole context back. Use the history only to understand follow-up questions.

8. TONE
Supportive, plain, no judgment, no moralizing about the user's time."""


def build_chat_prompt(
    context: ChatContext,
    history: list[ChatMessage],
    message: str,
) -> str:
    """Structured prompt: verified context, recent conversation, then the question."""
    conversation = (
        "\n".join(f"{entry.role}: {entry.content}" for entry in history)
        if history
        else "(no previous messages)"
    )
    return "\n".join(
        [
            render_chat_context(context),
            "",
            "<conversation>",
            conversation,
            "</conversation>",
            "",
            "<user_question>",
            message,
            "</user_question>",
        ]
    )


class ChatService:
    """Orchestrates one chat request: verified context in, grounded reply out."""

    def __init__(self, context_builder: AIContextBuilder, provider: AIProvider) -> None:
        self._context_builder = context_builder
        self._provider = provider

    async def chat(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        request: ChatRequest,
    ) -> ChatResponse:
        day = request.date or date.today()

        context = await self._context_builder.build(
            session, user_id, day, request.tz_offset_minutes
        )
        prompt = build_chat_prompt(
            context,
            request.history[-MAX_HISTORY_MESSAGES:],
            request.message,
        )

        try:
            reply = await self._provider.complete(
                system_prompt=CHAT_SYSTEM_PROMPT,
                prompt=prompt,
            )
        except AIUnavailable:
            logger.info("Chat reply unavailable for period %s", day.isoformat())
            raise AIUnavailable(CHAT_UNAVAILABLE_MESSAGE, code="chat_unavailable") from None

        reply = reply.strip()
        if not reply:
            raise AIUnavailable(CHAT_UNAVAILABLE_MESSAGE, code="chat_unavailable")

        return ChatResponse(reply=reply, date=day.isoformat())
