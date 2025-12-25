# FastAPI 核心模式

## 分层架构

```
Router (HTTP 层) → Service (业务逻辑层) → Repository (数据访问层) → Database
```

| 层 | 职责 | 不应该做 |
|----|------|----------|
| **Router** | HTTP 处理、参数验证、响应格式、异常转换 | 写 SQL、业务逻辑 |
| **Service** | 业务逻辑、数据转换、跨模块协调 | 直接操作数据库、HTTP 处理 |
| **Repository** | 数据访问、SQL 查询、ORM 操作 | 处理 HTTP、业务规则 |

### 分层示例

```python
# modules/user/repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user
```

```python
# modules/user/service.py
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate
from app.modules.user.models import User
from app.core.security import hash_password


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.repo.get_by_id(user_id)

    async def create(self, data: UserCreate) -> User:
        # 业务逻辑：检查邮箱唯一性
        if await self.repo.get_by_email(data.email):
            raise ValueError("Email already registered")

        # 业务逻辑：密码哈希
        user = User(
            email=data.email,
            name=data.name,
            hashed_password=hash_password(data.password),
        )
        return await self.repo.create(user)
```

```python
# modules/user/dependencies.py
from typing import Annotated
from fastapi import Depends

from app.core.dependencies import DBSession
from app.modules.user.repository import UserRepository
from app.modules.user.service import UserService


def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

```python
# modules/user/router.py
from fastapi import APIRouter, HTTPException

from app.modules.user.dependencies import UserServiceDep
from app.modules.user.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}")
async def get_user(user_id: int, service: UserServiceDep) -> UserResponse:
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", status_code=201)
async def create_user(data: UserCreate, service: UserServiceDep) -> UserResponse:
    try:
        return await service.create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 分层好处

- **可测试**：mock Repository 测试 Service，mock Service 测试 Router
- **可替换**：切换数据库只需修改 Repository
- **职责清晰**：每层专注自己的事
- **代码复用**：Service 可被多个 Router 或后台任务复用

---

## async def vs def 选择

| 场景 | 推荐 | 原因 |
|-----|------|------|
| 无 I/O 的简单逻辑 | `async def` | 避免线程池开销 |
| 异步 I/O（httpx, asyncpg） | `async def` + `await` | 非阻塞 |
| 同步阻塞 I/O | `def` | FastAPI 自动线程池 |
| CPU 密集型 | `ProcessPoolExecutor` | 不阻塞事件循环 |

```python
from fastapi import APIRouter

router = APIRouter()

# I/O 密集型：async def
@router.get("/external")
async def call_api():
    async with httpx.AsyncClient() as client:
        return (await client.get("https://api.example.com")).json()

# 同步阻塞：def（自动线程池）
@router.get("/sync")
def sync_operation():
    time.sleep(1)  # 不会阻塞事件循环
    return {"done": True}

# CPU 密集型：外部进程
executor = ProcessPoolExecutor(max_workers=4)

@router.post("/compute")
async def compute(data: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, heavy_task, data)
```

### 常见错误

```python
# 错误：在 async def 中阻塞
@router.get("/bad")
async def bad():
    time.sleep(5)  # 阻塞事件循环！

# 正确：使用 def 或 asyncio.sleep
@router.get("/good")
async def good():
    await asyncio.sleep(5)
```

---

## 依赖注入

### 基本用法（Annotated 推荐）

```python
from typing import Annotated
from fastapi import APIRouter, Depends, Query

router = APIRouter()


def pagination(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, le=100),
) -> dict:
    return {"skip": skip, "limit": limit}

Pagination = Annotated[dict, Depends(pagination)]

@router.get("/items/")
async def list_items(params: Pagination):
    return params
```

### 依赖链

```python
async def get_token(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid format")
    return authorization[7:]

async def get_current_user(token: Annotated[str, Depends(get_token)]) -> User:
    user = await decode_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

@router.get("/me")
async def get_me(user: CurrentUser):
    return user
```

### yield 依赖（资源管理）

`yield` 依赖用于管理需要清理的资源（数据库连接、HTTP 客户端等）。

```python
async def get_resource() -> AsyncGenerator[Resource, None]:
    resource = await create_resource()
    try:
        yield resource      # 请求处理期间使用
    finally:
        await resource.close()  # 请求结束后清理
```

