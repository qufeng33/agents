# FastAPI 日志（Loguru）

## 设计原则
- 先保证日志可用，再加载配置
- 统一日志入口，避免多套配置
- 生产环境结构化输出，开发环境易读输出
- 记录必要上下文，避免泄露敏感信息
- 日志不阻塞请求链路

## 最佳实践
1. 两阶段初始化（Bootstrap → Settings → 正式配置）
2. 正式阶段日志由配置驱动
3. 统一拦截标准 logging
4. 请求日志通过中间件注入上下文
5. 生产环境禁用 Uvicorn access log

## 目录
- `概述`
- `两阶段初始化`
- `日志配置`
- `日志相关配置`
- `上下文绑定`
- `测试中捕获日志`
- `启动命令`
- `相关文档`

---

## 概述

Loguru 是一个简单、强大的 Python 日志库，开箱即用。

```bash
uv add loguru
```

---

## 两阶段初始化

日志配置依赖 `Settings`，但配置加载可能失败，因此需要最小化 bootstrap 配置。

```
setup_bootstrap_logging()  # 最小日志
        ↓
get_settings()             # 可能失败
        ↓
setup_logging(settings)    # 正式配置
```

---

## 日志配置

```python
import logging
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_bootstrap_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=("<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}"),
        colorize=True,
    )


def setup_logging(
    *,
    level: LogLevel = "INFO",
    json_format: bool = False,
    to_file: bool = False,
    log_dir: str | Path = "logs",
) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, serialize=json_format, enqueue=True)

    if to_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        logger.add(Path(log_dir) / "app.log", level=level, enqueue=True, serialize=json_format)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)
```

> `InterceptHandler` 用于拦截标准库日志并转发到 Loguru，可按需实现。

---

## 日志相关配置

```python
class Settings(BaseSettings):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False
    log_to_file: bool = False
    log_dir: Path = Path("logs")
```

> 生产环境建议 `log_json=True`，便于日志采集系统解析。

---

## 上下文绑定

请求级别的上下文（如 `request_id`）由日志中间件注入，业务代码直接 `logger.info()` 即可。

---

## 测试中捕获日志

```python
from contextlib import contextmanager

from loguru import logger


@contextmanager
def capture_logs(level: str = "DEBUG"):
    output: list = []
    handler_id = logger.add(lambda m: output.append(m.record), level=level, format="{message}")
    try:
        yield output
    finally:
        logger.remove(handler_id)
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

---

## 相关文档

- [配置管理](./fastapi-config.md) - Settings
- [应用生命周期](./fastapi-app-lifecycle.md) - 启动流程
- [中间件](./fastapi-middleware.md) - 请求日志
