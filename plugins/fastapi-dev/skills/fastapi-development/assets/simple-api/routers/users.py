"""用户路由"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import DBSession
from app.schemas.user import UserCreate, UserResponse, UserList
from app.services.user_service import UserService

router = APIRouter()


def get_user_service(db: DBSession) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get("/", response_model=UserList)
async def list_users(
    service: UserServiceDep,
    skip: int = 0,
    limit: int = 20,
):
    """获取用户列表"""
    return await service.list(skip=skip, limit=limit)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, service: UserServiceDep):
    """创建用户"""
    return await service.create(user_in)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, service: UserServiceDep):
    """获取单个用户"""
    return await service.get(user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, service: UserServiceDep):
    """删除用户"""
    await service.delete(user_id)
