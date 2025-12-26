# FastAPI 性能优化

## 响应优化

### ORJSONResponse

使用 orjson 替代标准 json，大型响应性能提升显著。

```bash
uv add orjson
```

```python
from fastapi import APIRouter, FastAPI
from fastapi.responses import ORJSONResponse

router = APIRouter()

# 全局默认
app = FastAPI(default_response_class=ORJSONResponse)

# 或单个路由
@router.get("/items/", response_class=ORJSONResponse)
async def list_items():
    return [{"id": i, "name": f"Item {i}"} for i in range(1000)]
```

### GZip 压缩

```python
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # 只压缩大于 1KB 的响应
)
```

### 流式响应

大文件使用流式响应，避免内存占用。

```python
from fastapi.responses import StreamingResponse


async def generate_large_file():
    for i in range(10000):
        yield f"Line {i}\n"


@router.get("/download")
async def download():
    return StreamingResponse(
        generate_large_file(),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=large.txt"},
    )
```

---

## 缓存策略

### lru_cache 缓存配置

```python
from functools import lru_cache


@lru_cache
def get_settings():
    """只在第一次调用时读取配置"""
    return Settings()
```

### Redis 缓存

使用 lifespan 管理 Redis 连接：

```python
# core/cache.py
import json
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, FastAPI, Request


async def init_redis(app: FastAPI) -> None:
    """初始化 Redis 连接"""
    app.state.redis = await redis.from_url("redis://localhost")


async def close_redis(app: FastAPI) -> None:
    """关闭 Redis 连接"""
    await app.state.redis.close()


async def get_redis(request: Request) -> redis.Redis:
    """依赖注入：获取 Redis 客户端"""
    return request.app.state.redis


RedisClient = Annotated[redis.Redis, Depends(get_redis)]


async def get_cached_or_fetch(
    redis_client: redis.Redis,
    key: str,
    fetch_func,
    ttl: int = 300,
):
    """尝试从缓存获取，否则调用 fetch_func 并缓存"""
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    data = await fetch_func()
    await redis_client.setex(key, ttl, json.dumps(data))
    return data
```

```python
# 使用示例
from uuid import UUID

@router.get("/users/{user_id}")
async def get_user(user_id: UUID, redis_client: RedisClient):
    cache_key = f"user:{user_id}"

    async def fetch():
        return await user_service.get(user_id)

    return await get_cached_or_fetch(redis_client, cache_key, fetch, ttl=600)
```

### HTTP 缓存头

```python
from fastapi import Response


@router.get("/static-data")
async def get_static_data(response: Response):
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = "abc123"
    return {"data": "static content"}
```

---

## 数据库优化

### 连接池配置

```python
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.db.url,         # postgresql+asyncpg://...
    pool_size=20,            # 常驻连接数
    max_overflow=10,         # 溢出连接数
    pool_timeout=30,         # 获取超时（秒）
    pool_recycle=3600,       # 回收周期（秒）
    pool_pre_ping=True,      # 使用前检测
)
```

> 完整的异步引擎配置、Session 管理详见 [数据库集成](./fastapi-database.md)

### 预加载关联（避免 N+1）

```python
# repository.py
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload

from app.core.dependencies import DBSession


class UserRepository:
    def __init__(self, db: DBSession):
        self.db = db

    async def list_with_relations(self) -> list[User]:
        result = await self.db.execute(
            select(User).options(
                selectinload(User.posts),
                selectinload(User.comments),
            )
        )
        return list(result.scalars().all())


class PostRepository:
    def __init__(self, db: DBSession):
        self.db = db

    async def get_with_author(self, post_id: UUID) -> Post | None:
        result = await self.db.execute(
            select(Post)
            .where(Post.id == post_id)
            .options(joinedload(Post.author))
        )
        return result.scalar_one_or_none()
```

```python
# service.py
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def list_users(self) -> list[User]:
        return await self.repo.list_with_relations()


class PostService:
    def __init__(self, repo: PostRepository):
        self.repo = repo

    async def get_post(self, post_id: UUID) -> Post | None:
        return await self.repo.get_with_author(post_id)
```

```python
# router.py
@router.get("/users/")
async def list_users(service: UserServiceDep):
    return await service.list_users()


@router.get("/posts/{post_id}")
async def get_post(post_id: UUID, service: PostServiceDep):
    return await service.get_post(post_id)
```

