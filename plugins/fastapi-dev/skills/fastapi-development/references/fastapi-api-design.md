# FastAPI API 设计原则

## RESTful 设计规范

### URL 设计

```python
# 资源用名词复数，不用动词
GET    /api/users              # 获取用户列表
POST   /api/users              # 创建用户
GET    /api/users/{id}         # 获取单个用户
PUT    /api/users/{id}         # 完整更新用户
PATCH  /api/users/{id}         # 部分更新用户
DELETE /api/users/{id}         # 删除用户

# 嵌套资源（表示从属关系）
GET    /api/users/{id}/orders  # 获取用户的订单
POST   /api/users/{id}/orders  # 为用户创建订单

# 避免（反模式）
POST   /api/createUser         # ❌ 动词
POST   /api/user/create        # ❌ 动词
GET    /api/getUserById        # ❌ 动词
```

### HTTP 方法语义

| 方法 | 语义 | 幂等性 | 安全性 | 示例 |
|------|------|--------|--------|------|
| GET | 获取资源 | ✓ | ✓ | 获取用户信息 |
| POST | 创建资源 | ✗ | ✗ | 创建新用户 |
| PUT | 完整替换 | ✓ | ✗ | 更新整个用户对象 |
| PATCH | 部分更新 | ✓ | ✗ | 只更新用户邮箱 |
| DELETE | 删除资源 | ✓ | ✗ | 删除用户 |

---

## 状态码规范

### 成功响应

```python
from uuid import UUID

from fastapi import status

from app.schemas.response import ApiResponse


@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get(user_id)
    return ApiResponse(data=user)  # 200 OK（默认）


@router.post("/users", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(user_in)
    return ApiResponse(data=user)  # 201 Created


@router.delete("/users/{user_id}", response_model=ApiResponse[None], status_code=status.HTTP_200_OK)
async def delete_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[None]:
    await service.delete(user_id)
    return ApiResponse(data=None, message="User deleted")  # 200 OK
```

> **重要**：路由函数必须标注返回类型，确保与实际返回值和 `response_model` 匹配。使用 `ApiResponse[T]` 统一包装响应。

### 错误响应

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 400 | Bad Request | 请求格式错误、参数无效 |
| 401 | Unauthorized | 未认证（缺少/无效 token） |
| 403 | Forbidden | 已认证但无权限 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突（如邮箱已存在） |
| 422 | Unprocessable Entity | 验证失败（FastAPI 默认） |
| 500 | Internal Server Error | 服务器内部错误 |

---

## 分页设计

### 分页参数约定

| 参数 | 说明 | 默认值 | 约束 |
|------|------|--------|------|
| `page` | 页码，**从 0 开始** | 0 | `ge=0` |
| `page_size` | 每页数量 | 20 | `ge=1, le=100` |

> **注意**：`page` 从 0 开始，与数组索引一致。`offset = page * page_size`。

### 请求参数

```python
from typing import Annotated
from fastapi import Query

from app.schemas.response import ApiPagedResponse


@router.get("/users", response_model=ApiPagedResponse[UserResponse])
async def list_users(
    service: UserServiceDep,
    page: Annotated[int, Query(ge=0, description="页码（从 0 开始）")] = 0,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
) -> ApiPagedResponse[UserResponse]:
    users, total = await service.list(page=page, page_size=page_size)
    return ApiPagedResponse(data=users, total=total, page=page, page_size=page_size)
```

### 响应模型

使用统一的 `ApiPagedResponse[T]`（定义在 `app/schemas/response.py`）：

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiPagedResponse(BaseModel, Generic[T]):
    """分页列表响应"""

    code: int = 0
    message: str = "success"
    data: list[T]
    total: int
    page: int        # 当前页码（从 0 开始）
    page_size: int
```

### 分页实现（Repository 层）

```python
from datetime import datetime
from sqlalchemy import or_, select, func


async def list(
    self,
    page: int = 0,
    page_size: int = 20,
    status: UserStatus | None = None,
    is_verified: bool | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    search: str | None = None,
) -> tuple[list[User], int]:
    """分页查询（page 从 0 开始）"""
    filters = []
    if status is not None:
        filters.append(User.status == status)
    if is_verified is not None:
        filters.append(User.is_verified == is_verified)
    if created_after:
        filters.append(User.created_at >= created_after)
    if created_before:
        filters.append(User.created_at <= created_before)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(User.email.ilike(pattern), User.username.ilike(pattern)))

    # 计算总数（包含过滤条件）
    total = await self.db.scalar(
        select(func.count(User.id)).where(*filters)
    ) or 0

    # 计算偏移（page 从 0 开始，直接相乘）
    offset = page * page_size

    # 获取数据
    result = await self.db.execute(
        select(User)
        .where(*filters)
        .order_by(User.id)
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())

    return items, total
