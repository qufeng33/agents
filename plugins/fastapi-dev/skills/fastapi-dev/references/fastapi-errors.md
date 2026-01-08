# FastAPI 错误处理与统一响应
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。


## 设计原则

| 原则 | 说明 |
|------|------|
| **统一响应格式** | 成功返回 `code` + `message` + `data`，失败返回 `code` + `message` + `data` + `detail` |
| **业务错误码** | 5 位整数，分段管理 |
| **HTTP 状态码映射** | 业务错误映射到语义化 HTTP 状态码 |
| **类型安全** | 泛型响应模型 `ApiResponse[T]` |

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **统一响应格式** | `ApiResponse[T]` 包装所有成功响应 |
| **错误码分段** | 5 位整数，按类别分段管理 |
| **异常继承体系** | 继承 `ApiError` 基类，按业务分类 |
| **模块级异常** | 按领域组织，如 `user/exceptions.py` |
| **依赖验证** | 在依赖中抛出异常，路由保持简洁 |
| **分层处理** | Service 抛业务异常，Router 包装响应 |
| **日志记录** | 业务异常 warning，系统异常 exception |
| **隐藏细节** | 生产环境不暴露堆栈和内部信息 |
| **文档化错误** | 在 OpenAPI 中声明 `responses` |

---

## 目录

- 设计原则
- 最佳实践
- 响应模型
- 错误码体系
- 业务异常
- 全局异常处理器
- 模块级异常
- 依赖中的异常处理
- OpenAPI 文档
- 相关文档

---

## 响应模型

### 统一响应格式

```python
# app/schemas/response.py
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """单个对象响应"""

    code: int = 0
    message: str = "success"
    data: T

class ErrorResponse(BaseModel):
    """错误响应"""

    code: int
    message: str
    data: None = None
    detail: dict | None = None
```

**分页响应说明**：使用 `ApiPagedResponse` 时保留 `code/message/data/total/page/page_size` 字段即可；`data` 为列表，`total` 为总数。

### 使用示例

```python
from uuid import UUID

from app.schemas.response import ApiResponse
from app.schemas.user import UserResponse


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UUID, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get(user_id)
    return ApiResponse(data=user)
```

**列表接口**：用 `ApiPagedResponse[T]`，并在 Service 返回 `(items, total)`。

---

## 错误码体系

### 错误码分段

| 范围 | 类别 | HTTP 状态码 | 说明 |
|------|------|-------------|------|
| 0 | 成功 | 200 | 正常响应 |
| 10000-19999 | 系统级错误 | 500 | 数据库、缓存等内部错误 |
| 20000-29999 | 服务级错误 | 500/503 | 服务不可用、超时 |
| 30000-39999 | 业务校验错误 | 400/404/409 | 资源不存在、重复等 |
| 40000-49999 | 客户端请求错误 | 400/401/403/422 | 参数错误、认证失败 |
| 50000-59999 | 外部依赖错误 | 502/504 | 第三方 API 错误 |

### 错误码枚举

```python
# app/core/error_codes.py
from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0

    # 10000-19999: 系统级错误
    SYSTEM_ERROR = 10000
    DATABASE_ERROR = 10001
    CACHE_ERROR = 10002

    # 20000-29999: 服务级错误
    SERVICE_UNAVAILABLE = 20000
    SERVICE_TIMEOUT = 20001

    # 30000-39999: 业务校验错误
    RESOURCE_NOT_FOUND = 30000
    USER_NOT_FOUND = 30001
    DUPLICATE_ENTRY = 30100
    USERNAME_ALREADY_EXISTS = 30101
    USER_NOT_DELETED = 30102

    # 40000-49999: 客户端请求错误
    INVALID_REQUEST = 40000
    INVALID_PARAMETER = 40001
    MISSING_PARAMETER = 40002
    UNAUTHORIZED = 40100
    TOKEN_EXPIRED = 40101
    TOKEN_INVALID = 40102
    FORBIDDEN = 40200
    USER_DISABLED = 40201
    INSUFFICIENT_PERMISSIONS = 40202

    # 50000-59999: 外部依赖错误
    EXTERNAL_API_ERROR = 50000
    EXTERNAL_API_TIMEOUT = 50001
```

> **扩展规范**：新增错误码时，在对应分段内顺延编号，保持同类错误码连续。模块级错误码（如 `USER_NOT_FOUND`）建议定义在此枚举中统一管理，而非分散到各模块。

---

## 业务异常

### 异常基类

```python
# app/core/exceptions.py
from app.core.error_codes import ErrorCode


class ApiError(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        status_code: int = 400,
        detail: dict | None = None,
    ):
        self.code = code
        self.message = message or code.name.replace("_", " ").title()
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)
```

### 常用异常类

