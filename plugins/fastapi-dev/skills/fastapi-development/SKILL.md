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
├── main.py              # 应用入口
├── config.py            # 配置管理
├── routers/             # 所有路由
│   ├── users.py
│   └── items.py
├── schemas/             # 所有 Pydantic 模型
├── services/            # 所有业务逻辑
├── models/              # 所有 ORM 模型
└── core/                # 核心基础设施
```

### 模块化结构（按领域组织）

```
app/
├── main.py
├── config.py
├── api/v1/router.py     # 路由聚合
├── modules/             # 按领域划分（单数命名）
│   ├── user/            # 用户模块（自包含）
│   │   ├── router.py       # HTTP 处理
│   │   ├── schemas.py      # Pydantic 模型
│   │   ├── repository.py   # 数据访问层
│   │   ├── service.py      # 业务逻辑层
│   │   ├── models.py       # ORM 模型
│   │   └── dependencies.py # 依赖注入
│   └── item/
└── core/
```

详见 [项目结构](./references/fastapi-project-structure.md) | 模板代码：`assets/simple-api/`、`assets/modular-api/`

---

## 应用入口模板

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.modules.user.router import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 启动时初始化应用级资源，存储到 app.state
    # app.state.db_pool = await create_db_pool()
    # app.state.redis = await create_redis_client()
    yield
    # 关闭时清理
    # await app.state.db_pool.close()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
)

# 中间件（顺序重要：后添加的先执行）
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(user_router, prefix="/api/v1/users", tags=["users"])
```

---

## 配置管理

采用二阶段初始化：先初始化日志，再加载配置，配置失败时日志可用。

```python
from functools import lru_cache
from typing import Literal

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # 必填配置（无默认值，缺失时启动报错）
    database_url: str
    secret_key: str

    # 可选配置
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing = ["/".join(map(str, err.get("loc", []))) for err in exc.errors()]
        raise RuntimeError(f"缺少必要的环境变量: {', '.join(missing)}") from None
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
