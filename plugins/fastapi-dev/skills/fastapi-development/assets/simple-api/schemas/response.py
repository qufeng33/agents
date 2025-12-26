"""统一响应模型"""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_serializer

T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    所有 Schema 的基类

    特性：
    - from_attributes: 支持 ORM 模型转换
    - str_strip_whitespace: 自动去除字符串首尾空白
    - datetime 序列化为 ISO8601 格式（Z 后缀）
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    @field_serializer("*", mode="wrap")
    def serialize_datetime(self, value, handler):
        """datetime 序列化为 ISO8601 格式（Z 后缀）"""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        return handler(value)


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
