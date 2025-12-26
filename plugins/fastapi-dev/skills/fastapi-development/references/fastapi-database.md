# FastAPI 数据库集成

> SQLAlchemy 2.0 异步优先 | asyncpg | Alembic

## 核心配置

### 异步引擎与 Session

```python
# core/database.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 异步驱动：postgresql+asyncpg:// | mysql+aiomysql:// | sqlite+aiosqlite://
async_engine = create_async_engine(
    settings.db.url,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # 悲观连接检测
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 推荐：避免 commit 后隐式查询
    autoflush=False,         # 显式控制 flush 时机
)


class Base(DeclarativeBase):
    pass
```

---

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
> ⚠️ 迁移/重构项目可能仍沿用自增主键类型。此时请保持全项目 ID 类型一致，示例中的 UUIDv7 可替换为现有类型。

### 时间处理约定

```python
# ✅ 正确：应用层始终使用 aware datetime
from datetime import datetime, timezone

now = datetime.now(timezone.utc)

# ❌ 错误：naive datetime
now = datetime.now()  # 无时区信息
now = datetime.utcnow()  # 已废弃，返回 naive
```

数据库配置（如 `postgres.conf` 的 `timezone`）不影响存储结果，因为应用层始终传入带时区的 UTC 时间。

---

## 审计字段设计

审计字段用于记录“谁创建/更新了记录”。字段设计与约束在数据库层确定，自动填充逻辑见 [审计日志](./fastapi-audit.md)。

