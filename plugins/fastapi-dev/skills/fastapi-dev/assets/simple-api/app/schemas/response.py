"""统一响应模型"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    所有 Schema 的基类

    特性：
    - from_attributes: 支持 ORM 模型转换
    - str_strip_whitespace: 自动去除字符串首尾空白

    注意：datetime 字段请使用 UTCDateTime 类型（见 datetime_types.py）
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


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
