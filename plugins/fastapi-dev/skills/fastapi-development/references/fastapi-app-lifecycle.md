# FastAPI 应用生命周期

> 完整可运行模板见 `assets/simple-api/` 和 `assets/modular-api/`

## 初始化顺序

```
1. get_settings()      # 配置加载
2. create_app()        # 创建 FastAPI 实例
3. lifespan            # 应用生命周期（数据库等资源初始化/清理）
```

---

## 模块入口 (app/main.py)

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import close_database, init_database
from app.core.middlewares import setup_middlewares
from app.core.routers import setup_routers
from app.core.exception_handlers import setup_exception_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化
    await init_database()
    yield
    # 关闭时清理
    await close_database()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # 注册组件
    setup_middlewares(application)
    setup_routers(application)
    setup_exception_handlers(application)

    return application


app = create_app()
```

---

## Lifespan 详解

`lifespan` 用于管理应用级别的资源（数据库连接池、HTTP 客户端、任务队列等）。

### 基本模式

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化资源，存储到 app.state
    app.state.http_client = httpx.AsyncClient()
    yield
    # 关闭：清理资源
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)
```

### 多资源管理

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动顺序
    await init_database()
    init_scheduler()
    await init_arq(app)

    yield

    # 关闭顺序（与启动相反）
    await close_arq(app)
    close_scheduler()
    await close_database()
```

### 通过依赖注入访问资源

```python
async def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]


@router.get("/external")
async def call_external(client: HttpClient):
    response = await client.get("https://api.example.com")
    return response.json()
```

---

## init/setup/close 函数模式

### 命名约定

| 前缀 | 用途 | 示例 |
|------|------|------|
| `init_xxx` | 异步初始化，创建资源 | `init_database` |
| `setup_xxx` | 同步配置，注册组件 | `setup_middlewares`, `setup_routers` |
| `close_xxx` | 清理资源 | `close_database` |

### 各模块初始化函数

| 函数 | 位置 | 详细文档 |
|------|------|----------|
| `init_database` / `close_database` | core/database.py | [数据库配置](./fastapi-database-setup.md) |
| `setup_middlewares` | core/middlewares.py | [中间件](./fastapi-middleware.md) |
| `setup_routers` | core/routers.py | [API 设计](./fastapi-api-design.md) |
| `setup_exception_handlers` | core/exception_handlers.py | [错误处理](./fastapi-errors.md) |
| `init_arq` / `close_arq` | core/arq.py | [ARQ 任务队列](./fastapi-tasks-arq.md) |
| `init_scheduler` / `close_scheduler` | core/scheduler.py | [定时任务](./fastapi-tasks-scheduler.md) |

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **create_app 工厂模式** | 便于测试和多实例场景 |
| **setup_xxx 分离注册** | 中间件、路由、异常处理器分离到独立函数 |
| **lifespan 管理资源** | 启动时初始化，关闭时清理 |
| **close 对应 init** | 每个 `init_xxx` 都有对应的 `close_xxx` |
| **顺序一致** | 关闭顺序与初始化顺序相反 |
| **app.state 存储共享资源** | 通过依赖注入访问 |

---

## 相关文档

- [项目结构](./fastapi-project-structure.md) - 目录布局
- [核心模式](./fastapi-patterns.md) - 依赖注入、分层架构
- [中间件](./fastapi-middleware.md) - CORS、GZip 等配置
