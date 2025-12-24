---
name: fastapi-development
description: |
  This skill should be used when the user wants to implement, write, or code FastAPI features.
  Covers project structure, async patterns, dependency injection, Pydantic schemas, SQLAlchemy/SQLModel,
  error handling, testing, logging, performance optimization, and deployment.

  Trigger phrases: "write a router", "implement endpoint", "create API", "add CRUD", "write service",
  "Pydantic schema", "SQLAlchemy model", "async database", "error handling", "write tests",
  "配置管理", "依赖注入", "数据库集成", "错误处理", "性能优化"
---

# FastAPI 最佳实践

> 适用版本：FastAPI >= 0.120.0 | Python >= 3.11 | Pydantic >= 2.7.0
>
> 更新时间：2025-12

## 快速参考

### 版本要求

```bash
# 使用 uv 创建项目（推荐）
uv init my-project && cd my-project
uv add "fastapi[standard]"  # 包含 uvicorn, pydantic-settings 等
```

### 核心原则

1. **异步优先** - I/O 操作使用 `async def`，CPU 密集型任务分发到 worker
2. **类型安全** - 使用 `Annotated` 声明参数和依赖
3. **分离关注点** - 请求/响应模型分离，按领域组织代码
4. **依赖注入** - 利用 DI 系统管理资源和验证逻辑
5. **显式配置** - 使用 pydantic-settings 管理环境配置

---

## 项目结构

根据项目规模选择合适的结构：

| 场景 | 推荐结构 |
|------|----------|
| 小项目 / 原型 / 单人开发 | 简单结构（按层组织） |
| 团队开发 / 中大型项目 | 模块化结构（按领域组织） |

### 简单结构（按层组织）

```
app/
├── __init__.py
├── main.py              # 应用入口
├── config.py            # 配置管理
├── dependencies.py      # 共享依赖
├── exceptions.py        # 异常定义
│
├── routers/             # 路由层（按资源划分）
│   ├── __init__.py
│   ├── users.py
│   └── items.py
│
├── schemas/             # Pydantic 模型
│   ├── __init__.py
│   ├── user.py
│   └── item.py
│
├── services/            # 业务逻辑
│   ├── __init__.py
│   ├── user_service.py
│   └── item_service.py
│
├── models/              # ORM 模型
│   ├── __init__.py
│   └── user.py
│
└── core/                # 核心基础设施
    ├── __init__.py
    ├── database.py
    ├── security.py
    └── middleware.py
```

### 模块化结构（按领域组织）

```
app/
├── __init__.py
├── main.py                 # 应用入口
├── config.py               # 全局配置
├── dependencies.py         # 全局共享依赖
├── exceptions.py           # 全局异常基类
│
├── api/                    # API 版本管理
│   └── v1/
│       ├── __init__.py
│       └── router.py       # v1 路由聚合
│
├── modules/                # 功能模块（按领域划分，单数命名）
│   ├── __init__.py
│   │
│   ├── user/               # 用户模块（完全自包含）
│   │   ├── __init__.py
│   │   ├── router.py       # HTTP 处理
│   │   ├── schemas.py      # Pydantic 模型
│   │   ├── models.py       # ORM 模型
│   │   ├── repository.py   # 数据访问层
│   │   ├── service.py      # 业务逻辑层
│   │   ├── dependencies.py # 依赖注入
│   │   └── exceptions.py   # 模块异常
│   │
│   └── item/
│       └── ...
│
└── core/                   # 核心基础设施
    ├── __init__.py
    ├── database.py
    ├── security.py
    ├── cache.py
    └── middleware.py

# tests/ 目录与 app/ 同级
```

详见 [项目结构](./references/fastapi-project-structure.md) | 模板代码：`assets/simple-api/`、`assets/modular-api/`

---

## 应用入口模板

采用 `setup_xxx` / `init_xxx` 模式分离职责：

- `setup_xxx(app)` - 配置组件（中间件、路由）
- `init_xxx(app)` / `close_xxx(app)` - 管理资源生命周期（数据库、HTTP 客户端）

```python
# main.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.config import get_settings
from app.api.v1.router import setup_router
from app.core.database import init_database, close_database
from app.core.http import init_http_client, close_http_client
from app.core.middleware import setup_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_database()
    await init_http_client(app)
    yield
    await close_http_client(app)
    await close_database()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
)

setup_middleware(app)
setup_router(app)
```

