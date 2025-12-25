# FastAPI 错误处理

## HTTPException

FastAPI 内置的异常类，用于返回 HTTP 错误响应。在分层架构中，Router 层负责将业务异常转换为 HTTP 响应。

```python
from fastapi import APIRouter, HTTPException, status

from app.modules.item.dependencies import ItemServiceDep
from app.modules.item.exceptions import ItemNotFoundError

router = APIRouter()


@router.get("/items/{item_id}")
async def get_item(item_id: int, service: ItemServiceDep):
    try:
        return await service.get_by_id(item_id)
    except ItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
```

### 带自定义 Headers

```python
raise HTTPException(
    status_code=401,
    detail="Invalid token",
    headers={"WWW-Authenticate": "Bearer"},
)
```

---

## 自定义异常体系

### 定义基础异常

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
```

### 注册异常处理器

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.exceptions import AppException


app = FastAPI()


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"][1:]),  # 跳过 "body"
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


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # 生产环境隐藏内部错误细节
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {},
        },
    )
```

---

## 模块级异常

```python
# app/modules/user/exceptions.py
from app.exceptions import AppException, NotFoundError, ConflictError


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

### 使用

```python
# app/modules/user/service.py
from .repository import UserRepository
from .exceptions import UserNotFoundError, EmailAlreadyExistsError


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get(self, user_id: int) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def create(self, user_in: UserCreate) -> User:
        if await self.repo.get_by_email(user_in.email):
            raise EmailAlreadyExistsError(user_in.email)
        # 创建用户...
```

---

## 依赖中的异常处理

### yield 依赖的异常处理

```python
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except AppException:
            # 业务异常：回滚但不隐藏
            await session.rollback()
            raise
        except Exception:
            # 其他异常：回滚
            await session.rollback()
            raise
```

### 捕获并转换异常

```python
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


@app.get("/users/{user_id}")
async def get_user(user: ValidUser):
    return user  # 如果用户不存在，依赖会抛出 404
```

---

## 错误响应模型

### 定义统一响应格式

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


# OpenAPI 文档中显示错误响应
@app.get(
    "/items/{item_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Item not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def get_item(item_id: int):
    ...
```

---

## 日志记录

```python
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    # 记录业务异常
    logger.warning(
        "Business exception: %s",
        exc.message,
        extra={
            "code": exc.code,
            "path": request.url.path,
            "method": request.method,
        },
    )
    return JSONResponse(...)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # 记录未预期异常
    logger.exception(
        "Unexpected error",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )
    return JSONResponse(...)
```

---

## 中间件异常处理

```python
import time
import traceback


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        # 中间件中的异常不会被 exception_handler 捕获
        logger.exception("Unhandled exception in middleware")
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "Internal server error"},
        )
```

---

## 最佳实践

1. **定义异常体系** - 继承基类，分类管理
2. **统一响应格式** - code + message + details
3. **模块级异常** - 业务异常按模块组织
4. **依赖验证** - 在依赖中抛出异常而非路由
5. **日志记录** - 记录异常上下文
6. **隐藏内部细节** - 生产环境不暴露堆栈
7. **文档化错误** - 在 OpenAPI 中声明错误响应
