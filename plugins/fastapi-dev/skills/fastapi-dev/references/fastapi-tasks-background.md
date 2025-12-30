# FastAPI BackgroundTasks

FastAPI 内置的轻量级后台任务，适合无需追踪状态的简单操作。

## 设计原则
- 任务简单且无状态追踪需求
- 不阻塞请求主流程
- 任务逻辑与请求分离
- 数据库操作使用独立 session
- 失败可接受或可忽略

## 最佳实践
1. 只做轻量任务
2. 传递 ID 而非 ORM 对象
3. 同步函数优先（线程池执行）
4. 失败不做重试
5. 复杂任务升级到队列系统

## 目录
- `基本用法`
- `数据库操作`
- `局限性`
- `相关文档`

---

## 基本用法

```python
from fastapi import APIRouter, BackgroundTasks
from app.schemas.response import ApiResponse

router = APIRouter()


def send_notification(username: str, message: str) -> None:
    # 发送通知...
    pass


@router.post("/notify", response_model=ApiResponse[dict[str, str]])
async def notify(username: str, bg: BackgroundTasks) -> ApiResponse[dict[str, str]]:
    bg.add_task(send_notification, username, "Hello")
    return ApiResponse(data={"status": "scheduled"})
```

---

## 数据库操作

后台任务在请求完成后执行，此时请求的异步 session 已关闭，需要创建独立 session。

```python
from uuid import UUID
from sqlalchemy import select
from app.core.database import get_sync_session


def process_order(order_id: UUID) -> None:
    with get_sync_session() as db:
        order = db.scalar(select(Order).where(Order.id == order_id))
        if order:
            order.status = "processed"
            db.commit()
```

> 同步引擎配置见数据库模块，任务完成后确保释放连接池。

---

## 局限性

- 同进程执行，应用重启任务丢失
- 无任务状态追踪
- 无重试机制

> 需要更强功能？考虑 [ARQ](./fastapi-tasks-arq.md) 或 [Celery](./fastapi-tasks-celery.md)。

---

## 相关文档

- [ARQ](./fastapi-tasks-arq.md)
- [Celery](./fastapi-tasks-celery.md)
- [数据库配置](./fastapi-database-setup.md)
