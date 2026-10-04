from typing import Protocol

from app.models import User
from app.schemas.user import ClerkUser


class UserRepositoryInterface(Protocol):
    async def get_by_clerk_user_id(self, clerk_user_id: str) -> User | None: ...

    async def create_if_absent(self, user: ClerkUser) -> tuple[User, bool]: ...
