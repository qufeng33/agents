"""数据库配置 - 增强型基类（简化版）"""

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, MetaData, Select, create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
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
    增强型 ORM 基类（简化版）

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
        """转换为字典"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


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
    """初始化数据库：验证连接"""
    from loguru import logger

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("数据库连接成功")
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}，应用将在无数据库模式下启动")


async def close_database() -> None:
    """关闭连接池"""
    await engine.dispose()
    close_sync_engine()


@lru_cache
def get_sync_engine():
    """同步引擎（仅任务/同步场景使用，需要 psycopg）"""
    return create_engine(settings.db.sync_url, pool_pre_ping=True)


def close_sync_engine() -> None:
    """释放同步引擎连接池（若已创建）"""
    if get_sync_engine.cache_info().currsize:
        get_sync_engine().dispose()
        get_sync_engine.cache_clear()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """获取同步 Session（仅任务/同步场景使用）"""
    sync_engine = get_sync_engine()
    with Session(sync_engine) as session:
        yield session
