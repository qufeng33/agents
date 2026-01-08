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
        message: str = "资源不存在",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=404, detail=detail)


class ValidationError(ApiError):
    """业务验证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.INVALID_PARAMETER,
        message: str = "验证失败",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=400, detail=detail)


class ConflictError(ApiError):
    """资源冲突"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.DUPLICATE_ENTRY,
        message: str = "资源冲突",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=409, detail=detail)


class UnauthorizedError(ApiError):
    """认证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        message: str = "认证失败",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=401, detail=detail)


class InvalidCredentialsError(UnauthorizedError):
    """凭证无效"""

    def __init__(
        self,
        message: str = "凭证无效",
        detail: dict | None = None,
    ) -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, detail)


class ForbiddenError(ApiError):
    """权限不足"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.FORBIDDEN,
        message: str = "权限不足",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=403, detail=detail)


class UserDisabledError(ForbiddenError):
    """用户已禁用"""

    def __init__(
        self,
        message: str = "用户已禁用",
        detail: dict | None = None,
    ) -> None:
        super().__init__(ErrorCode.USER_DISABLED, message, detail)


class ServiceUnavailableError(ApiError):
    """服务不可用"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE,
        message: str = "服务不可用",
        detail: dict | None = None,
    ) -> None:
        super().__init__(code, message, status_code=503, detail=detail)
