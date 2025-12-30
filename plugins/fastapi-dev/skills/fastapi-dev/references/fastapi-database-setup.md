# FastAPI 数据库配置

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

## 连接池配置

### 生产环境推荐

```python
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

# 外部连接池（如 PgBouncer）
engine = create_async_engine(settings.db.url, poolclass=NullPool)

# 内存数据库测试
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
)
```

---

## 相关文档

- [ORM 基类与软删除](./fastapi-database-orm.md)
- [Repository 与事务](./fastapi-database-patterns.md)
- [数据库迁移](./fastapi-database-migrations.md)
