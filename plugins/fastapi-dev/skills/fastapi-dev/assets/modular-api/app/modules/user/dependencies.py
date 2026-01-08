"""用户模块 - 依赖注入"""

from typing import Annotated

from fastapi import Depends

from app.dependencies import DBSession
from .repository import UserRepository
from .service import UserService


def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository)


# 类型别名，简化路由中的依赖声明
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
