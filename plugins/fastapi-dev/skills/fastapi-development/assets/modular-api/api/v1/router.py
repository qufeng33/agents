"""API v1 路由聚合"""

from fastapi import APIRouter

from app.modules.user.router import router as user_router
from app.modules.item.router import router as item_router

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["users"])
api_router.include_router(item_router, prefix="/items", tags=["items"])
