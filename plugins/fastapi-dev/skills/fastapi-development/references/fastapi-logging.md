# FastAPI 日志（Loguru）

## 概述

Loguru 是一个简单、强大的 Python 日志库，开箱即用，无需繁琐配置。

```bash
uv add loguru
```

---

## 核心架构：两阶段初始化

### 为什么需要两阶段？

日志配置依赖 `Settings`，但加载 `Settings` 本身可能失败（如缺少环境变量），此时需要日志来输出错误信息。这是一个"鸡生蛋"问题。

**解决方案**：两阶段初始化

```
setup_bootstrap_logging()     # 阶段1: 最小化配置，确保日志可用
        ↓
get_settings()               # 可能失败，失败时有日志输出
        ↓
setup_logging(settings)      # 阶段2: 根据配置正式初始化
```

### 目录结构

```
app/
├── main.py              # 应用入口，两阶段初始化
├── config.py            # Settings 定义
└── core/
    └── logging.py       # 日志配置
```

---

## 日志系统 (app/core/logging.py)

```python
import logging
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


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


def setup_bootstrap_logging() -> None:
    """
    引导阶段日志配置。

    在 Settings 加载前调用，确保配置加载失败时有日志输出。
    使用固定配置，不依赖任何外部配置。
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=(
            "<dim>{time:HH:mm:ss}</dim> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )


def setup_logging(
    *,
    level: LogLevel = "INFO",
    json_format: bool = False,
    to_file: bool = False,
    log_dir: str | Path = "logs",
) -> None:
    """
    正式日志配置。

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式（生产环境）
        to_file: 是否输出到文件
        log_dir: 日志文件目录
    """
    # 1. 清除所有 handler（包括 bootstrap 阶段的）
    logger.remove()

    # 2. 控制台输出
    if json_format:
        # 生产环境：结构化 JSON
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,
            enqueue=True,
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

    # 3. 文件输出（可选）
    if to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path / "app.log",
            level=level,
            rotation="100 MB",
            retention="7 days",
            compression="zip",
            enqueue=True,
            serialize=json_format,  # 文件格式与控制台一致
        )

    # 4. 拦截标准库日志（uvicorn、httpx 等）
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 5. 降低第三方库日志级别
    for name in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    logger.debug(
        "Logging initialized | level={} json={} file={}",
        level,
        json_format,
        to_file,
    )
```

---

## 日志相关配置

在 `Settings` 中添加日志相关字段：

```python
from pathlib import Path
from typing import Literal

class Settings(BaseSettings):
    # ... 其他配置

    # 日志配置
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False      # 生产环境设为 True
    log_to_file: bool = False
    log_dir: Path = Path("logs")
```

`get_settings()` 中捕获验证错误并使用 logger 输出：

```python
@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        # 此时 bootstrap logging 已生效
        missing = ["/".join(map(str, err.get("loc", []))) for err in exc.errors()]
        logger.critical("缺少必要的环境变量: {}", ", ".join(missing))
        raise RuntimeError("配置加载失败") from None
```

> 完整配置管理详见 [配置管理](./fastapi-config.md)

> 完整应用启动流程详见 [应用启动与初始化](./fastapi-startup.md)
>
> 请求日志中间件详见 [中间件](./fastapi-middleware.md)

---

## 上下文绑定

请求级别的上下文（如 `request_id`）由 `LoggingMiddleware` 通过 `contextualize()` 自动处理。

业务代码中直接使用 logger 即可：

```python
from loguru import logger


class UserService:
    async def get_by_id(self, user_id: int) -> User | None:
        logger.info("Fetching user {}", user_id)  # 自动带上 request_id
        return await self.repo.get_by_id(user_id)
```

> 详见 [中间件 - 请求日志](./fastapi-middleware.md)

---

## 测试中捕获日志

```python
from collections.abc import Generator
from contextlib import contextmanager

from loguru import logger


@contextmanager
def capture_logs(level: str = "DEBUG") -> Generator[list, None, None]:
    """捕获日志用于测试断言"""
    output: list = []
    handler_id = logger.add(
        lambda m: output.append(m.record),
        level=level,
        format="{message}",
    )
    try:
        yield output
    finally:
        logger.remove(handler_id)


def test_logging():
    with capture_logs() as logs:
        logger.info("Test message")

    assert len(logs) == 1
    assert logs[0]["message"] == "Test message"
```

---

## 启动命令

禁用 Uvicorn 默认 access log（使用自定义日志中间件）：

```bash
# 开发
uvicorn app.main:app --reload --no-access-log

# 生产
uvicorn app.main:app --workers 4 --no-access-log
```

或在代码中：

```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", access_log=False)
```

**为什么禁用 access log？** 详见 [中间件 - 请求日志](./fastapi-middleware.md)

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **两阶段初始化** | Bootstrap → Settings → 正式配置 |
| **Bootstrap 固定配置** | 不依赖外部配置，确保始终可用 |
| **配置驱动** | 正式阶段日志行为由 `Settings` 控制 |
| **异步队列** | 始终 `enqueue=True`，防止 I/O 阻塞 |
| **统一拦截** | `InterceptHandler` 拦截第三方库日志 |
| **上下文绑定** | `contextualize()` 用于请求，`bind()` 用于持久绑定 |
| **禁用 access log** | `--no-access-log`，使用自定义日志中间件 |
| **环境适配** | 开发用彩色，生产用 JSON |
| **敏感信息** | 不记录密码、token 等 |
