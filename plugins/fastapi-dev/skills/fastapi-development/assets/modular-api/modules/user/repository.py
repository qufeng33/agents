"""用户模块 - 数据访问层"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


class UserRepository:
    """用户数据访问层

    注意：事务由 get_db() 依赖自动管理，Repository 只用 flush/refresh
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.scalar(select(User).where(User.email == email))
        return result

    async def list(self, skip: int = 0, limit: int = 20) -> tuple[list[User], int]:
        total = await self.db.scalar(select(func.count(User.id))) or 0
        result = await self.db.execute(
            select(User).offset(skip).limit(limit).order_by(User.id)
        )
        items = list(result.scalars().all())
        return items, total

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.flush()
