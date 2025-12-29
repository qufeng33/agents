# FastAPI Repository 与事务
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。


## 依赖注入

### Session 依赖

```python
# app/dependencies.py
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

完整的分层模式详见 [分层架构](./fastapi-layered-architecture.md)。

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
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    __tablename__ = "app_user"

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
    author_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"))

    author: Mapped["User"] = relationship(
        back_populates="posts",
        lazy="raise",
    )
```

### 查询时显式加载

```python
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

---

## 事务管理

> **核心约定**：**一个请求 = 一个事务**。事务由 `get_db()` 依赖统一管理。
> - Repository 层**禁止调用 `commit()`**，只用 `flush()` 同步数据
> - Service 层无需显式事务操作

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
```

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

### CRUD 方法规范

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_by_id(id)` | `Model \| None` | 主键查询 |
| `get_by_xxx(field)` | `Model \| None` | 唯一字段查询 |
| `list(page, page_size)` | `tuple[list[Model], int]` | 分页列表，返回 (items, total) |
| `create(model)` | `Model` | 创建，使用 `flush()` + `refresh()` |
| `update(model, data)` | `Model` | 更新，使用 `flush()` + `refresh()` |
| `delete(model)` | `None` | 删除（默认软删除） |
| `count()` | `int` | 统计数量 |

### 关键操作

```python
# 创建：flush 同步到 DB 获取自增 ID，refresh 刷新对象状态
async def create(self, user: User) -> User:
    self.db.add(user)
    await self.db.flush()
    await self.db.refresh(user)
    return user

# 聚合查询：使用 SQL 函数
async def count(self) -> int:
    result = await self.db.execute(select(func.count(User.id)))
    return result.scalar_one()
```

---

## SQL 优先聚合

数据库处理聚合比 Python 更快更高效。

```python
# 错误：Python 侧聚合（可能 OOM）
async def get_stats_slow(db: AsyncSession):
    result = await db.execute(select(Post))
    posts = result.scalars().all()
    return {"total": len(posts)}


# 正确：SQL 聚合
from sqlalchemy import func, case

async def get_stats(db: AsyncSession):
    result = await db.execute(
        select(
            func.count(Post.id).label("total"),
            func.count(case((Post.is_published == True, 1))).label("published"),
        )
    )
    row = result.one()
    return {"total": row.total, "published": row.published}
```

---

## 相关文档

- [数据库配置](./fastapi-database-setup.md)
- [ORM 基类与软删除](./fastapi-database-orm.md)
- [数据库迁移](./fastapi-database-migrations.md)
- [分层架构](./fastapi-layered-architecture.md)
