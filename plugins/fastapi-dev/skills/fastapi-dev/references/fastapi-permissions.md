# FastAPI 权限控制
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 最小权限原则
- 认证与授权分离
- 权限判断集中在依赖层
- 敏感数据默认不输出
- 审计与日志脱敏并行

## 最佳实践
1. 角色与权限边界清晰
2. Scopes 粒度与资源一致
3. 统一错误响应与状态码
4. 响应模型过滤敏感字段
5. 日志脱敏避免泄露

## 目录
- `基于角色`
- `基于 OAuth2 Scopes`
- `敏感数据处理`
- `相关文档`

---

## 基于角色

```python
from enum import Enum
from uuid import UUID

from app.core.exceptions import ForbiddenError


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class RoleChecker:
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: CurrentUser) -> User:
        if user.role not in self.allowed_roles:
            raise ForbiddenError(message="Insufficient permissions")
        return user


allow_admin = RoleChecker([Role.ADMIN])


@router.delete("/users/{user_id}")
async def delete_user(user_id: UUID, admin: Annotated[User, Depends(allow_admin)]):
    ...
```

> 角色检查建议在依赖层实现，路由只声明所需权限。

---

## 基于 OAuth2 Scopes

```python
def decode_access_token_with_scopes(token: str) -> tuple[UUID, list[str]] | None:
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        sub = payload.get("sub")
        scopes = payload.get("scopes", [])
        return UUID(sub), scopes if sub else None
    except (InvalidTokenError, ValueError, TypeError):
        return None
```

```python
from fastapi import Security
from fastapi.security import SecurityScopes

async def get_current_user_with_scopes(security_scopes: SecurityScopes, token: str, ...) -> User:
    ...


@router.get("/me", dependencies=[Security(get_current_user_with_scopes, scopes=["users:read"])])
async def read_own_user():
    ...
```

> Scopes 建议按资源+操作定义（如 `users:read`、`users:write`）。

---

## 敏感数据处理

### 响应模型过滤

响应模型应排除敏感字段（如 `hashed_password`）。

### 日志脱敏

```python
def sanitize_log(data: dict) -> dict:
    sensitive_keys = {"password", "token", "secret"}
    return {k: "***" if k.lower() in sensitive_keys else v for k, v in data.items()}
```

---

## 相关文档

- [认证](./fastapi-authentication.md) - OAuth2 + JWT
- [错误处理](./fastapi-errors.md) - ForbiddenError、UnauthorizedError
