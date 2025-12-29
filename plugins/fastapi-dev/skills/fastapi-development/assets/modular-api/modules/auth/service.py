"""认证模块 - 业务逻辑层"""

from app.core.exceptions import InvalidCredentialsError
from app.core.security import Token, create_access_token, verify_password
from app.modules.user.repository import UserRepository


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def authenticate(self, email: str, password: str) -> Token:
        """校验用户凭证并签发 access token"""
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        access_token = create_access_token(data={"sub": str(user.id)})
        return Token(access_token=access_token)
