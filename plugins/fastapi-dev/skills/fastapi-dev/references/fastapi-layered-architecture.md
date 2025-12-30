# FastAPI 分层架构
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

## 设计原则
- 让每一层只做一类职责，避免层间混用
- 业务规则集中在 Service，数据访问集中在 Repository
- Router 只处理 HTTP 语义，不下沉业务细节
- 可测试性优先，分层便于替换与 mock
- 简化结构时必须明确责任边界

## 最佳实践
1. Router 只做参数解析、响应封装和状态码控制
2. Service 负责规则校验、编排与异常语义
3. Repository 只提供数据访问能力，不做业务判断
4. 小项目可省略 Repository，但要明确 Service 直接持有 `AsyncSession`
5. 分层示例与模板集中维护在 `assets/`

## 目录
- `概述`
- `分层示例`
- `分层好处`
- `代码模板`
- `相关文档`

---

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
```

> Repository 只封装查询与持久化细节，避免任何业务判断。

### Service 层

```python
# modules/user/service.py
from uuid import UUID

from app.modules.user.repository import UserRepository
from app.modules.user.schemas import UserResponse
from app.modules.user.exceptions import UserNotFoundError


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_by_id(self, user_id: UUID) -> UserResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserResponse.model_validate(user)
```

> 复杂业务校验（如唯一性校验、权限判断、加密）应在 Service 中完成。

### Router 层

```python
# modules/user/router.py
from uuid import UUID

from fastapi import APIRouter

from app.schemas.response import ApiResponse
from app.modules.user.dependencies import UserServiceDep
from app.modules.user.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get_by_id(user_id)
    return ApiResponse(data=user)
```

> Router 只处理 HTTP 语义（路径、状态码、响应封装），不下沉业务细节。

---

## 分层好处

- **可测试**：mock Repository 测试 Service，mock Service 测试 Router
- **可替换**：切换数据库只需修改 Repository
- **职责清晰**：每层专注自己的事
- **代码复用**：Service 可被多个 Router 或后台任务复用

---

## 代码模板

完整可运行示例见 `assets/` 目录：

- `assets/simple-api/services/` - Service 直接操作 AsyncSession
- `assets/modular-api/modules/user/` - 完整三层架构（含 Repository）

---

## 相关文档

- [依赖注入](./fastapi-dependency-injection.md) - Service/Repository 注入模式
- [项目结构](./fastapi-project-structure.md) - 目录布局
- [应用生命周期](./fastapi-app-lifecycle.md) - lifespan、init/setup 模式
