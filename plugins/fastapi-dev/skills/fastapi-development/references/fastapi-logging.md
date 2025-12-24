# FastAPI 日志（Loguru）

## 概述

Loguru 是一个简单、强大的 Python 日志库，开箱即用，无需繁琐配置。

```bash
uv add loguru
```

---

## 核心架构：二阶段初始化

为了确保配置验证的严格性以及日志输出的统一性，采用以下流程：

1. **引导阶段 (Bootstrap)**:
   - 在 `config.py` 中通过 `pydantic-settings` 加载环境变量
   - 如果验证失败，使用 Loguru 默认配置打印错误并立即退出
2. **配置阶段 (Configuration)**:
   - 一旦 `Settings` 对象成功加载，调用日志配置函数
   - 重置 Loguru，应用自定义格式（开发环境彩色，生产环境 JSON）
   - 通过 `InterceptHandler` 接管 Uvicorn 和 FastAPI 的内部日志

### 配置管理 (app/config.py)

```python
from functools import lru_cache
from typing import Literal

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    debug: bool = False

    # 日志
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False  # 生产环境建议设为 True

    # 必填配置（无默认值）
    openai_api_key: str


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    try:
        return Settings()
    except ValidationError as exc:
        missing = ["/".join(map(str, err.get("loc", []))) for err in exc.errors()]
        missing_str = ", ".join(missing) if missing else "未知字段"
        raise RuntimeError(
            f"缺少必要的环境变量: {missing_str}。请在 .env 文件中配置后再启动。"
        ) from None
```

### 日志系统 (app/core/logging.py)

```python
import logging
import sys
from typing import Literal

from loguru import logger


class InterceptHandler(logging.Handler):
    """拦截标准 logging 并转发到 Loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO",
    json_format: bool = False,
) -> None:
    """配置日志系统"""
    # 1. 清除默认 Handler
    logger.remove()

    # 2. 配置输出格式
    if json_format:
        # 生产环境：结构化 JSON
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,
            enqueue=True,  # 异步写入
        )
    else:
        # 开发环境：彩色美化
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
            enqueue=True,
        )

    # 3. 拦截标准库日志（uvicorn、httpx 等）
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 4. 降低第三方库日志级别
    for name in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    logger.info(f"Log system initialized. Level: {level}, JSON: {json_format}")
```

### 应用集成 (app/main.py)

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from loguru import logger

from app.config import get_settings
from app.core.logging import setup_logging

# 1. 先初始化日志（使用默认配置）
setup_logging()

# 2. 加载配置（失败时日志可用）
try:
    settings = get_settings()
except RuntimeError as exc:
    logger.error(str(exc))
    raise SystemExit(1) from None

# 3. 用配置重新初始化日志
setup_logging(level=settings.log_level, json_format=settings.log_json)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application starting...")
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title="My API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
)
```

---

## 请求日志中间件

```python
import time
from fastapi import Request
from loguru import logger


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()

    with logger.contextualize(
        request_id=request.headers.get("X-Request-ID", ""),
        path=request.url.path,
        method=request.method,
    ):
        logger.info("Request started")

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        logger.info(
            "Request completed | status={} | duration={:.3f}s",
            response.status_code,
            duration,
        )

    response.headers["X-Process-Time"] = str(duration)
    return response
```

---

## 上下文绑定

### bind() - 永久绑定

```python
from loguru import logger

# 创建带上下文的 logger
user_logger = logger.bind(user_id=123, service="auth")
user_logger.info("User logged in")
# Output: ... | user_id=123 service=auth | User logged in
```

### contextualize() - 临时上下文

```python
from loguru import logger


async def process_request(request_id: str):
    with logger.contextualize(request_id=request_id):
        logger.info("Processing request")
        await do_work()
        logger.info("Request completed")
    # 离开上下文后 request_id 自动移除
```

### 依赖注入中使用

```python
from typing import Annotated
from fastapi import Depends, Request
from loguru import logger


async def get_request_logger(request: Request):
    """为每个请求创建带上下文的 logger"""
    return logger.bind(
        request_id=request.headers.get("X-Request-ID", ""),
        path=request.url.path,
    )


RequestLogger = Annotated[logger.__class__, Depends(get_request_logger)]


@app.get("/users/{user_id}")
async def get_user(user_id: int, log: RequestLogger):
    log.info("Fetching user {}", user_id)
    # ...
```

---

## 异常日志

### 自动捕获异常

```python
from loguru import logger


@logger.catch(reraise=True)
async def risky_operation():
    result = 1 / 0
    return result


# 或使用装饰器
@app.get("/risky")
@logger.catch(message="Error in risky endpoint")
async def risky_endpoint():
    raise ValueError("Something went wrong")
```

### 手动记录异常

```python
try:
    await risky_operation()
except Exception:
    logger.exception("Operation failed")  # 自动包含堆栈
    raise
```

---

## 多 Worker 配置

### Gunicorn/Uvicorn 多进程

```python
import os
from loguru import logger


def setup_worker_logging():
    """每个 worker 独立的日志文件"""
    pid = os.getpid()

    logger.remove()
    logger.add(
        f"logs/worker_{pid}.log",
        rotation="100 MB",
        retention="7 days",
        enqueue=True,  # 异步写入，线程安全
    )
```

---

## 测试中捕获日志

```python
from contextlib import contextmanager
from loguru import logger


@contextmanager
def capture_logs(level="INFO"):
    """捕获日志用于测试断言"""
    output = []
    handler_id = logger.add(
        lambda m: output.append(m.record),
        level=level,
        format="{message}",
    )
    yield output
    logger.remove(handler_id)


def test_logging():
    with capture_logs() as logs:
        logger.info("Test message")

    assert len(logs) == 1
    assert logs[0]["message"] == "Test message"
```

---

## 最佳实践

1. **二阶段初始化** - 先初始化日志（默认配置），再加载配置，最后用配置重新初始化
2. **配置驱动** - 所有日志行为（级别、格式）由 `Settings` 控制
3. **异步队列** - 始终使用 `enqueue=True`，防止日志 I/O 成为性能瓶颈
4. **禁用 Uvicorn 默认配置** - 启动时使用 `--log-config=None`
5. **环境适配** - 通过 `LOG_JSON` 环境变量切换开发（彩色）和生产（JSON）格式
6. **移除默认处理器** - 使用 `logger.remove()` 避免重复日志
7. **统一日志** - 使用 `InterceptHandler` 拦截第三方库日志
8. **上下文绑定** - 使用 `bind()` 或 `contextualize()` 添加请求上下文
9. **异常记录** - 使用 `logger.exception()` 或 `@logger.catch`
10. **避免敏感信息** - 不要记录密码、token 等敏感数据
