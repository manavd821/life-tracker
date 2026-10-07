from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import clerk_user_id_from_token
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.db.session import get_db
from app.models.user import User
from app.repositories.activity_label_repository import ActivityLabelRepository
from app.repositories.behavior_repository import BehaviorRepository
from app.repositories.context_tag_repository import ContextTagRepository
from app.repositories.interfaces.activity_label_repository import (
    ActivityLabelRepositoryInterface,
)
from app.repositories.interfaces.behavior_repository import BehaviorRepositoryInterface
from app.repositories.interfaces.context_tag_repository import (
    ContextTagRepositoryInterface,
)
from app.repositories.interfaces.task_repository import TaskRepositoryInterface
from app.repositories.interfaces.user_repository import UserRepositoryInterface
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_label_service import ActivityLabelService
from app.services.ai_chat_service import ChatService
from app.services.ai_context_builder import AIContextBuilder
from app.services.ai_insight_service import AIInsightService
from app.services.ai_provider import AIProvider, GeminiProvider
from app.services.analytics_service import AnalyticsService
from app.services.behavior_service import BehaviorService
from app.services.pattern_detection_service import PatternDetectionService
from app.services.context_tag_service import ContextTagService
from app.services.task_analysis_service import TaskAnalysisService
from app.services.task_service import TaskService
from app.services.user_service import UserService

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_user_repository(session: DbSession) -> UserRepositoryInterface:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepositoryInterface, Depends(get_user_repository)]


def get_user_service(repository: UserRepositoryDep) -> UserService:
    return UserService(repository)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_activity_label_repository() -> ActivityLabelRepositoryInterface:
    return ActivityLabelRepository()


ActivityLabelRepositoryDep = Annotated[
    ActivityLabelRepositoryInterface, Depends(get_activity_label_repository)
]


def get_context_tag_repository() -> ContextTagRepositoryInterface:
    return ContextTagRepository()


ContextTagRepositoryDep = Annotated[
    ContextTagRepositoryInterface, Depends(get_context_tag_repository)
]


def get_behavior_repository() -> BehaviorRepositoryInterface:
    return BehaviorRepository()


BehaviorRepositoryDep = Annotated[
    BehaviorRepositoryInterface, Depends(get_behavior_repository)
]


def get_behavior_service(
    behaviors: BehaviorRepositoryDep,
    activity_labels: ActivityLabelRepositoryDep,
    context_tags: ContextTagRepositoryDep,
) -> BehaviorService:
    return BehaviorService(behaviors, activity_labels, context_tags)


BehaviorServiceDep = Annotated[BehaviorService, Depends(get_behavior_service)]


def get_activity_label_service(
    labels: ActivityLabelRepositoryDep,
) -> ActivityLabelService:
    return ActivityLabelService(labels)


ActivityLabelServiceDep = Annotated[
    ActivityLabelService, Depends(get_activity_label_service)
]


def get_context_tag_service(tags: ContextTagRepositoryDep) -> ContextTagService:
    return ContextTagService(tags)


ContextTagServiceDep = Annotated[ContextTagService, Depends(get_context_tag_service)]


def get_task_repository() -> TaskRepositoryInterface:
    return TaskRepository()


TaskRepositoryDep = Annotated[TaskRepositoryInterface, Depends(get_task_repository)]


def get_task_service(
    tasks: TaskRepositoryDep,
    activity_labels: ActivityLabelRepositoryDep,
    context_tags: ContextTagRepositoryDep,
) -> TaskService:
    return TaskService(tasks, activity_labels, context_tags)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


def get_task_analysis_service(
    tasks: TaskRepositoryDep,
    behaviors: BehaviorRepositoryDep,
) -> TaskAnalysisService:
    return TaskAnalysisService(tasks, behaviors)


TaskAnalysisServiceDep = Annotated[
    TaskAnalysisService, Depends(get_task_analysis_service)
]


def get_analytics_service(
    behaviors: BehaviorRepositoryDep,
    task_analysis: TaskAnalysisServiceDep,
) -> AnalyticsService:
    return AnalyticsService(behaviors, task_analysis)


AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


def get_pattern_detection_service(
    behaviors: BehaviorRepositoryDep,
    settings: SettingsDep,
) -> PatternDetectionService:
    return PatternDetectionService(
        behaviors,
        min_transition_count=settings.PATTERN_MIN_TRANSITION_COUNT,
        min_context_sessions=settings.PATTERN_MIN_CONTEXT_SESSIONS,
    )


PatternDetectionServiceDep = Annotated[
    PatternDetectionService, Depends(get_pattern_detection_service)
]


def get_ai_insight_service(
    behaviors: BehaviorRepositoryDep,
    analytics: AnalyticsServiceDep,
    task_analysis: TaskAnalysisServiceDep,
    pattern_detection: PatternDetectionServiceDep,
) -> AIInsightService:
    return AIInsightService(
        behaviors,
        analytics,
        task_analysis,
        pattern_detection,
    )


AIInsightServiceDep = Annotated[
    AIInsightService, Depends(get_ai_insight_service)
]


def get_ai_provider(settings: SettingsDep) -> AIProvider:
    return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)


AIProviderDep = Annotated[AIProvider, Depends(get_ai_provider)]


def get_ai_context_builder(
    analytics: AnalyticsServiceDep,
    task_analysis: TaskAnalysisServiceDep,
    tasks: TaskRepositoryDep,
    pattern_detection: PatternDetectionServiceDep,
) -> AIContextBuilder:
    return AIContextBuilder(analytics, task_analysis, tasks, pattern_detection)


AIContextBuilderDep = Annotated[AIContextBuilder, Depends(get_ai_context_builder)]


def get_chat_service(
    context_builder: AIContextBuilderDep,
    provider: AIProviderDep,
) -> ChatService:
    return ChatService(context_builder, provider)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


async def get_current_user(
    session: DbSession,
    repository: UserRepositoryDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing bearer token")
    clerk_user_id = clerk_user_id_from_token(authorization.split(" ", 1)[1].strip())
    user = await repository.get_by_clerk_user_id(clerk_user_id)
    if user is None:
        raise AuthenticationError("No local user for this session")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]