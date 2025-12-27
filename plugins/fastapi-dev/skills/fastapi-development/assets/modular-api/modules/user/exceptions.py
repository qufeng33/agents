"""用户模块 - 异常"""

from uuid import UUID

from app.core.exceptions import NotFoundError, ConflictError
from app.core.error_codes import ErrorCode


class UserNotFoundError(NotFoundError):
    """用户不存在"""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            code=ErrorCode.USER_NOT_FOUND,
            message="用户不存在",
            detail={"user_id": str(user_id)},
        )


class EmailAlreadyExistsError(ConflictError):
    """邮箱已注册"""

    def __init__(self, email: str) -> None:
        super().__init__(
            code=ErrorCode.EMAIL_ALREADY_EXISTS,
            message="邮箱已注册",
            detail={"email": email},
        )
