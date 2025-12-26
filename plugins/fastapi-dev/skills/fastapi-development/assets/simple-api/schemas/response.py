"""统一响应模型"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """单个对象响应"""

    code: int = 0
    message: str = "success"
    data: T


class ApiPagedResponse(BaseModel, Generic[T]):
    """分页列表响应"""

    code: int = 0
    message: str = "success"
    data: list[T]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """错误响应"""

    code: int
    message: str
    data: None = None
    detail: dict | None = None
