# FastAPI BackgroundTasks

FastAPI 内置的轻量级后台任务，适合无需追踪状态的简单操作。

## 基本用法

```python
from fastapi import APIRouter, BackgroundTasks
from app.schemas.response import ApiResponse

router = APIRouter()


def send_email(email: str, message: str):
    """同步函数自动在线程池执行"""
    # 发送邮件...
    pass


@router.post("/notify", response_model=ApiResponse[dict[str, str]])
async def notify(email: str, bg: BackgroundTasks) -> ApiResponse[dict[str, str]]:
    bg.add_task(send_email, email, "Hello")
    return ApiResponse(data={"status": "scheduled"})
```

---

## 数据库操作

后台任务在请求完成后执行，此时请求的异步 session 已关闭。需要创建独立 session。

> **为什么使用同步 Session？** FastAPI 自动将同步函数放入线程池，不会阻塞事件循环；同步引擎通常用于任务场景。

```python
from uuid import UUID
from sqlalchemy import select
from app.core.database import get_sync_session  # 同步 Session，专用于后台任务


def process_order(order_id: UUID):
    """后台任务：使用同步 session（运行在线程池）"""
    with get_sync_session() as db:
        order = db.scalar(select(Order).where(Order.id == order_id))
        if order:
            order.status = "processed"
            db.commit()


@router.post("/orders", status_code=201, response_model=ApiResponse[OrderResponse])
async def create_order(
    order: OrderCreate,
    bg: BackgroundTasks,
    service: OrderServiceDep,
) -> ApiResponse[OrderResponse]:
    created = await service.create(order)
    bg.add_task(process_order, created.id)  # 传 ID，不传对象
    return ApiResponse(data=created)
```

> **同步引擎配置**：模板已提供 `get_sync_session()`，底层使用 `settings.db.sync_url`（需安装 `psycopg`）
>
> **资源释放**：若任务场景使用过同步引擎，可在应用关闭时调用 `close_sync_engine()` 释放连接池。

---

## 最佳实践

1. **传递 ID 而非对象** - ORM 对象绑定 session，跨 session 使用会出错
2. **同步函数优先** - 自动线程池执行，避免阻塞事件循环
3. **不追踪状态** - 无法知道任务是否完成，失败无重试

---

## 局限性

- 同进程执行，应用重启任务丢失
- 无任务状态追踪
- 无重试机制
- 不支持任务优先级/队列

> 需要更强功能？考虑 [ARQ](./fastapi-tasks-arq.md) 或 [Celery](./fastapi-tasks-celery.md)
