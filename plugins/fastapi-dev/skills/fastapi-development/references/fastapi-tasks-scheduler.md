# FastAPI APScheduler 定时任务

支持多种触发器的任务调度器，可与 FastAPI 深度集成。示例基于 APScheduler 3.11.2。

## 安装

```bash
uv add apscheduler
# 可选：持久化
uv add sqlalchemy psycopg  # PostgreSQL（同步驱动）
```

---

## FastAPI 集成

```python
# app/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
from sqlalchemy import delete

from app.config import get_settings
from app.core.database import AsyncSessionLocal
from app.modules.session.models import UserSession

settings = get_settings()
scheduler: AsyncIOScheduler | None = None


async def cleanup_expired_sessions():
    """定时清理过期会话"""
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(UserSession).where(UserSession.expires_at < datetime.now(timezone.utc))
        )
        await db.commit()


async def generate_daily_report():
    """每日报告"""
    # 生成报告...
    pass


def init_scheduler() -> AsyncIOScheduler:
    global scheduler

    # 持久化（可选）：SQLAlchemyJobStore 仅支持同步驱动
    jobstores = {
        # PostgreSQL 示例：postgresql+psycopg://user:pass@host/db
        "default": SQLAlchemyJobStore(url="sqlite:///./scheduler.db"),
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

    # 添加定时任务
    scheduler.add_job(
        cleanup_expired_sessions,
        IntervalTrigger(hours=1),
        id="cleanup_sessions",
    )
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=6, minute=0),  # 每天 6:00
        id="daily_report",
    )

    scheduler.start()
    return scheduler


def close_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
```

```python
# app/main.py
from app.core.scheduler import init_scheduler, close_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_scheduler()
    yield
    close_scheduler()
```

---

## 触发器类型

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

---

## 动态添加任务

```python
from app.core.scheduler import scheduler
from app.schemas.response import ApiResponse


@router.post("/schedules", response_model=ApiResponse[dict[str, str]])
async def create_schedule(
    cron: str,
    task_name: str,
) -> ApiResponse[dict[str, str]]:
    """动态创建定时任务"""
    job = scheduler.add_job(
        my_task,
        CronTrigger.from_crontab(cron),
        id=f"user_schedule_{task_name}",
    )
    return ApiResponse(data={"status": "created", "job_id": job.id})


@router.delete("/schedules/{schedule_id}", response_model=ApiResponse[dict[str, str]])
async def delete_schedule(schedule_id: str) -> ApiResponse[dict[str, str]]:
    """删除定时任务"""
    scheduler.remove_job(schedule_id)
    return ApiResponse(data={"status": "deleted"})
```

---

## 任务装饰器

```python
from apscheduler.triggers.interval import IntervalTrigger
from app.core.scheduler import scheduler


@scheduler.scheduled_job(
    IntervalTrigger(minutes=5),
    id="my_cleanup_task",
    max_instances=1,            # 最多同时运行 1 个
    misfire_grace_time=300,     # 错过后 5 分钟内仍执行
)
async def cleanup_task():
    pass
```

---

## 最佳实践

| 实践 | 说明 |
|-----|------|
| 传递 ID 而非对象 | 避免序列化问题，任务内重新查询 |
| 幂等性设计 | 任务可能重复执行，确保结果一致 |
| 合理超时 | 设置 `task_time_limit` 防止任务卡死 |
| 优雅关闭 | lifespan 中正确关闭 scheduler |
| 日志追踪 | 记录 job_id 便于排查 |
