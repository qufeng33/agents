"""用户服务"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import filter_active
from app.core.error_codes import ErrorCode
from app.core.security import hash_password
from app.core.exceptions import ConflictError, NotFoundError
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse


class UserService:
    """
    用户业务逻辑层

    注意：
    - 事务由 get_db() 依赖自动管理，Service 层不调用 commit
    - 默认查询排除已软删除的记录
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_list(
        self,
        page: int = 0,
        page_size: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """分页查询用户列表（page 从 0 开始，排除已删除）"""
        count_stmt = select(func.count()).select_from(
            filter_active(select(User)).subquery()
        )
        total = await self.db.scalar(count_stmt) or 0

        offset = page * page_size
        stmt = filter_active(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        users = result.scalars().all()
        return [UserResponse.model_validate(u) for u in users], total

    async def get_one(self, user_id: UUID) -> UserResponse:
        """获取单个用户（排除已删除）"""
        stmt = filter_active(select(User).where(User.id == user_id))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(
                code=ErrorCode.USER_NOT_FOUND,
                message="用户不存在",
                detail={"user_id": str(user_id)},
            )
        return UserResponse.model_validate(user)

    async def create(self, user_in: UserCreate) -> UserResponse:
        """创建用户"""
        # 检查用户名是否已存在（全局唯一，包含已删除）
        stmt = select(User).where(User.username == user_in.username)
        existing = await self.db.scalar(stmt)
        if existing:
            raise ConflictError(
                code=ErrorCode.USERNAME_ALREADY_EXISTS,
                message="用户名已存在",
                detail={"username": user_in.username},
            )

        user = User(
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def delete(self, user_id: UUID) -> None:
        """软删除用户"""
        stmt = filter_active(select(User).where(User.id == user_id))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(
                code=ErrorCode.USER_NOT_FOUND,
                message="用户不存在",
                detail={"user_id": str(user_id)},
            )

        user.soft_delete()
        await self.db.flush()
