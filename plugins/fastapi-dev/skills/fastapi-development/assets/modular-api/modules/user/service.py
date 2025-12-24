"""用户模块 - 业务逻辑层"""

from .models import User
from .repository import UserRepository
from .schemas import UserCreate
from .exceptions import UserNotFoundError, UserAlreadyExistsError
from app.core.security import hash_password


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def list(self, skip: int = 0, limit: int = 20) -> dict:
        items, total = await self.repository.list(skip=skip, limit=limit)
        return {"items": items, "total": total}

    async def get(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def create(self, user_in: UserCreate) -> User:
        existing = await self.repository.get_by_email(user_in.email)
        if existing:
            raise UserAlreadyExistsError(user_in.email)

        user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        return await self.repository.create(user)

    async def delete(self, user_id: int) -> None:
        user = await self.get(user_id)
        await self.repository.delete(user)
