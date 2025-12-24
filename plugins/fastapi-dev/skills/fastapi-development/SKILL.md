---
name: fastapi-development
description: |
  FastAPI 开发实现知识库：编写代码的最佳实践，包括 API、数据库、测试、代码规范。
  This skill should be used when implementing FastAPI code, writing routers, services, models, schemas, or tests.
  Triggers: "实现", "编写", "代码", "router", "service", "model", "测试", "重构", "implement", "write code", "create endpoint", "refactor", "add test", "CRUD", "dependency injection", "error handling", "Pydantic schema"
---

# FastAPI 开发实现指南

专注于**代码编写**的最佳实践。

---

## 0. Pydantic 规范

### 充分利用内置验证

- 使用 `EmailStr`, `HttpUrl`, `Field(min_length=, max_length=, ge=, le=)` 等内置验证
- 使用 `Enum` 限制可选值
- 使用 `regex` 模式匹配
- 避免自定义验证器，除非内置无法满足

### 全局 Base Model

```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AppBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )
```

### Settings 拆分

按模块拆分 `BaseSettings`，不要单一大配置文件：

```python
# app/modules/auth/config.py
class AuthSettings(BaseSettings):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

# app/modules/database/config.py
class DatabaseSettings(BaseSettings):
    url: str
    pool_size: int = 5
```

---

## 0.1 Dependencies 规范

### 业务校验

Pydantic 无法处理的校验放在依赖中：

```python
async def valid_user_id(user_id: int, db: DBSession) -> User:
    """验证用户存在"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user

async def valid_owned_resource(
    resource_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> Resource:
    """验证资源存在且属于当前用户"""
    resource = await db.get(Resource, resource_id)
    if not resource or resource.owner_id != current_user.id:
        raise HTTPException(404, "Resource not found")
    return resource
```

### 依赖缓存

同一请求内，相同依赖只执行一次。可以放心组合依赖：

```python
# 这两个依赖都调用 get_db，但 get_db 只执行一次
async def get_user_service(db: DBSession) -> UserService: ...
async def get_order_service(db: DBSession) -> OrderService: ...
```

### 优先 async

即使非 I/O 操作，也优先使用 async 依赖，避免线程池开销。

---

## 0.2 Observability 规范

### Structured Logging

```python
from loguru import logger
import sys

# 配置 JSON 格式（生产环境）
logger.configure(
    handlers=[{
        "sink": sys.stdout,
        "format": "{message}",
        "serialize": True,  # JSON 格式
    }]
)

# 使用
logger.info("User created", user_id=user.id, email=user.email)
```

### Health Checks

```python
@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

@router.get("/ready")
async def ready(db: DBSession) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
```

### Request ID Tracking

```python
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
```

---

## 0.3 Documentation 规范

### 生产环境隐藏文档

```python
app = FastAPI(
    openapi_url="/openapi.json" if settings.debug else None,
)
```

### 完整元数据

```python
@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
    description="创建新用户账户",
    responses={
        409: {"description": "邮箱已存在"},
    },
)
async def create_user(...): ...
```

---

## 0.4 Testing 规范

### 从一开始用 async 测试

使用 `httpx.AsyncClient`，避免后期事件循环冲突：

```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
```

### 测试原则

- 测试行为，不测试实现
- 每个测试独立，不依赖执行顺序
- 使用 factory 创建测试数据
- 覆盖 happy path + edge cases

---

## 1. 代码规范

### 工具配置

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "ASYNC"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### 命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| 变量/函数 | snake_case | `get_user_by_id` |
| 类 | PascalCase | `UserService` |
| 常量 | UPPER_SNAKE | `MAX_RETRIES` |

### 类型提示

