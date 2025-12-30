# FastAPI 性能优化
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 优先保证事件循环不被阻塞，I/O 和 CPU 任务分离
- 让 `response_model` 统一处理序列化，避免重复转换
- 缓存、连接池、共享客户端用于提升吞吐与稳定性
- 先监控再优化，性能结论基于数据而非直觉
- 优化不牺牲可读性与可测试性

## 最佳实践
1. **使用 ORJSONResponse** - 大型响应必备
2. **启用 GZip** - 减少传输数据量
3. **配置连接池** - 避免连接耗尽
4. **预加载关联** - 避免 N+1 查询
5. **合理分页** - 限制单次返回数量
6. **并行请求** - `asyncio.gather`
7. **共享资源** - HTTP 客户端、Redis 连接
8. **CPU 任务分离** - 进程池或任务队列
9. **监控耗时** - 中间件记录请求时间
10. **缓存热点数据** - Redis 或内存缓存

## 目录
- `async def vs def 选择`
- `响应优化`
- `缓存策略`
- `数据库优化`
- `异步优化`
- `CPU 密集型任务`
- `监控与分析`

---

## async def vs def 选择

| 场景 | 推荐 | 原因 |
|-----|------|------|
| 无 I/O 的简单逻辑 | `async def` | 避免线程池开销 |
| 异步 I/O（httpx, asyncpg） | `async def` + `await` | 非阻塞 |
| 同步阻塞 I/O | `def` | FastAPI 自动线程池 |
| CPU 密集型 | `ProcessPoolExecutor` | 不阻塞事件循环 |

> 上述选择针对 FastAPI 路由/依赖场景；纯工具函数（不在请求链路中）可使用 `def`。

```python
import asyncio
import time

import httpx
from fastapi import APIRouter

router = APIRouter()

# I/O 密集型：async def
@router.get("/external")
async def call_api():
    async with httpx.AsyncClient() as client:
        return (await client.get("https://api.example.com")).json()

# 同步阻塞：def（自动线程池）
@router.get("/sync")
def sync_operation():
    time.sleep(1)  # 不会阻塞事件循环
    return {"done": True}
```

### 常见错误

```python
# 错误：在 async def 中阻塞
@router.get("/bad")
async def bad():
    time.sleep(5)  # 阻塞事件循环！

# 正确：使用 def 或 asyncio.sleep
@router.get("/good")
async def good():
    await asyncio.sleep(5)
```

### 包装同步 SDK（run_in_threadpool）

在 async 函数中需要调用同步 SDK 时，使用 `run_in_threadpool` 避免阻塞事件循环：

```python
from starlette.concurrency import run_in_threadpool

@router.get("/sync-sdk")
async def call_sync_sdk():
    result = await run_in_threadpool(sync_sdk.heavy_operation)
    return {"result": result}
```

> 需要传参时可用 `lambda` 或 `functools.partial` 包装同步函数。

**适用场景**：
- 第三方 SDK 只提供同步接口（如某些云服务 SDK）
- 需要在 async 函数中调用同步 I/O 操作
- 无法使用 `def` 路由（如需要 `await` 其他操作）

---

## 响应优化

### 避免双重序列化

FastAPI 使用 `response_model` 时会自动验证和序列化返回值。手动创建 Pydantic 模型实例再返回，会导致双重处理。

```python
# 推荐：Service 返回 ORM 对象，交给 response_model 统一序列化
@router.get("/user/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep):
    user = await service.get(user_id)
    return ApiResponse(data=user)
```

```python
# 不使用包装时，直接返回 ORM 对象
@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, service: UserServiceDep):
    return await service.get(user_id)
```

> Service 层尽量返回 ORM 对象；如必须返回 Schema，请注明原因（例如权限裁剪或聚合字段）。

### ORJSONResponse

使用 orjson 替代标准 json，大型响应性能提升显著。

```bash
uv add orjson
```

```python
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
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

import redis.asyncio as redis
from fastapi import FastAPI, Request


async def init_redis(app: FastAPI) -> None:
    app.state.redis = await redis.from_url("redis://localhost")


async def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis


async def get_cached_or_fetch(
    redis_client: redis.Redis,
    key: str,
    fetch_func,
    ttl: int = 300,
):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    data = await fetch_func()
    await redis_client.setex(key, ttl, json.dumps(data))
    return data
```

> 路由中通过依赖注入获取 `redis_client` 并构造缓存键。`key` 建议包含版本或租户信息，`ttl` 按数据更新频率设定。

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

> 完整的异步引擎配置、Session 管理详见 [数据库配置](./fastapi-database-setup.md)

### 预加载关联（避免 N+1）

```python
# repository.py
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.dependencies import DBSession


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

> Service 层/Router 层只需调用 Repository；示例省略以突出关键查询形态。

### 分页

```python
# repository.py
from sqlalchemy import func, select


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

> Router 侧仅负责接收 `page/page_size` 并构造响应；若 `response_model` 支持 `from_attributes`，可直接传 ORM 列表。

---

## 异步优化

### 并行请求

```python
import asyncio
import httpx


@router.get("/aggregate")
async def aggregate_data():
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get("https://api1.example.com/data"),
            client.get("https://api2.example.com/data"),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        "api1": results[0].json() if not isinstance(results[0], Exception) else None,
        "api2": results[1].json() if not isinstance(results[1], Exception) else None,
    }
```

> 建议为请求设置超时，并明确异常兜底策略。

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

> 长耗时任务建议交给任务队列处理，以获得重试、延时与异步结果能力。
>
> 任务队列详见：
> - [Celery](./fastapi-tasks-celery.md) - 分布式任务队列
> - [Arq](./fastapi-tasks-arq.md) - 轻量级异步任务队列
> - [后台任务](./fastapi-tasks-background.md) - FastAPI 内置方案

---

## 监控与分析

### 请求耗时中间件

```python
import logging
import time

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

logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

> 如需按阈值记录慢查询，可在 SQLAlchemy 事件中统计耗时并输出告警。

---
