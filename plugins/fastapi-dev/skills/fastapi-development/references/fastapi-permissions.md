# FastAPI 权限控制

## 基于角色

```python
from uuid import UUID
from enum import Enum

from app.core.exceptions import ForbiddenError


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class RoleChecker:
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: CurrentUser) -> User:
        if user.role not in self.allowed_roles:
            raise ForbiddenError(message="Insufficient permissions")
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

---

## 基于 OAuth2 Scopes

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
# app/dependencies.py
from fastapi import Depends, Security
from fastapi.security import SecurityScopes

from app.core.security import decode_access_token_with_scopes
from app.core.exceptions import InvalidCredentialsError, ForbiddenError
from app.modules.user.repository import UserRepository


async def get_current_user_with_scopes(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    # 解码 token
    token_data = decode_access_token_with_scopes(token)
    if token_data is None:
        raise InvalidCredentialsError()

    user_id, token_scopes = token_data

    # 检查 scopes
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise ForbiddenError(message="Not enough permissions")

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError()
    return user


@router.get("/me", dependencies=[Security(get_current_user_with_scopes, scopes=["users:read"])])
async def read_own_user():
    ...


@router.put("/me", dependencies=[Security(get_current_user_with_scopes, scopes=["users:write"])])
async def update_own_user():
    ...
```

---

## 敏感数据处理

### 响应模型过滤

```python
from uuid import UUID

from app.modules.user.exceptions import UserNotFoundError


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
        raise UserNotFoundError(user_id=user_id)
    return ApiResponse(data=user)  # ApiResponse 的 data 按 UserResponse 过滤敏感字段
```

### 日志脱敏

```python
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

| 实践 | 说明 |
|------|------|
| **最小权限原则** | 只授予必要的权限 |
| **角色分离** | admin、moderator、user 职责清晰 |
| **Scopes 粒度** | 按资源和操作定义，如 `users:read`、`users:write` |
| **响应过滤** | 使用 response_model 排除敏感字段 |
| **日志脱敏** | 避免记录密码、token 等 |

---

## 相关文档

- [认证](./fastapi-authentication.md) - OAuth2 + JWT、API Key
- [错误处理](./fastapi-errors.md) - ForbiddenError、UnauthorizedError
