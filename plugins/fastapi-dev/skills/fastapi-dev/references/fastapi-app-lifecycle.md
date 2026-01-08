# FastAPI 应用生命周期

> 完整可运行模板见 `assets/simple-api/app/` 和 `assets/modular-api/app/`

## 设计原则
- 资源初始化与清理必须成对出现
- 应用入口最小化，启动流程可读可测
- 共享资源统一放 `app.state` 并通过依赖注入访问
- 初始化顺序清晰，关闭顺序严格相反
- 与项目结构保持一致（`init/setup/close`）

## 最佳实践
1. 使用 `create_app` 工厂模式
2. 组件注册拆成 `setup_xxx` 函数
3. 资源生命周期用 `lifespan` 统一管理
4. `init_xxx` 与 `close_xxx` 一一对应
5. 关闭顺序与初始化顺序相反

## 目录
- `初始化顺序`
- `模块入口 (app/main.py)`
- `Lifespan 详解`
- `init/setup/close 函数模式`
- `相关文档`

---

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
from app.core.exception_handlers import setup_exception_handlers
from app.core.middlewares import setup_middlewares
from app.core.routers import setup_routers

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_database()
    yield
    await close_database()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    setup_middlewares(application)
    setup_routers(application)
    setup_exception_handlers(application)

    return application


app = create_app()
```

> 更复杂的初始化逻辑应拆分到 `init_xxx`/`setup_xxx`，保持入口可读。

---

## Lifespan 详解

`lifespan` 用于管理应用级别的资源（数据库连接池、HTTP 客户端、任务队列等）。

### 基本模式

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)
```

### 多资源管理

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_database()
    init_scheduler()
    await init_arq(app)

    yield

    await close_arq(app)
    close_scheduler()
    await close_database()
```

> 多资源场景下，关闭顺序必须与初始化顺序相反。

### 通过依赖注入访问资源

```python
async def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
```

> 路由中通过依赖注入获取共享资源，避免直接访问 `app.state`。

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

## 相关文档

- [项目结构](./fastapi-project-structure.md) - 目录布局
- [分层架构](./fastapi-layered-architecture.md) - Router/Service/Repository
- [依赖注入](./fastapi-dependency-injection.md) - Annotated、依赖链
- [中间件](./fastapi-middleware.md) - CORS、GZip 等配置
