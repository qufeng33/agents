# FastAPI 后台任务与调度

> BackgroundTasks | ARQ | Celery | APScheduler

## 概述

| 方案 | 适用场景 | 特点 |
|------|---------|------|
| **BackgroundTasks** | 轻量任务、无需追踪 | 内置、简单、同进程 |
| **ARQ** | 异步任务队列 | async 原生、Redis、轻量 |
| **Celery** | 企业级任务系统 | 生态成熟、功能全面、学习曲线陡 |
| **APScheduler** | 定时任务 | 多种触发器、支持持久化 |

**选型建议**：
- 简单通知/日志 → BackgroundTasks
- 异步优先项目 → ARQ
- 复杂工作流/已有 Celery 经验 → Celery
- 定时任务 → APScheduler（可与上述任意方案组合）

---

## BackgroundTasks（内置）

FastAPI 内置的轻量级后台任务，适合无需追踪状态的简单操作。

### 基本用法

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

### 数据库操作

后台任务在请求完成后执行，此时请求的异步 session 已关闭。需要创建独立 session。

> **为什么使用同步 Session？**
> FastAPI 自动将同步函数放入线程池，不会阻塞事件循环。

```python
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import sync_engine  # 同步引擎，专用于后台任务


def process_order(order_id: UUID):
    """后台任务：使用同步 session（运行在线程池）"""
    with Session(sync_engine) as db:
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

> **同步引擎配置**：在 `core/database.py` 中添加 `sync_engine = create_engine(SYNC_DATABASE_URL)`

### 最佳实践

1. **传递 ID 而非对象** - ORM 对象绑定 session，跨 session 使用会出错
2. **同步函数优先** - 自动线程池执行，避免阻塞事件循环
3. **不追踪状态** - 无法知道任务是否完成，失败无重试

### 局限性

- 同进程执行，应用重启任务丢失
- 无任务状态追踪
- 无重试机制
- 不支持任务优先级/队列

---

## ARQ（推荐）

基于 Redis 的异步任务队列，与 FastAPI 异步优先理念一致。

### 安装

```bash
uv add arq
```

### 定义任务

```python
# app/tasks/worker.py
from uuid import UUID
from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def send_email(ctx: dict, email: str, message: str):
    """异步任务函数，ctx 包含 redis 连接等上下文"""
    # 发送邮件...
    return {"sent_to": email}


async def process_order(ctx: dict, order_id: UUID):
    """处理订单"""
    # 使用异步 session
    async with AsyncSessionLocal() as db:
        order = await db.scalar(select(Order).where(Order.id == order_id))
        if order:
            order.status = "processed"
            await db.commit()
    return {"order_id": order_id, "status": "processed"}


class WorkerSettings:
    """ARQ Worker 配置"""
    functions = [send_email, process_order]
    redis_settings = RedisSettings(
        host=settings.redis.host,
        port=settings.redis.port,
    )
    max_jobs = 10
    job_timeout = 300  # 5 分钟
```

### FastAPI 集成

```python
# app/core/arq.py
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()
arq_redis: ArqRedis | None = None


async def init_arq() -> ArqRedis:
    global arq_redis
    arq_redis = await create_pool(
        RedisSettings(host=settings.redis.host, port=settings.redis.port)
    )
    return arq_redis


async def close_arq():
    global arq_redis
    if arq_redis:
        await arq_redis.close()
```

```python
# app/main.py
from app.core.arq import init_arq, close_arq


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_arq()
    yield
    await close_arq()
```

### 在路由中使用

```python
from app.core.arq import arq_redis


@router.post("/orders", status_code=201)
async def create_order(order: OrderCreate, db: DBSession):
    db_order = Order(**order.model_dump())
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)

    # 入队任务
    job = await arq_redis.enqueue_job("process_order", db_order.id)

    return {"order_id": db_order.id, "job_id": job.job_id}
```

### 依赖注入模式

```python
# app/dependencies.py
from typing import Annotated
from fastapi import Depends, Request
from arq import ArqRedis


