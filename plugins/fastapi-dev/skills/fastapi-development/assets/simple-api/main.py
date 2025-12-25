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
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.database import async_engine, Base
from app.routers import users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动：开发环境自动创建表
    if settings.debug:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭：释放连接池
    await async_engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

# 中间件（直接配置）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由（直接注册）
app.include_router(users.router, prefix="/users", tags=["users"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
