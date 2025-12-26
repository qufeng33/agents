"""共享依赖"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.user_service import UserService

# 数据库会话依赖（自动管理事务）
DBSession = Annotated[AsyncSession, Depends(get_db)]


# Service 依赖
def get_user_service(db: DBSession) -> UserService:
    """创建 UserService 实例"""
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
