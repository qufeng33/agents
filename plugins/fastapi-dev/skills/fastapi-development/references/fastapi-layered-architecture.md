# FastAPI 分层架构
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/app_users`。


## 概述

```
Router (HTTP 层) → Service (业务逻辑层) → Repository (数据访问层) → Database
```

| 层 | 职责 | 不应该做 |
|----|------|----------|
| **Router** | HTTP 处理、参数验证、响应格式、异常转换 | 写 SQL、业务逻辑 |
| **Service** | 业务逻辑、数据转换、跨模块协调 | 直接操作数据库、HTTP 处理 |
| **Repository** | 数据访问、SQL 查询、ORM 操作 | 处理 HTTP、业务规则 |

> 若采用简化结构（无 Repository），Service 兼任数据访问职责，可直接操作 `AsyncSession`。

---

## 分层示例

### Repository 层

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

### Service 层

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

### Router 层

```python
# modules/user/router.py
from uuid import UUID

from fastapi import APIRouter, status

from app.schemas.response import ApiResponse
from app.modules.user.dependencies import UserServiceDep
from app.modules.user.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/app_users", tags=["app_users"])


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get_by_id(user_id)  # 不存在时抛出 UserNotFoundError
    return ApiResponse(data=user)


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(data)  # 邮箱重复时抛出 EmailAlreadyExistsError
    return ApiResponse(data=user)
```

---

## 分层好处

- **可测试**：mock Repository 测试 Service，mock Service 测试 Router
- **可替换**：切换数据库只需修改 Repository
- **职责清晰**：每层专注自己的事
- **代码复用**：Service 可被多个 Router 或后台任务复用

---

## 代码模板

完整可运行示例见 `assets/` 目录：

| 结构 | 模板目录 | 特点 |
|------|----------|------|
| 简单结构 | `assets/simple-api/services/` | Service 直接操作 AsyncSession |
| 模块化结构 | `assets/modular-api/modules/user/` | 完整三层架构（含 Repository）|

---

## 相关文档

- [依赖注入](./fastapi-dependency-injection.md) - Service/Repository 注入模式
- [项目结构](./fastapi-project-structure.md) - 目录布局
- [应用生命周期](./fastapi-app-lifecycle.md) - lifespan、init/setup 模式
