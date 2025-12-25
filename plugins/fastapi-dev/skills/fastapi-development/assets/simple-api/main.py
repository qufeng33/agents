"""
简单 FastAPI 项目模板 - 按层组织
适用于：小项目、原型验证、单人开发
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import close_database, init_database
from app.core.middlewares import setup_middlewares
from app.core.routers import setup_routers
from app.exceptions import setup_exception_handlers

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


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
