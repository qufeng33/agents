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

> 本节为三层架构约束；若采用简化结构（无 Repository），Service 兼任数据访问职责，可直接操作 `AsyncSession`。

### 分层示例

```python
# modules/user/repository.py
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
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
from uuid import UUID
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserCreate, UserResponse
from app.modules.user.models import User
from app.modules.user.exceptions import UserNotFoundError, EmailAlreadyExistsError
from app.core.security import hash_password


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_by_id(self, user_id: UUID) -> UserResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserResponse.model_validate(user)

    async def create(self, data: UserCreate) -> UserResponse:
        # 业务逻辑：检查邮箱唯一性
        if await self.repo.get_by_email(data.email):
            raise EmailAlreadyExistsError(data.email)

        # 业务逻辑：密码哈希
        user = User(
            email=data.email,
            name=data.name,
            hashed_password=hash_password(data.password),
        )
        user = await self.repo.create(user)
        return UserResponse.model_validate(user)
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
from uuid import UUID

from fastapi import APIRouter, status

from app.schemas.response import ApiResponse
from app.modules.user.dependencies import UserServiceDep
from app.modules.user.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get_by_id(user_id)  # 不存在时抛出 UserNotFoundError
    return ApiResponse(data=user)


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(data)  # 邮箱重复时抛出 EmailAlreadyExistsError
    return ApiResponse(data=user)
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

> 说明：上述选择针对 FastAPI 路由/依赖场景；纯工具函数（不在请求链路中）可使用 `def`。

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
    loop = asyncio.get_running_loop()
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
    page: int = Query(default=0, ge=0, description="页码（从 0 开始）"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return {"page": page, "page_size": page_size}

Pagination = Annotated[dict, Depends(pagination)]

@router.get("/items/")
async def list_items(params: Pagination):
    return params  # {"page": 0, "page_size": 20}
```

### 依赖链

```python
from app.core.exceptions import UnauthorizedError
from app.core.error_codes import ErrorCode


async def get_token(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError(message="Invalid authorization format")
    return authorization[7:]


async def get_current_user(token: Annotated[str, Depends(get_token)]) -> User:
    user = await decode_token(token)
    if not user:
        raise UnauthorizedError(code=ErrorCode.TOKEN_INVALID, message="Invalid token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(user: CurrentUser) -> ApiResponse[UserResponse]:
    return ApiResponse(data=UserResponse.model_validate(user))
```

### 依赖放置位置

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

## 后台任务

详见 [后台任务与调度](./fastapi-tasks.md)（BackgroundTasks、ARQ、Celery、APScheduler）。

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
from uuid import UUID

@router.get("/users/batch")
async def get_users(user_ids: list[UUID]):
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
7. **lifespan 管理资源** - 启动时初始化，关闭时清理

---

## 代码模板

完整可运行示例见 `assets/` 目录：

| 结构 | 模板目录 | 特点 |
|------|----------|------|
| 简单结构 | `assets/simple-api/services/` | Service 直接操作 AsyncSession |
| 模块化结构 | `assets/modular-api/modules/user/` | 完整三层架构（含 Repository）|
