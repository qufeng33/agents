# FastAPI 中间件

## 设计原则
- 中间件只处理横切关注点，避免业务逻辑
- 注册顺序决定执行顺序（洋葱模型）
- 异常交给 `exception_handler` 统一处理
- 需要全局生效才使用中间件
- 配置优先从 Settings 读取

## 最佳实践
1. 日志中间件放最外层
2. CORS/GZip 等基础中间件放内层
3. 性能敏感时优先纯 ASGI 中间件
4. 认证/权限优先使用依赖注入
5. 中间件注册集中在 `setup_middlewares`

## 目录
- `概述`
- `执行顺序`
- `请求日志中间件`
- `CORS 中间件`
- `异常处理器（推荐）`
- `GZip 压缩`
- `请求限流`
- `安全响应头`
- `Trusted Host`
- `HTTPS 重定向`
- `中间件 vs 依赖注入`
- `相关文档`

---

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
    app.add_middleware(CORSMiddleware, ...)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(LoggingMiddleware)
```

---

## 请求日志中间件

```python
# app/middlewares/logging.py
import time
from uuid import uuid4
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

# 简化的上下文定义（完整版见 fastapi-audit.md）
@dataclass
class RequestContext:
    request_id: str | None = None

request_context: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())

def get_request_context() -> RequestContext:
    return request_context.get()

def set_request_context(ctx: RequestContext):
    request_context.set(ctx)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ctx = get_request_context()
        if not ctx.request_id:
            ctx.request_id = uuid4().hex[:8]
            set_request_context(ctx)

        start_time = time.perf_counter()
        with logger.contextualize(request_id=ctx.request_id):
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            logger.info("Completed {} in {:.3f}s", response.status_code, duration)

        response.headers["X-Process-Time"] = f"{duration:.3f}"
        return response
```

> 性能敏感场景可改用纯 ASGI 中间件；实现要点一致。

---

## CORS 中间件

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> 建议从 Settings 读取 `cors_origins`，避免硬编码。

---

## 异常处理器（推荐）

统一异常处理应由 `exception_handler` 负责，中间件不应捕获所有异常，避免覆盖业务异常/参数校验的状态码与响应格式。

```python
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

```python
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
```

> 路由使用 `@limiter.limit()`；限流规则按业务调整。

---

## 安全响应头

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
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

if not settings.debug:
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

## 中间件 vs 依赖注入

- **全局必需**：中间件
- **局部生效**：依赖注入
- **复杂业务逻辑**：依赖注入
- **请求/响应改写**：中间件

---

## 相关文档

- [应用生命周期](./fastapi-app-lifecycle.md) - 注册入口
- [错误处理](./fastapi-errors.md) - exception_handler
