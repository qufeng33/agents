# FastAPI 中间件

## 概述

中间件在请求到达路由之前和响应返回之前执行，用于处理横切关注点（日志、认证、CORS 等）。

---

## 执行顺序

**后注册的中间件先执行**（洋葱模型）：

```python
app.add_middleware(A)  # 第二个执行
app.add_middleware(B)  # 第一个执行

# 请求流程：B → A → 路由 → A → B
```

推荐注册顺序（从后往前）：

```python
def setup_middlewares(app: FastAPI) -> None:
    # 3. CORS（最内层）
    app.add_middleware(CORSMiddleware, ...)

    # 2. GZip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 1. 请求日志（最外层，最先执行）
    app.add_middleware(LoggingMiddleware)
```

---

## 请求日志中间件

```python
# app/middlewares/logging.py
import time
from uuid import uuid4

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.context import get_request_context, set_request_context


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        # 生成或获取 request_id
        ctx = get_request_context()
        if not ctx.request_id:
            ctx.request_id = uuid4().hex[:8]
            set_request_context(ctx)
        request_id = ctx.request_id
        start_time = time.perf_counter()

        # 绑定上下文
        with logger.contextualize(request_id=request_id):
            logger.info("{} {}", request.method, request.url.path)

            response = await call_next(request)

            duration = time.perf_counter() - start_time
            logger.info(
                "Completed {} in {:.3f}s",
                response.status_code,
                duration,
            )

        # 添加响应头
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        return response
```

> `X-Request-ID` 由 `RequestContextMiddleware` 统一注入，日志中间件只读取，避免重复生成导致链路不一致。

### 使用纯 ASGI 中间件（性能更好）

```python
# app/middlewares/logging.py
import time
from uuid import uuid4

from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.context import get_request_context, set_request_context


class LoggingMiddleware:
    """纯 ASGI 请求日志中间件"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ctx = get_request_context()
        if not ctx.request_id:
            ctx.request_id = uuid4().hex[:8]
            set_request_context(ctx)
        request_id = ctx.request_id
        start_time = time.perf_counter()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        method = scope.get("method", "")
        path = scope.get("path", "")

        with logger.contextualize(request_id=request_id):
            logger.info("{} {}", method, path)

            await self.app(scope, receive, send_wrapper)

            duration = time.perf_counter() - start_time
            logger.info("Completed {} in {:.3f}s", status_code, duration)
```

---

## CORS 中间件

```python
from starlette.middleware.cors import CORSMiddleware

# 有需要时再开启 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 配置驱动

```python
# app/config.py
class Settings(BaseSettings):
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v


# app/core/middlewares.py
def setup_middlewares(app: FastAPI) -> None:
    settings = get_settings()

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
```

---

## 异常处理器（推荐）

统一异常处理应由 `exception_handler` 负责，中间件不应捕获所有异常，否则会覆盖业务异常/参数校验的状态码与响应格式。

```python
# app/main.py
from fastapi import FastAPI

from app.core.exception_handlers import setup_exception_handlers

app = FastAPI()
setup_exception_handlers(app)
```

详见 [错误处理](./fastapi-errors.md)（`setup_exception_handlers`）

---

## GZip 压缩

```python
from starlette.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## 请求限流

使用 `slowapi`（基于 Redis，支持分布式限流）：

```bash
uv add slowapi
```

```python
# core/middlewares.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)


def setup_middlewares(app: FastAPI) -> None:
    # 限流配置（slowapi 要求挂载到 app.state）
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    # 其他中间件...
```

```python
# 在路由中使用
from fastapi import APIRouter, Request

from app.core.middlewares import limiter

router = APIRouter()


@router.get("/limited")
@limiter.limit("10/minute")
async def limited_route(request: Request):
    return {"message": "This route is rate limited"}
```

---

## 安全响应头

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

---

## Trusted Host

防止 Host Header 攻击：

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com", "localhost"],
)
```

---

## HTTPS 重定向

```python
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

# 生产环境强制 HTTPS
if not settings.debug:
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

## 完整注册示例

```python
# app/core/middlewares.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.middlewares.logging import LoggingMiddleware


def setup_middlewares(app: FastAPI) -> None:
    """
    注册中间件。

    注意：后注册的先执行（洋葱模型）
    执行顺序：Logging → GZip → CORS → 路由
    """
    settings = get_settings()

    # 4. CORS（最内层）
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 3. GZip 压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 1. 请求日志（最外层，最先执行）
    app.add_middleware(LoggingMiddleware)
```

> **在 main.py 中调用** 详见 [应用生命周期](./fastapi-app-lifecycle.md)

---

## 中间件 vs 依赖注入

| 场景 | 推荐 |
|------|------|
| 每个请求都需要 | 中间件 |
| 只有部分路由需要 | 依赖注入 |
| 需要修改请求/响应 | 中间件 |
| 复杂业务逻辑 | 依赖注入 |
| 全局日志、CORS | 中间件 |
| 认证、权限检查 | 依赖注入（更灵活） |

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **注意顺序** | 后注册的先执行 |
| **日志最外层** | 确保记录所有请求 |
| **异常处理** | 使用 `exception_handler` 统一处理，不在中间件吞异常 |
| **纯 ASGI** | 高性能场景用纯 ASGI 中间件 |
| **配置驱动** | CORS origins 等从 Settings 读取 |
| **依赖注入优先** | 认证等复杂逻辑优先用 DI |
