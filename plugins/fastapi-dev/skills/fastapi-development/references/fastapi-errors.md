# FastAPI 错误处理与统一响应

## 设计原则

| 原则 | 说明 |
|------|------|
| **统一响应格式** | 成功和失败都返回 `code` + `message` + `data` |
| **业务错误码** | 5 位整数，分段管理 |
| **HTTP 状态码映射** | 业务错误映射到语义化 HTTP 状态码 |
| **类型安全** | 泛型响应模型 `ApiResponse[T]` |

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


class ApiPagedResponse(BaseModel, Generic[T]):
    """分页列表响应"""

    code: int = 0
    message: str = "success"
    data: list[T]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """错误响应"""

    code: int
    message: str
    data: None = None
    detail: dict | None = None
```

### 使用示例

```python
from app.schemas.response import ApiResponse, ApiPagedResponse
from app.schemas.user import UserResponse


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: int, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get(user_id)
    return ApiResponse(data=user)


@router.get("/", response_model=ApiPagedResponse[UserResponse])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    service: UserServiceDep,
) -> ApiPagedResponse[UserResponse]:
    users, total = await service.list(page, page_size)
    return ApiPagedResponse(data=users, total=total, page=page, page_size=page_size)
```

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
    ORDER_NOT_FOUND = 30002
    DUPLICATE_ENTRY = 30100
    EMAIL_ALREADY_EXISTS = 30101
    USERNAME_ALREADY_EXISTS = 30102

    # 40000-49999: 客户端请求错误
    INVALID_REQUEST = 40000
    INVALID_PARAMETER = 40001
    MISSING_PARAMETER = 40002
    UNAUTHORIZED = 40100
    TOKEN_EXPIRED = 40101
    TOKEN_INVALID = 40102
    FORBIDDEN = 40200
    INSUFFICIENT_PERMISSIONS = 40201

    # 50000-59999: 外部依赖错误
    EXTERNAL_API_ERROR = 50000
    EXTERNAL_API_TIMEOUT = 50001
    PAYMENT_GATEWAY_ERROR = 50100
```

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


class ValidationError(ApiError):
    """业务验证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.INVALID_PARAMETER,
        message: str = "Validation failed",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=400, detail=detail)


class UnauthorizedError(ApiError):
    """认证失败"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        message: str = "Unauthorized",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=401, detail=detail)


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


class ServiceUnavailableError(ApiError):
    """服务不可用"""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE,
        message: str = "Service unavailable",
        detail: dict | None = None,
    ):
        super().__init__(code, message, status_code=503, detail=detail)
```

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
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"][1:]),
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
        503: ErrorCode.SERVICE_UNAVAILABLE,
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

> **完整 main.py 示例** 详见 [应用启动与初始化](./fastapi-startup.md)

---

## 模块级异常

```python
# app/modules/user/exceptions.py
from app.core.exceptions import NotFoundError, ConflictError, UnauthorizedError
from app.core.error_codes import ErrorCode


class UserNotFoundError(NotFoundError):
    """用户不存在"""

    def __init__(self, user_id: int):
        super().__init__(
            code=ErrorCode.USER_NOT_FOUND,
            message="用户不存在",
            detail={"user_id": user_id},
        )


class EmailAlreadyExistsError(ConflictError):
    """邮箱已注册"""

    def __init__(self, email: str):
        super().__init__(
            code=ErrorCode.EMAIL_ALREADY_EXISTS,
            message="邮箱已注册",
            detail={"email": email},
        )


class InvalidCredentialsError(UnauthorizedError):
    """凭证无效"""

    def __init__(self):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message="邮箱或密码错误",
        )
```

### Service 层使用

```python
# app/modules/user/service.py
from app.schemas.response import ApiResponse
from app.schemas.user import UserCreate, UserResponse
from .exceptions import UserNotFoundError, EmailAlreadyExistsError


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: int) -> UserResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return UserResponse.model_validate(user)

    async def create(self, data: UserCreate) -> UserResponse:
        if await self.repo.get_by_email(data.email):
            raise EmailAlreadyExistsError(data.email)
        user = await self.repo.create(data)
        return UserResponse.model_validate(user)
```

### Router 层使用

```python
# app/modules/user/router.py
from fastapi import APIRouter, status

from app.schemas.response import ApiResponse
from app.schemas.user import UserCreate, UserResponse
from .dependencies import UserServiceDep

router = APIRouter()


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(user_in)
    return ApiResponse(data=user)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: int, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.get(user_id)
    return ApiResponse(data=user)
```

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
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select

from app.modules.user.exceptions import UserNotFoundError


async def get_user_or_404(user_id: int, db: DBSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(user_id)
    return user


ValidUser = Annotated[User, Depends(get_user_or_404)]


@router.get("/users/{user_id}")
async def get_user(user: ValidUser) -> ApiResponse[UserResponse]:
    return ApiResponse(data=UserResponse.model_validate(user))
```

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
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def get_item(item_id: int, service: ItemServiceDep) -> ApiResponse[ItemResponse]:
    item = await service.get(item_id)
    return ApiResponse(data=item)
```

---

## 相关文档

- **日志记录** - 详见 [日志](./fastapi-logging.md)
- **请求追踪** - 详见 [中间件](./fastapi-middleware.md)
- **应用启动** - 详见 [应用启动与初始化](./fastapi-startup.md)

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
