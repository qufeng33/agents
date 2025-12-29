"""API v1 路由聚合"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.user.router import router as user_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(user_router, prefix="/app_users", tags=["app_users"])
# 添加其他模块路由：
# from app.modules.item.router import router as item_router
# api_router.include_router(item_router, prefix="/items", tags=["items"])
