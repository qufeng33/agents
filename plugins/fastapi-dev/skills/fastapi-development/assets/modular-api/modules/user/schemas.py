"""用户模块 - Schema"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.response import BaseSchema


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)


class UserResponse(BaseSchema):
    """用户响应模型"""

    id: UUID
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserDetailResponse(UserResponse):
    """用户详情响应（含审计信息）"""

    created_by: UUID | None = None
    updated_by: UUID | None = None
    deleted_at: datetime | None = None
