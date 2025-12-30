# FastAPI 数据库配置

> SQLAlchemy 2.0 异步优先 | asyncpg | Alembic

## 设计原则
- 异步引擎统一管理，避免多实例
- Session 生命周期由依赖注入控制
- 生产连接池参数清晰可调
- 特殊场景使用明确的 poolclass
- 配置与数据库文档保持一致

## 最佳实践
1. 使用 `create_async_engine` + `async_sessionmaker`
2. `expire_on_commit=False` 避免隐式查询
3. 生产环境启用 `pool_pre_ping`
4. 连接池参数基于负载评估
5. 测试/外部连接池用专用 poolclass

## 目录
- `核心配置`
- `连接池配置`
- `相关文档`

---

## 核心配置

### 异步引擎与 Session

```python
# core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.db.url,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass

### 同步兼容（可选）

用于 BackgroundTasks、Celery 或迁移脚本等同步场景。

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# 独立的同步引擎
sync_engine = create_engine(
    settings.db.url.replace("+asyncpg", "+psycopg"),  # 切换驱动
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=sync_engine)

def get_sync_session() -> Generator[Session, None, None]:
    with SyncSessionLocal() as session:
        yield session
```
```

> 驱动示例：`postgresql+asyncpg://`、`mysql+aiomysql://`、`sqlite+aiosqlite://`。

---

## 连接池配置

### 生产环境推荐

```python
async_engine = create_async_engine(
    settings.db.url,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

### 特殊场景

```python
from sqlalchemy.pool import NullPool, StaticPool

# 外部连接池（如 PgBouncer）
engine = create_async_engine(settings.db.url, poolclass=NullPool)

# 内存数据库测试
engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
```

> 生产参数需结合并发量与数据库连接上限调整。

---

## 相关文档

- [ORM 基类与软删除](./fastapi-database-orm.md)
- [Repository 与事务](./fastapi-database-patterns.md)
- [数据库迁移](./fastapi-database-migrations.md)
