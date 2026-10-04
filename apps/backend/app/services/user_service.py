import logging

from app.models import User
from app.repositories.interfaces.user_repository import UserRepositoryInterface
from app.schemas.user import ClerkUser

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, repository: UserRepositoryInterface) -> None:
        self._repository = repository

    async def create_user_from_clerk(self, clerk_user: ClerkUser) -> tuple[User, bool]:
        existing = await self._repository.get_by_clerk_user_id(clerk_user.id)
        if existing is not None:
            return existing, False

        user, created = await self._repository.create_if_absent(clerk_user)
        if created:
            logger.info(f"Created user {user.id} for Clerk user {clerk_user.id}")

        return user, created
