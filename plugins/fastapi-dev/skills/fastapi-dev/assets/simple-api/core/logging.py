"""日志配置"""

import logging
import sys
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


def setup_logging(level: LogLevel = "INFO", *, json_format: bool = False) -> None:
    """
    配置日志

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式（生产环境建议开启）
    """
    logger.remove()
    logger.add(sys.stderr, level=level, serialize=json_format, enqueue=True)

    # 拦截标准库日志
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 降低第三方库日志级别
    for name in ["httpx", "httpcore", "uvicorn.access"]:
        logging.getLogger(name).setLevel(logging.WARNING)
