---
name: fastapi-development
description: |
  FastAPI 开发最佳实践。包含分层架构、项目结构、异步模式、依赖注入、数据验证、数据库集成、错误处理、测试等。
  触发：实现端点、创建 API、CRUD 操作、Pydantic schema、SQLAlchemy 模型、异步数据库、错误处理、编写测试
---

# FastAPI 最佳实践

> FastAPI >= 0.120.0 | Python >= 3.11 | Pydantic >= 2.7.0

## 核心原则

1. **分层架构** - Router → Service → Repository
2. **异步优先** - I/O 操作使用 `async def`
3. **类型安全** - 使用 `Annotated` 声明依赖
4. **分离关注点** - 请求/响应模型分离，按领域组织代码
5. **依赖注入** - 利用 DI 系统管理资源和验证逻辑
6. **显式配置** - 使用 pydantic-settings 管理环境配置

---

## 分层架构

```
Router (HTTP 层)
   ↓ 调用
Service (业务逻辑层)
   ↓ 调用
Repository (数据访问层)
   ↓ 操作
Database
```

| 层 | 职责 | 不应该做 |
|----|------|----------|
| **Router** | HTTP 处理、参数验证、响应格式 | 写 SQL、业务逻辑 |
| **Service** | 业务逻辑、事务编排、跨模块协调 | 直接操作数据库 |
| **Repository** | 数据访问、SQL 查询、ORM 操作 | 处理 HTTP、业务规则 |

### 分层示例

```python
# repository.py - 只负责数据访问
class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


# service.py - 业务逻辑
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def register(self, data: UserCreate) -> User:
        if self.repo.get_by_email(data.email):
            raise UserAlreadyExistsError(data.email)
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
        )
        return self.repo.create(user)


# dependencies.py
def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)

def get_user_service(repo: Annotated[UserRepository, Depends(get_user_repository)]) -> UserService:
    return UserService(repo)


# router.py - HTTP 处理
@router.post("/", response_model=UserResponse, status_code=201)
def create_user(
    data: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.register(data)
```

### 分层的好处

| 好处 | 说明 |
|------|------|
| **可测试** | Service 可 mock Repository 进行单元测试 |
| **可替换** | 切换数据库只需替换 Repository 实现 |
| **职责清晰** | Router 不写 SQL，Repository 不处理 HTTP |
| **复用** | 多个 Router 可共用同一个 Service |

---

## 项目结构

| 场景 | 推荐结构 |
|------|----------|
| 小项目 / 原型 / 单人开发 | 简单结构（按层组织） |
| 团队开发 / 中大型项目 | 模块化结构（按领域组织） |

### 简单结构（按层组织）

```
app/
├── __init__.py
├── main.py                 # 应用入口
├── config.py               # 配置管理
├── dependencies.py         # 共享依赖
├── exceptions.py           # 异常定义
│
├── routers/                # 路由层
│   ├── __init__.py
│   ├── users.py
│   └── items.py
│
├── schemas/                # Pydantic 模型
│   ├── __init__.py
│   ├── user.py
│   └── item.py
│
├── services/               # 业务逻辑层
│   ├── __init__.py
│   ├── user_service.py
│   └── item_service.py
│
├── repositories/           # 数据访问层
│   ├── __init__.py
│   ├── user_repository.py
│   └── item_repository.py
│
├── models/                 # ORM 模型
│   ├── __init__.py
│   └── user.py
│
└── core/                   # 核心基础设施
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
├── modules/                # 功能模块（按领域划分）
│   ├── __init__.py
│   │
│   ├── user/               # 用户模块（完全自包含）
│   │   ├── __init__.py
│   │   ├── router.py       # 路由层
│   │   ├── schemas.py      # Pydantic 模型
│   │   ├── models.py       # ORM 模型
│   │   ├── repository.py   # 数据访问层
│   │   ├── service.py      # 业务逻辑层
│   │   ├── dependencies.py # 模块依赖
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
```

详见 [项目结构详解](./references/fastapi-project-structure.md)

---

## 快速参考

### 应用入口

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化资源
    yield
    # 关闭：清理资源

app = FastAPI(title="MyApp", lifespan=lifespan)
```

### 配置管理

使用 `pydantic-settings` 管理应用配置：

- **`.env` 文件** - 管理开发环境配置
- **`SecretStr`** - 敏感信息防止日志泄露
- **必填字段无默认值** - 启动时强制验证
- **`Field(ge=1, le=100)`** - 类型约束验证
- **`@lru_cache`** - 全局单例，避免重复解析
- **嵌套配置** - 使用 `env_nested_delimiter="_"` + `env_nested_max_split=1`

详见 [配置管理](./references/fastapi-config.md)

### 路由与依赖注入

```python
from typing import Annotated
from fastapi import APIRouter, Depends

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(
    data: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.register(data)
```

### 数据库依赖

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DBSession = Annotated[Session, Depends(get_db)]
```

### Pydantic 模型

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

class UserCreate(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8)

class UserResponse(BaseSchema):
    id: int
    email: EmailStr
```

### 错误处理

```python
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

## 详细文档

### 核心开发
- [核心模式](./references/fastapi-patterns.md) - 异步、依赖注入、后台任务、Lifespan
- [配置管理](./references/fastapi-config.md) - pydantic-settings、嵌套配置、验证器
- [数据模型](./references/fastapi-models.md) - Pydantic 验证、类型注解
- [错误处理](./references/fastapi-errors.md) - 异常体系、统一响应
- [项目结构](./references/fastapi-project-structure.md) - 目录布局详解

### 数据与安全
- [数据库集成](./references/fastapi-database.md) - SQLAlchemy 2.0 异步
- [安全性](./references/fastapi-security.md) - OAuth2、JWT、权限控制

### 工具与运维
- [开发工具](./references/fastapi-tooling.md) - uv、Ruff、ty、pre-commit
- [API 设计](./references/fastapi-api-design.md) - REST 规范、分页
- [性能优化](./references/fastapi-performance.md) - 缓存、连接池、并发
- [测试](./references/fastapi-testing.md) - pytest-asyncio、依赖覆盖
- [部署](./references/fastapi-deployment.md) - Docker、Kubernetes

### 集成
- [HTTP 客户端](./references/fastapi-httpx.md) - httpx AsyncClient
- [日志](./references/fastapi-logging.md) - Loguru 结构化日志

---

## 获取更多文档

使用 context7 获取最新官方文档：

```
mcp__context7__get-library-docs
  context7CompatibleLibraryID: /fastapi/fastapi
  topic: <相关主题>
  mode: code (API/示例) 或 info (概念)
```

常用主题：`dependencies`, `middleware`, `lifespan`, `background tasks`, `websocket`, `testing`, `security`, `oauth2`, `jwt`
