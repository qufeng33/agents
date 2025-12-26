"""业务异常定义"""

from app.core.error_codes import ErrorCode


class ApiError(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        status_code: int = 400,
        detail: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message or code.name.replace("_", " ").title()
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(ApiError):
    """资源不存在"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
        message: str = "Resource not found",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=404, detail=detail)


class ValidationError(ApiError):
    """业务验证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.INVALID_PARAMETER,
        message: str = "Validation failed",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=400, detail=detail)


class ConflictError(ApiError):
    """资源冲突"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.DUPLICATE_ENTRY,
        message: str = "Resource conflict",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=409, detail=detail)


class UnauthorizedError(ApiError):
    """认证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        message: str = "Unauthorized",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=401, detail=detail)
