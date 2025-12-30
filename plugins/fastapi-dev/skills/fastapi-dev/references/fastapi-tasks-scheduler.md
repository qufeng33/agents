# FastAPI APScheduler 定时任务

支持多种触发器的任务调度器，可与 FastAPI 深度集成。示例基于 APScheduler 3.11.2。

## 设计原则
- 任务幂等，支持重复执行
- 任务参数可序列化
- 任务运行时长可控
- 生命周期与应用一致
- 日志可追踪

## 最佳实践
1. 传递 ID 而非对象
2. 任务超时与并发限制明确
3. scheduler 在 lifespan 中启动/关闭
4. 任务失败有告警
5. 持久化按需启用

## 目录
- `安装`
- `FastAPI 集成`
- `触发器类型`
- `动态任务与装饰器`
- `相关文档`

---

## 安装

```bash
uv add apscheduler
# 可选：持久化（SQLAlchemyJobStore 仅支持同步驱动）
uv add sqlalchemy psycopg
```

---

## FastAPI 集成

```python
# app/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler: AsyncIOScheduler | None = None


async def cleanup_expired_sessions():
    ...


def init_scheduler() -> AsyncIOScheduler:
    global scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(cleanup_expired_sessions, IntervalTrigger(hours=1), id="cleanup_sessions")
    scheduler.add_job(generate_daily_report, CronTrigger(hour=6, minute=0), id="daily_report")
    scheduler.start()
    return scheduler


def close_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
```

> 持久化 JobStore 可按需启用（仅同步驱动）。

---

## 触发器类型

```python
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

IntervalTrigger(hours=1)
CronTrigger(day_of_week="mon-fri", hour=9)
DateTrigger(run_time=datetime.utcnow() + timedelta(days=7))
```

> 日历间隔触发器适用于 DST 场景。

---

## 动态任务与装饰器

- 动态创建/删除任务可暴露管理 API
- `@scheduler.scheduled_job` 适合小型固定任务

---

## 相关文档

- [应用生命周期](./fastapi-app-lifecycle.md)
- [任务队列（ARQ）](./fastapi-tasks-arq.md)
- [任务队列（Celery）](./fastapi-tasks-celery.md)
