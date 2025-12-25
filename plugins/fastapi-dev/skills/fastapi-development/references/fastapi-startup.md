# 应用启动与初始化

## 概述

FastAPI 应用启动涉及多个子系统的初始化，需要按正确顺序执行。

---

## 初始化顺序

```
1. setup_bootstrap_logging()     # 日志（最先，确保后续错误可见）
2. get_settings()                # 配置（可能失败，需要日志）
3. setup_logging(settings)       # 正式日志配置
4. create_app()                  # 创建 FastAPI 实例
5. lifespan                      # 应用生命周期（数据库、HTTP 客户端等）
```

---

## 模块入口 (app/main.py)

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.config import get_settings
from app.core.database import init_database, close_database
from app.core.http import init_http_client, close_http_client
from app.core.logging import setup_bootstrap_logging, setup_logging
from app.core.middlewares import setup_middlewares
from app.core.routers import setup_routers
from app.exceptions import setup_exception_handlers

# ============================================================
# 1. 两阶段日志初始化
# ============================================================

setup_bootstrap_logging()

try:
    settings = get_settings()
except RuntimeError:
    raise SystemExit(1) from None

setup_logging(
    level=settings.log_level,
    json_format=settings.log_json,
    to_file=settings.log_to_file,
    log_dir=settings.log_dir,
)

# ============================================================
# 2. Lifespan（子系统初始化）
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动
    await init_database(app)
    await init_http_client(app)

    logger.info("Application started")
    yield

    # 关闭（顺序与启动相反）
    logger.info("Application shutting down...")
    await close_http_client(app)
    await close_database(app)


# ============================================================
# 3. 创建应用
# ============================================================

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # 注册组件
    setup_middlewares(app)
    setup_routers(app)
    setup_exception_handlers(app)

    return app


app = create_app()
```

---

## init/setup 函数模式

### 命名约定

| 前缀 | 用途 | 示例 |
|------|------|------|
| `init_xxx` | 异步初始化，创建资源 | `init_database`, `init_http_client` |
| `setup_xxx` | 同步配置，注册组件 | `setup_middlewares`, `setup_routers` |
| `close_xxx` | 清理资源 | `close_database`, `close_http_client` |

### 各模块初始化

| 函数 | 位置 | 详细文档 |
|------|------|----------|
| `setup_bootstrap_logging` / `setup_logging` | core/logging.py | [日志](./fastapi-logging.md) |
| `init_database` / `close_database` | core/database.py | [数据库](./fastapi-database.md) |
| `init_http_client` / `close_http_client` | core/http.py | [HTTP 客户端](./fastapi-httpx.md) |
| `setup_routers` | core/routers.py | [API 设计](./fastapi-api-design.md) |
| `setup_middlewares` | core/middlewares.py | [中间件](./fastapi-middleware.md) |
| `setup_exception_handlers` | exceptions.py | [错误处理](./fastapi-errors.md) |

---

## 相关文档

- **依赖注入获取资源** - 详见 [核心模式](./fastapi-patterns.md)（通过 DI 从 `app.state` 获取资源）
- **目录结构** - 详见 [项目结构](./fastapi-project-structure.md)

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **日志最先** | 确保后续初始化错误可见 |
| **两阶段日志** | Bootstrap → Settings → 正式配置 |
| **app.state 存储** | 共享资源存储在 `app.state` |
| **依赖注入获取** | 通过 DI 获取资源，便于测试 |
| **init/setup 分离** | `init_` 异步创建资源，`setup_` 同步注册组件 |
| **close 对应 init** | 每个 `init_xxx` 都有对应的 `close_xxx` |
| **顺序一致** | 关闭顺序与初始化顺序相反 |
