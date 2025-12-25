"""用户服务"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.exceptions import NotFoundError, ConflictError
from app.models.user import User
from app.schemas.user import UserCreate


class UserService:
    """用户业务逻辑层

    注意：事务由 get_db() 依赖自动管理，Service 层不调用 commit
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, skip: int = 0, limit: int = 20) -> dict:
        total = await self.db.scalar(select(func.count(User.id)))
        result = await self.db.execute(
            select(User).offset(skip).limit(limit).order_by(User.id)
        )
        items = result.scalars().all()
        return {"items": items, "total": total or 0}

    async def get(self, user_id: int) -> User:
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        return user

    async def create(self, user_in: UserCreate) -> User:
        existing = await self.db.scalar(
            select(User).where(User.email == user_in.email)
        )
        if existing:
            raise ConflictError(f"Email {user_in.email} already registered")

        user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: int) -> None:
        user = await self.get(user_id)
        await self.db.delete(user)
        await self.db.flush()