### 分页

```python
from fastapi import Query
from sqlalchemy import select, func


@router.get("/items/", response_model=ApiPagedResponse[ItemResponse])
async def list_items(
    page: int = Query(default=0, ge=0, description="页码（从 0 开始）"),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ItemServiceDep,
) -> ApiPagedResponse[ItemResponse]:
    items, total = await service.list_items(page=page, page_size=page_size)
    return ApiPagedResponse(data=items, total=total, page=page, page_size=page_size)
```

```python
# service.py
class ItemService:
    def __init__(self, repo: ItemRepository):
        self.repo = repo

    async def list_items(self, page: int, page_size: int) -> tuple[list[ItemResponse], int]:
        items, total = await self.repo.list(page=page, page_size=page_size)
        return [ItemResponse.model_validate(i) for i in items], total
```

```python
# repository.py
class ItemRepository:
    def __init__(self, db: DBSession):
        self.db = db

    async def list(self, page: int, page_size: int) -> tuple[list[Item], int]:
        total_result = await self.db.execute(select(func.count()).select_from(Item))
        total = total_result.scalar_one()

        offset = page * page_size
        result = await self.db.execute(select(Item).offset(offset).limit(page_size))
        items = list(result.scalars().all())
        return items, total
```

---

## 异步优化

### 并行请求

```python
import asyncio
import httpx


@router.get("/aggregate")
async def aggregate_data():
    async with httpx.AsyncClient() as client:
        # 并行请求
        tasks = [
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
            client.get("https://api3.example.com/data"),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        "api1": results[0].json() if not isinstance(results[0], Exception) else None,
        "api2": results[1].json() if not isinstance(results[1], Exception) else None,
        "api3": results[2].json() if not isinstance(results[2], Exception) else None,
    }
```

### 共享 HTTP 客户端

详见 [fastapi-httpx.md](./fastapi-httpx.md) 的「生命周期管理 + 依赖注入」章节。

核心要点：
- 在 lifespan 中初始化 `httpx.AsyncClient`，存储到 `app.state`
- 通过依赖注入获取客户端
- 测试时可用 `dependency_overrides` 替换

---

## CPU 密集型任务

### 进程池处理

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)


def cpu_intensive(data: str) -> str:
    # CPU 密集型计算
    import hashlib
    for _ in range(1000000):
        data = hashlib.sha256(data.encode()).hexdigest()
    return data


@router.post("/compute")
async def compute(data: str):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, cpu_intensive, data)
    return {"result": result}
```

### 任务队列（Celery）

```python
from uuid import UUID
from celery import Celery

celery_app = Celery("tasks", broker="redis://localhost:6379/0")


@celery_app.task
def process_video(video_id: UUID):
    # 耗时任务
    ...


@router.post("/videos/{video_id}/process")
async def start_processing(video_id: UUID):
    task = process_video.delay(video_id)
    return {"task_id": task.id}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = celery_app.AsyncResult(task_id)
    return {"status": task.status, "result": task.result}
```

---

## 监控与分析

### 请求耗时中间件

```python
import time
import logging

logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    logger.info(
        "Request completed",
        extra={
            "path": request.url.path,
            "method": request.method,
            "duration_ms": round(duration * 1000, 2),
            "status_code": response.status_code,
        },
    )

    response.headers["X-Process-Time"] = str(duration)
    return response
```

### 慢查询日志

```python
import logging

# SQLAlchemy 慢查询日志
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# 或自定义
from sqlalchemy import event

@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop()
    if total > 0.5:  # 超过 500ms
        logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}")
```

---

## 最佳实践

1. **使用 ORJSONResponse** - 大型响应必备
2. **启用 GZip** - 减少传输数据量
3. **配置连接池** - 避免连接耗尽
4. **预加载关联** - 避免 N+1 查询
5. **合理分页** - 限制单次返回数量
6. **并行请求** - asyncio.gather
7. **共享资源** - HTTP 客户端、Redis 连接
8. **CPU 任务分离** - 进程池或任务队列
9. **监控耗时** - 中间件记录请求时间
10. **缓存热点数据** - Redis 或内存缓存
