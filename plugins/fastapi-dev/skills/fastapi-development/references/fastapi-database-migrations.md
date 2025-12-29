# FastAPI 数据库迁移

## Alembic 配置

### 异步初始化

```bash
alembic init -t async alembic
```

### 配置 env.py

```python
# alembic/env.py
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

## 同步兼容

当必须使用同步库时，使用 `run_in_threadpool` 避免阻塞：

```python
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def sync_operation(session, user_id: UUID):
    """同步数据库操作"""
    return session.query(User).filter(User.id == user_id).first()


sync_engine = create_engine(settings.db.sync_url)


def get_sync_db() -> Session:
    with Session(sync_engine) as session:
        yield session


class UserService:
    def __init__(self, db: Session):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await run_in_threadpool(sync_operation, self.db, user_id)
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
| `expire_on_commit=False` | 避免 commit 后隐式查询 |
| `lazy="raise"` | 防止意外懒加载 |
| `selectinload` / `joinedload` | 显式预加载，避免 N+1 |
| 依赖注入管理 Session | 自动关闭，请求隔离 |
| Repository 模式 | 封装数据访问，便于测试 |
| SQL 聚合 | 复杂计算在数据库层完成 |
| 连接池配置 | `pool_pre_ping=True` 检测失效连接 |
| Alembic 迁移 | 版本化数据库变更 |
| `dispose()` 连接池 | lifespan 关闭时释放资源 |

---

## 相关文档

- [数据库配置](./fastapi-database-setup.md)
- [ORM 基类与软删除](./fastapi-database-orm.md)
- [Repository 与事务](./fastapi-database-patterns.md)
