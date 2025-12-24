"""用户模块 - 依赖注入"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from .repository import UserRepository
from .service import UserService


def get_user_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository)
