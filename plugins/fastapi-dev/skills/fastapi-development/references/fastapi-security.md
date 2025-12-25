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


def decode_access_token(token: str) -> int | None:
    """解码 token，返回 user_id，无效则返回 None"""
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        return payload.get("sub")
    except InvalidTokenError:
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

        access_token = create_access_token(data={"sub": user.id})
        return Token(access_token=access_token)
```

### 登录端点

```python
# modules/auth/router.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import Token
from .service import AuthService
from .dependencies import get_auth_service
from .exceptions import InvalidCredentialsError

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        return await auth_service.authenticate(form_data.username, form_data.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
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


@app.get("/protected")
async def protected_route(api_key: ValidAPIKey):
    return {"message": "Access granted"}
```

---

## 权限控制

### 基于角色

```python
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


@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(allow_admin)],
):
    # 只有 admin 可访问
    ...
```

### 基于 OAuth2 Scopes

```python
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

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://myapp.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=600,  # 预检请求缓存时间（秒）
)
```

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

可在 `core/middleware.py` 的 `setup_middleware` 中配置：

```python
# core/middleware.py
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
from app.core.middleware import limiter


@app.get("/limited")
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
class UserInDB(BaseModel):
    id: int
    email: str
    hashed_password: str  # 敏感字段


class UserResponse(BaseModel):
    id: int
    email: str
    # 不包含 hashed_password


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, service: UserServiceDep):
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user  # FastAPI 根据 response_model 自动过滤 hashed_password
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
