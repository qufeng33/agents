# FastAPI ORM 基类与软删除
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。


## ORM 基类增强

推荐使用增强型基类，统一处理主键、时间戳、软删除等通用字段。

### 依赖安装

```bash
uv add uuid-utils  # UUIDv7 生成
```

### 完整基类

```python
# core/database.py
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, MetaData, select
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_utils import uuid7

# 命名约定（Alembic 自动生成迁移友好）
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


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
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
        }
```

### 设计说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDv7 | 时间有序（可按 ID 排序即按时间排序）、分布式友好 |
| `created_at` | datetime (tz) | 创建时间，UTC，不可变 |
| `updated_at` | datetime (tz) | 更新时间，UTC，自动更新 |
| `deleted_at` | datetime (tz) | 软删除时间，NULL 表示未删除 |

> **为什么用 UUIDv7？**
> - 比 UUIDv4 有序，索引性能更好
> - 比自增 ID 更适合分布式系统
> - 前 48 位是毫秒时间戳，天然可排序
>
> 迁移/重构项目可能仍沿用自增主键类型。此时请保持全项目 ID 类型一致。

### 时间处理约定

```python
# 正确：应用层始终使用 aware datetime
from datetime import datetime, timezone

now = datetime.now(timezone.utc)

# 错误：naive datetime
now = datetime.now()  # 无时区信息
now = datetime.utcnow()  # 已废弃，返回 naive
```

---

## 审计字段设计

审计字段用于记录"谁创建/更新了记录"。字段设计与约束在数据库层确定，自动填充逻辑见 [审计日志](./fastapi-audit.md)。

```python
# core/audit.py
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """审计字段 Mixin"""

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"),
        default=None,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"),
        default=None,
        onupdate=None,  # 手动设置，见审计日志文档
    )
```

---

## 软删除

### 查询封装

```python
# core/database.py（续）
from sqlalchemy import Select


def filter_active[T: Base](stmt: Select[tuple[T]]) -> Select[tuple[T]]:
    """过滤已删除记录的通用方法"""
    entity = stmt.column_descriptions[0]["entity"]
    return stmt.where(entity.deleted_at.is_(None))
```

> **注意**：`filter_active()` 只适用于返回实体的查询。聚合查询请显式使用 `where(Model.deleted_at.is_(None))`。

### Repository 集成

```python
# modules/user/repository.py
from uuid import UUID
from sqlalchemy import select

from app.core.database import Base, filter_active


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """获取用户（排除已删除）"""
        stmt = filter_active(select(User).where(User.id == user_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, user: User) -> None:
        """软删除"""
        user.soft_delete()
        await self.db.flush()

    async def restore(self, user: User) -> None:
        """恢复"""
        user.restore()
        await self.db.flush()
```

### 唯一约束与软删除

软删除后，原记录的唯一字段仍然占用（不允许复用）。使用**全局唯一索引**：

```python
from sqlalchemy import Index, String


class User(Base):
    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        Index("uq_user_username", "username", unique=True),
    )
```

### 级联软删除

```python
# Service 层处理级联
class UserService:
    async def soft_delete_user(self, user_id: UUID) -> None:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        # 级联软删除用户的文章
        posts = await self.post_repo.list_by_author(user_id)
        for post in posts:
            post.soft_delete()

        user.soft_delete()
        await self.db.flush()
```

---

## 不使用增强基类的场景

某些表不需要软删除或审计字段时，可定义简化基类：

```python
class SimpleBase(DeclarativeBase):
    """简化基类：仅 UUIDv7 主键"""
    metadata = MetaData(naming_convention=convention)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)


class AuditLog(SimpleBase):
    """审计日志表：不需要软删除自己"""
    __tablename__ = "audit_log"
    # ...
```

---

## 生命周期管理

```python
# core/database.py
async def init_database() -> None:
    """初始化数据库（仅开发环境创建表）"""
    if settings.debug:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_database() -> None:
    """关闭连接池"""
    await async_engine.dispose()
```

> **在 lifespan 中调用** 详见 [应用生命周期](./fastapi-app-lifecycle.md)

---

## 相关文档

- [数据库配置](./fastapi-database-setup.md)
- [Repository 与事务](./fastapi-database-patterns.md)
- [审计日志](./fastapi-audit.md)
