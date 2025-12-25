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
from fastapi import status

@router.get("/users/{user_id}")
async def get_user(user_id: int):
    return user  # 200 OK（默认）

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    return new_user  # 201 Created

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int):
    return None  # 204 No Content
```

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

### 请求参数

```python
from typing import Annotated
from fastapi import Query


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    sort_by: Annotated[str | None, Query(description="排序字段")] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
):
    ...
```

### 响应模型

```python
from typing import Generic, TypeVar
from pydantic import BaseModel, computed_field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @computed_field
    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @computed_field
    @property
    def has_prev(self) -> bool:
        return self.page > 1


# 使用
class UserList(PaginatedResponse[UserResponse]):
    pass
```

### 分页实现

```python
async def paginate(
    query,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> dict:
    # 计算总数
    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    # 计算偏移
    offset = (page - 1) * page_size

    # 获取数据
    result = await db.execute(query.offset(offset).limit(page_size))
    items = result.scalars().all()

    return {
        "items": items,
        "total": total or 0,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }
```

---

## 过滤与搜索

### 查询参数过滤

```python
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@router.get("/users")
async def list_users(
    status: UserStatus | None = Query(None, description="用户状态"),
    is_verified: bool | None = Query(None, description="是否已验证"),
    created_after: datetime | None = Query(None, description="创建时间起始"),
    created_before: datetime | None = Query(None, description="创建时间截止"),
    search: str | None = Query(None, min_length=2, description="搜索关键词"),
):
    query = select(User)

    if status:
        query = query.where(User.status == status)
    if is_verified is not None:
        query = query.where(User.is_verified == is_verified)
    if created_after:
        query = query.where(User.created_at >= created_after)
    if created_before:
        query = query.where(User.created_at <= created_before)
    if search:
        query = query.where(
            User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )

    return await paginate(query, page, page_size, db)
```

---

## 错误响应格式

### 统一错误模型

```python
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """错误详情"""
    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """统一错误响应"""
    code: str
    message: str
    details: list[ErrorDetail] | None = None


# 响应示例
{
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
        {"field": "email", "message": "Invalid email format", "code": "invalid_format"},
        {"field": "password", "message": "Must be at least 8 characters", "code": "min_length"}
    ]
}
```

### 异常类设计

```python
class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str, id: str) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} with id '{id}' not found",
            status_code=404,
        )


class ValidationError(AppException):
    def __init__(self, details: list[ErrorDetail]) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message="Validation failed",
            status_code=422,
            details=details,
        )


class ConflictError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=409,
        )
```

### 全局异常处理器

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ).model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(str(loc) for loc in err["loc"]),
            message=err["msg"],
            code=err["type"],
        )
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        ).model_dump(),
    )


# 注册
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
```

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
class UserResponse(BaseModel):
    """用户响应（排除敏感字段）"""
    model_config = ConfigDict(from_attributes=True)

    id: int
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

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(users_router, prefix="/users")

# app/api/v2/router.py
v2_router = APIRouter(prefix="/api/v2")
v2_router.include_router(users_v2_router, prefix="/users")

# main.py
app.include_router(v1_router)
app.include_router(v2_router)
```

### 版本共存策略

```python
# 保持向后兼容，新版本添加新功能
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
