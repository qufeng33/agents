# FastAPI 依赖注入
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 依赖只做一件事，职责清晰
- 依赖集中在 `dependencies.py`，避免分散
- 组合小依赖实现复杂逻辑
- 资源类依赖必须可清理
- 类型标注明确，减少隐式行为

## 最佳实践
1. 使用 `Annotated` 创建类型别名
2. 优先 `async` 依赖，避免线程池开销
3. 依赖链组合而非复制粘贴
4. `yield` 依赖必须确保资源释放
5. 依赖集中管理，避免循环导入

## 目录
- `基本用法（Annotated 推荐）`
- `依赖放置位置`
- `yield 依赖（资源管理）`
- `类作为依赖`
- `依赖缓存`
- `路由级依赖`
- `资源存在性验证`
- `相关文档`

---

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
    return params
```

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

> 依赖链（如鉴权 → 用户 → 权限）建议拆成小依赖并组合，而非在路由内直接编排。

---

## yield 依赖（资源管理）

`yield` 依赖用于管理需要清理的资源（数据库连接、HTTP 客户端等）。

```python
async def get_resource() -> AsyncGenerator[Resource, None]:
    resource = await create_resource()
    try:
        yield resource
    finally:
        await resource.close()
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


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    service: UserServiceDep,
):
    await service.delete(user_id)
    return {"status": "ok"}
```

> 复杂权限建议分解为多个依赖（鉴权 → 角色 → 资源校验）。

---

## 依赖缓存

同一请求中相同依赖只执行一次（共享实例）。

```python
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

> 路由级依赖适合统一鉴权或审计，不适合执行重逻辑。

---

## 资源存在性验证

通过依赖注入进行资源验证，不存在时抛出模块级异常。

```python
# modules/item/dependencies.py
async def get_item_or_404(
    item_id: UUID,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> Item:
    item = await service.get_by_id(item_id)
    if not item:
        raise ItemNotFoundError(item_id)
    return item
```

> Router 只依赖 `ValidItem`，具体校验逻辑留在依赖函数里。

---

## 相关文档

- [分层架构](./fastapi-layered-architecture.md) - Router/Service/Repository 分层
- [性能优化](./fastapi-performance.md) - async def vs def、并发请求
