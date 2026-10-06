import asyncio
import os
import pathlib
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("CLERK_ISSUER", "https://test.invalid")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("CLERK_ALLOWED_ORIGINS", "[]")


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = [
        line
        for line in (pathlib.Path(__file__).resolve().parents[1] / ".env").read_text().splitlines()
        if line.startswith("DATABASE_URL=")
    ][0].split("=", 1)[1].strip().strip('"').strip("'")
    return re.sub(r"/([^/?]+)(\?|$)", r"/lifetracker_test\2", url)


TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

_TRUNCATE = (
    "TRUNCATE task_context_tag_map, tasks, behavior_context_tag_map, behaviors, "
    "activity_labels, behavior_context_tags, users RESTART IDENTITY CASCADE"
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    backend_root = pathlib.Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stderr}")

    created = create_async_engine(TEST_DATABASE_URL)
    async with created.begin() as connection:
        await connection.execute(text(_TRUNCATE))
    await created.dispose()
    return create_async_engine(TEST_DATABASE_URL)


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session
        await db_session.rollback()
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE))


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> uuid.UUID:
    from app.models.user import User

    row = User(clerk_user_id=f"user_{uuid.uuid4().hex}", first_name="Test")
    session.add(row)
    await session.commit()
    return row.id


@pytest_asyncio.fixture
async def other_user(session: AsyncSession) -> uuid.UUID:
    from app.models.user import User

    row = User(clerk_user_id=f"other_{uuid.uuid4().hex}", first_name="Other")
    session.add(row)
    await session.commit()
    return row.id


@pytest_asyncio.fixture
async def behavior_service():
    from app.repositories.activity_label_repository import ActivityLabelRepository
    from app.repositories.behavior_repository import BehaviorRepository
    from app.repositories.context_tag_repository import ContextTagRepository
    from app.services.behavior_service import BehaviorService

    return BehaviorService(
        BehaviorRepository(), ActivityLabelRepository(), ContextTagRepository()
    )


@pytest_asyncio.fixture
async def task_service():
    from app.repositories.activity_label_repository import ActivityLabelRepository
    from app.repositories.context_tag_repository import ContextTagRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.task_service import TaskService

    return TaskService(
        TaskRepository(), ActivityLabelRepository(), ContextTagRepository()
    )


@pytest_asyncio.fixture
async def task_analysis_service():
    from app.repositories.behavior_repository import BehaviorRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.task_analysis_service import TaskAnalysisService

    return TaskAnalysisService(TaskRepository(), BehaviorRepository())


@pytest_asyncio.fixture
async def analytics_service():
    from app.repositories.behavior_repository import BehaviorRepository
    from app.repositories.task_repository import TaskRepository
    from app.services.analytics_service import AnalyticsService
    from app.services.task_analysis_service import TaskAnalysisService

    return AnalyticsService(
        BehaviorRepository(), TaskAnalysisService(TaskRepository(), BehaviorRepository())
    )


@pytest_asyncio.fixture
def pattern_detection_service():
    from app.repositories.behavior_repository import BehaviorRepository
    from app.services.pattern_detection_service import PatternDetectionService

    return PatternDetectionService(BehaviorRepository())


@pytest_asyncio.fixture
async def label_service():
    from app.repositories.activity_label_repository import ActivityLabelRepository
    from app.services.activity_label_service import ActivityLabelService

    return ActivityLabelService(ActivityLabelRepository())


@pytest_asyncio.fixture
async def tag_service():
    from app.repositories.context_tag_repository import ContextTagRepository
    from app.services.context_tag_service import ContextTagService

    return ContextTagService(ContextTagRepository())


@pytest_asyncio.fixture
async def client(user: uuid.UUID) -> AsyncIterator[AsyncClient]:
    from app.api.dependencies import get_current_user
    from app.main import app

    async def fake_current_user():
        return SimpleNamespace(id=user)

    app.dependency_overrides[get_current_user] = fake_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()