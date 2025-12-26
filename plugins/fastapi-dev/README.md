# FastAPI Dev Plugin

个人 FastAPI 开发工作流插件，基于个人开发习惯和偏好定制。

## 设计理念

- **个人工具箱** - 为自己的开发流程优化，不追求通用性
- **最佳实践沉淀** - 将日常开发中的模式和经验固化为可复用的指导
- **渐进式完善** - 根据实际使用不断迭代改进

## 技术栈偏好

| 组件 | 选型 |
|------|------|
| 框架 | FastAPI ≥0.120.0, Pydantic v2 |
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

### Agent

- `fastapi-pro` - FastAPI 专家 (Opus)，自动加载 fastapi-development skill

### Skill

- `fastapi-development` - 架构设计 + 代码实现最佳实践，含 19 份参考文档

## 核心原则

1. **KISS** - 简单直接，不过度设计
2. **分层架构** - Router → Service → Repository
3. **异步优先** - I/O 操作使用 async/await
4. **类型安全** - 全面使用类型注解
5. **No backward compatibility** - 优先最佳实践，不为兼容性妥协