```python
# core/middleware.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings


def setup_middleware(app: FastAPI) -> None:
    """配置中间件（顺序重要：后添加的先执行）"""
    settings = get_settings()
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

```python
# api/v1/router.py
from fastapi import APIRouter, FastAPI

from app.modules.user.router import router as user_router

api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["users"])


def setup_router(app: FastAPI) -> None:
    """配置路由"""
    app.include_router(api_router, prefix="/api/v1")
```

---

## 配置管理

采用分层嵌套结构，使用 `env_prefix` 区分模块，`@lru_cache` 缓存实例：

```python
# config.py
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置，环境变量前缀 DB_"""
    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "app"
    user: str = "postgres"
    password: SecretStr

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis 配置，环境变量前缀 REDIS_"""
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class Settings(BaseSettings):
    """应用主配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用配置
    app_name: str = "FastAPI App"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: SecretStr

    # 嵌套配置
    db: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()

    # 其他配置
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """获取配置（缓存单例）"""
    return Settings()
```

对应的 `.env` 文件：

```bash
# 应用
SECRET_KEY=your-secret-key
DEBUG=true

# 数据库（DB_ 前缀）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=postgres
DB_PASSWORD=password

# Redis（REDIS_ 前缀）
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

## 路由与依赖注入

```python
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.user.schemas import UserCreate, UserResponse
from app.modules.user.service import UserService
from app.modules.user.dependencies import get_user_service

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
):
    return await service.create(user_in)
```

---

## Pydantic 模型

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )


class UserCreate(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")


class UserResponse(BaseSchema):
    id: int
    email: EmailStr
    username: str
    created_at: datetime
```

---

## 数据库依赖

```python
from typing import Annotated, Generator
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSession = Annotated[Session, Depends(get_db)]
```

---

## 错误处理

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )
```

---

## 后台任务

```python
from fastapi import BackgroundTasks


def process_in_background(item_id: int):
    """后台任务应创建自己的数据库连接"""
    db = SessionLocal()
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        # 处理逻辑...
    finally:
        db.close()


@router.post("/items/")
async def create_item(item: ItemCreate, background_tasks: BackgroundTasks, db: DBSession):
    db_item = Item(**item.model_dump())
    db.add(db_item)
    db.commit()
    # 传递 ID 而非对象
    background_tasks.add_task(process_in_background, db_item.id)
    return db_item
```

---

## 详细文档

更多详细内容请参考 references 目录：

### 核心开发
- [编码规范](./references/fastapi-coding-conventions.md) - 命名规范、类型注解、Ruff 配置
- [项目结构](./references/fastapi-project-structure.md) - 两种结构选择（简单/模块化）
- [API 设计](./references/fastapi-api-design.md) - REST 规范、分页、错误处理
- [异步处理](./references/fastapi-async.md)
- [依赖注入](./references/fastapi-dependencies.md)
- [数据验证](./references/fastapi-validation.md)

### 数据与安全
- [数据库集成](./references/fastapi-database.md) - SQLAlchemy 2.0/SQLModel 异步
- [安全性](./references/fastapi-security.md) - OAuth2、JWT、CORS
- [错误处理](./references/fastapi-error-handling.md)

### 第三方集成
- [HTTP 客户端](./references/fastapi-httpx.md) - httpx AsyncClient 最佳实践
- [日志](./references/fastapi-logging.md) - Loguru 二阶段初始化、结构化日志
- [测试](./references/fastapi-testing.md) - pytest-asyncio、依赖覆盖、数据库测试

### 工具与运维
- [uv 包管理](./references/fastapi-uv.md) - 项目初始化、依赖管理、Docker 集成
- [性能优化](./references/fastapi-performance.md) - 缓存、连接池、并发
- [部署](./references/fastapi-deployment.md) - Docker、K8s、Nginx

### 项目模板
- `assets/simple-api/` - 简单结构模板（按层组织）
- `assets/modular-api/` - 模块化结构模板（按领域组织）

---

## 获取更多文档

如果以上内容不足，使用 context7 获取最新官方文档：

```
mcp__context7__get-library-docs
  context7CompatibleLibraryID: /fastapi/fastapi
  topic: <相关主题>
  mode: code (API/示例) 或 info (概念)
```

常用主题：`dependencies`, `middleware`, `lifespan`, `background tasks`, `websocket`, `testing`, `security`, `oauth2`, `jwt`
