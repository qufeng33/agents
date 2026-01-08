# FastAPI Dev Plugin

个人 FastAPI 开发工作流插件，基于个人开发习惯和偏好定制。

## 设计理念

- **个人工具箱** - 为自己的开发流程优化，不追求通用性
- **最佳实践沉淀** - 将日常开发中的模式和经验固化为可复用的指导
- **渐进式完善** - 根据实际使用不断迭代改进

## 技术栈偏好

| 组件 | 选型 |
|------|------|
| 框架 | FastAPI ≥0.122.0, Python ≥3.13, Pydantic ≥2.10 |
| 数据库 | PostgreSQL, SQLAlchemy 2.0 (async), Alembic |
| 测试 | pytest, pytest-asyncio, httpx |
| 工具链 | uv, ruff, ty |
| 认证 | JWT (pyjwt), OAuth2, pwdlib (Argon2) |
| 日志 | loguru |

## 组件

### Commands

| 命令 | 用途 |
|------|------|
| `/fastapi-dev:init` | 项目初始化 |
| `/fastapi-dev:design` | 架构设计 |
| `/fastapi-dev:feature` | 功能开发 |
| `/fastapi-dev:review` | 代码审查 |
| `/fastapi-dev:test` | 测试生成 |
| `/fastapi-dev:refactor` | 代码重构 |

### Agents

| Agent | 用途 | Model |
|-------|------|-------|
| `fastapi-designer` | 需求分析、技术决策、API 契约设计 | Opus |
| `fastapi-developer` | 代码实现、遵循分层架构 | Opus |
| `fastapi-tester` | 测试用例编写、pytest-asyncio | Opus |
| `fastapi-reviewer` | 代码审查（支持多维度：正确性/架构/安全） | Opus |

### Skill

- `fastapi-dev` - 架构设计 + 代码实现最佳实践，含多份参考文档

### Hooks

- **PostToolUse** - Write/Edit 后自动执行 `ruff format` 和 `ruff check --fix`

### 特性

- **置信度过滤** - 审查只报告置信度 ≥80% 的问题，避免误报
- **并行审查** - 同一 reviewer 支持 3 个维度（正确性/架构/安全），可并行执行
- **经验沉淀** - commands 可传递经验文档路径，agent 自动追加

## 核心原则

1. **KISS** - 简单直接，不过度设计
2. **分层架构** - Router → Service → Repository
3. **异步优先** - I/O 操作使用 async/await
4. **类型安全** - 全面使用类型注解
5. **兼容性需确认** - 优先最佳实践，是否保持向后兼容需由用户/业务明确，必要时通过版本化实现