```python
# app/core/exceptions.py (续)


class NotFoundError(ApiError):
    """资源不存在"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
        message: str = "Resource not found",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=404, detail=detail)


class UnauthorizedError(ApiError):
    """认证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        message: str = "Unauthorized",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=401, detail=detail)


class InvalidCredentialsError(UnauthorizedError):
    """凭证无效（登录失败）"""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(ErrorCode.UNAUTHORIZED, message)


class ForbiddenError(ApiError):
    """权限不足"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.FORBIDDEN,
        message: str = "Forbidden",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=403, detail=detail)


class ConflictError(ApiError):
    """资源冲突"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.DUPLICATE_ENTRY,
        message: str = "Resource conflict",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=409, detail=detail)
```

> 其他异常（如 `ValidationError`、`ServiceUnavailableError`）按同模式扩展。

---

## 全局异常处理器

### 定义处理器

```python
# app/core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ApiError
from app.core.error_codes import ErrorCode


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """业务异常处理"""
    logger.warning(
        "Business error: {} | code={} path={}",
        exc.message,
        exc.code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
            "detail": exc.detail,
        },
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """请求验证异常处理"""
    errors = []
    for error in exc.errors():
        # 将 loc 列表转换为点分字符串 (e.g. ["body", "user", "name"] -> "user.name")
        # 跳过第一个元素（通常是 'body' 或 'query'）
        loc = error["loc"]
        field = ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else str(loc[0])
        
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.INVALID_PARAMETER,
            "message": "Validation failed",
            "data": None,
            "detail": {"errors": errors},
        },
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """HTTP 异常处理（中间件、Starlette 等）"""
    # 映射 HTTP 状态码到业务错误码
    code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        500: ErrorCode.SYSTEM_ERROR,
    }
    code = code_map.get(exc.status_code, ErrorCode.SYSTEM_ERROR)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": str(exc.detail),
            "data": None,
            "detail": None,
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常处理"""
    logger.exception("Unexpected error | path={}", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.SYSTEM_ERROR,
            "message": "Internal server error",
            "data": None,
            "detail": None,
        },
    )
```

### 注册处理器

```python
# app/core/exception_handlers.py (续)
from fastapi import FastAPI


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
```

> **完整 main.py 示例** 详见 [应用生命周期](./fastapi-app-lifecycle.md)

---

## 模块级异常

```python
# app/modules/user/exceptions.py
from app.core.exceptions import NotFoundError
from app.core.error_codes import ErrorCode


class UserNotFoundError(NotFoundError):
    """用户不存在"""

    def __init__(self, user_id: UUID):
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="用户不存在",
            detail={"user_id": str(user_id)},
        )
```

**扩展说明**：冲突/权限类异常按 `ConflictError`/`ForbiddenError` 模式扩展即可。

### Service 层使用

```python
# app/modules/user/service.py
from app.schemas.user import UserCreate, UserResponse
from .exceptions import UserNotFoundError
from .models import User
from app.core.security import hash_password


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: UUID) -> UserResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserResponse.model_validate(user)

    async def create(self, data: UserCreate) -> UserResponse:
        user = User(
            username=data.username,
            hashed_password=hash_password(data.password),
        )
        user = await self.repo.create(user)
        return UserResponse.model_validate(user)
```

**补充说明**：如需唯一性校验，按需抛出 `ConflictError`（或其派生类）并携带冲突字段信息。

**Router 层**：直接返回 `ApiResponse(data=...)`，异常交给全局处理器。

---

## 依赖中的异常处理

### yield 依赖的事务管理

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApiError


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except ApiError:
            await session.rollback()
            raise  # 业务异常：回滚后继续抛出
        except Exception:
            await session.rollback()
            raise  # 其他异常：回滚
```

### 依赖中验证并抛出异常

```python
from fastapi import Depends
from sqlalchemy import select

from app.modules.user.exceptions import UserNotFoundError


async def get_user_or_404(user_id: UUID, db: DBSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(user_id)
    return user
```

**使用方式**：在路由依赖中引用 `get_user_or_404` 即可，异常会被全局处理器统一转换为错误响应。

---

## OpenAPI 文档

### 错误响应声明

```python
from app.schemas.response import ErrorResponse


@router.get(
    "/items/{item_id}",
    response_model=ApiResponse[ItemResponse],
    responses={
        404: {"model": ErrorResponse, "description": "Item not found"},
    },
)
async def get_item(item_id: UUID, service: ItemServiceDep) -> ApiResponse[ItemResponse]:
    item = await service.get(item_id)
    return ApiResponse(data=item)
```

**补充说明**：根据端点需要补充 401/403/422 等错误响应声明。

---

## 相关文档

- **日志记录** - 详见 [日志](./fastapi-logging.md)
- **请求追踪** - 详见 [中间件](./fastapi-middleware.md)
- **应用启动** - 详见 [应用生命周期](./fastapi-app-lifecycle.md)
