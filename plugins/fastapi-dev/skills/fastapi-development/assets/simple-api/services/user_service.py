"""用户服务"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.security import hash_password
from app.exceptions import NotFoundError, ConflictError
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse


class UserService:
    """用户业务逻辑层

    注意：事务由 get_db() 依赖自动管理，Service 层不调用 commit
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        page: int = 0,
        page_size: int = 20,
    ) -> tuple[list[UserResponse], int]:
        """分页查询用户列表（page 从 0 开始）"""
        total = await self.db.scalar(select(func.count(User.id))) or 0
        offset = page * page_size
        result = await self.db.execute(
            select(User).offset(offset).limit(page_size).order_by(User.id)
        )
        users = result.scalars().all()
        return [UserResponse.model_validate(u) for u in users], total

    async def get(self, user_id: int) -> UserResponse:
        """获取单个用户"""
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError(
                code=ErrorCode.USER_NOT_FOUND,
                message="用户不存在",
                detail={"user_id": user_id},
            )
        return UserResponse.model_validate(user)

    async def create(self, user_in: UserCreate) -> UserResponse:
        """创建用户"""
        existing = await self.db.scalar(
            select(User).where(User.email == user_in.email)
        )
        if existing:
            raise ConflictError(
                code=ErrorCode.EMAIL_ALREADY_EXISTS,
                message="邮箱已注册",
                detail={"email": user_in.email},
            )

        user = User(
            email=user_in.email,
            username=user_in.username,
            hashed_password=hash_password(user_in.password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return UserResponse.model_validate(user)

    async def delete(self, user_id: int) -> None:
        """删除用户"""
        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError(
                code=ErrorCode.USER_NOT_FOUND,
                message="用户不存在",
                detail={"user_id": user_id},
            )
        await self.db.delete(user)
        await self.db.flush()
