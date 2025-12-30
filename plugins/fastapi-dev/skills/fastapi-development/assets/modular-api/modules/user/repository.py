"""用户模块 - 数据访问层"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import filter_active

from .models import User


class UserRepository:
    """
    用户数据访问层

    注意：
    - 事务由 get_db() 依赖自动管理，Repository 只用 flush/refresh
    - 默认查询排除已软删除的记录
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ============================================================
    # 查询方法（默认排除已删除）
    # ============================================================

    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据 ID 获取用户（排除已删除）"""
        stmt = filter_active(select(User).where(User.id == user_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(
        self, username: str, *, include_deleted: bool = False
    ) -> User | None:
        """根据用户名获取用户"""
        stmt = select(User).where(User.username == username)
        if not include_deleted:
            stmt = filter_active(stmt)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, page: int = 0, page_size: int = 20) -> tuple[list[User], int]:
        """分页查询用户列表（page 从 0 开始，排除已删除）"""
        # 统计总数
        count_stmt = select(func.count(User.id)).where(User.deleted_at.is_(None))
        total = await self.db.scalar(count_stmt) or 0

        # 分页查询
        offset = page * page_size
        stmt = filter_active(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    # ============================================================
    # 包含已删除的查询（仅管理员使用）
    # ============================================================

    async def get_by_id_including_deleted(self, user_id: UUID) -> User | None:
        """根据 ID 获取用户（包含已删除）"""
        return await self.db.get(User, user_id)

    async def list_deleted(
        self, page: int = 0, page_size: int = 20
    ) -> tuple[list[User], int]:
        """查询已删除的用户"""
        count_stmt = select(func.count(User.id)).where(User.deleted_at.isnot(None))
        total = await self.db.scalar(count_stmt) or 0

        offset = page * page_size
        stmt = (
            select(User)
            .where(User.deleted_at.isnot(None))
            .order_by(User.deleted_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    # ============================================================
    # 写操作
    # ============================================================

    async def create(self, user: User) -> User:
        """创建用户"""
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """更新用户"""
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def soft_delete(self, user: User) -> None:
        """软删除用户"""
        user.soft_delete()
        await self.db.flush()

    async def delete(self, user: User) -> None:
        """删除用户（默认软删除）"""
        await self.soft_delete(user)

    async def restore(self, user: User) -> None:
        """恢复软删除的用户"""
        user.restore()
        await self.db.flush()

    async def hard_delete(self, user: User) -> None:
        """物理删除用户（谨慎使用）"""
        await self.db.delete(user)
        await self.db.flush()
