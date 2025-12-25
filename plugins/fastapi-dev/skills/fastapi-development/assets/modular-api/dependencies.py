"""全局共享依赖"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# 数据库会话依赖（自动管理事务）
DBSession = Annotated[AsyncSession, Depends(get_db)]
