"""路由配置"""

from fastapi import FastAPI

from app.api.v1.router import api_router


def setup_routers(app: FastAPI) -> None:
    """注册路由"""
    app.include_router(api_router, prefix="/api/v1")
