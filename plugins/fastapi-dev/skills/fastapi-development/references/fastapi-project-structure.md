# FastAPI 项目结构

## 如何选择结构

| 场景 | 推荐结构 | 理由 |
|------|----------|------|
| 原型/MVP | 简单结构 | 快速开发，无需过度设计 |
| 小项目（< 20 文件） | 简单结构 | 易于理解和维护 |
| 单人开发 | 简单结构 | 无协作冲突风险 |
| 团队开发 | 模块化结构 | 减少合并冲突，便于分工 |
| 中大型项目 | 模块化结构 | 高内聚低耦合，易于扩展 |
| 需要 API 版本管理 | 模块化结构 | 内置版本化支持 |

---

## 结构一：简单结构（按层组织）

适用于小项目、原型验证、单人开发。

```
app/
├── __init__.py
├── main.py              # 应用入口
├── config.py            # 配置管理
├── dependencies.py      # 共享依赖
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
    ├── exception_handlers.py
    ├── exceptions.py
    └── middlewares.py
```

### 优点

- 简单直观，容易上手
- 同类文件放在一起，查找方便
- 适合快速迭代

### 缺点

- 随着功能增加，每个目录变得臃肿
- 修改一个功能需要跨多个目录
- 团队协作时容易产生冲突

### 代码示例

```python
# dependencies.py（集中管理依赖）
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.user_service import UserService

DBSession = Annotated[AsyncSession, Depends(get_db)]

def get_user_service(db: DBSession) -> UserService:
    return UserService(db)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

```python
# routers/users.py（只导入依赖，不定义）
from fastapi import APIRouter, status

from app.dependencies import UserServiceDep
from app.schemas.response import ApiResponse
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(user_in)
    return ApiResponse(data=user)
```

---

## 结构二：模块化结构（按领域组织）

适用于中大型项目、团队开发、长期维护。

```
app/
├── __init__.py
├── main.py                 # 应用入口
├── config.py               # 全局配置
├── dependencies.py         # 全局共享依赖
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
│   ├── item/
│   │   └── ...
│   │
│   └── order/
│       └── ...
│
└── core/                   # 核心基础设施
    ├── __init__.py
    ├── database.py
    ├── security.py
    ├── cache.py
    ├── exception_handlers.py
    ├── exceptions.py
    └── middlewares.py

# tests/ 目录与 app/ 同级
```

### 优点

- 每个模块完全自包含，高内聚
- 修改一个功能只需改一个目录
- 便于团队分工，减少合并冲突
- 支持 API 版本管理
- 易于添加/删除功能模块

### 缺点

- 初期设置稍复杂
- 小项目可能过度设计
- 模块间共享代码需要放到 `core/`

### 代码示例

```python
# modules/user/dependencies.py（模块自包含的依赖）
from typing import Annotated
from fastapi import Depends

from app.dependencies import DBSession
from .repository import UserRepository
from .service import UserService


def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

```python
# modules/user/router.py（只导入依赖，不定义）
from fastapi import APIRouter, status

from app.schemas.response import ApiResponse
from .schemas import UserCreate, UserResponse
from .dependencies import UserServiceDep

router = APIRouter()


@router.post("/", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, service: UserServiceDep) -> ApiResponse[UserResponse]:
    user = await service.create(user_in)
    return ApiResponse(data=user)
```

```python
# api/v1/router.py（路由聚合）
from fastapi import APIRouter

from app.modules.user.router import router as user_router

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["users"])
# 添加其他模块路由：
# from app.modules.item.router import router as item_router
# api_router.include_router(item_router, prefix="/items", tags=["items"])
```

---

## 分层架构

模块化结构采用三层架构，职责分离：

```
Router → Service → Repository → Database
  ↓         ↓           ↓
HTTP处理  业务逻辑    数据访问
```

| 层 | 职责 | 示例 |
|---|---|---|
| Router | HTTP 处理 | 参数解析、响应格式、状态码 |
| Service | 业务逻辑 | 校验规则、编排、异常处理 |
| Repository | 数据访问 | CRUD、查询构建、事务 |

**优势**：
- 关注点分离，代码清晰
- 便于测试（可单独 mock repository）
- 易于替换数据源（如从 PostgreSQL 迁移到 MongoDB）

> 完整的分层代码示例（Repository、Service、Router、依赖注入）详见 [核心模式 - 分层架构](./fastapi-patterns.md#分层架构)

---

## 命名约定

| 元素 | 命名方式 | 示例 |
|------|----------|------|
| 模块目录 | 单数 | `modules/user/`, `modules/order/` |
| API 路径 | 复数 | `/api/v1/users`, `/api/v1/orders` |
| 类名 | 单数 | `User`, `UserService`, `UserRepository` |
| 测试文件 | 单数 | `test_user.py`, `test_order.py` |

**理由**：
- 模块目录表示"领域"而非"资源集合"
- 与类名保持一致（User → user/）
- 符合 DDD 命名习惯

---

## 模块文件职责

| 文件 | 职责 | 内容 |
|------|------|------|
| `router.py` | HTTP 层 | 路由定义、请求/响应处理 |
| `schemas.py` | 数据验证 | Pydantic 请求/响应模型 |
| `models.py` | 持久化 | ORM 数据库模型 |
| `repository.py` | 数据访问 | 数据库查询封装 |
| `service.py` | 业务逻辑 | 核心业务规则 |
| `dependencies.py` | 依赖注入 | 模块专用依赖 |
| `exceptions.py` | 错误处理 | 模块专用异常 |

---

## 模板代码

完整模板代码位于 `assets/` 目录：

- `assets/simple-api/` - 简单结构模板
- `assets/modular-api/` - 模块化结构模板