```python
# 必须使用类型提示
from typing import Annotated

async def get_user(user_id: int) -> User | None:
    ...

# 使用 Annotated 增强依赖注入
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

---

## 2. API 实现

### Router 模板

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UserResponse])
async def list_users(
    service: UserServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[UserResponse]:
    """获取用户列表"""
    return await service.list(skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    service: UserServiceDep,
) -> UserResponse:
    """获取单个用户"""
    user = await service.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    service: UserServiceDep,
) -> UserResponse:
    """创建用户"""
    return await service.create(data)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    service: UserServiceDep,
) -> UserResponse:
    """更新用户"""
    user = await service.update(user_id, data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    service: UserServiceDep,
) -> None:
    """删除用户"""
    if not await service.delete(user_id):
        raise HTTPException(status_code=404, detail="User not found")
```

### 依赖注入

```python
# app/core/deps.py
from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    return UserService(db)

# 类型别名
DBSession = Annotated[AsyncSession, Depends(get_db)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

---

## 3. Schema 实现

### Pydantic 模型

```python
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(None, min_length=1, max_length=100)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
```

### 分页响应

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

---

## 4. Service 实现

### Service 模板

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 20) -> list[User]:
        result = await self.session.execute(
            select(User).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump(exclude={"password"}))
        user.hashed_password = hash_password(data.password)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user_id: int, data: UserUpdate) -> User | None:
        user = await self.get(user_id)
        if not user:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user_id: int) -> bool:
        user = await self.get(user_id)
        if not user:
            return False
        await self.session.delete(user)
        return True
```

---

## 5. Model 实现

### SQLAlchemy 模型

```python
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)

    # 关系
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
```

### 数据库连接

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
```

### 查询优化

```python
from sqlalchemy.orm import selectinload, joinedload

# 避免 N+1：使用预加载
async def get_user_with_orders(user_id: int) -> User | None:
    result = await session.execute(
        select(User)
        .options(selectinload(User.orders))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()
```

---

## 6. 错误处理

### 自定义异常

```python
from fastapi import HTTPException, status

class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code

class NotFoundError(AppException):
    def __init__(self, resource: str, id: int | str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id {id} not found",
            code="NOT_FOUND",
        )

class ConflictError(AppException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            code="CONFLICT",
        )
```

---

## 7. 测试实现

### conftest.py

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

@pytest.fixture
async def db_session():
    """每个测试使用独立事务，自动回滚"""
    async with engine.connect() as conn:
        await conn.begin()
        async with async_session(bind=conn) as session:
            yield session
        await conn.rollback()

@pytest.fixture
async def client(db_session) -> AsyncClient:
    """测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

### API 测试

```python
class TestUsersAPI:
    async def test_create_success(self, client: AsyncClient):
        response = await client.post("/users/", json={
            "email": "test@example.com",
            "name": "Test",
            "password": "secret123",
        })
        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"

    async def test_create_duplicate_email(self, client: AsyncClient):
        await client.post("/users/", json={...})
        response = await client.post("/users/", json={...})
        assert response.status_code == 409

    async def test_get_not_found(self, client: AsyncClient):
        response = await client.get("/users/99999")
        assert response.status_code == 404
```

### Service 测试

```python
class TestUserService:
    async def test_create(self, mock_session):
        service = UserService(mock_session)
        result = await service.create(UserCreate(...))
        mock_session.add.assert_called_once()
```

### Fixture 工厂

```python
@pytest.fixture
def user_factory(db_session):
    async def create(**kwargs) -> User:
        user = User(
            email=kwargs.get("email", "test@example.com"),
            name=kwargs.get("name", "Test"),
            hashed_password="hashed",
        )
        db_session.add(user)
        await db_session.flush()
        return user
    return create
```

---

## 8. 代码质量检查

```bash
# 格式化
ruff format .

# Lint
ruff check . --fix

# 类型检查
mypy app

# 测试 + 覆盖率
pytest --cov=app --cov-report=term-missing
```

### 质量标准

| 指标 | 目标 |
|------|------|
| 测试覆盖率 | >= 80% |
| 类型覆盖率 | 100% |
| 函数长度 | <= 20 行 |
| 圈复杂度 | <= 10 |
