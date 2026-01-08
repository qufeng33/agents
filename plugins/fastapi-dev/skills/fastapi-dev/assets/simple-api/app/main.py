"""
简单 FastAPI 项目模板 - 按层组织
适用于：小项目、原型验证、单人开发

特点：
- 直接在 main.py 配置，无需 setup_xxx 抽象
- 路由直接 include，简单明了
- 适合快速迭代
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.database import close_database, init_database
from app.core.exception_handlers import setup_exception_handlers
from app.core.logging import setup_logging
from app.core.middlewares import setup_middlewares
from app.routers import users
from app.schemas.response import ApiResponse

settings = get_settings()

# 初始化日志（在 settings 加载后）
setup_logging(
    level=settings.log_level,
    json_format=settings.log_json,
    to_file=settings.log_to_file,
    log_dir=settings.log_dir,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动：验证数据库连接
    await init_database()
    yield
    # 关闭：释放连接池
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# 中间件
setup_middlewares(app)

# 路由（直接注册）
app.include_router(users.router, prefix="/users", tags=["users"])

# 异常处理
setup_exception_handlers(app)


@app.get("/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"status": "ok"})
