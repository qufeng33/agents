"""全局异常处理"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """资源不存在"""

    def __init__(self, resource: str, resource_id: Any) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
            details={"resource": resource, "id": resource_id},
        )


class ValidationError(AppException):
    """业务验证失败"""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details={"field": field} if field else {},
        )


class ConflictError(AppException):
    """资源冲突"""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=409,
        )


class AuthenticationError(AppException):
    """认证失败"""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="AUTHENTICATION_ERROR",
            message=message,
            status_code=401,
        )


class AuthorizationError(AppException):
    """权限不足"""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(
            code="AUTHORIZATION_ERROR",
            message=message,
            status_code=403,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """业务异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""
    app.add_exception_handler(AppException, app_exception_handler)
