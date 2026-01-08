# FastAPI 项目结构
> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

聚焦目录组织与职责边界；API 路径/版本/响应规范详见 [API 设计](./fastapi-api-design.md)。

## 设计原则
- 结构服务于协作与演进，先小后大
- 目录边界与业务领域对齐，减少跨模块耦合
- 路由只处理 HTTP 语义，业务逻辑下沉到服务层
- 共享基础能力集中到 `core/`，避免散落
- API 规范集中在单一文档维护，避免分叉

## 最佳实践
1. 规模小先用简单结构，规模上来再切模块化
2. 模块内自包含，跨模块共享放 `core/`
3. 路由仅做参数解析、响应封装与状态码控制
4. 命名规则统一：模块单数、路径复数
5. API 版本/路径约束统一遵循 [API 设计](./fastapi-api-design.md)

## 目录
- `如何选择结构`
- `结构一：简单结构（按层组织）`
- `结构二：模块化结构（按领域组织）`
- `分层架构`
- `命名约定`
- `模块文件职责`
- `模板代码`

---

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

### 使用要点

- 依赖在 `dependencies.py` 统一管理，路由只引用依赖
- Service 负责业务规则，Router 负责 HTTP 语义
- 结构扩张后可平滑迁移到模块化结构

> 完整示例见 `assets/simple-api/app/`，此处省略细节以突出结构要点。

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

### 使用要点

- `api/v1/router.py` 只做路由聚合
- 模块内部维护自己的依赖、模型与异常
- API 路径/版本规范详见 [API 设计](./fastapi-api-design.md)

```python
# api/v1/router.py（路由聚合）
from fastapi import APIRouter
from app.modules.user.router import router as user_router

api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["users"])
```

> 完整示例见 `assets/modular-api/app/`，此处省略依赖与路由细节。

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

> 完整的分层代码示例（Repository、Service、Router、依赖注入）详见 [分层架构](./fastapi-layered-architecture.md)

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

> API 路径与版本规则以 [API 设计](./fastapi-api-design.md) 为准。

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

- `assets/simple-api/app/` - 简单结构模板
- `assets/modular-api/app/` - 模块化结构模板
