"""用户模块 - 业务逻辑层"""

from uuid import UUID

from .models import User
from .repository import UserRepository
from .schemas import UserCreate, UserResponse
from .exceptions import UserNotFoundError, UsernameAlreadyExistsError
from app.core.security import hash_password


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def list(
        self,
        page: int = 0,
        page_size: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """获取用户列表"""
        users, total = await self.repository.list(page=page, page_size=page_size)
        return [UserResponse.model_validate(u) for u in users], total

    async def get(self, user_id: UUID) -> UserResponse:
        """获取单个用户"""
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserResponse.model_validate(user)

    async def create(self, user_in: UserCreate) -> UserResponse:
        """创建用户"""
        existing = await self.repository.get_by_username(
            user_in.username, include_deleted=True
        )
        if existing:
            raise UsernameAlreadyExistsError(user_in.username)

        user = User(
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        user = await self.repository.create(user)
        return UserResponse.model_validate(user)

    async def delete(self, user_id: UUID) -> None:
        """删除用户"""
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        await self.repository.delete(user)
