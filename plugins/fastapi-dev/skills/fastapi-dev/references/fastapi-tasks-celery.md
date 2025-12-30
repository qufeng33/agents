# FastAPI Celery 任务队列

企业级分布式任务队列，功能全面但配置复杂。

## 安装

```bash
uv add celery[redis]
```

> 如任务需要访问数据库，建议使用同步 Session，并额外安装 `psycopg`（同步驱动）。

---

## 配置

```python
# app/core/celery.py
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tasks",
    broker=f"redis://{settings.redis.host}:{settings.redis.port}/0",
    backend=f"redis://{settings.redis.host}:{settings.redis.port}/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])
```

---

## 定义任务

```python
# app/tasks/orders.py
from uuid import UUID
from app.core.celery import celery_app
from app.core.database import get_sync_session


@celery_app.task(bind=True, max_retries=3)
def process_order(self, order_id: UUID):
    """
    Celery 任务（同步）
    bind=True 允许访问 self（任务实例）
    """
    try:
        with get_sync_session() as db:
            order = db.get(Order, order_id)
            if order:
                order.status = "processed"
                db.commit()
        return {"order_id": order_id, "status": "processed"}
    except Exception as exc:
        # 指数退避重试
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

---

## Pydantic 集成（Celery 5.5+）

```python
from uuid import UUID
from pydantic import BaseModel
from app.core.celery import celery_app


class OrderData(BaseModel):
    order_id: UUID
    items: list[str]


class OrderResult(BaseModel):
    order_id: UUID
    status: str


@celery_app.task(pydantic=True)
def process_order_v2(data: OrderData) -> OrderResult:
    """Pydantic 自动序列化/反序列化"""
    # 处理订单...
    return OrderResult(order_id=data.order_id, status="processed")
```

---

## 在路由中使用

```python
from app.tasks.orders import process_order
from typing import Any
from app.schemas.response import ApiResponse


@router.post("/orders", status_code=201, response_model=ApiResponse[dict[str, str]])
async def create_order(
    order: OrderCreate,
    service: OrderServiceDep,
) -> ApiResponse[dict[str, str]]:
    db_order = await service.create(order)

    # 异步调用 Celery 任务
    task = process_order.delay(db_order.id)

    return ApiResponse(data={"order_id": db_order.id, "task_id": task.id})
```

---

## 任务链

```python
from celery import chain, group

# 串行执行
result = chain(
    validate_order.s(order_id),
    process_payment.s(),
    send_confirmation.s(),
).delay()

# 并行执行
result = group(
    send_notification.s(username),
    send_sms.s(phone),
    log_notification.s(user_id),
).delay()
```

---

## 错误处理与重试

```python
@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,  # 指数退避
    retry_jitter=True,   # 随机抖动
)
def robust_task(self, data):
    try:
        # 操作...
        pass
    except CustomError as exc:
        raise self.retry(exc=exc, countdown=30)
```

### 死信队列

```python
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}

celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_acks_late = True


@celery_app.task(bind=True)
def handle_failed_task(self, task_id: str, error: str):
    """处理失败任务"""
    # 记录日志、通知等
    pass
```

---

## 任务状态追踪

```python
from typing import Any
from celery.result import AsyncResult
from app.schemas.response import ApiResponse


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict[str, Any]])
async def get_task_status(task_id: str) -> ApiResponse[dict[str, Any]]:
    result = AsyncResult(task_id)
    return ApiResponse(
        data={
            "task_id": task_id,
            "status": result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
        }
    )
```

---

## 启动 Worker

```bash
celery -A app.core.celery worker --loglevel=info
```
