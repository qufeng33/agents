# FastAPI 依赖注入
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。


## 基本用法（Annotated 推荐）

```python
from typing import Annotated
from fastapi import APIRouter, Depends, Query

router = APIRouter()


def pagination(
    page: int = Query(default=0, ge=0, description="页码（从 0 开始）"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return {"page": page, "page_size": page_size}

Pagination = Annotated[dict, Depends(pagination)]

@router.get("/items/")
async def list_items(params: Pagination):
    return params  # {"page": 0, "page_size": 20}
```

---

## 依赖链

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer

from app.schemas.response import ApiResponse
from app.schemas.user import UserResponse
from app.models.user import User  # 模块化结构改为 app.modules.user.models
from app.core.exceptions import UnauthorizedError
from app.core.error_codes import ErrorCode


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token/raw")


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    user = await decode_token(token)
    if not user:
        raise UnauthorizedError(code=ErrorCode.TOKEN_INVALID, message="Invalid token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


router = APIRouter()


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(user: CurrentUser) -> ApiResponse[UserResponse]:
    return ApiResponse(data=UserResponse.model_validate(user))
```

说明：
- 使用 `OAuth2PasswordBearer` 由框架解析 `Authorization`，避免自行处理头部格式。
- `tokenUrl` 指向 OAuth2 规范的 raw token 接口；如果项目统一使用 `ApiResponse`，401 仍需携带 `WWW-Authenticate` 头，可由异常处理器统一补齐。

---

## 依赖放置位置

依赖注入函数和类型别名应该放在 `dependencies.py`，**不要放在 router 或 service 里**。

| 结构 | 位置 | 说明 |
|------|------|------|
| **简单结构** | `dependencies.py`（全局） | 集中管理所有依赖 |
| **模块化结构** | `modules/xxx/dependencies.py` | 模块自包含 |

**原因：**
- **避免重复**：多个 router 可能使用同一个 Service
- **职责分离**：router 只做 HTTP 处理，service 只做业务逻辑
- **避免循环导入**：dependencies 作为独立层，打破循环依赖

**简单结构示例：**

```python
# dependencies.py
from app.services.user_service import UserService

DBSession = Annotated[AsyncSession, Depends(get_db)]

def get_user_service(db: DBSession) -> UserService:
    return UserService(db)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

```python
# routers/users.py（只导入依赖，不定义）
from uuid import UUID

from app.dependencies import UserServiceDep

@router.get("/{user_id}")
async def get_user(user_id: UUID, service: UserServiceDep):
    ...
```

**模块化结构示例：**

```python
# modules/user/dependencies.py
def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)

def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repo)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

---

## yield 依赖（资源管理）

`yield` 依赖用于管理需要清理的资源（数据库连接、HTTP 客户端等）。

```python
async def get_resource() -> AsyncGenerator[Resource, None]:
    resource = await create_resource()
    try:
        yield resource      # 请求处理期间使用
    finally:
        await resource.close()  # 请求结束后清理
```

> **数据库 Session 依赖**：完整的 `get_db()` 实现（含事务管理）详见 [数据库配置](./fastapi-database-setup.md)

---

## 类作为依赖

```python
from uuid import UUID

from app.core.exceptions import ForbiddenError
from app.core.error_codes import ErrorCode


class PermissionChecker:
    def __init__(self, permissions: list[str]):
        self.permissions = permissions

    def __call__(self, user: CurrentUser) -> User:
        for p in self.permissions:
            if p not in user.permissions:
                raise ForbiddenError(
                    code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                    message=f"Missing permission: {p}",
                )
        return user


require_admin = PermissionChecker(["admin"])


@router.delete("/users/{user_id}", response_model=ApiResponse[None])
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    service: UserServiceDep,
) -> ApiResponse[None]:
    await service.delete(user_id)
    return ApiResponse(data=None, message="User deleted")
```

---

## 依赖缓存

同一请求中相同依赖只执行一次（共享实例）。

```python
# 禁用缓存：每次都创建新实例
@router.get("/items/")
async def items(val: Annotated[str, Depends(get_random, use_cache=False)]):
    ...
```

---

## 路由级依赖

```python
router = APIRouter(dependencies=[Depends(get_current_user)])
app = FastAPI(dependencies=[Depends(get_current_user)])
```

---

## 资源存在性验证

通过依赖注入进行资源验证，不存在时抛出模块级异常。

```python
# modules/item/dependencies.py
from uuid import UUID
from typing import Annotated

from fastapi import Depends

from .service import ItemService
from .exceptions import ItemNotFoundError


def get_item_service(
    repo: Annotated[ItemRepository, Depends(get_item_repository)],
) -> ItemService:
    return ItemService(repo)


async def get_item_or_404(
    item_id: UUID,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> Item:
    item = await service.get_by_id(item_id)
    if not item:
        raise ItemNotFoundError(item_id)
    return item


ValidItem = Annotated[Item, Depends(get_item_or_404)]
```

```python
# modules/item/router.py
from app.schemas.response import ApiResponse
from .schemas import ItemResponse, ItemUpdate


@router.get("/{item_id}", response_model=ApiResponse[ItemResponse])
async def read_item(item: ValidItem) -> ApiResponse[ItemResponse]:
    return ApiResponse(data=ItemResponse.model_validate(item))


@router.put("/{item_id}", response_model=ApiResponse[ItemResponse])
async def update_item(
    item: ValidItem,
    data: ItemUpdate,
    service: ItemServiceDep,
) -> ApiResponse[ItemResponse]:
    updated = await service.update(item, data)
    return ApiResponse(data=updated)
```

---

## 最佳实践

1. **使用 Annotated 创建类型别名** - 提高可读性和可维护性
2. **单一职责** - 每个依赖只做一件事
3. **利用依赖链** - 组合小依赖构建复杂逻辑
4. **yield 管理资源** - 确保资源正确清理
5. **类型提示** - 始终提供返回类型
6. **优先 async** - 简单逻辑使用 async 依赖，避免线程池开销

---

## 相关文档

- [分层架构](./fastapi-layered-architecture.md) - Router/Service/Repository 分层
- [性能优化](./fastapi-performance.md) - async def vs def、并发请求