async def get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq_redis


ArqPool = Annotated[ArqRedis, Depends(get_arq)]


# 路由中使用
@router.post("/notify")
async def notify(email: str, arq: ArqPool):
    await arq.enqueue_job("send_email", email, "Hello")
    return {"status": "queued"}
```

### 任务选项

```python
# 延迟执行
await arq_redis.enqueue_job("send_email", email, _defer_by=60)  # 60 秒后

# 指定执行时间
await arq_redis.enqueue_job("send_email", email, _defer_until=datetime(2024, 1, 1))

# 任务唯一性（防止重复）
await arq_redis.enqueue_job("process_order", order_id, _job_id=f"order:{order_id}")
```

### 启动 Worker

```bash
arq app.tasks.worker.WorkerSettings
```

---

## Celery

企业级分布式任务队列，功能全面但配置复杂。

### 安装

```bash
uv add celery[redis]
```

### 配置

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

### 定义任务

```python
# app/tasks/orders.py
from uuid import UUID
from app.core.celery import celery_app
from app.core.database import SyncSessionLocal


@celery_app.task(bind=True, max_retries=3)
def process_order(self, order_id: UUID):
    """
    Celery 任务（同步）
    bind=True 允许访问 self（任务实例）
    """
    try:
        with SyncSessionLocal() as db:
            order = db.query(Order).get(order_id)
            if order:
                order.status = "processed"
                db.commit()
        return {"order_id": order_id, "status": "processed"}
    except Exception as exc:
        # 指数退避重试
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Pydantic 集成（Celery 5.5+）

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

### 在路由中使用

```python
from app.tasks.orders import process_order


@router.post("/orders", status_code=201)
async def create_order(order: OrderCreate, db: DBSession):
    db_order = Order(**order.model_dump())
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)

    # 异步调用 Celery 任务
    task = process_order.delay(db_order.id)

    return {"order_id": db_order.id, "task_id": task.id}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    from celery.result import AsyncResult

    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
```

### 任务链

```python
from celery import chain

# 串行执行
result = chain(
    validate_order.s(order_id),
    process_payment.s(),
    send_confirmation.s(),
).delay()

# 并行执行
from celery import group

result = group(
    send_email.s(email),
    send_sms.s(phone),
    log_notification.s(user_id),
).delay()
```

### 启动 Worker

```bash
celery -A app.core.celery worker --loglevel=info
```

---

## APScheduler（定时任务）

支持多种触发器的任务调度器，可与 FastAPI 深度集成。

### 安装

```bash
uv add apscheduler
# 可选：持久化
uv add sqlalchemy asyncpg  # PostgreSQL
```

### FastAPI 集成

```python
# app/core/scheduler.py
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

settings = get_settings()
scheduler: AsyncScheduler | None = None


async def cleanup_expired_sessions():
    """定时清理过期会话"""
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(Session).where(Session.expires_at < datetime.utcnow())
        )
        await db.commit()


async def generate_daily_report():
    """每日报告"""
    # 生成报告...
    pass


async def init_scheduler() -> AsyncScheduler:
    global scheduler

    engine = create_async_engine(settings.db.url)
    data_store = SQLAlchemyDataStore(engine)
    event_broker = AsyncpgEventBroker.from_async_sqla_engine(engine)

    scheduler = AsyncScheduler(data_store, event_broker)

    # 添加定时任务
    await scheduler.add_schedule(
        cleanup_expired_sessions,
        IntervalTrigger(hours=1),
        id="cleanup_sessions",
    )
    await scheduler.add_schedule(
        generate_daily_report,
        CronTrigger(hour=6, minute=0),  # 每天 6:00
        id="daily_report",
    )

    await scheduler.start_in_background()
    return scheduler


async def close_scheduler():
    global scheduler
    if scheduler:
        await scheduler.stop()
```

```python
# app/main.py
from app.core.scheduler import init_scheduler, close_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_scheduler()
    yield
    await close_scheduler()
```

