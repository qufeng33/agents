# FastAPI 认证

## 设计原则
- 密码永不明文存储
- Token 有效期短、可撤销
- 认证逻辑集中在安全模块
- 鉴权依赖注入，不下沉到路由
- 响应模型不泄露敏感字段

## 最佳实践
1. 密码哈希使用 Argon2
2. JWT 过期时间保持短（15–60 分钟）
3. 生产环境强制 HTTPS
4. 认证失败统一返回 401
5. Swagger OAuth2 使用标准 token 端点

## 目录
- `依赖安装`
- `OAuth2 + JWT 认证`
- `密码策略`
- `登录端点`
- `相关文档`

---

## 依赖安装

```bash
uv add pyjwt "pwdlib[argon2]"
```

---

## OAuth2 + JWT 认证

### 核心实现

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
password_hash = PasswordHash.recommended()


class Token(BaseModel):
    """OAuth2 token 响应"""
    access_token: str
    token_type: str = "bearer"


def verify_password(*, plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        sub = payload.get("sub")
        return UUID(sub) if sub is not None else None
    except (InvalidTokenError, ValueError, TypeError):
        return None
```

### 当前用户依赖

```python
# app/dependencies.py
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import InvalidCredentialsError
from app.core.security import decode_access_token
from app.modules.user.dependencies import get_user_repository
from app.modules.user.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token/raw")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    user_id = decode_access_token(token)
    if user_id is None:
        raise InvalidCredentialsError()

    user = await user_repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError()

    return user
```

> 认证依赖应放在 `dependencies.py`，避免在路由中编排鉴权逻辑。

### 配置示例

```python
class Settings(BaseSettings):
    secret_key: SecretStr  # 生成方式: openssl rand -hex 32
    access_token_expire_minutes: int = 30
```

---

## 密码策略

```python
import re
from pydantic import BaseModel, Field, field_validator


class PasswordMixin(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        return v
```

> 其余强度规则（小写/特殊字符/常见密码黑名单）按安全要求补充。

---

## 登录端点

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.response import ApiResponse
from app.core.security import Token
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

> Swagger OAuth2 如需标准 token 响应，可提供 `/token/raw` 端点。

---

## 相关文档

- [权限控制](./fastapi-permissions.md) - 角色、Scopes、敏感数据处理
- [中间件](./fastapi-middleware.md) - HTTPS 重定向、限流、安全响应头
