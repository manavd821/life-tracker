from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.user import ClerkUser


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_clerk_user_id(self, clerk_user_id: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        return result.scalar_one_or_none()

    async def create_if_absent(self, user: ClerkUser) -> tuple[User, bool]:
        result = await self._session.execute(
            pg_insert(User)
            .values(
                clerk_user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
            )
            .on_conflict_do_nothing(index_elements=[User.clerk_user_id])
            .returning(User)
        )
        created = result.scalar_one_or_none()
        await self._session.commit()

        if created is not None:
            return created, True

        return await self.get_by_clerk_user_id(user.id), False
