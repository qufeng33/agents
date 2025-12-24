# FastAPI 依赖注入

## 基础概念

依赖注入（DI）是 FastAPI 的核心特性，用于：
- 共享逻辑（数据库连接、认证）
- 参数验证
- 资源管理（自动清理）

---

## 基本用法

### 使用 Annotated（推荐）

```python
from typing import Annotated
from fastapi import Depends, Query


def common_parameters(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=1000),
) -> dict:
    return {"skip": skip, "limit": limit}


# 创建类型别名
CommonParams = Annotated[dict, Depends(common_parameters)]


@app.get("/items/")
async def read_items(params: CommonParams):
    return {"skip": params["skip"], "limit": params["limit"]}


@app.get("/users/")
async def read_users(params: CommonParams):
    return {"skip": params["skip"], "limit": params["limit"]}
```

---

## 依赖链

依赖可以依赖其他依赖，形成依赖链。

```python
from typing import Annotated
from fastapi import Depends, Header, HTTPException


async def get_token(authorization: str = Header()):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    return authorization[7:]


async def get_current_user(token: Annotated[str, Depends(get_token)]):
    user = await decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


async def get_active_user(user: Annotated[User, Depends(get_current_user)]):
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return user


# 类型别名
CurrentUser = Annotated[User, Depends(get_current_user)]
ActiveUser = Annotated[User, Depends(get_active_user)]


@app.get("/me")
async def get_me(user: CurrentUser):
    return user


@app.post("/items")
async def create_item(user: ActiveUser, item: ItemCreate):
    return await create_item_for_user(user.id, item)
```

---

## yield 依赖（资源管理）

使用 `yield` 管理需要清理的资源。

```python
from typing import Generator


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]


@app.get("/users/{user_id}")
async def get_user(user_id: int, db: DBSession):
    return db.query(User).filter(User.id == user_id).first()
```

### 异常处理

```python
async def get_db_with_transaction():
    db = SessionLocal()
    try:
        yield db
        db.commit()  # 成功时提交
    except Exception:
        db.rollback()  # 异常时回滚
        raise
    finally:
        db.close()  # 始终关闭
```

---

## 类作为依赖

```python
class Pagination:
    def __init__(
        self,
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=20, le=100),
    ):
        self.skip = skip
        self.limit = limit


@app.get("/items/")
async def list_items(pagination: Pagination = Depends()):
    return {"skip": pagination.skip, "limit": pagination.limit}
```

### 可调用类

```python
class PermissionChecker:
    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions

    def __call__(self, user: CurrentUser) -> User:
        for permission in self.required_permissions:
            if permission not in user.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission}",
                )
        return user


# 创建不同权限检查器
require_admin = PermissionChecker(["admin"])
require_editor = PermissionChecker(["editor"])


@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(require_admin)],
):
    # 只有 admin 能执行
    ...
```

---

## 依赖缓存

默认情况下，同一请求中相同依赖只执行一次。

```python
def get_db():
    print("Creating DB session")  # 只打印一次
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_service(db: DBSession):
    return UserService(db)


def get_order_service(db: DBSession):
    return OrderService(db)


@app.post("/orders")
async def create_order(
    user_service: Annotated[UserService, Depends(get_user_service)],
    order_service: Annotated[OrderService, Depends(get_order_service)],
):
    # get_db() 只调用一次，两个 service 共享同一个 db session
    ...
```

### 禁用缓存

某些场景需要每次都创建新实例：

```python
@app.get("/items/")
async def read_items(
    fresh_value: Annotated[str, Depends(get_random_value, use_cache=False)],
):
    # 每次请求都会调用 get_random_value
    return {"value": fresh_value}
```

---

## 路由级依赖

应用于整个路由器的依赖。

```python
async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != "secret-key":
        raise HTTPException(status_code=403, detail="Invalid API key")


# 路由器级别
router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/protected")
async def protected_route():
    return {"message": "Access granted"}


# 或应用级别
app = FastAPI(dependencies=[Depends(verify_api_key)])
```

---

## 实用模式

### 数据库存在性验证

```python
from fastapi import Path


async def get_item_or_404(
    item_id: int = Path(),
    db: DBSession = Depends(get_db),
) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


ValidItem = Annotated[Item, Depends(get_item_or_404)]


@app.get("/items/{item_id}")
async def read_item(item: ValidItem):
    return item  # item 一定存在


@app.put("/items/{item_id}")
async def update_item(item: ValidItem, update: ItemUpdate):
    # item 一定存在，直接更新
    ...
```

### 权限检查组合

```python
def require_owner(
    item: ValidItem,
    user: CurrentUser,
) -> Item:
    if item.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not the owner")
    return item


OwnedItem = Annotated[Item, Depends(require_owner)]


@app.delete("/items/{item_id}")
async def delete_item(item: OwnedItem):
    # 确保 item 存在且当前用户是所有者
    ...
```

### 请求上下文

```python
from fastapi import Request
import uuid


async def get_request_id(request: Request) -> str:
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


RequestID = Annotated[str, Depends(get_request_id)]


@app.get("/")
async def root(request_id: RequestID):
    return {"request_id": request_id}
```

---

## async 依赖 vs sync 依赖

sync 依赖在线程池中运行，有额外开销。对于简单逻辑，优先使用 async。

```python
# ❌ 不推荐：sync 依赖处理简单逻辑
def get_pagination(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
) -> dict:
    # 简单逻辑，无 I/O，却被放到线程池执行
    return {"skip": skip, "limit": limit}


# ✅ 推荐：async 依赖处理简单逻辑
async def get_pagination(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
) -> dict:
    # 在事件循环中直接执行，无线程切换开销
    return {"skip": skip, "limit": limit}


# ✅ 正确使用 sync：真正需要阻塞操作时
def get_db() -> Generator[Session, None, None]:
    # 同步数据库连接，确实需要在线程池中
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**选择规则**：

| 场景 | 推荐 |
|-----|------|
| 无 I/O 的简单逻辑 | `async def` |
| 异步 I/O（httpx, asyncpg） | `async def` + `await` |
| 同步阻塞 I/O（sync DB） | `def`（FastAPI 自动线程池） |
| CPU 密集型 | 外部进程 / ProcessPoolExecutor |

---

## 最佳实践

1. **使用 Annotated 创建类型别名** - 提高可读性和可维护性
2. **单一职责** - 每个依赖只做一件事
3. **利用依赖链** - 组合小依赖构建复杂逻辑
4. **yield 管理资源** - 确保资源正确清理
5. **类型提示** - 始终提供返回类型
6. **避免副作用** - 依赖应该是幂等的（除非特意设计）
7. **优先 async** - 简单逻辑使用 async 依赖，避免线程池开销
8. **验证数据库约束** - 利用依赖验证资源存在性，复用验证逻辑
