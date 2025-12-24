"""共享依赖"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

# 数据库会话依赖
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
