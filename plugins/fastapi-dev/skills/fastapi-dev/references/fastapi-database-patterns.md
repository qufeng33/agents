# FastAPI Repository 与事务
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 一个请求一个事务
- Repository 封装数据访问
- Service 负责业务编排
- 查询加载策略显式声明
- SQL 处理聚合与过滤

## 最佳实践
1. Repository 禁止 `commit()`，仅 `flush()`
2. Session 依赖统一管理事务
3. 关系加载使用 `selectinload/joinedload`
4. SQL 优先处理聚合/过滤/排序
5. 复杂事务用 savepoint 或后台任务

## 目录
- `依赖注入`
- `关系加载策略`
- `事务管理`
- `Repository 模式`
- `SQL 优先原则`
- `相关文档`

---

## 依赖注入

### Session 依赖

```python
# app/dependencies.py
from collections.abc import AsyncGenerator
from typing import Annotated

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

**推荐策略**：
- One-to-Many / Many-to-Many 使用 `selectinload()`
- Many-to-One 使用 `joinedload()`
- 默认启用 `lazy="raise"` 防止意外懒加载

```python
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "app_user"
    posts: Mapped[list["Post"]] = relationship(back_populates="author", lazy="raise")
```

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_user_with_posts(db: AsyncSession, user_id: UUID) -> User | None:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.posts))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

> 嵌套关系可链式 `selectinload().selectinload()`，按需使用。

---

## 事务管理

**核心约定**：**一个请求 = 一个事务**。事务由 `get_db()` 依赖统一管理。

| 层 | 事务操作 | 说明 |
|----|---------|------|
| **Repository** | `flush()` / `refresh()` | 不调用 commit |
| **Service** | 无显式操作 | 依赖注入自动管理 |
| **Router** | 无 | 不接触事务 |

```python
# Repository - 只用 flush，不 commit
async def create(self, user: User) -> User:
    self.db.add(user)
    await self.db.flush()
    await self.db.refresh(user)
    return user
```

> 嵌套事务可用 `session.begin_nested()`；后台任务/CLI 可手动 `session.begin()`。

---

## Repository 模式

Repository 封装数据访问逻辑，提供领域友好的查询接口。

### CRUD 方法规范

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_one(id, *, include_deleted=False)` | `Model \| None` | 主键查询 |
| `get_one_by_*(field, *, include_deleted=False)` | `Model \| None` | 字段查询 |
| `get_list(page, page_size, *, include_deleted=False)` | `tuple[list[Model], int]` | 分页列表 |
| `create(model)` | `Model` | 创建，使用 `flush()` + `refresh()` |
| `update(model, data)` | `Model` | 更新，使用 `flush()` + `refresh()` |
| `delete(model)` | `None` | 删除（默认软删除） |

### 列表查询实现示例

```python
from sqlalchemy import func, select

async def get_list(
    self,
    page: int = 0,
    page_size: int = 20,
    *,
    include_deleted: bool = False,
) -> tuple[list[User], int]:
    # 1. 统计总数
    count_stmt = select(func.count(User.id))
    if not include_deleted:
        count_stmt = count_stmt.where(User.deleted_at.is_(None))
    total = await self.db.scalar(count_stmt) or 0

    # 2. 分页查询
    stmt = select(User).order_by(User.id.desc()).offset(page * page_size).limit(page_size)
    if not include_deleted:
        stmt = filter_active(stmt)

    # 3. 执行查询
    result = await self.db.execute(stmt)
    return list(result.scalars().all()), total
```

---

## SQL 优先原则

让数据库做它擅长的事：复杂查询、聚合、过滤、排序应在 SQL 层完成。

```python
# ❌ 错误：Python 侧聚合
async def get_stats_slow(db: AsyncSession):
    result = await db.execute(select(Post))
    posts = result.scalars().all()
    return {"total": len(posts)}

# ✅ 正确：SQL 聚合
from sqlalchemy import func

async def get_stats(db: AsyncSession):
    result = await db.execute(select(func.count(Post.id)))
    total = result.scalar_one()
    return {"total": total}
```

> JOIN、分页、排序同理，应优先在 SQL 层完成。

---

## 相关文档

- [数据库配置](./fastapi-database-setup.md)
- [ORM 基类与软删除](./fastapi-database-orm.md)
- [数据库迁移](./fastapi-database-migrations.md)
- [分层架构](./fastapi-layered-architecture.md)
