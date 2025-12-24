"""用户模块 - 异常"""

from app.exceptions import AppException


class UserNotFoundError(AppException):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"User with id {user_id} not found",
            status_code=404,
        )


class UserAlreadyExistsError(AppException):
    def __init__(self, email: str) -> None:
        super().__init__(
            code="USER_ALREADY_EXISTS",
            message=f"User with email {email} already exists",
            status_code=409,
        )
