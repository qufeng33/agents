---
name: fastapi-dev
version: 1.0.0
description: |
  FastAPI 开发最佳实践。包含架构设计、分层架构、项目结构、异步模式、依赖注入、数据验证、数据库集成、错误处理、测试、部署等完整开发周期。

  触发场景：
  - 架构设计、需求分析、技术选型、数据库设计、表设计
  - 创建 FastAPI 端点、路由、REST API 设计
  - SQLAlchemy 2.0 异步数据库操作、事务管理、Alembic 迁移
  - ORM 基类设计、UUIDv7 主键、软删除、时间戳字段
  - 审计日志、操作追踪、变更历史、contextvars
  - Pydantic v2 模型验证、序列化、ConfigDict 配置
  - 中间件配置、CORS、请求日志、GZip 压缩
  - 认证授权、OAuth2、JWT、权限控制
  - 错误处理体系、自定义异常、统一响应格式
  - 后台任务、任务队列（ARQ、Celery）、定时任务（APScheduler）
  - 日志配置、Loguru 两阶段初始化
  - pytest 异步测试、依赖覆盖、fixture
  - httpx 异步 HTTP 客户端集成
  - Docker 部署、Kubernetes、生产配置
  - 性能优化、缓存、连接池

  关键词：设计、架构、需求、技术选型、实现端点、创建 API、CRUD 操作、Pydantic schema、SQLAlchemy 模型、异步数据库、错误处理、编写测试、FastAPI 中间件、JWT 认证、部署配置、lifespan、依赖注入、后台任务、定时任务、任务队列、软删除、审计日志、UUIDv7、基类、Mixin

  不适用：Django、Flask、Tornado 等其他 Python Web 框架
---

# FastAPI 最佳实践

