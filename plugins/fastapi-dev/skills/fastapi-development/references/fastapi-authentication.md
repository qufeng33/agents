# FastAPI 认证

## 依赖安装

```bash
# JWT + 密码哈希（推荐 Argon2）
uv add pyjwt "pwdlib[argon2]"
```

---

## OAuth2 + JWT 认证

### 完整实现

```python
# core/security.py
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel
from pwdlib import PasswordHash

from app.config import get_settings

settings = get_settings()

# 密码哈希（使用 Argon2 算法）
password_hash = PasswordHash.recommended()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> UUID | None:
    """解码 token，返回 user_id，无效则返回 None"""
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        sub = payload.get("sub")
        return UUID(sub) if sub is not None else None
    except (InvalidTokenError, ValueError, TypeError):
        return None
```

```python
# app/dependencies.py
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token
from app.core.exceptions import InvalidCredentialsError
from app.modules.user.exceptions import UserDisabledError
from app.modules.user.repository import UserRepository
from app.modules.user.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise InvalidCredentialsError()

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UserDisabledError()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

### 配置示例

```python
# app/config.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 生成方式: openssl rand -hex 32
    secret_key: SecretStr
    api_key: SecretStr
    access_token_expire_minutes: int = 30
```

### AuthService

```python
# modules/auth/service.py
from app.core.security import verify_password, create_access_token, Token
from app.modules.user.repository import UserRepository
from app.core.exceptions import InvalidCredentialsError


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def authenticate(self, email: str, password: str) -> Token:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        access_token = create_access_token(data={"sub": str(user.id)})
        return Token(access_token=access_token)
```

### 密码策略

在用户注册/修改密码时验证密码强度：

```python
# modules/user/schemas.py
import re

from pydantic import BaseModel, Field, field_validator


class PasswordMixin(BaseModel):
    """密码验证 Mixin"""

    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("密码必须包含至少一个特殊字符")
        return v


class UserCreate(PasswordMixin):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
```

> 密码验证在 Pydantic schema 层完成，确保所有入口（注册、修改密码）统一校验。

### 登录端点

```python
# modules/auth/router.py
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import Token
from app.schemas.response import ApiResponse
from .service import AuthService
from .dependencies import get_auth_service

router = APIRouter()


@router.post("/token", response_model=ApiResponse[Token])
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    token = await auth_service.authenticate(form_data.username, form_data.password)
    return ApiResponse(data=token)
```

---

## API Key 认证

```python
from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, APIKeyQuery

from app.core.exceptions import UnauthorizedError, ForbiddenError

# Header 方式
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Query 方式
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


async def get_api_key(
    api_key_header: str | None = Security(api_key_header),
    api_key_query: str | None = Security(api_key_query),
) -> str:
    api_key = api_key_header or api_key_query
    if not api_key:
        raise UnauthorizedError(message="API key required")
    if api_key != settings.api_key.get_secret_value():
        raise ForbiddenError(message="Invalid API key")
    return api_key


ValidAPIKey = Annotated[str, Depends(get_api_key)]


@router.get("/protected")
async def protected_route(api_key: ValidAPIKey):
    return {"message": "Access granted"}
```

---

## 最佳实践

1. **永远不存储明文密码** - 使用 Argon2（推荐）或 bcrypt
2. **JWT 过期时间要短** - 建议 15-60 分钟
3. **使用 HTTPS** - 生产环境必须
4. **验证所有输入** - Pydantic + 自定义验证
5. **响应模型过滤** - 永远不返回敏感数据

---

## 相关文档

- [权限控制](./fastapi-permissions.md) - 角色、Scopes、敏感数据处理
- [中间件](./fastapi-middleware.md) - HTTPS 重定向、限流、安全响应头
