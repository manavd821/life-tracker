from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.interfaces.user_repository import UserRepositoryInterface
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_user_repository(session: DbSession) -> UserRepositoryInterface:
    return UserRepository(session)


UserRepositoryDep = Annotated[UserRepositoryInterface, Depends(get_user_repository)]


def get_user_service(repository: UserRepositoryDep) -> UserService:
    return UserService(repository)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