> **数据库 Session 依赖**：完整的 `get_db()` 实现（含事务管理）详见 [数据库集成 - 依赖注入](./fastapi-database.md#依赖注入)

### 类作为依赖

```python
class PermissionChecker:
    def __init__(self, permissions: list[str]):
        self.permissions = permissions

    def __call__(self, user: CurrentUser) -> User:
        for p in self.permissions:
            if p not in user.permissions:
                raise HTTPException(403, f"Missing: {p}")
        return user

require_admin = PermissionChecker(["admin"])

@router.delete("/users/{user_id}")
async def delete_user(admin: Annotated[User, Depends(require_admin)]):
    ...
```

### 依赖缓存

同一请求中相同依赖只执行一次（共享实例）。

```python
# 禁用缓存：每次都创建新实例
@router.get("/items/")
async def items(val: Annotated[str, Depends(get_random, use_cache=False)]):
    ...
```

### 路由级依赖

```python
router = APIRouter(dependencies=[Depends(verify_api_key)])
app = FastAPI(dependencies=[Depends(log_request)])
```

---

## 资源存在性验证

通过 Service 层进行资源验证，保持分层一致性。

```python
# modules/item/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException

from .service import ItemService


def get_item_service(
    repo: Annotated[ItemRepository, Depends(get_item_repository)],
) -> ItemService:
    return ItemService(repo)


async def get_item_or_404(
    item_id: int,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> Item:
    item = await service.get_by_id(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item


ValidItem = Annotated[Item, Depends(get_item_or_404)]
```

```python
# modules/item/router.py
@router.get("/{item_id}")
async def read_item(item: ValidItem):
    return item  # 保证存在


@router.put("/{item_id}")
async def update_item(item: ValidItem, data: ItemUpdate, service: ItemServiceDep):
    return await service.update(item, data)
```

---

## 后台任务

```python
from fastapi import BackgroundTasks

def send_email(email: str, msg: str):
    # 同步函数自动在线程池执行
    ...

@router.post("/notify")
async def notify(email: str, bg: BackgroundTasks):
    bg.add_task(send_email, email, "Hello")
    return {"status": "scheduled"}
```

**最佳实践**：传递 ID 而非对象，后台任务自己创建 session。

```python
def process_order(order_id: int):
    db = SessionLocal()
    try:
        order = db.query(Order).get(order_id)
        # 处理...
    finally:
        db.close()

@router.post("/orders")
async def create_order(order: OrderCreate, bg: BackgroundTasks, db: DBSession):
    db_order = Order(**order.model_dump())
    db.add(db_order)
    db.commit()
    bg.add_task(process_order, db_order.id)  # 传 ID，不传对象
    return db_order
```

---

## 生命周期管理（Lifespan）

`lifespan` 用于管理应用级别的资源（数据库连接池、HTTP 客户端等）。

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化资源，存储到 app.state
    app.state.http_client = httpx.AsyncClient()
    yield
    # 关闭：清理资源
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)
```

通过依赖注入访问共享资源（推荐）：

```python
async def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

HttpClient = Annotated[httpx.AsyncClient, Depends(get_http_client)]
```

> 完整的应用启动流程和 `init_xxx`/`setup_xxx` 模式详见 [应用启动与初始化](./fastapi-startup.md)

---

## 并发请求

```python
@router.get("/users/batch")
async def get_users(user_ids: list[int]):
    tasks = [fetch_user(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    users, errors = [], []
    for uid, r in zip(user_ids, results):
        if isinstance(r, Exception):
            errors.append({"id": uid, "error": str(r)})
        else:
            users.append(r)
    return {"users": users, "errors": errors}
```

---

## 异步数据库

详见 [fastapi-database.md](./fastapi-database.md) 的「SQLAlchemy 2.0 异步」章节。

---

## 最佳实践

1. **使用 Annotated 创建类型别名** - 提高可读性和可维护性
2. **单一职责** - 每个依赖只做一件事
3. **利用依赖链** - 组合小依赖构建复杂逻辑
4. **yield 管理资源** - 确保资源正确清理
5. **类型提示** - 始终提供返回类型
6. **优先 async** - 简单逻辑使用 async 依赖，避免线程池开销
7. **后台任务传 ID** - 不传递 ORM 对象或 db session
8. **lifespan 管理资源** - 启动时初始化，关闭时清理
