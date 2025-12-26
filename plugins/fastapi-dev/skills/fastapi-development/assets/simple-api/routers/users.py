"""用户路由"""

from fastapi import APIRouter, Query, status

from app.dependencies import UserServiceDep
from app.schemas.response import ApiResponse, ApiPagedResponse
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


@router.get("/", response_model=ApiPagedResponse[UserResponse])
async def list_users(
    service: UserServiceDep,
    page: int = Query(default=0, ge=0, description="页码（从 0 开始）"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiPagedResponse[UserResponse]:
    """获取用户列表"""
    users, total = await service.list(page=page, page_size=page_size)
    return ApiPagedResponse(data=users, total=total, page=page, page_size=page_size)


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    service: UserServiceDep,
) -> ApiResponse[UserResponse]:
    """创建用户"""
    user = await service.create(user_in)
    return ApiResponse(data=user)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: int,
    service: UserServiceDep,
) -> ApiResponse[UserResponse]:
    """获取单个用户"""
    user = await service.get(user_id)
    return ApiResponse(data=user)


@router.delete("/{user_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    service: UserServiceDep,
) -> ApiResponse[None]:
    """删除用户"""
    await service.delete(user_id)
    return ApiResponse(data=None, message="User deleted")
