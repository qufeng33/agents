"""路由配置"""

from fastapi import FastAPI

from app.routers import users


def setup_routers(app: FastAPI) -> None:
    """注册路由"""
    app.include_router(users.router, prefix="/api/users", tags=["users"])
