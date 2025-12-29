"""
模块化 FastAPI 项目模板 - 按领域组织
适用于：中大型项目、团队开发、长期维护

特点：
- create_app 工厂模式，便于测试和多实例
- setup_xxx 函数分离注册逻辑
- 支持 API 版本管理
- 三层架构：Router → Service → Repository
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import close_database, init_database
from app.core.middlewares import setup_middlewares
from app.core.routers import setup_routers
from app.core.exception_handlers import setup_exception_handlers
from app.schemas.response import ApiResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化
    await init_database()
    yield
    # 关闭时清理
    await close_database()


def create_app() -> FastAPI:
    """应用工厂函数"""
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # 注册组件（顺序重要）
    setup_middlewares(application)
    setup_routers(application)
    setup_exception_handlers(application)

    return application


app = create_app()


@app.get("/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"status": "ok"})