### 触发器类型

```python
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.calendarinterval import CalendarIntervalTrigger

# 间隔触发
IntervalTrigger(seconds=30)
IntervalTrigger(minutes=5)
IntervalTrigger(hours=1)

# Cron 表达式
CronTrigger(hour=6, minute=0)                    # 每天 6:00
CronTrigger(day_of_week="mon-fri", hour=9)       # 工作日 9:00
CronTrigger(day=1, hour=0, minute=0)             # 每月 1 号 0:00

# 单次执行
DateTrigger(run_time=datetime(2024, 12, 31, 23, 59))

# 日历间隔（考虑 DST）
CalendarIntervalTrigger(days=1)  # 每天（比 IntervalTrigger 更精确）
```

### 动态添加任务

```python
from app.core.scheduler import scheduler


@router.post("/schedules")
async def create_schedule(cron: str, task_name: str):
    """动态创建定时任务"""
    await scheduler.add_schedule(
        my_task,
        CronTrigger.from_crontab(cron),
        id=f"user_schedule_{task_name}",
    )
    return {"status": "created"}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """删除定时任务"""
    await scheduler.remove_schedule(schedule_id)
    return {"status": "deleted"}
```

### 任务装饰器

```python
from datetime import timedelta
from apscheduler import task


@task(
    id="my_cleanup_task",
    max_running_jobs=1,              # 最多同时运行 1 个
    misfire_grace_time=timedelta(minutes=5),  # 错过后 5 分钟内仍执行
)
async def cleanup_task():
    pass
```

---

## 错误处理与重试

### ARQ 重试

```python
from arq import Retry


async def unreliable_task(ctx: dict, data: str):
    try:
        # 可能失败的操作...
        pass
    except TemporaryError:
        raise Retry(defer=60)  # 60 秒后重试
```

### Celery 重试

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

### 死信队列（Celery）

```python
# celery 配置
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}

celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_acks_late = True

# 失败任务处理
@celery_app.task(bind=True)
def handle_failed_task(self, task_id: str, error: str):
    """处理失败任务"""
    # 记录日志、通知等
    pass
```

---

## 任务状态追踪

### ARQ 任务状态

```python
from arq.jobs import Job


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, arq: ArqPool):
    job = Job(job_id, arq)
    info = await job.info()

    if info is None:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job_id,
        "status": info.status,
        "result": info.result,
        "start_time": info.start_time,
        "finish_time": info.finish_time,
    }
```

### Celery 任务状态

```python
from celery.result import AsyncResult


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }
```

---

## 最佳实践

| 实践 | 说明 |
|-----|------|
| 传递 ID 而非对象 | 避免序列化问题，任务内重新查询 |
| 幂等性设计 | 任务可能重复执行，确保结果一致 |
| 合理超时 | 设置 `task_time_limit` 防止任务卡死 |
| 重试策略 | 指数退避 + 抖动，避免雪崩 |
| 资源隔离 | 不同类型任务使用不同队列 |
| 监控告警 | Flower (Celery) / ARQ 仪表盘 |
| 优雅关闭 | lifespan 中正确关闭连接 |
| 日志追踪 | 记录 task_id/job_id 便于排查 |

---

## 方案对比

| 特性 | BackgroundTasks | ARQ | Celery |
|------|----------------|-----|--------|
| 依赖 | 无 | Redis | Redis/RabbitMQ |
| 异步支持 | 同步（线程池） | 原生 async | 同步为主 |
| 持久化 | 无 | Redis | 多种后端 |
| 重试机制 | 无 | 内置 | 强大 |
| 任务追踪 | 无 | 内置 | 内置 |
| 定时任务 | 无 | 无 | Celery Beat |
| 任务链 | 无 | 无 | 内置 |
| 监控 | 无 | 基础 | Flower |
| 学习曲线 | 低 | 中 | 高 |
| 适用规模 | 小 | 中 | 大 |