**要求**: FastAPI ≥0.122.0 | Python ≥3.13 | Pydantic ≥2.10

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
Router (HTTP 层) → Service (业务逻辑层) → Repository (数据访问层) → Database
```

| 层 | 职责 | 不应该做 |
|----|------|----------|
| **Router** | HTTP 处理、参数验证、响应格式 | 写 SQL、业务逻辑 |
| **Service** | 业务逻辑、事务编排、跨模块协调 | 直接操作数据库（简化结构例外） |
| **Repository** | 数据访问、SQL 查询、ORM 操作 | 处理 HTTP、业务规则、**调用 commit** |

> **注意 - 事务约定**：一个请求 = 一个事务。`get_db()` 依赖统一管理 commit/rollback，Repository 只用 `flush()`。

**好处**：可测试（mock Repository）、可替换（切换数据库）、职责清晰、代码复用

详见 [分层架构](./references/fastapi-layered-architecture.md)

---

## 项目结构

| 场景 | 推荐结构 |
|------|----------|
| 小项目 / 原型 / 单人开发 | 简单结构（按层组织） |
| 团队开发 / 中大型项目 | 模块化结构（按领域组织） |

> 说明：`user` 是数据库保留字，示例统一使用表名 `app_user`、API 路径 `/users`。

### 简单结构

```
{project}/
├── app/
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置管理
│   ├── dependencies.py      # 共享依赖
│   ├── routers/             # 路由层
│   ├── schemas/             # Pydantic 模型
│   ├── services/            # 业务逻辑层（简化结构可直接操作数据库）
│   ├── models/              # ORM 模型
│   └── core/                # 数据库、安全等基础设施
├── tests/
│   └── conftest.py          # 测试配置与 Fixtures
├── pyproject.toml
├── .env.example
└── README.md
```

> **简化架构**：`Router → Service → Database`（无 Repository 层）。此模式下 Service 兼任 Repository，允许直接注入 `AsyncSession` 操作数据库，适合快速开发。事务仍由 `get_db()` 统一管理。

### 模块化结构

```
{project}/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/v1/              # API 版本管理
│   ├── modules/             # 功能模块（按领域划分）
│   │   ├── user/            # 完全自包含：router/schemas/models/service/repository/exceptions/dependencies
│   │   └── item/
│   └── core/                # 基础设施 + 全局异常
├── tests/
│   └── conftest.py
├── pyproject.toml
├── .env.example
└── README.md
```

详见 [项目结构详解](./references/fastapi-project-structure.md)

**代码模板**：`assets/simple-api/` 和 `assets/modular-api/`，模板内 `app/` 目录即应用代码，复制后直接得到正确的项目结构。

---

## 快速参考

### 应用入口

使用 `lifespan` 管理应用生命周期（启动/关闭时的资源初始化与清理）。

详见 [应用生命周期](./references/fastapi-app-lifecycle.md)

### 配置管理

使用 `pydantic-settings` 管理应用配置：

- **`.env` 文件** - 开发环境配置
- **`SecretStr`** - 敏感信息防泄露
- **必填字段无默认值** - 启动时强制验证
- **`Field(ge=1, le=100)`** - 类型约束
- **`@lru_cache`** - 全局单例
- **嵌套配置** - `env_nested_delimiter="_"` + `env_nested_max_split=1`

详见 [配置管理](./references/fastapi-config.md)

### 路由与依赖注入

- 使用 `Annotated[T, Depends(...)]` 声明依赖
- 依赖链：Router → Service → Repository → Database
- 类型别名简化重复声明：`DBSession = Annotated[Session, Depends(get_db)]`
- **返回类型必须标注**：`async def get_user(...) -> UserResponse:`

详见 [依赖注入](./references/fastapi-dependency-injection.md)

### 数据模型

- 基类配置：`ConfigDict(from_attributes=True, str_strip_whitespace=True)`
- 分离模型：`Create` / `Update` / `Response` / `InDB`
- 字段验证：`Field(min_length=8)`, `@field_validator`

详见 [数据模型](./references/fastapi-models.md)

### 错误处理与统一响应

- **统一响应格式**：`ApiResponse[T]` / `ApiPagedResponse[T]` / `ErrorResponse`
- **5 位业务错误码**：分段管理（系统/服务/业务/客户端/外部）
- **异常体系**：`ApiError` 基类 + 派生异常类
- **全局处理器**：统一错误响应格式

详见 [错误处理与统一响应](./references/fastapi-errors.md)

### 数据库

- SQLAlchemy 2.0 异步：`AsyncSession`, `async_sessionmaker`
- Repository 模式封装数据访问
- 事务管理在 Service 层

详见 [数据库配置](./references/fastapi-database-setup.md) | [ORM 基类](./references/fastapi-database-orm.md) | [Repository 模式](./references/fastapi-database-patterns.md)

---

## 后台任务选型

| 方案 | 适用场景 | 特点 |
|------|---------|------|
| BackgroundTasks | 轻量任务、无需追踪 | 内置、简单、同进程 |
| ARQ | 异步任务队列 | async 原生、Redis、轻量 |
| Celery | 企业级任务系统 | 生态成熟、功能全面 |
| APScheduler | 定时任务 | 多种触发器、可持久化 |

> 选型建议：简单通知 → BackgroundTasks | 异步优先 → ARQ | 复杂工作流 → Celery | 定时任务 → APScheduler

详见 [BackgroundTasks](./references/fastapi-tasks-background.md) | [ARQ](./references/fastapi-tasks-arq.md) | [Celery](./references/fastapi-tasks-celery.md) | [APScheduler](./references/fastapi-tasks-scheduler.md)

---

## 参考文档

按主题分类的详细文档：

| 分类 | 主题 | 文档 | 说明 |
|------|------|------|------|
| **核心** | 项目规划 | [fastapi-project-planning.md](./references/fastapi-project-planning.md) | 需求分析、技术选型、设计文档模板 |
| | 分层架构 | [fastapi-layered-architecture.md](./references/fastapi-layered-architecture.md) | Router/Service/Repository 分层 |
| | 依赖注入 | [fastapi-dependency-injection.md](./references/fastapi-dependency-injection.md) | Annotated、依赖链、类依赖 |
| | 应用生命周期 | [fastapi-app-lifecycle.md](./references/fastapi-app-lifecycle.md) | lifespan、init/setup/close 模式 |
| | 配置管理 | [fastapi-config.md](./references/fastapi-config.md) | pydantic-settings、嵌套配置 |
| | 数据模型 | [fastapi-models.md](./references/fastapi-models.md) | Pydantic 验证、分离模型 |
| | 错误处理 | [fastapi-errors.md](./references/fastapi-errors.md) | 异常体系、统一响应、错误码 |
| | 中间件 | [fastapi-middleware.md](./references/fastapi-middleware.md) | CORS、日志、限流、安全响应头 |
| | 项目结构 | [fastapi-project-structure.md](./references/fastapi-project-structure.md) | 简单/模块化布局 |
| **数据** | 数据库配置 | [fastapi-database-setup.md](./references/fastapi-database-setup.md) | 连接池、Session、get_db |
| | ORM 基类 | [fastapi-database-orm.md](./references/fastapi-database-orm.md) | UUIDv7、软删除、时间戳 |
| | Repository | [fastapi-database-patterns.md](./references/fastapi-database-patterns.md) | 事务、关联加载、分页 |
| | 迁移 | [fastapi-database-migrations.md](./references/fastapi-database-migrations.md) | Alembic 配置、同步兼容 |
| | 审计日志 | [fastapi-audit.md](./references/fastapi-audit.md) | 操作追踪、变更历史 |
| **安全** | 认证 | [fastapi-authentication.md](./references/fastapi-authentication.md) | OAuth2、JWT |
| | 权限 | [fastapi-permissions.md](./references/fastapi-permissions.md) | 角色、Scopes、敏感数据 |
| **运维** | 内置任务 | [fastapi-tasks-background.md](./references/fastapi-tasks-background.md) | BackgroundTasks |
| | ARQ | [fastapi-tasks-arq.md](./references/fastapi-tasks-arq.md) | 异步任务队列 |
| | Celery | [fastapi-tasks-celery.md](./references/fastapi-tasks-celery.md) | 企业级任务系统 |
| | 定时任务 | [fastapi-tasks-scheduler.md](./references/fastapi-tasks-scheduler.md) | APScheduler |
| | 日志 | [fastapi-logging.md](./references/fastapi-logging.md) | Loguru 两阶段初始化 |
| | 测试 | [fastapi-testing.md](./references/fastapi-testing.md) | pytest-asyncio、依赖覆盖 |
| | 部署 | [fastapi-deployment.md](./references/fastapi-deployment.md) | Docker、Kubernetes |
| | 性能 | [fastapi-performance.md](./references/fastapi-performance.md) | async/def、缓存、连接池 |
| **工具** | 开发工具 | [fastapi-tooling.md](./references/fastapi-tooling.md) | uv、Ruff、ty |
| | 代码重构 | [fastapi-refactoring.md](./references/fastapi-refactoring.md) | 重构模式、代码坏味道 |
| | API 设计 | [fastapi-api-design.md](./references/fastapi-api-design.md) | REST 规范、分页 |
| | HTTP 客户端 | [fastapi-httpx.md](./references/fastapi-httpx.md) | httpx AsyncClient |

代码模板见 `assets/simple-api/app/` 和 `assets/modular-api/app/`

---

## 获取更多文档

使用 context7 获取最新官方文档（先解析库 ID）：

```
mcp__context7__resolve-library-id
  libraryName: fastapi
```

```
mcp__context7__query-docs
  libraryId: <resolve 返回的 ID>
  query: <相关主题>
```

常用主题：`dependencies`, `middleware`, `lifespan`, `background tasks`, `websocket`, `testing`, `security`, `oauth2`, `jwt`
