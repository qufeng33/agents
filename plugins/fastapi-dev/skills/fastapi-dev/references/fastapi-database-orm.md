# FastAPI ORM 基类与软删除
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 统一基类，减少重复字段
- 软删除与审计字段有清晰边界
- 时间统一使用 UTC aware datetime
- 主键策略全项目一致
- Repository 封装查询规则

## 最佳实践
1. 使用 UUIDv7 作为主键（可排序）
2. `created_at/updated_at` 自动维护
3. 软删除优先于物理删除
4. 软删除过滤逻辑集中封装
5. 审计字段交由审计模块填充

## 目录
- `ORM 基类增强`
- `审计字段设计`
- `软删除`
- `不使用增强基类的场景`
- `相关说明`

---

## ORM 基类增强

推荐使用增强型基类，统一处理主键、时间戳、软删除等通用字段。

### 依赖安装

```bash
uv add uuid-utils
```

### 基类示例

```python
# core/database.py
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_utils import uuid7

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
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

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)

    def soft_delete(self) -> None:
        self.deleted_at = utc_now()

    def restore(self) -> None:
        self.deleted_at = None
```

> 额外方法（如 `to_dict`）可按需添加，避免基类过度膨胀。

### 设计说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDv7 | 可排序、分布式友好 |
| `created_at` | datetime (tz) | UTC 创建时间 |
| `updated_at` | datetime (tz) | UTC 更新时间 |
| `deleted_at` | datetime (tz) | 软删除时间 |

> 如项目已有自增主键，请保持全项目一致，避免混用。

### 时间处理约定

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)  # 推荐：aware datetime
```

---

## 审计字段设计

审计字段用于记录创建/更新人，自动填充逻辑见 [审计日志](./fastapi-audit.md)。

```python
# core/audit.py
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"),
        default=None,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"),
        default=None,
        onupdate=None,
    )
```

---

## 软删除

### 查询封装

```python
from sqlalchemy import Select


def filter_active[T: Base](stmt: Select[tuple[T]]) -> Select[tuple[T]]:
    entity = stmt.column_descriptions[0]["entity"]
    return stmt.where(entity.deleted_at.is_(None))
```

聚合查询统一使用 `filter_active()` 子查询：

```python
from sqlalchemy import func, select

# 统计活跃记录数
count_stmt = select(func.count()).select_from(
    filter_active(select(User)).subquery()
)
total = await db.scalar(count_stmt) or 0
```

### Repository 集成

```python
from uuid import UUID
from sqlalchemy import select

from app.core.database import filter_active


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = filter_active(select(User).where(User.id == user_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

### 唯一约束与软删除

软删除后，原记录的唯一字段仍占用，使用全局唯一索引：

```python
from sqlalchemy import Index, String


class User(Base):
    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        Index("uq_user_username", "username", unique=True),
    )
```

> 若需“可复用唯一值”，需引入条件索引或额外状态字段。

---

## 不使用增强基类的场景

某些表不需要软删除或审计字段时，可定义简化基类：

```python
class SimpleBase(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
```

---

## 相关说明

- [审计日志](./fastapi-audit.md)
- [数据库配置](./fastapi-database-setup.md)
- [数据库模式](./fastapi-database-patterns.md)
