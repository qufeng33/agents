# FastAPI 安全性

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
from app.schemas.response import ApiResponse

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
# core/dependencies.py
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token
from app.modules.user.repository import UserRepository
from app.modules.user.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception

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
    access_token_expire_minutes: int = 30
```

### AuthService

```python
# modules/auth/service.py
from app.core.security import verify_password, create_access_token, Token
from app.modules.user.repository import UserRepository
from app.modules.auth.exceptions import InvalidCredentialsError


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


class PasswordChange(BaseModel):
    """修改密码"""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # 复用相同逻辑
        return PasswordMixin.validate_password_strength(v)
```

> 💡 **提示**：密码验证在 Pydantic schema 层完成，确保所有入口（注册、修改密码）统一校验。

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
from fastapi import Security
from fastapi.security import APIKeyHeader, APIKeyQuery

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return api_key


ValidAPIKey = Annotated[str, Depends(get_api_key)]


@router.get("/protected")
async def protected_route(api_key: ValidAPIKey):
    return {"message": "Access granted"}
```

---

## 权限控制

### 基于角色

```python
from uuid import UUID
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class RoleChecker:
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: CurrentUser) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user


# 创建权限检查器
allow_admin = RoleChecker([Role.ADMIN])
allow_moderator = RoleChecker([Role.ADMIN, Role.MODERATOR])


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(allow_admin)],
):
    # 只有 admin 可访问
    ...
```

### 基于 OAuth2 Scopes

```python
# core/security.py（扩展）
from uuid import UUID


def decode_access_token_with_scopes(token: str) -> tuple[UUID, list[str]] | None:
    """解码 token，返回 (user_id, scopes)，无效则返回 None"""
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        sub = payload.get("sub")
        if sub is None:
            return None
        scopes = payload.get("scopes", [])
        return UUID(sub), scopes
    except (InvalidTokenError, ValueError, TypeError):
        return None
```

```python
# core/dependencies.py
from fastapi import Security
from fastapi.security import SecurityScopes

from app.core.security import decode_access_token_with_scopes
from app.modules.user.repository import UserRepository


async def get_current_user_with_scopes(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    authenticate_value = "Bearer"
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    # 解码 token
    token_data = decode_access_token_with_scopes(token)
    if token_data is None:
        raise credentials_exception

    user_id, token_scopes = token_data

    # 检查 scopes
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


@router.get("/me", dependencies=[Security(get_current_user_with_scopes, scopes=["users:read"])])
async def read_own_user():
    ...


@router.put("/me", dependencies=[Security(get_current_user_with_scopes, scopes=["users:write"])])
async def update_own_user():
    ...
```

---

## CORS 配置

CORS（跨域资源共享）是 Web 安全的重要组成部分，控制哪些域可以访问 API。

**关键配置项**：

| 参数 | 说明 |
|------|------|
| `allow_origins` | 允许的源列表（为空时不启用 CORS） |
| `allow_credentials` | 是否允许携带 Cookie |
| `allow_methods` | 允许的 HTTP 方法 |
| `expose_headers` | 允许前端访问的响应头 |

> 完整配置示例和配置驱动模式详见 [中间件 - CORS](./fastapi-middleware.md#cors-中间件)

---

## Host Header 验证

防止 Host Header 攻击：

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com", "localhost"],
)
```

---

## HTTPS 重定向

```python
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

# 生产环境强制 HTTPS
if not settings.debug:
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

## 请求限流

可在 `core/middlewares.py` 的 `setup_middlewares` 中配置：

```python
# core/middlewares.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)


def setup_middleware(app: FastAPI) -> None:
    # 限流配置（slowapi 要求挂载到 app.state）
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    # 其他中间件...
```

```python
# 在路由中使用
from fastapi import APIRouter

from app.core.middleware import limiter

router = APIRouter()


@router.get("/limited")
@limiter.limit("10/minute")
async def limited_route(request: Request):
    return {"message": "This route is rate limited"}
```

---

## 安全响应头

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

---

## 敏感数据处理

### 响应模型过滤

```python
from uuid import UUID


class UserInDB(BaseModel):
    id: UUID
    email: str
    hashed_password: str  # 敏感字段


class UserResponse(BaseModel):
    id: UUID
    email: str
    # 不包含 hashed_password


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep):
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ApiResponse(data=user)  # ApiResponse 的 data 按 UserResponse 过滤敏感字段
```

### 日志脱敏

```python
import re


def sanitize_log(data: dict) -> dict:
    """移除敏感字段"""
    sensitive_keys = {"password", "token", "secret", "api_key"}
    return {
        k: "***" if k.lower() in sensitive_keys else v
        for k, v in data.items()
    }
```

---

## 最佳实践

1. **永远不存储明文密码** - 使用 Argon2（推荐）或 bcrypt
2. **JWT 过期时间要短** - 建议 15-60 分钟
3. **使用 HTTPS** - 生产环境必须
4. **验证所有输入** - Pydantic + 自定义验证
5. **响应模型过滤** - 永远不返回敏感数据
6. **Host Header 验证** - 防止 DNS 重绑定攻击
7. **限流** - 防止暴力破解和 DDoS
8. **安全响应头** - XSS、点击劫持防护
