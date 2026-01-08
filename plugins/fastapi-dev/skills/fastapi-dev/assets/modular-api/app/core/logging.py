"""日志配置"""

import logging
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class InterceptHandler(logging.Handler):
    """拦截标准库日志并转发到 Loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
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
    Bootstrap 阶段日志配置

    在加载 Settings 之前使用，确保配置加载失败时也能输出日志。
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<dim>{time:HH:mm:ss}</dim> | <level>{level: <8}</level> | {message}",
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
    配置日志（正式阶段）

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式（生产环境建议开启）
        to_file: 是否输出到文件
        log_dir: 日志文件目录
    """
    logger.remove()
    logger.add(sys.stderr, level=level, serialize=json_format, enqueue=True)

    if to_file:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        logger.add(
            Path(log_dir) / "app.log",
            level=level,
            serialize=json_format,
            enqueue=True,
            rotation="10 MB",
            retention="7 days",
        )

    # 拦截标准库日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 降低第三方库日志级别
    for name in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)
