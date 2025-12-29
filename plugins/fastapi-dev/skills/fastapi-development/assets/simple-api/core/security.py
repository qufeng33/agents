"""安全工具

依赖安装: uv add pyjwt "pwdlib[argon2]"
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from pwdlib import PasswordHash

from app.config import get_settings

settings = get_settings()

# 使用推荐的 Argon2 算法
password_hash = PasswordHash.recommended()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(password: str) -> str:
    """密码哈希"""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return password_hash.verify(hashed_password, plain_password)


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm="HS256"
    )


def decode_access_token(token: str) -> UUID | None:
    """解码 JWT token，返回 user_id（UUID），无效则返回 None"""
    try:
        payload = jwt.decode(
            token, settings.secret_key.get_secret_value(), algorithms=["HS256"]
        )
        sub = payload.get("sub")
        return UUID(sub) if sub else None
    except (InvalidTokenError, ValueError, TypeError):
        return None
