from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

CHAT_PATH = "/api/insights/chat"
FRIENDLY_MESSAGE = (
    "I couldn't generate a response right now. "
    "Your recorded data is still available."
)


def iso(hour: int, minute: int = 0) -> str:
    return datetime(2026, 10, 4, hour, minute, tzinfo=timezone.utc).isoformat()


class FakeProvider:
    """Stands in for Gemini so tests never call the real API."""

    def __init__(self, reply: str = "Grounded answer.", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.system_prompts: list[str] = []
        self.prompts: list[str] = []

    async def complete(self, *, system_prompt: str, prompt: str) -> str:
        self.system_prompts.append(system_prompt)
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest_asyncio.fixture
async def chat_client(client, fake_provider):
    from app.api.dependencies import get_ai_provider
    from app.main import app

    app.dependency_overrides[get_ai_provider] = lambda: fake_provider
    yield client
    app.dependency_overrides.pop(get_ai_provider, None)


@pytest.fixture
def ai_context_builder():
    from app.repositories.behavior_repository import BehaviorRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.ai_context_builder import AIContextBuilder
    from app.services.analytics_service import AnalyticsService
    from app.services.pattern_detection_service import PatternDetectionService
    from app.services.task_analysis_service import TaskAnalysisService

    task_analysis = TaskAnalysisService(TaskRepository(), BehaviorRepository())
    return AIContextBuilder(
        AnalyticsService(BehaviorRepository(), task_analysis),
        task_analysis,
        TaskRepository(),
        PatternDetectionService(BehaviorRepository()),
    )


async def test_chat_requires_authentication():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        response = await anon.post(CHAT_PATH, json={"message": "hello", "date": "2026-10-04"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_chat_context_is_scoped_to_the_authenticated_user(
    chat_client, session, user, other_user, ai_context_builder
):
    label = (
        await chat_client.post(
            "/api/activity-labels",
            json={"primary_category": "Study", "activity_label": "DSA"},
        )
    ).json()
    await chat_client.post(
        "/api/behaviors",
        json={
            "start_time": iso(9),
            "end_time": iso(11),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )
    await chat_client.post(
        "/api/tasks",
        json={
            "title": "DSA Preparation",
            "start_time": iso(9),
            "end_time": iso(12),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )

    own = await ai_context_builder.build(session, user, date(2026, 10, 4))
    foreign = await ai_context_builder.build(session, other_user, date(2026, 10, 4))

    assert own.analytics.tracked_minutes == 120
    assert [task.title for task in own.tasks] == ["DSA Preparation"]

    # The other user's context must never contain the first user's data.
    assert foreign.analytics.tracked_minutes == 0
    assert foreign.analytics.behavior_count == 0
    assert foreign.tasks == []
    assert foreign.analytics.task_totals.count == 0


async def test_chat_prompt_contains_analytics_and_task_analysis(
    chat_client, fake_provider
):
    label = (
        await chat_client.post(
            "/api/activity-labels",
            json={"primary_category": "Study", "activity_label": "DSA"},
        )
    ).json()
    await chat_client.post(
        "/api/behaviors",
        json={
            "start_time": iso(9),
            "end_time": iso(11),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )
    await chat_client.post(
        "/api/tasks",
        json={
            "title": "DSA Preparation",
            "start_time": iso(9),
            "end_time": iso(12),
            "primary_category": "Study",
            "activity_label_id": label["activity_label_id"],
        },
    )

    response = await chat_client.post(
        CHAT_PATH,
        json={"message": "Why was my study completion low?", "date": "2026-10-04"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reply"] == "Grounded answer."
    assert body["date"] == "2026-10-04"

    prompt = fake_provider.prompts[-1]
    assert "<life_tracker_context>" in prompt
    assert "Tracked: 120 minutes" in prompt
    assert "Study/DSA 120 min" in prompt
    assert '"DSA Preparation"' in prompt
    # Completion comes from TaskAnalysisService, not from the LLM.
    assert "completion 66.67%" in prompt
    assert "Why was my study completion low?" in prompt
    assert "Life Tracker AI assistant" in fake_provider.system_prompts[-1]


async def test_chat_prompt_contains_detected_patterns(chat_client, fake_provider):
    for offset in range(12):
        category = "Study" if offset % 2 == 0 else "Entertainment"
        await chat_client.post(
            "/api/behaviors",
            json={
                "start_time": iso(9 + offset),
                "end_time": iso(10 + offset),
                "primary_category": category,
            },
        )

    response = await chat_client.post(
        CHAT_PATH,
        json={"message": "What patterns did you notice?", "date": "2026-10-04"},
    )

    assert response.status_code == 200, response.text
    prompt = fake_provider.prompts[-1]
    assert "category_transition: Study -> Entertainment" in prompt
    assert "6 transition(s)" in prompt


async def test_chat_passes_recent_history_and_truncates_old_messages(
    chat_client, fake_provider
):
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"turn-{index}"}
        for index in range(20)
    ]

    response = await chat_client.post(
        CHAT_PATH,
        json={"message": "latest question", "date": "2026-10-04", "history": history},
    )

    assert response.status_code == 200, response.text
    prompt = fake_provider.prompts[-1]
    assert "<conversation>" in prompt
    assert "turn-19" in prompt
    assert "latest question" in prompt
    # Only the most recent messages are sent to the model.
    assert "turn-0" not in prompt
    assert "turn-9" not in prompt


async def test_chat_empty_day_context_reports_nothing_recorded(
    chat_client, fake_provider
):
    response = await chat_client.post(
        CHAT_PATH,
        json={"message": "What patterns did you notice?", "date": "2026-10-04"},
    )

    assert response.status_code == 200, response.text
    prompt = fake_provider.prompts[-1]
    assert "Tracked: 0 minutes" in prompt
    assert "none recorded" in prompt
    assert "(no tasks scheduled for this date)" in prompt
    assert "(no patterns detected for this date)" in prompt


async def test_chat_provider_failure_returns_friendly_error(chat_client, fake_provider):
    fake_provider.error = RuntimeError("boom: internal details sk-secret-123")

    response = await chat_client.post(
        CHAT_PATH, json={"message": "Why?", "date": "2026-10-04"}
    )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "chat_unavailable"
    assert error["message"] == FRIENDLY_MESSAGE
    assert "sk-secret-123" not in response.text


async def test_chat_invalid_provider_response_is_handled(chat_client, fake_provider):
    fake_provider.reply = "   "

    response = await chat_client.post(
        CHAT_PATH, json={"message": "Why?", "date": "2026-10-04"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "chat_unavailable"
    assert response.json()["error"]["message"] == FRIENDLY_MESSAGE


async def test_chat_api_key_is_never_returned_to_the_client(chat_client, fake_provider):
    from app.core.errors import AIUnavailable

    fake_provider.error = AIUnavailable("GEMINI_API_KEY=sk-test-key-987 rejected by upstream")

    response = await chat_client.post(
        CHAT_PATH, json={"message": "Why?", "date": "2026-10-04"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["message"] == FRIENDLY_MESSAGE
    assert "sk-test-key-987" not in response.text
    assert "GEMINI_API_KEY" not in response.text


async def test_chat_rejects_empty_message(chat_client):
    response = await chat_client.post(
        CHAT_PATH, json={"message": "", "date": "2026-10-04"}
    )
    assert response.status_code == 422
