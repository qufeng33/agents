---
name: fastapi-development
description: |
  FastAPI 开发最佳实践。包含分层架构、项目结构、异步模式、依赖注入、数据验证、数据库集成、错误处理、测试等。
  触发：实现端点、创建 API、CRUD 操作、Pydantic schema、SQLAlchemy 模型、异步数据库、错误处理、编写测试
---

# FastAPI 最佳实践

> FastAPI >= 0.120.0 | Python >= 3.13 | Pydantic >= 2.10

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
| **Service** | 业务逻辑、事务编排、跨模块协调 | 直接操作数据库 |
| **Repository** | 数据访问、SQL 查询、ORM 操作 | 处理 HTTP、业务规则 |

**好处**：可测试（mock Repository）、可替换（切换数据库）、职责清晰、代码复用

详见 [核心模式](./references/fastapi-patterns.md)

---

## 项目结构

| 场景 | 推荐结构 |
|------|----------|
| 小项目 / 原型 / 单人开发 | 简单结构（按层组织） |
| 团队开发 / 中大型项目 | 模块化结构（按领域组织） |

### 简单结构

```
app/
├── main.py              # 应用入口
├── config.py            # 配置管理
├── dependencies.py      # 共享依赖
├── exceptions.py        # 异常定义
├── routers/             # 路由层
├── schemas/             # Pydantic 模型
├── services/            # 业务逻辑层
├── models/              # ORM 模型
└── core/                # 数据库、安全等基础设施
```

### 模块化结构

```
app/
├── main.py
├── config.py
├── api/v1/              # API 版本管理
├── modules/             # 功能模块（按领域划分）
│   ├── user/            # 完全自包含：router/schemas/models/service/repository/exceptions/dependencies
│   └── item/
└── core/
```

详见 [项目结构详解](./references/fastapi-project-structure.md) | 代码模板见 `assets/`

---

## 快速参考

### 应用入口

使用 `lifespan` 管理应用生命周期（启动/关闭时的资源初始化与清理）。

详见 [核心模式 - Lifespan](./references/fastapi-patterns.md)

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

详见 [核心模式 - 依赖注入](./references/fastapi-patterns.md)

### 数据模型

- 基类配置：`ConfigDict(from_attributes=True, str_strip_whitespace=True)`
- 分离模型：`Create` / `Update` / `Response` / `InDB`
- 字段验证：`Field(min_length=8)`, `EmailStr`, `@field_validator`

详见 [数据模型](./references/fastapi-models.md)

### 错误处理

- 自定义异常基类：包含 `code`, `message`, `status_code`
- 全局异常处理器：统一响应格式
- 业务异常：继承基类，定义具体错误

详见 [错误处理](./references/fastapi-errors.md)

### 数据库

- SQLAlchemy 2.0 异步：`AsyncSession`, `async_sessionmaker`
- Repository 模式封装数据访问
- 事务管理在 Service 层

详见 [数据库集成](./references/fastapi-database.md)

---

## 详细文档

### 核心开发
- [核心模式](./references/fastapi-patterns.md) - 分层架构、依赖注入、后台任务
- [应用启动](./references/fastapi-startup.md) - 两阶段初始化、Lifespan、init/setup 模式
- [中间件](./references/fastapi-middleware.md) - 请求日志、CORS、异常处理、认证
- [配置管理](./references/fastapi-config.md) - pydantic-settings、嵌套配置、验证器
- [数据模型](./references/fastapi-models.md) - Pydantic 验证、类型注解
- [错误处理](./references/fastapi-errors.md) - 异常体系、统一响应
- [项目结构](./references/fastapi-project-structure.md) - 目录布局详解

### 数据与安全
- [数据库集成](./references/fastapi-database.md) - SQLAlchemy 2.0 异步
- [安全性](./references/fastapi-security.md) - OAuth2、JWT、权限控制

### 工具与运维
- [日志](./references/fastapi-logging.md) - Loguru 两阶段初始化、上下文绑定
- [开发工具](./references/fastapi-tooling.md) - uv、Ruff、ty、pre-commit
- [API 设计](./references/fastapi-api-design.md) - REST 规范、分页
- [性能优化](./references/fastapi-performance.md) - 缓存、连接池、并发
- [测试](./references/fastapi-testing.md) - pytest-asyncio、依赖覆盖
- [部署](./references/fastapi-deployment.md) - Docker、Kubernetes

### 集成
- [HTTP 客户端](./references/fastapi-httpx.md) - httpx AsyncClient

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
