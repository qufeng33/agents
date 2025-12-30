# FastAPI ARQ 任务队列

基于 Redis 的异步任务队列，与 FastAPI 异步优先理念一致。

## 设计原则
- 任务异步化、可重试
- 任务入参可序列化
- 连接池统一管理
- 任务失败可追踪
- 与 FastAPI 生命周期一致

## 最佳实践
1. 任务函数保持纯净
2. 重要任务设置重试
3. 任务 ID 可用于幂等
4. Worker 配置集中管理
5. 路由只负责入队

## 目录
- `安装`
- `定义任务`
- `FastAPI 集成`
- `依赖注入`
- `在路由中使用`
- `错误处理与重试`
- `启动 Worker`

---

## 安装

```bash
uv add arq
```

---

## 定义任务

```python
# app/tasks/worker.py
from uuid import UUID
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def process_order(ctx: dict, order_id: UUID):
    async with AsyncSessionLocal() as db:
        order = await db.scalar(select(Order).where(Order.id == order_id))
        if order:
            order.status = "processed"
            await db.commit()


class WorkerSettings:
    functions = [process_order]
    redis_settings = RedisSettings(host=settings.redis.host, port=settings.redis.port)
    max_jobs = 10
    job_timeout = 300
```

---

## FastAPI 集成

```python
# app/core/arq.py
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()


async def init_arq(app: FastAPI) -> None:
    app.state.arq_redis = await create_pool(
        RedisSettings(host=settings.redis.host, port=settings.redis.port)
    )


async def close_arq(app: FastAPI) -> None:
    arq_redis: ArqRedis | None = getattr(app.state, "arq_redis", None)
    if arq_redis:
        await arq_redis.close()
```

---

## 依赖注入

```python
from typing import Annotated
from fastapi import Depends, Request
from arq import ArqRedis


async def get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq_redis


ArqPool = Annotated[ArqRedis, Depends(get_arq)]
```

---

## 在路由中使用

```python
from app.schemas.response import ApiResponse


@router.post("/orders", status_code=201, response_model=ApiResponse[dict[str, str]])
async def create_order(order: OrderCreate, service: OrderServiceDep, arq: ArqPool):
    db_order = await service.create(order)
    job = await arq.enqueue_job("process_order", db_order.id)
    return ApiResponse(data={"order_id": db_order.id, "job_id": job.job_id})
```

---

## 错误处理与重试

```python
from arq import Retry


async def unreliable_task(ctx: dict, data: str):
    try:
        ...
    except TemporaryError:
        raise Retry(defer=60)
```

> 延迟执行/任务唯一性/状态追踪等特性按需启用。

---

## 启动 Worker

```bash
arq app.tasks.worker.WorkerSettings
```
