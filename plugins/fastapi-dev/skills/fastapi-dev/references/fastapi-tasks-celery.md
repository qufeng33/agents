# FastAPI Celery 任务队列

企业级分布式任务队列，功能全面但配置复杂。

## 设计原则
- 任务独立、可重试、可追踪
- 任务入参尽量序列化友好
- 数据库访问使用同步 Session
- 失败策略明确
- 队列资源可控

## 最佳实践
1. 任务用 `delay()` 异步触发
2. 重要任务启用重试
3. 结果查询提供最小接口
4. 任务失败要有告警
5. Worker 参数与队列规模匹配

## 目录
- `安装`
- `配置`
- `定义任务`
- `在路由中使用`
- `任务状态追踪`
- `启动 Worker`

---

## 安装

```bash
uv add celery[redis]
```

> 如任务需要访问数据库，建议使用同步 Session，并额外安装 `psycopg`。

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
    worker_prefetch_multiplier=1,
)

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
    try:
        with get_sync_session() as db:
            order = db.get(Order, order_id)
            if order:
                order.status = "processed"
                db.commit()
        return {"order_id": order_id, "status": "processed"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

> 复杂序列化可使用 Pydantic（Celery 5.5+），按需启用。

---

## 在路由中使用

```python
from app.tasks.orders import process_order
from app.schemas.response import ApiResponse


@router.post("/orders", response_model=ApiResponse[dict[str, str]])
async def create_order(order: OrderCreate, service: OrderServiceDep) -> ApiResponse[dict[str, str]]:
    db_order = await service.create(order)
    task = process_order.delay(db_order.id)
    return ApiResponse(data={"order_id": str(db_order.id), "task_id": task.id})
```

---

## 任务状态追踪

```python
from celery.result import AsyncResult


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id)
    return {"task_id": task_id, "status": result.status}
```

> 详细结果/traceback 可按需暴露给内部用户。

---

## 启动 Worker

```bash
celery -A app.core.celery worker --loglevel=info
```