```python
# core/audit.py
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """审计字段 Mixin"""

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        default=None,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
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
    # 获取查询的主实体
    entity = stmt.column_descriptions[0]["entity"]
    return stmt.where(entity.deleted_at.is_(None))
```

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

    async def get_by_id_including_deleted(self, user_id: UUID) -> User | None:
        """获取用户（包含已删除）- 仅管理员使用"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_active(self, page: int = 0, page_size: int = 20) -> list[User]:
        """列表查询（排除已删除）"""
        stmt = filter_active(
            select(User)
            .order_by(User.created_at.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

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

软删除后，原记录的唯一字段（如 email）仍然占用，导致无法重新注册。

**解决方案：部分唯一索引**（PostgreSQL）

```python
from sqlalchemy import Index


class User(Base):
    __tablename__ = "user"

    email: Mapped[str] = mapped_column(unique=False)  # 不用列级 unique

    __table_args__ = (
        # 只对未删除的记录强制唯一
        Index(
            "uq_user_email_active",
            "email",
            unique=True,
            postgresql_where=deleted_at.is_(None),  # type: ignore
        ),
    )
```

**Alembic 迁移**：

```python
# migrations/versions/xxx_add_partial_unique_index.py
from alembic import op

def upgrade():
    op.create_index(
        "uq_user_email_active",
        "user",
        ["email"],
        unique=True,
        postgresql_where="deleted_at IS NULL",
    )

def downgrade():
    op.drop_index("uq_user_email_active", table_name="user")
```

> **MySQL 不支持部分索引**，替代方案：软删除时将 email 改为 `email_deleted_{timestamp}`。

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

### 生命周期管理

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

> **在 lifespan 中调用** 详见 [应用启动与初始化](./fastapi-startup.md)

---

## 依赖注入

### Session 依赖

```python
# core/dependencies.py
from typing import Annotated
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DBSession = Annotated[AsyncSession, Depends(get_db)]
```

### 分层架构

DBSession 不应直接注入到 Router，而是通过分层架构访问：

```
Router → Service → Repository → DBSession
```

完整的分层模式（Repository、Service、依赖注入链）详见 [核心模式 - 分层架构](./fastapi-patterns.md#分层架构)。

---

## 关系加载策略

> **异步环境禁止隐式懒加载**，访问未加载的关系会抛出 `MissingGreenlet` 错误。

### 推荐策略

| 关系类型 | 加载策略 | 说明 |
|---------|---------|------|
| One-to-Many / Many-to-Many | `selectinload()` | IN 查询，不影响原查询 |
| Many-to-One | `joinedload()` | 单条记录，JOIN 更高效 |
| 默认防护 | `lazy="raise"` | 强制显式加载，防止意外 |

### 模型定义

```python
from uuid import UUID
from uuid_utils import uuid7
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str]

    # lazy="raise" 防止异步环境下的意外懒加载
    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        lazy="raise",
    )


class Post(Base):
    __tablename__ = "post"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    title: Mapped[str]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))

    author: Mapped["User"] = relationship(
        back_populates="posts",
        lazy="raise",
    )
```

### 查询时显式加载

```python
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload


# One-to-Many: 使用 selectinload
async def get_user_with_posts(db: AsyncSession, user_id: UUID) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.posts))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# Many-to-One: 使用 joinedload
async def get_post_with_author(db: AsyncSession, post_id: UUID) -> Post | None:
    stmt = (
        select(Post)
        .where(Post.id == post_id)
        .options(joinedload(Post.author))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# 嵌套关系: 链式加载
async def get_user_with_posts_and_comments(db: AsyncSession, user_id: UUID):
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.posts).selectinload(Post.comments)
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

### 自动加载（简化场景）

```python
# 关系定义时设置默认加载策略（适用于总是需要加载的场景）
posts: Mapped[list["Post"]] = relationship(
    back_populates="author",
    lazy="selectin",  # 自动使用 selectin 加载
)
```

---

## 事务管理

> ⚠️ **核心约定**：**一个请求 = 一个事务**。事务由 `get_db()` 依赖统一管理。
> - Repository 层**禁止调用 `commit()`**，只用 `flush()` 同步数据
> - Service 层无需显式事务操作
> - 违反此约定会破坏事务原子性（部分操作已提交，异常时无法完整回滚）

### 默认行为（依赖注入）

`get_db()` 依赖已处理事务生命周期：

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # 请求成功自动 commit
        except Exception:
            await session.rollback()  # 异常自动 rollback
            raise
```

**事务边界 = Service 方法**：一个 Service 方法对应一个请求，对应一个事务。

### 分层中的事务规则

| 层 | 事务操作 | 说明 |
|----|---------|------|
| **Repository** | `flush()` / `refresh()` | 不调用 commit，只同步到数据库获取 ID |
| **Service** | 无显式操作 | 依赖注入自动管理 |
| **Router** | 无 | 不接触事务 |

```python
# Repository - 只用 flush，不 commit
async def create(self, user: User) -> User:
    self.db.add(user)
    await self.db.flush()      # 同步到 DB，获取自增 ID
    await self.db.refresh(user)  # 刷新对象状态
    return user

# Service - 多个 Repository 操作在同一事务中
async def create_user_with_profile(self, data: UserCreate) -> User:
    user = await self.user_repo.create(User(...))
    await self.profile_repo.create(Profile(user_id=user.id, ...))
    return user  # 两个操作在同一事务，依赖注入统一 commit
```

### 嵌套事务（Savepoint）

部分操作允许失败时使用：

```python
# Service 层
from uuid import UUID

async def transfer_with_notification(
    self,
    from_id: UUID,
    to_id: UUID,
    amount: float,
) -> None:
    # 主事务：转账（必须成功）
    from_account = await self.account_repo.get_by_id(from_id)
    to_account = await self.account_repo.get_by_id(to_id)

    from_account.balance -= amount
    to_account.balance += amount

    # 嵌套事务：通知（可失败）
    try:
        async with self.db.begin_nested():
            await self.notification_repo.create(...)
    except NotificationError:
        pass  # 通知失败不影响转账，savepoint 自动回滚

    # 不调用 commit，由 get_db() 统一处理
```

#### 数据库兼容性

| 数据库 | Savepoint 支持 | 注意事项 |
|--------|----------------|----------|
| PostgreSQL | ✅ 完全支持 | 无限制 |
| MySQL/MariaDB | ✅ 支持 | 仅 InnoDB 引擎，MyISAM 不支持事务 |
| SQLite | ⚠️ 部分支持 | 需要 `PRAGMA foreign_keys=ON`，WAL 模式下更稳定 |

> **测试注意**：使用 SQLite 内存数据库测试时，savepoint 行为与 PostgreSQL 一致。但文件模式下并发写入可能有限制。

### 手动事务（特殊场景）

后台任务、CLI 脚本等非请求上下文：

```python
async def background_job():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 操作...
            pass
        # 自动 commit
```

---

## Repository 模式

Repository 封装数据访问逻辑，提供领域友好的查询接口。

完整的分层架构示例（Repository → Service → Router）详见 [核心模式 - 分层架构](./fastapi-patterns.md#分层架构)。

### Repository CRUD 方法规范

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_by_id(id)` | `Model \| None` | 主键查询 |
| `get_by_xxx(field)` | `Model \| None` | 唯一字段查询 |
| `list(page, page_size)` | `tuple[list[Model], int]` | 分页列表，返回 (items, total) |
| `create(model)` | `Model` | 创建，使用 `flush()` + `refresh()` |
| `update(model, data)` | `Model` | 更新，使用 `flush()` + `refresh()` |
| `delete(model)` | `None` | 删除 |
| `count()` | `int` | 统计数量 |

### 关键操作说明

```python
# 创建：flush 同步到 DB 获取自增 ID，refresh 刷新对象状态
async def create(self, user: User) -> User:
    self.db.add(user)
    await self.db.flush()      # 同步到 DB，获取自增 ID
    await self.db.refresh(user)  # 刷新对象状态
    return user

# 聚合查询：使用 SQL 函数
async def count(self) -> int:
    result = await self.db.execute(select(func.count(User.id)))
    return result.scalar_one()
```

> **注意**：Repository 层只调用 `flush()`，不调用 `commit()`。事务由依赖注入的 `get_db()` 统一管理。

---

## 数据库迁移（Alembic）

### 异步初始化

```bash
alembic init -t async migrations
```

### 配置 env.py

```python
# migrations/env.py
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.core.database import Base
from app.models import *  # noqa: F401, F403 - 导入所有模型

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db.url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.db.url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
```

### 常用命令

```bash
# 创建迁移
alembic revision --autogenerate -m "add user table"

# 执行迁移
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看历史
alembic history --verbose
```

### Docker 集成

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0"]
```

---

## SQL 优先聚合

数据库处理聚合比 Python 更快更高效。

```python
# ❌ Python 侧聚合 - 加载全部数据到内存
async def get_stats_slow(db: AsyncSession):
    result = await db.execute(select(Post))
    posts = result.scalars().all()
    return {
        "total": len(posts),
        "published": sum(1 for p in posts if p.is_published),
    }


# ✅ SQL 聚合 - 只返回结果
from sqlalchemy import func, case

async def get_stats(db: AsyncSession):
    result = await db.execute(
        select(
            func.count(Post.id).label("total"),
            func.count(case((Post.is_published == True, 1))).label("published"),  # noqa: E712
            func.coalesce(func.avg(Post.views), 0).label("avg_views"),
        )
    )
    row = result.one()
    return {"total": row.total, "published": row.published, "avg_views": float(row.avg_views)}
```

---

## 连接池配置

### 生产环境推荐

```python
from app.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.db.url,
    pool_size=20,        # 常驻连接数
    max_overflow=10,     # 溢出连接数
    pool_timeout=30,     # 获取超时（秒）
    pool_recycle=3600,   # 回收周期（秒）
    pool_pre_ping=True,  # 使用前检测
)
```

### 特殊场景

```python
from sqlalchemy.pool import NullPool, StaticPool
from app.config import get_settings

settings = get_settings()

# 外部连接池（如 PgBouncer）
engine = create_async_engine(settings.db.url, poolclass=NullPool)

# 内存数据库测试
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
)
```

---

## 同步兼容（精简）

当必须使用同步库时，使用 `run_in_threadpool` 避免阻塞：

```python
from uuid import UUID
from fastapi.concurrency import run_in_threadpool


def sync_operation(session, user_id: UUID):
    """同步数据库操作"""
    return session.query(User).filter(User.id == user_id).first()


@router.get("/users/{user_id}")
async def get_user(user_id: UUID, db: SyncDBSession):
    user = await run_in_threadpool(sync_operation, db, user_id)
    return user
```

或在异步 Session 中运行同步代码：

```python
async def async_main():
    async with AsyncSessionLocal() as session:
        result = await session.run_sync(sync_orm_function)
```

---

## 最佳实践

| 实践 | 说明 |
|-----|------|
| 异步驱动 | asyncpg / aiomysql / aiosqlite |
| `expire_on_commit=False` | 推荐：避免 commit 后隐式查询；如需强制重新加载以避免陈旧数据，可设为 True |
| `lazy="raise"` | 防止意外懒加载，强制显式 |
| `selectinload` / `joinedload` | 显式预加载，避免 N+1 |
| 依赖注入管理 Session | 自动关闭，请求隔离 |
| Repository 模式 | 封装数据访问，便于测试 |
| SQL 聚合 | 复杂计算在数据库层完成 |
| 连接池配置 | `pool_pre_ping=True` 检测失效连接 |
| Alembic 迁移 | 版本化数据库变更 |
| `dispose()` 连接池 | lifespan 关闭时释放资源 |
