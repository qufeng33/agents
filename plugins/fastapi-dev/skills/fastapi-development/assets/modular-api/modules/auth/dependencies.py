"""认证模块 - 依赖注入"""

from typing import Annotated

from fastapi import Depends

from app.modules.user.dependencies import get_user_repository
from app.modules.user.repository import UserRepository
from .service import AuthService


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(user_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