```

---

## 过滤与搜索

### 查询参数过滤

```python
from enum import Enum

from app.schemas.response import ApiPagedResponse


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@router.get("/users", response_model=ApiPagedResponse[UserResponse])
async def list_users(
    service: UserServiceDep,
    page: int = Query(default=0, ge=0, description="页码（从 0 开始）"),
    page_size: int = Query(default=20, ge=1, le=100),
    status: UserStatus | None = Query(None, description="用户状态"),
    is_verified: bool | None = Query(None, description="是否已验证"),
    created_after: datetime | None = Query(None, description="创建时间起始"),
    created_before: datetime | None = Query(None, description="创建时间截止"),
    search: str | None = Query(None, min_length=2, description="搜索关键词"),
) -> ApiPagedResponse[UserResponse]:
    users, total = await service.list(
        page=page,
        page_size=page_size,
        status=status,
        is_verified=is_verified,
        created_after=created_after,
        created_before=created_before,
        search=search,
    )
    return ApiPagedResponse(data=users, total=total, page=page, page_size=page_size)
```

---

## 错误响应格式

统一错误响应格式：`code` + `message` + `data` + `detail` 四元组。

```json
{
    "code": 40001,
    "message": "Validation failed",
    "data": null,
    "detail": {
        "errors": [
            {"field": "email", "message": "Invalid email format", "type": "value_error"},
            {"field": "password", "message": "Must be at least 8 characters", "type": "string_too_short"}
        ]
    }
}
```

> 错误码分段与完整异常体系详见 [错误处理与统一响应](./fastapi-errors.md)

---

## 请求/响应模型分离

### 输入模型（创建/更新）

```python
class UserCreate(BaseModel):
    """创建用户请求"""
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    """更新用户请求（所有字段可选）"""
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=50)


class UserUpdatePassword(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str = Field(min_length=8)
```

### 输出模型（响应）

```python
from uuid import UUID


class UserResponse(BaseModel):
    """用户响应（排除敏感字段）"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime
    # 注意：不包含 password、hashed_password


class UserDetailResponse(UserResponse):
    """用户详情（包含更多信息）"""
    last_login_at: datetime | None
    login_count: int
```

---

## API 版本管理

### URL 版本（推荐）

```python
# app/api/v1/router.py
from fastapi import APIRouter

v1_router = APIRouter()
v1_router.include_router(users_router, prefix="/users")

# app/api/v2/router.py
v2_router = APIRouter()
v2_router.include_router(users_v2_router, prefix="/users")

# main.py
app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
```

### 版本共存策略

在设计阶段先确认是否需要向后兼容。需要兼容则版本共存；不需要兼容则允许破坏性变更并更新版本号。

```python
# 需要兼容：新版本添加新功能
# v1: GET /api/v1/users → UserResponse
# v2: GET /api/v2/users → UserResponseV2（添加新字段）

class UserResponseV2(UserResponse):
    """V2 新增字段"""
    avatar_url: str | None = None
    preferences: dict | None = None
```

---

## 路由注册

集中管理路由注册，在 `main.py` 中统一调用。

```python
# app/core/routers.py
from fastapi import FastAPI

from app.api.v1.router import api_router as v1_router
from app.routers import health


def setup_routers(app: FastAPI) -> None:
    """注册所有路由"""
    # 健康检查
    app.include_router(health.router, tags=["health"])

    # API v1
    app.include_router(v1_router, prefix="/api/v1")
```

```python
# app/api/v1/router.py
from fastapi import APIRouter

from app.modules.user.router import router as user_router
from app.modules.item.router import router as item_router

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["users"])
api_router.include_router(item_router, prefix="/items", tags=["items"])
```

> **在 main.py 中调用** 详见 [应用启动与初始化](./fastapi-startup.md)

---

## 最佳实践清单

### 路由设计
- [ ] URL 使用名词复数，不使用动词
- [ ] 使用正确的 HTTP 方法
- [ ] 返回正确的状态码
- [ ] 嵌套资源最多 2 层

### 数据验证
- [ ] 请求模型和响应模型分离
- [ ] 使用 Pydantic Field 约束
- [ ] 响应模型排除敏感字段

### 错误处理
- [ ] 统一错误响应格式
- [ ] 全局异常处理器
- [ ] 有意义的错误码和消息

### 分页与过滤
- [ ] 列表接口支持分页
- [ ] 限制最大 page_size
- [ ] 支持常用过滤参数
