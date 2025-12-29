"""认证模块 - 路由"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import Token
from app.schemas.response import ApiResponse
from .dependencies import AuthServiceDep

router = APIRouter()


@router.post("/token", response_model=ApiResponse[Token])
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDep,
) -> ApiResponse[Token]:
    """登录并获取 access token"""
    token = await auth_service.authenticate(form_data.username, form_data.password)
    return ApiResponse(data=token)
