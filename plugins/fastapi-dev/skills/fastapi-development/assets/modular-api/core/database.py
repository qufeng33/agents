"""数据库配置 - 增强型基类"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, MetaData, Select
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_utils import uuid7

from app.config import get_settings

settings = get_settings()

# 命名约定（Alembic 自动生成迁移友好）
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def utc_now() -> datetime:
    """返回当前 UTC 时间（aware datetime）"""
    return datetime.now(timezone.utc)


class Base(AsyncAttrs, DeclarativeBase):
    """
    增强型 ORM 基类

    特性：
    - UUIDv7 主键（时间有序，分布式友好）
    - 自动时间戳（created_at, updated_at）
    - 软删除支持（deleted_at）
    - 时区感知（所有时间 UTC）
    """

    metadata = MetaData(naming_convention=convention)

    # UUIDv7 主键
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)

    # 时间戳（带时区，应用层 UTC）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    # 软删除
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """是否已软删除"""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """标记为软删除"""
        self.deleted_at = utc_now()

    def restore(self) -> None:
        """恢复软删除"""
        self.deleted_at = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（排除内部属性）"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class SimpleBase(DeclarativeBase):
    """简化基类：仅 UUIDv7 主键，无软删除和时间戳"""

    metadata = MetaData(naming_convention=convention)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)


def filter_active[T: Base](stmt: Select[tuple[T]]) -> Select[tuple[T]]:
    """过滤已删除记录的通用方法"""
    entity = stmt.column_descriptions[0]["entity"]
    return stmt.where(entity.deleted_at.is_(None))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话依赖，自动管理事务"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """初始化数据库（仅开发环境创建表）"""
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """关闭连接池"""
    await engine.dispose()
