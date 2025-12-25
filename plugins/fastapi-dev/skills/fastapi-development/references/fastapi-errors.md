# FastAPI 错误处理

## 错误分类

| 类型 | 描述 | 处理策略 |
|------|------|----------|
| **操作性错误** | 资源不存在、权限不足、验证失败 | 返回明确的错误响应 |
| **程序错误** | 代码缺陷、类型错误 | 记录日志，返回通用错误 |
| **系统错误** | 数据库连接失败、外部服务超时 | 重试/降级，返回 503 |

---

## HTTPException

FastAPI 内置异常类，用于返回 HTTP 错误响应。

```python
from fastapi import HTTPException, status

# 基础用法
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Item not found",
)

# detail 支持复杂类型（dict/list）
raise HTTPException(
    status_code=400,
    detail={
        "error": "validation_failed",
        "fields": ["email", "password"],
    },
)

# 带自定义 Headers（常用于认证）
raise HTTPException(
    status_code=401,
    detail="Invalid token",
    headers={"WWW-Authenticate": "Bearer"},
)
```

**关键点**：用 `raise` 抛出，不是 `return`。抛出后立即终止请求处理。

---

## 自定义异常体系

### 基础异常类

```python
# app/exceptions.py
from typing import Any


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """资源不存在"""

    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} with id {resource_id} not found",
            status_code=404,
            details={"resource": resource, "id": resource_id},
        )


class ValidationError(AppException):
    """业务验证失败"""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details={"field": field} if field else {},
        )


class AuthenticationError(AppException):
    """认证失败"""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="AUTHENTICATION_ERROR",
            message=message,
            status_code=401,
        )


class AuthorizationError(AppException):
    """权限不足"""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            code="AUTHORIZATION_ERROR",
            message=message,
            status_code=403,
        )


class ConflictError(AppException):
    """资源冲突"""

    def __init__(self, message: str):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=409,
        )


class ServiceUnavailableError(AppException):
    """外部服务不可用"""

    def __init__(self, service: str):
        super().__init__(
            code="SERVICE_UNAVAILABLE",
            message=f"{service} is temporarily unavailable",
            status_code=503,
        )
```

---

## 全局异常处理器

### 定义处理器函数

```python
# app/exceptions.py (续)
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


async def app_exception_handler(request: Request, exc: AppException):
    """业务异常处理"""
    logger.warning(
        "Business exception: {} | code={} path={}",
        exc.message,
        exc.code,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
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
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
        },
    )


async def starlette_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    """Starlette HTTP 异常处理（中间件、插件等）"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "details": {},
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """未捕获异常处理"""
    logger.exception("Unexpected error | path={}", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {},
        },
    )
```

### 注册处理器

```python
# app/exceptions.py (续)
from fastapi import FastAPI


def setup_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
```

> **完整 main.py 示例** 详见 [应用启动与初始化](./fastapi-startup.md)

### 复用默认处理器

需要在自定义处理中保留默认行为时：

```python
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)


async def custom_http_handler(request: Request, exc: StarletteHTTPException):
    """自定义处理后复用默认行为"""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return await http_exception_handler(request, exc)
```

---

## 模块级异常

```python
# app/modules/user/exceptions.py
from app.exceptions import NotFoundError, ConflictError, AppException


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int):
        super().__init__(resource="User", resource_id=user_id)


class EmailAlreadyExistsError(ConflictError):
    def __init__(self, email: str):
        super().__init__(message=f"Email {email} is already registered")


class InvalidCredentialsError(AppException):
    def __init__(self):
        super().__init__(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )
```

### Service 层使用

```python
# app/modules/user/service.py
from .exceptions import UserNotFoundError, EmailAlreadyExistsError


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def create(self, data: UserCreate) -> User:
        if await self.repo.get_by_email(data.email):
            raise EmailAlreadyExistsError(data.email)
        return await self.repo.create(data)
```

---

## 依赖中的异常处理

### yield 依赖的事务管理

基于 [数据库集成](./fastapi-database.md#依赖注入) 中的 `get_db()` 依赖，可扩展区分业务异常：

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except AppException:
            await session.rollback()
            raise  # 业务异常：回滚后继续抛出，由异常处理器处理
        except Exception:
            await session.rollback()
            raise  # 其他异常：回滚
```

### 依赖中验证并抛出异常

```python
from typing import Annotated
from fastapi import Depends

from app.modules.user.exceptions import UserNotFoundError


async def get_user_or_404(
    user_id: int,
    db: AsyncDBSession,
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UserNotFoundError(user_id)
    return user


ValidUser = Annotated[User, Depends(get_user_or_404)]


@router.get("/users/{user_id}")
async def get_user(user: ValidUser):
    return user  # 用户不存在时，依赖已抛出 404
```

---

## 错误响应模型

### 定义统一格式

```python
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str
    type: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | list[ErrorDetail] = {}
```

### OpenAPI 文档声明

```python
@router.get(
    "/items/{item_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Item not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def get_item(item_id: int, service: ItemServiceDep):
    return await service.get(item_id)
```

---

## 相关文档

- **日志记录** - 详见 [日志](./fastapi-logging.md)（两阶段初始化、Loguru 配置）
- **请求追踪** - 详见 [中间件](./fastapi-middleware.md)（LoggingMiddleware、request_id）
- **中间件异常** - 详见 [中间件](./fastapi-middleware.md)（ExceptionMiddleware）

---

## 最佳实践

| 实践 | 说明 |
|------|------|
| **定义异常体系** | 继承基类，分类管理（NotFoundError, ValidationError 等） |
| **统一响应格式** | `code` + `message` + `details` 三元组 |
| **模块级异常** | 按领域组织，如 `user/exceptions.py` |
| **依赖验证** | 在依赖中抛出异常，路由保持简洁 |
| **分层处理** | Service 抛业务异常，Router 转换为 HTTP 响应 |
| **日志记录** | 业务异常 warning，系统异常 exception |
| **隐藏细节** | 生产环境不暴露堆栈和内部信息 |
| **文档化错误** | 在 OpenAPI 中声明 `responses` |
| **兼容 Starlette** | 注册 `StarletteHTTPException` 处理器 |
