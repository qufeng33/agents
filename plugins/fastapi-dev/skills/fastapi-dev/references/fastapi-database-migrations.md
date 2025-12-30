# FastAPI 数据库迁移
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 迁移与模型定义保持一致
- 元数据必须完整导入
- 异步优先，同步场景单独处理
- 迁移可追溯、可回滚
- 运行环境可复现

## 最佳实践
1. 使用 `alembic init -t async`
2. 迁移前确认 `target_metadata` 完整
3. 自动生成后人工检查
4. CI/容器启动时执行迁移
5. 同步任务用 `run_in_threadpool`

## 目录
- `Alembic 配置`
- `常用命令`
- `Docker 集成`
- `同步兼容`
- `相关文档`

---

## Alembic 配置

### 异步初始化

```bash
alembic init -t async alembic
```

### env.py 核心片段

```python
# alembic/env.py
from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.core.database import Base

# 简单结构：导入所有模型
from app.models import *  # noqa: F401, F403

# 模块化结构：显式导入各模块模型
# from app.modules.user import models as user_models  # noqa: F401

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db.url)


def run_migrations_offline() -> None:
    context.configure(url=settings.db.url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
```

> 确保所有模型被导入，否则 `metadata` 不完整会导致漏生成迁移。

---

## 常用命令

```bash
alembic revision --autogenerate -m "add app_user table"
alembic upgrade head
alembic downgrade -1
alembic history --verbose
```

---

## Docker 集成

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0"]
```

---

## 同步兼容

当需要在同步任务场景访问数据库（例如 BackgroundTasks、Celery、APScheduler 持久化）时，使用 `run_in_threadpool` 避免阻塞。

```python
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.database import get_sync_session


def sync_operation(session: Session):
    return session.get(User, user_id)


async def load_user(user_id: UUID) -> User | None:
    def _load() -> User | None:
        with get_sync_session() as session:
            return sync_operation(session)

    return await run_in_threadpool(_load)
```

> 同步查询/异步 `run_sync` 适用于旧库或第三方 SDK 仍依赖同步 Session 的场景。

---

## 相关文档

- [数据库配置](./fastapi-database-setup.md)
- [ORM 基类与软删除](./fastapi-database-orm.md)
- [Repository 与事务](./fastapi-database-patterns.md)
