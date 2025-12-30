# FastAPI ARQ 任务队列

基于 Redis 的异步任务队列，与 FastAPI 异步优先理念一致。

## 安装

```bash
uv add arq
```

---

## 定义任务

```python
# app/tasks/worker.py
from uuid import UUID
from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def send_notification(ctx: dict, username: str, message: str):
    """异步任务函数，ctx 包含 redis 连接等上下文"""
    # 发送通知...
    return {"sent_to": username}


async def process_order(ctx: dict, order_id: UUID):
    """处理订单"""
    async with AsyncSessionLocal() as db:
        order = await db.scalar(select(Order).where(Order.id == order_id))
        if order:
            order.status = "processed"
            await db.commit()
    return {"order_id": order_id, "status": "processed"}


class WorkerSettings:
    """ARQ Worker 配置"""
    functions = [send_notification, process_order]
    redis_settings = RedisSettings(
        host=settings.redis.host,
        port=settings.redis.port,
    )
    max_jobs = 10
    job_timeout = 300  # 5 分钟
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

```python
# app/main.py
from app.core.arq import init_arq, close_arq


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_arq(app)
    yield
    await close_arq(app)
```

---

## 依赖注入

```python
# app/dependencies.py
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


@router.post("/notify", response_model=ApiResponse[dict[str, str]])
async def notify(username: str, arq: ArqPool) -> ApiResponse[dict[str, str]]:
    await arq.enqueue_job("send_notification", username, "Hello")
    return ApiResponse(data={"status": "queued"})


@router.post("/orders", status_code=201, response_model=ApiResponse[dict[str, str]])
async def create_order(
    order: OrderCreate,
    service: OrderServiceDep,
    arq: ArqPool,
) -> ApiResponse[dict[str, str]]:
    db_order = await service.create(order)
    job = await arq.enqueue_job("process_order", db_order.id)
    return ApiResponse(data={"order_id": db_order.id, "job_id": job.job_id})
```

---

## 任务选项

```python
# 延迟执行
await arq.enqueue_job("send_notification", username, _defer_by=60)  # 60 秒后

# 指定执行时间
await arq.enqueue_job("send_notification", username, _defer_until=datetime(2024, 1, 1))

# 任务唯一性（防止重复）
await arq.enqueue_job("process_order", order_id, _job_id=f"order:{order_id}")
```

---

## 错误处理与重试

```python
from arq import Retry


async def unreliable_task(ctx: dict, data: str):
    try:
        # 可能失败的操作...
        pass
    except TemporaryError:
        raise Retry(defer=60)  # 60 秒后重试
```

---

## 任务状态追踪

```python
from typing import Any
from arq.jobs import Job
from app.schemas.response import ApiResponse
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError


@router.get("/jobs/{job_id}", response_model=ApiResponse[dict[str, Any]])
async def get_job_status(job_id: str, arq: ArqPool) -> ApiResponse[dict[str, Any]]:
    job = Job(job_id, arq)
    info = await job.info()

    if info is None:
        raise NotFoundError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    return ApiResponse(
        data={
            "job_id": job_id,
            "status": info.status,
            "result": info.result,
            "start_time": info.start_time,
            "finish_time": info.finish_time,
        }
    )
```

---

## 启动 Worker

```bash
arq app.tasks.worker.WorkerSettings
```
