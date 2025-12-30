"""用户模块 - 异常"""

from uuid import UUID

from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.core.error_codes import ErrorCode


class UserNotFoundError(NotFoundError):
    """用户不存在"""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            code=ErrorCode.USER_NOT_FOUND,
            message="用户不存在",
            detail={"user_id": str(user_id)},
        )


class UsernameAlreadyExistsError(ConflictError):
    """用户名已存在"""

    def __init__(self, username: str) -> None:
        super().__init__(
            code=ErrorCode.USERNAME_ALREADY_EXISTS,
            message="用户名已存在",
            detail={"username": username},
        )


class UserDisabledError(ForbiddenError):
    """用户已禁用"""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.USER_DISABLED,
            message="用户已被禁用",
        )
